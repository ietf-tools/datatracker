# Copyright The IETF Trust 2026, All Rights Reserved
from unittest import mock

import jsonschema
import requests.exceptions
import typesense.exceptions
from django.conf import settings
from django.test.utils import override_settings

from ietf.blobdb.models import Blob
from ietf.doc.factories import (
    BcpFactory,
    PublishedRfcDocEventFactory,
    StdFactory,
    WgDraftFactory,
    WgRfcFactory,
)
from ietf.doc.models import Document, RelatedDocument
from ietf.doc.storage_utils import store_str
from ietf.person.factories import PersonFactory

from . import searchindex
from .test_utils import TestCase


class SearchindexTests(TestCase):
    def setUp(self):
        super().setUp()
        # Keep tests independent of popularity.json in the reef bucket
        popularity_patcher = mock.patch("ietf.utils.searchindex.get_popularity_score")
        self.mock_get_popularity_score = popularity_patcher.start()
        self.addCleanup(popularity_patcher.stop)

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

    def test_sanitize_abstract(self):
        dirty_abstract = (
            "Mixed\n"
            "Newlines\r"
            "And\r\n"
            "Things\n\r"
            " Sometimes\n"
            "\n"
            "With\r\n"
            "\r\n"
            "Double  \n\r"
            "\n\r"
            "   Newlines\r"
            "\r"
            "Whee!"
        )
        sanitized = (
            "Mixed\n"
            "Newlines\n"
            "And\n"
            "Things\n"
            "Sometimes\n"
            "\n"
            "With\n"
            "\n"
            "Double\n"
            "\n"
            "Newlines\n"
            "\n"
            "Whee!"
        )
        self.assertEqual(searchindex._sanitize_abstract(dirty_abstract), sanitized)

    def test_typesense_doc_from_rfc(self):
        self.mock_get_popularity_score.return_value = 0.5
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
        self.assertEqual(result["abstract"], searchindex._sanitize_abstract(rfc.abstract))
        self.assertEqual(result["pages"], rfc.pages)
        self.assertNotIn("adName", result)
        self.assertNotIn("content", result)  # no blob
        self.assertNotIn("subseries", result)
        self.assertEqual(result["popularity"], 0.5)
        self.assertEqual(self.mock_get_popularity_score.call_args, mock.call(rfc))

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

    def test_typesense_doc_from_rfc_flags_obsoleted(self):
        """typesense docs should set correct flags for obsoleted RFC"""
        rfc = PublishedRfcDocEventFactory().doc
        assert isinstance(rfc, Document)
        self.assertEqual(len(rfc.related_that("obs")), 0)
        self.assertEqual(len(rfc.related_that("updates")), 0)
        self.assertNotEqual(rfc.std_level.slug, "hist")
        result = searchindex.typesense_doc_from_rfc(rfc)
        self.assertFalse(result["flags"]["hiddenDefault"])
        self.assertFalse(result["flags"]["obsoleted"])
        self.assertFalse(result["flags"]["updated"])

        RelatedDocument.objects.create(
            source=(PublishedRfcDocEventFactory().doc),
            target=rfc,
            relationship_id="obs",
        )
        result = searchindex.typesense_doc_from_rfc(rfc)
        self.assertTrue(result["flags"]["hiddenDefault"])
        self.assertTrue(result["flags"]["obsoleted"])
        self.assertFalse(result["flags"]["updated"])

    def test_typesense_doc_from_rfc_flags_updated(self):
        """typesense docs should set flags correctly for updated RFC"""
        rfc = PublishedRfcDocEventFactory().doc
        assert isinstance(rfc, Document)
        self.assertEqual(len(rfc.related_that("obs")), 0)
        self.assertEqual(len(rfc.related_that("updates")), 0)
        self.assertNotEqual(rfc.std_level.slug, "hist")
        result = searchindex.typesense_doc_from_rfc(rfc)
        self.assertFalse(result["flags"]["hiddenDefault"])
        self.assertFalse(result["flags"]["obsoleted"])
        self.assertFalse(result["flags"]["updated"])

        RelatedDocument.objects.create(
            source=(PublishedRfcDocEventFactory().doc),
            target=rfc,
            relationship_id="updates",
        )
        result = searchindex.typesense_doc_from_rfc(rfc)
        self.assertFalse(result["flags"]["hiddenDefault"])
        self.assertFalse(result["flags"]["obsoleted"])
        self.assertTrue(result["flags"]["updated"])

    def test_typesense_doc_from_rfc_flags_historic(self):
        """typesense docs should set flags correctly for historic RFC"""
        rfc = PublishedRfcDocEventFactory(doc__std_level_id="hist").doc
        assert isinstance(rfc, Document)
        result = searchindex.typesense_doc_from_rfc(rfc)
        self.assertTrue(result["flags"]["hiddenDefault"])
        self.assertFalse(result["flags"]["obsoleted"])
        self.assertFalse(result["flags"]["updated"])

    def test_typesense_doc_from_rfc_popularity_unavailable(self):
        rfc = PublishedRfcDocEventFactory().doc
        for err in [FileNotFoundError(), jsonschema.ValidationError("invalid")]:
            with self.subTest(repr(err)):
                self.mock_get_popularity_score.side_effect = err
                result = searchindex.typesense_doc_from_rfc(rfc)
                self.assertEqual(result["rfcNumber"], rfc.rfc_number)
                self.assertNotIn("popularity", result)

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
    def test_partial_update_rfc_entries(self, mock_ts_client_constructor):
        mock_import_ = mock_ts_client_constructor.return_value.collections[
            "frogs"  # matches value in override_settings above
        ].documents.import_
        # Alternate success and failure results
        mock_import_.side_effect = lambda tdata_batch, params: [
            {"success": index % 2 == 0, "error": "failed"}
            for index in range(len(tdata_batch))
        ]
        fields = {
            "rfcNumber": lambda rfc: rfc.rfc_number,
            "constant": lambda rfc: "some value",
        }

        def expected_tdata(rfc):
            return {
                "id": f"doc-{rfc.pk}",
                "rfcNumber": rfc.rfc_number,
                "constant": "some value",
            }

        rfcs = WgRfcFactory.create_batch(3)
        searchindex.partial_update_rfc_entries(rfcs, fields)
        self.assertEqual(mock_import_.call_count, 1)
        self.assertEqual(
            mock_import_.call_args,
            mock.call([expected_tdata(rfc) for rfc in rfcs], {"action": "update"}),
        )

        mock_import_.reset_mock()
        rfc = rfcs[0]
        searchindex.partial_update_rfc_entries([rfc] * 50, fields, batchsize=20)
        self.assertEqual(
            mock_import_.call_args_list,
            [
                mock.call([expected_tdata(rfc)] * 20, {"action": "update"}),
                mock.call([expected_tdata(rfc)] * 20, {"action": "update"}),
                mock.call([expected_tdata(rfc)] * 10, {"action": "update"}),
            ],
        )

    @mock.patch("ietf.utils.searchindex.partial_update_rfc_entries", autospec=True)
    def test_update_rfc_popularities(self, mock_partial_update):
        mock_refresh = self.mock_get_popularity_score.refresh
        scored_rfc, unscored_rfc = WgRfcFactory.create_batch(2)
        mock_refresh.return_value = {scored_rfc.rfc_number: 0.75}
        rfcs = [scored_rfc, unscored_rfc]

        searchindex.update_rfc_popularities(rfcs, batchsize=7)
        self.assertEqual(
            mock_partial_update.call_args, mock.call(rfcs, mock.ANY, batchsize=7)
        )
        fields = mock_partial_update.call_args.args[1]
        self.assertEqual(list(fields.keys()), ["popularity"])
        self.assertEqual(fields["popularity"](scored_rfc), 0.75)
        self.assertIsNone(fields["popularity"](unscored_rfc))
        # Scores are loaded fresh once, not looked up in the cache per RFC
        self.assertEqual(mock_refresh.call_count, 1)
        self.assertFalse(
            self.mock_get_popularity_score.cached_popularity_scores.called
        )
        self.assertFalse(self.mock_get_popularity_score.called)

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
