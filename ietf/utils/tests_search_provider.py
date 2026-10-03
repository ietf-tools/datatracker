# Copyright The IETF Trust 2026, All Rights Reserved
from unittest import mock

import requests.exceptions
import typesense.exceptions
from django.conf import settings
from django.test.utils import override_settings

from . import search_provider
from .test_utils import TestCase


class SearchProviderTests(TestCase):
    def test_enabled(self):
        with override_settings():
            try:
                del settings.SEARCH_PROVIDER_CONFIG
            except AttributeError:
                pass
            self.assertFalse(search_provider.enabled())
        with override_settings(
            SEARCH_PROVIDER_CONFIG={"TYPESENSE_API_KEY": "this-is-not-a-key"}
        ):
            self.assertFalse(search_provider.enabled())
        with override_settings(
            SEARCH_PROVIDER_CONFIG={"TYPESENSE_API_URL": "http://example.com"}
        ):
            self.assertTrue(search_provider.enabled())

    @mock.patch("ietf.utils.search_provider.typesense.Client")
    def test_create(self, mock_ts_client_constructor):
        schema = {"fields": [{"name": "title", "type": "string"}]}
        search_provider.SearchIndex(name="frogs", schema=schema).create()
        self.assertEqual(mock_ts_client_constructor.call_count, 1)
        mock_collections = mock_ts_client_constructor.return_value.collections
        self.assertEqual(
            mock_collections.create.call_args,
            mock.call(
                {"name": "frogs", "fields": [{"name": "title", "type": "string"}]}
            ),
        )

    @mock.patch("ietf.utils.search_provider.typesense.Client")
    def test_delete(self, mock_ts_client_constructor):
        index = search_provider.SearchIndex(name="frogs", schema={})
        index.delete()
        self.assertEqual(mock_ts_client_constructor.call_count, 1)
        mock_collections = mock_ts_client_constructor.return_value.collections
        self.assertTrue(mock_collections["frogs"].delete.called)

        mock_collections[
            "frogs"
        ].delete.side_effect = typesense.exceptions.ObjectNotFound
        index.delete()  # should ignore the exception

    @override_settings(
        SEARCH_PROVIDER_CONFIG={
            "TYPESENSE_API_URL": "http://ts.example.com",
            "TYPESENSE_API_KEY": "test-api-key",
        }
    )
    def test_upsert_presets(self):
        presets = {
            "preset-a": {"collection": "frogs", "query_by": "title"},
            "preset-b": {"collection": "frogs", "query_by": "abstract"},
        }
        index = search_provider.SearchIndex(name="frogs", schema={}, presets=presets)
        self.requests_mock.put(
            "http://ts.example.com/presets/preset-a", text="ok", status_code=201
        )
        self.requests_mock.put(
            "http://ts.example.com/presets/preset-b", text="ok", status_code=202
        )
        index.upsert_presets()
        self.assertEqual(
            [request.json() for request in self.requests_mock.request_history],
            [
                {"value": {"collection": "frogs", "query_by": "title"}},
                {"value": {"collection": "frogs", "query_by": "abstract"}},
            ],
        )
        self.assertTrue(
            all(
                request.headers["X-TYPESENSE-API-KEY"] == "test-api-key"
                for request in self.requests_mock.request_history
            )
        )

        self.requests_mock.put(
            "http://ts.example.com/presets/preset-a", text="not ok", status_code=400
        )
        with self.assertRaises(requests.exceptions.HTTPError):
            index.upsert_presets()

        self.requests_mock.put(
            "http://ts.example.com/presets/preset-a", text="ok", status_code=200
        )
        self.requests_mock.put(
            "http://ts.example.com/presets/preset-b", text="not ok", status_code=400
        )
        with self.assertRaises(requests.exceptions.HTTPError):
            index.upsert_presets()

    @mock.patch("ietf.utils.search_provider.typesense.Client")
    def test_upsert_document(self, mock_ts_client_constructor):
        document = {"id": "doc-1"}
        index = search_provider.SearchIndex(name="frogs", schema={})
        index.upsert_document(document)
        mock_upsert = mock_ts_client_constructor.return_value.collections[
            "frogs"
        ].documents.upsert
        self.assertEqual(mock_upsert.call_args, mock.call(document))

        mock_upsert.side_effect = typesense.exceptions.RequestMalformed
        with self.assertRaises(typesense.exceptions.RequestMalformed):
            index.upsert_document(document)

    @mock.patch("ietf.utils.search_provider.typesense.Client")
    def test_upsert_documents(self, mock_ts_client_constructor):
        mock_import_ = mock_ts_client_constructor.return_value.collections[
            "frogs"
        ].documents.import_
        # Alternate success and failure results
        mock_import_.side_effect = lambda batch, params: [
            (
                {"success": True}
                if index % 2 == 0
                else {"success": False, "error": "failed", "code": 400}
            )
            for index in range(len(batch))
        ]
        documents = [{"id": f"doc-{n}"} for n in range(3)]
        index = search_provider.SearchIndex(name="frogs", schema={})
        result = index.upsert_documents(documents)
        self.assertEqual(
            mock_import_.call_args_list,
            [mock.call(documents, {"action": "upsert"})],
        )
        self.assertEqual(
            result,
            search_provider.WriteResult(
                written=2,
                failures=[search_provider.WriteFailure(documents[1], "failed")],
            ),
        )

        # With batchsize, a generator is consumed one batch at a time
        generated_count = 0

        def generate_documents():
            nonlocal generated_count
            for n in range(50):
                generated_count += 1
                yield {"id": f"doc-{n}"}

        generated_at_import = []

        def fake_import_(batch, params):
            generated_at_import.append(generated_count)
            return [{"success": True}] * len(batch)

        mock_import_.reset_mock()
        mock_import_.side_effect = fake_import_
        result = index.upsert_documents(generate_documents(), batchsize=20)
        self.assertEqual(
            mock_import_.call_args_list,
            [
                mock.call(
                    [{"id": f"doc-{n}"} for n in range(0, 20)], {"action": "upsert"}
                ),
                mock.call(
                    [{"id": f"doc-{n}"} for n in range(20, 40)], {"action": "upsert"}
                ),
                mock.call(
                    [{"id": f"doc-{n}"} for n in range(40, 50)], {"action": "upsert"}
                ),
            ],
        )
        self.assertEqual(generated_at_import, [20, 40, 50])
        self.assertEqual(result, search_provider.WriteResult(written=50))

    @mock.patch("ietf.utils.search_provider.typesense.Client")
    def test_update_documents(self, mock_ts_client_constructor):
        mock_import_ = mock_ts_client_constructor.return_value.collections[
            "frogs"
        ].documents.import_
        mock_import_.side_effect = lambda batch, params: [
            {"success": True},
            {"success": False, "error": "not found", "code": 404},
        ]
        partial_documents = [{"id": "doc-1", "x": 1}, {"id": "doc-2", "x": 2}]
        index = search_provider.SearchIndex(name="frogs", schema={})
        result = index.update_documents(partial_documents)
        self.assertEqual(
            mock_import_.call_args_list,
            [mock.call(partial_documents, {"action": "update"})],
        )
        self.assertEqual(
            result,
            search_provider.WriteResult(
                written=1,
                failures=[
                    search_provider.WriteFailure(partial_documents[1], "not found")
                ],
            ),
        )
