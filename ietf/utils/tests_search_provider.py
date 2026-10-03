# Copyright The IETF Trust 2026, All Rights Reserved
from unittest import mock

import requests.exceptions
import typesense.exceptions
from django.conf import settings
from django.test.utils import override_settings

from . import search_provider
from .test_typesense import FakeTypesenseClient
from .test_utils import TestCase

LIVE = "frogs_1"
BUILDING = "frogs_2"


def _mock_plain_collection(mock_client, name):
    """Make a mock client report one collection named name and no alias"""
    mock_client.aliases[name].retrieve.side_effect = typesense.exceptions.ObjectNotFound
    mock_client.collections.retrieve.return_value = [{"name": name}]


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
        _mock_plain_collection(mock_ts_client_constructor.return_value, "frogs")
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
        _mock_plain_collection(mock_ts_client_constructor.return_value, "frogs")
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
        _mock_plain_collection(mock_ts_client_constructor.return_value, "frogs")
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

    def test_index_state(self):
        state = search_provider._IndexState(
            name="frogs",
            alias_target=LIVE,
            collections={
                "frogs_1",
                "frogs_2",
                "frogs_10",
                "frogs_",
                "frogs_x",
                "frogs_1_old",
                "frogsx_1",
                "toads_1",
            },
        )
        self.assertEqual(state.live, LIVE)
        self.assertEqual(state.versioned, [LIVE, BUILDING, "frogs_10"])  # numeric order
        self.assertEqual(state.others, [BUILDING, "frogs_10"])
        self.assertEqual(state.write_targets, [LIVE, BUILDING, "frogs_10"])

        # no alias, plain collection (before the alias is created)
        state = search_provider._IndexState(
            name="frogs", alias_target=None, collections={"frogs", BUILDING}
        )
        self.assertEqual(state.live, "frogs")
        self.assertEqual(state.write_targets, ["frogs", BUILDING])

        # nothing
        state = search_provider._IndexState(
            name="frogs", alias_target=None, collections=set()
        )
        self.assertIsNone(state.live)
        self.assertEqual(state.write_targets, [])

        # regex characters in the name are literal
        state = search_provider._IndexState(
            name="fr.gs",
            alias_target=None,
            collections={"fr.gs_1", "frogs_1"},
        )
        self.assertEqual(state.versioned, ["fr.gs_1"])

    @mock.patch("ietf.utils.search_provider.typesense.Client")
    def test_upsert_document_targets(self, mock_ts_client_constructor):
        fake = FakeTypesenseClient()
        mock_ts_client_constructor.return_value = fake
        index = search_provider.SearchIndex(name="frogs", schema={})

        # before the alias is created: only the plain collection
        fake.add_collection("frogs")
        index.upsert_document({"id": "doc-1"})
        self.assertEqual(fake.documents("frogs"), {"doc-1": {"id": "doc-1"}})
        self.assertEqual(list(fake.collection_data), ["frogs"])

        # live collection and a rebuild in progress
        fake.collection_data.clear()
        fake.add_collection(LIVE)
        fake.add_collection(BUILDING)
        fake.alias_data["frogs"] = LIVE
        index.upsert_document({"id": "doc-1"})
        self.assertEqual(fake.documents(LIVE), {"doc-1": {"id": "doc-1"}})
        self.assertEqual(fake.documents(BUILDING), {"doc-1": {"id": "doc-1"}})

    @mock.patch("ietf.utils.search_provider.typesense.Client")
    def test_upsert_document_target_deleted(self, mock_ts_client_constructor):
        fake = FakeTypesenseClient()
        mock_ts_client_constructor.return_value = fake
        fake.add_collection(LIVE)
        fake.add_collection(BUILDING)
        fake.alias_data["frogs"] = LIVE

        def delete_building(collection):
            # a failed rebuild deletes its collection after targets were listed
            if collection == BUILDING:
                del fake.collection_data[BUILDING]

        fake.before_write = delete_building
        search_provider.SearchIndex(name="frogs", schema={}).upsert_document(
            {"id": "doc-1"}
        )
        self.assertEqual(fake.documents(LIVE), {"doc-1": {"id": "doc-1"}})

    @mock.patch("ietf.utils.search_provider.typesense.Client")
    def test_upsert_document_target_error(self, mock_ts_client_constructor):
        fake = FakeTypesenseClient()
        mock_ts_client_constructor.return_value = fake
        fake.add_collection(LIVE)
        fake.add_collection(BUILDING)
        fake.alias_data["frogs"] = LIVE

        def fail_live(collection):
            if collection == LIVE:
                raise typesense.exceptions.Timeout()

        fake.before_write = fail_live
        with self.assertRaises(typesense.exceptions.Timeout):
            search_provider.SearchIndex(name="frogs", schema={}).upsert_document(
                {"id": "doc-1"}
            )
        # other targets were still written
        self.assertEqual(fake.documents(BUILDING), {"doc-1": {"id": "doc-1"}})

    @mock.patch("ietf.utils.search_provider.typesense.Client")
    def test_upsert_document_no_index(self, mock_ts_client_constructor):
        mock_ts_client_constructor.return_value = FakeTypesenseClient()
        with self.assertRaises(typesense.exceptions.ObjectNotFound):
            search_provider.SearchIndex(name="frogs", schema={}).upsert_document(
                {"id": "doc-1"}
            )

    @mock.patch("ietf.utils.search_provider.log")
    @mock.patch("ietf.utils.search_provider.typesense.Client")
    def test_upsert_documents_targets(self, mock_ts_client_constructor, mock_log):
        fake = FakeTypesenseClient()
        mock_ts_client_constructor.return_value = fake
        fake.add_collection(LIVE)
        fake.add_collection(BUILDING)
        fake.alias_data["frogs"] = LIVE
        fake.document_errors[(BUILDING, "doc-3")] = "bad document"

        generated_count = 0
        generated_at_import = []

        def generate_documents():
            nonlocal generated_count
            for n in range(5):
                generated_count += 1
                yield {"id": f"doc-{n}"}

        fake.before_write = lambda collection: generated_at_import.append(
            (collection, generated_count)
        )
        result = search_provider.SearchIndex(name="frogs", schema={}).upsert_documents(
            generate_documents(), batchsize=2
        )
        # each batch is written to every target before the next batch is built
        self.assertEqual(
            generated_at_import,
            [
                (LIVE, 2),
                (BUILDING, 2),
                (LIVE, 4),
                (BUILDING, 4),
                (LIVE, 5),
                (BUILDING, 5),
            ],
        )
        self.assertEqual(len(fake.documents(LIVE)), 5)
        self.assertEqual(len(fake.documents(BUILDING)), 4)
        # result describes the live collection; other failures are logged
        self.assertEqual(result, search_provider.WriteResult(written=5))
        self.assertIn(
            mock.call(
                f"Write of doc-3 to in-progress collection {BUILDING} failed: "
                "bad document"
            ),
            mock_log.call_args_list,
        )

    @mock.patch("ietf.utils.search_provider.log")
    @mock.patch("ietf.utils.search_provider.typesense.Client")
    def test_update_documents_targets(self, mock_ts_client_constructor, mock_log):
        fake = FakeTypesenseClient()
        mock_ts_client_constructor.return_value = fake
        fake.add_collection(LIVE, documents=[{"id": "doc-1"}, {"id": "doc-2"}])
        fake.add_collection(BUILDING, documents=[{"id": "doc-1"}])
        fake.alias_data["frogs"] = LIVE

        result = search_provider.SearchIndex(name="frogs", schema={}).update_documents(
            [{"id": "doc-1", "x": 1}, {"id": "doc-2", "x": 2}, {"id": "doc-3", "x": 3}]
        )
        self.assertEqual(fake.documents(LIVE)["doc-2"], {"id": "doc-2", "x": 2})
        self.assertEqual(fake.documents(BUILDING), {"doc-1": {"id": "doc-1", "x": 1}})
        # missing documents in the in-progress collection are not failures...
        self.assertIn(
            mock.call(
                f"2 documents not yet in in-progress collection {BUILDING}, "
                "not updated there"
            ),
            mock_log.call_args_list,
        )
        # ...but are in the live collection
        self.assertEqual(result.written, 2)
        self.assertEqual(
            [failure.document["id"] for failure in result.failures], ["doc-3"]
        )
