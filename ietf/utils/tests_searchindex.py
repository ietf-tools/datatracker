# Copyright The IETF Trust 2026, All Rights Reserved
from unittest import mock

import requests.exceptions
import typesense.exceptions
from django.conf import settings
from django.test.utils import override_settings

from . import searchindex
from .test_utils import TestCase
from ..blobdb.models import Blob
from ..doc.factories import (
    WgDraftFactory,
    WgRfcFactory,
    PublishedRfcDocEventFactory,
    BcpFactory,
    StdFactory,
)
from ..doc.models import Document
from ..doc.storage_utils import store_str
from ..person.factories import PersonFactory


class SearchindexTests(TestCase):
    def test_enabled(self):
        with override_settings():
            try:
                del settings.SEARCHINDEX_CONFIG
            except AttributeError:
                pass
            self.assertFalse(searchindex.enabled())
        with override_settings(
            SEARCHINDEX_CONFIG={"TYPESENSE_API_KEY": "this-is-not-a-key"}
        ):
            self.assertFalse(searchindex.enabled())
        with override_settings(
            SEARCHINDEX_CONFIG={"TYPESENSE_API_URL": "http://example.com"}
        ):
            self.assertTrue(searchindex.enabled())

    def test_sanitize_text(self):
        dirty_text = """
        
        This is text.  It + is <---- full    of \tprobl.....ems! Fix it. 
        """
        sanitized = "This is text It is full of problems Fix it."
        self.assertEqual(searchindex._sanitize_text(dirty_text), sanitized)

    @override_settings(
        SEARCHINDEX_CONFIG={
            "TYPESENSE_API_URL": "http://ts.example.com",
            "TYPESENSE_API_KEY": "test-api-key",
            "TYPESENSE_COLLECTION_NAME": "frogs",
        }
    )
    def test_typesense_doc_from_rfc(self):
        not_rfc = WgDraftFactory()
        assert isinstance(not_rfc, Document)
        with self.assertRaises(AssertionError):
            searchindex.typesense_doc_from_rfc(not_rfc)

        invalid_rfc = WgRfcFactory(name="rfc1000000", rfc_number=None)
        assert isinstance(invalid_rfc, Document)
        with self.assertRaises(AssertionError):
            searchindex.typesense_doc_from_rfc(invalid_rfc)

        rfc = PublishedRfcDocEventFactory().doc
        assert isinstance(rfc, Document)
        result = searchindex.typesense_doc_from_rfc(rfc)
        # Check a few values, not exhaustive
        self.assertEqual(result["id"], f"doc-{rfc.pk}")
        self.assertEqual(result["rfcNumber"], rfc.rfc_number)
        self.assertEqual(result["abstract"], searchindex._sanitize_text(rfc.abstract))
        self.assertEqual(result["pages"], rfc.pages)
        self.assertNotIn("adName", result)
        self.assertNotIn("content", result)  # no blob
        self.assertNotIn("subseries", result)

        # repeat, this time with contents, an AD, and subseries docs
        store_str(
            kind="rfc",
            name=f"txt/{rfc.name}.txt",
            content="The contents of this RFC",
            doc_name=rfc.name,
            doc_rev=rfc.rev,  # expected to be None
        )
        rfc.ad = PersonFactory(name="Alfred D. Rector")
        # Put it in two Subseries docs to be sure this does not break things
        # (the typesense schema does not support this for real at the moment)
        BcpFactory(contains=[rfc], name="bcp1234")
        StdFactory(contains=[rfc], name="std1234")
        result = searchindex.typesense_doc_from_rfc(rfc)
        # Check a few values, not exhaustive
        self.assertEqual(
            result["content"],
            searchindex._sanitize_text("The contents of this RFC"),
        )
        self.assertEqual(result["adName"], "Alfred D. Rector")
        self.assertIn("subseries", result)
        ss_dict = result["subseries"]
        # We should get one of the two subseries docs, but neither is more correct
        # than the other...
        self.assertTrue(
            any(
                ss_dict == {"acronym": ss_type, "number": 1234, "total": 1}
                for ss_type in ["bcp", "std"]
            )
        )

        # Finally, delete the contents blob and make sure things don't blow up
        Blob.objects.get(bucket="rfc", name=f"txt/{rfc.name}.txt").delete()
        result = searchindex.typesense_doc_from_rfc(rfc)
        self.assertNotIn("content", result)

    @override_settings(
        SEARCHINDEX_CONFIG={
            "TYPESENSE_API_URL": "http://ts.example.com",
            "TYPESENSE_API_KEY": "test-api-key",
            "TYPESENSE_COLLECTION_NAME": "frogs",
        }
    )
    @mock.patch("ietf.utils.searchindex.typesense_doc_from_rfc")
    @mock.patch("ietf.utils.searchindex.typesense.Client")
    def test_update_or_create_rfc_entry(
        self, mock_ts_client_constructor, mock_tdoc_from_rfc
    ):
        fake_tdoc = object()
        mock_tdoc_from_rfc.return_value = fake_tdoc
        rfc = WgRfcFactory()
        assert isinstance(rfc, Document)
        searchindex.update_or_create_rfc_entry(rfc)
        self.assertTrue(mock_ts_client_constructor.called)
        # walk the tree down to the method we expected to be called...
        mock_upsert = mock_ts_client_constructor.return_value.collections[
            "frogs"  # matches value in override_settings above
        ].documents.upsert
        self.assertTrue(mock_upsert.called)
        self.assertEqual(mock_upsert.call_args, mock.call(fake_tdoc))

    @override_settings(
        SEARCHINDEX_CONFIG={
            "TYPESENSE_API_URL": "http://ts.example.com",
            "TYPESENSE_API_KEY": "test-api-key",
            "TYPESENSE_COLLECTION_NAME": "frogs",
        }
    )
    @mock.patch("ietf.utils.searchindex.typesense_doc_from_rfc")
    @mock.patch("ietf.utils.searchindex.typesense.Client")
    def test_update_or_create_rfc_entries(
        self, mock_ts_client_constructor, mock_tdoc_from_rfc
    ):
        fake_tdoc = object()
        mock_tdoc_from_rfc.return_value = fake_tdoc
        rfc = WgRfcFactory()
        assert isinstance(rfc, Document)
        searchindex.update_or_create_rfc_entries([rfc] * 50)  # list of docs...
        self.assertEqual(mock_ts_client_constructor.call_count, 1)
        # walk the tree down to the method we expected to be called...
        mock_import_ = mock_ts_client_constructor.return_value.collections[
            "frogs"  # matches value in override_settings above
        ].documents.import_
        self.assertEqual(mock_import_.call_count, 1)
        self.assertEqual(
            mock_import_.call_args, mock.call([fake_tdoc] * 50, {"action": "upsert"})
        )

        mock_import_.reset_mock()
        searchindex.update_or_create_rfc_entries([rfc] * 50, batchsize=20)
        self.assertEqual(mock_ts_client_constructor.call_count, 2)  # one more
        # walk the tree down to the method we expected to be called...
        mock_import_ = mock_ts_client_constructor.return_value.collections[
            "frogs"  # matches value in override_settings above
        ].documents.import_
        self.assertEqual(mock_import_.call_count, 3)
        self.assertEqual(
            mock_import_.call_args_list,
            [
                mock.call([fake_tdoc] * 20, {"action": "upsert"}),
                mock.call([fake_tdoc] * 20, {"action": "upsert"}),
                mock.call([fake_tdoc] * 10, {"action": "upsert"}),
            ],
        )

    @override_settings(
        SEARCHINDEX_CONFIG={
            "TYPESENSE_API_URL": "http://ts.example.com",
            "TYPESENSE_API_KEY": "test-api-key",
            "TYPESENSE_COLLECTION_NAME": "frogs",
        }
    )
    @mock.patch("ietf.utils.searchindex.typesense.Client")
    def test_create_collection(self, mock_ts_client_constructor):
        searchindex.create_collection()
        self.assertEqual(mock_ts_client_constructor.call_count, 1)
        mock_collections = mock_ts_client_constructor.return_value.collections
        self.assertTrue(mock_collections.create.called)
        self.assertEqual(mock_collections.create.call_args[0][0]["name"], "frogs")

    @override_settings(
        SEARCHINDEX_CONFIG={
            "TYPESENSE_API_URL": "http://ts.example.com",
            "TYPESENSE_API_KEY": "test-api-key",
            "TYPESENSE_COLLECTION_NAME": "frogs",
        }
    )
    @mock.patch("ietf.utils.searchindex.typesense.Client")
    def test_delete_collection(self, mock_ts_client_constructor):
        searchindex.delete_collection()
        self.assertEqual(mock_ts_client_constructor.call_count, 1)
        mock_collections = mock_ts_client_constructor.return_value.collections
        self.assertTrue(mock_collections["frogs"].delete.called)

        mock_collections["frogs"].side_effect = typesense.exceptions.ObjectNotFound
        searchindex.delete_collection()  # should ignore the exception

    @override_settings(
        SEARCHINDEX_CONFIG={
            "TYPESENSE_API_URL": "http://ts.example.com",
            "TYPESENSE_API_KEY": "test-api-key",
            "TYPESENSE_COLLECTION_NAME": "frogs",
        }
    )
    def test_upsert_presets(self):
        self.requests_mock.put(
            "http://ts.example.com/presets/red", text="ok", status_code=201
        )
        self.requests_mock.put(
            "http://ts.example.com/presets/red-content", text="ok", status_code=202
        )
        searchindex.upsert_presets()

        self.requests_mock.put(
            "http://ts.example.com/presets/red", text="not ok", status_code=400
        )
        with self.assertRaises(requests.exceptions.HTTPError):
            searchindex.upsert_presets()

        self.requests_mock.put(
            "http://ts.example.com/presets/red", text="ok", status_code=200
        )
        self.requests_mock.put(
            "http://ts.example.com/presets/red-content", text="not ok", status_code=400
        )
        with self.assertRaises(requests.exceptions.HTTPError):
            searchindex.upsert_presets()
