# Copyright The IETF Trust 2026, All Rights Reserved
from contextlib import contextmanager
from unittest import mock

import jsonschema
from django.db import connection
from django.test.utils import CaptureQueriesContext

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
from ietf.utils.search_provider import (
    RebuildFailedError,
    RebuildResult,
    WriteFailure,
    WriteResult,
)
from ietf.utils.test_utils import TestCase

from . import searchindexes


class FakeRebuild:
    """Stands in for search_provider.Rebuild, recording what is loaded"""

    def __init__(self):
        self.result = RebuildResult()
        self.loaded = []
        self.batchsizes = []

    def load(self, documents, *, batchsize=None):
        documents = list(documents)
        self.loaded.extend(documents)
        self.batchsizes.append(batchsize)
        self.result.loaded += len(documents)


class SearchindexesTests(TestCase):
    def test_sanitize_text(self):
        dirty_text = """
        
        This is text.  It + is <---- full    of \tprobl.....ems! Fix it. 
        """
        sanitized = "This is text It is full of problems Fix it."
        self.assertEqual(searchindexes._sanitize_text(dirty_text), sanitized)

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
        self.assertEqual(searchindexes._sanitize_abstract(dirty_abstract), sanitized)

    def test_typesense_doc_from_rfc(self):
        not_rfc = WgDraftFactory()
        assert isinstance(not_rfc, Document)
        with self.assertRaises(AssertionError):
            searchindexes.typesense_doc_from_rfc(not_rfc, {})

        invalid_rfc = WgRfcFactory(name="rfc1000000", rfc_number=None)
        assert isinstance(invalid_rfc, Document)
        with self.assertRaises(AssertionError):
            searchindexes.typesense_doc_from_rfc(invalid_rfc, {})

        rfc = PublishedRfcDocEventFactory().doc
        assert isinstance(rfc, Document)
        popularity_scores = {rfc.rfc_number: 0.5}
        result = searchindexes.typesense_doc_from_rfc(rfc, popularity_scores)
        # Check a few values, not exhaustive
        self.assertEqual(result["id"], f"doc-{rfc.pk}")
        self.assertEqual(result["rfcNumber"], rfc.rfc_number)
        self.assertEqual(
            result["abstract"], searchindexes._sanitize_abstract(rfc.abstract)
        )
        self.assertEqual(result["pages"], rfc.pages)
        self.assertNotIn("adName", result)
        self.assertNotIn("content", result)  # no blob
        self.assertNotIn("subseries", result)
        self.assertEqual(result["popularity"], 0.5)

        # Unscored RFC and unavailable scores both give None
        result = searchindexes.typesense_doc_from_rfc(rfc, {})
        self.assertIsNone(result["popularity"])
        result = searchindexes.typesense_doc_from_rfc(rfc, None)
        self.assertIsNone(result["popularity"])

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
        result = searchindexes.typesense_doc_from_rfc(rfc, popularity_scores)
        # Check a few values, not exhaustive
        self.assertEqual(
            result["content"],
            searchindexes._sanitize_text("The contents of this RFC"),
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
        result = searchindexes.typesense_doc_from_rfc(rfc, popularity_scores)
        self.assertNotIn("content", result)

    def test_typesense_doc_from_rfc_flags_obsoleted(self):
        """typesense docs should set correct flags for obsoleted RFC"""
        rfc = PublishedRfcDocEventFactory().doc
        assert isinstance(rfc, Document)
        self.assertEqual(len(rfc.related_that("obs")), 0)
        self.assertEqual(len(rfc.related_that("updates")), 0)
        self.assertNotEqual(rfc.std_level.slug, "hist")
        result = searchindexes.typesense_doc_from_rfc(rfc, {})
        self.assertFalse(result["flags"]["hiddenDefault"])
        self.assertFalse(result["flags"]["obsoleted"])
        self.assertFalse(result["flags"]["updated"])

        RelatedDocument.objects.create(
            source=(PublishedRfcDocEventFactory().doc),
            target=rfc,
            relationship_id="obs",
        )
        result = searchindexes.typesense_doc_from_rfc(rfc, {})
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
        result = searchindexes.typesense_doc_from_rfc(rfc, {})
        self.assertFalse(result["flags"]["hiddenDefault"])
        self.assertFalse(result["flags"]["obsoleted"])
        self.assertFalse(result["flags"]["updated"])

        RelatedDocument.objects.create(
            source=(PublishedRfcDocEventFactory().doc),
            target=rfc,
            relationship_id="updates",
        )
        result = searchindexes.typesense_doc_from_rfc(rfc, {})
        self.assertFalse(result["flags"]["hiddenDefault"])
        self.assertFalse(result["flags"]["obsoleted"])
        self.assertTrue(result["flags"]["updated"])

    def test_typesense_doc_from_rfc_flags_historic(self):
        """typesense docs should set flags correctly for historic RFC"""
        rfc = PublishedRfcDocEventFactory(doc__std_level_id="hist").doc
        assert isinstance(rfc, Document)
        result = searchindexes.typesense_doc_from_rfc(rfc, {})
        self.assertTrue(result["flags"]["hiddenDefault"])
        self.assertFalse(result["flags"]["obsoleted"])
        self.assertFalse(result["flags"]["updated"])

    @mock.patch("ietf.doc.searchindexes.cached_popularity_scores")
    def test_get_popularity_scores(self, mock_cached_scores):
        mock_cached_scores.return_value = {1234: 0.5}
        self.assertEqual(searchindexes._get_popularity_scores(), {1234: 0.5})
        for err in [FileNotFoundError(), jsonschema.ValidationError("invalid")]:
            with self.subTest(repr(err)):
                mock_cached_scores.side_effect = err
                self.assertIsNone(searchindexes._get_popularity_scores())

    @mock.patch("ietf.doc.searchindexes._get_popularity_scores")
    @mock.patch("ietf.utils.search_provider.SearchIndex.upsert_document", autospec=True)
    def test_update_or_create_rfc_entry(self, mock_upsert_document, mock_get_scores):
        rfc = PublishedRfcDocEventFactory().doc
        assert isinstance(rfc, Document)
        mock_get_scores.return_value = {rfc.rfc_number: 0.5}
        searchindexes.update_or_create_rfc_entry(rfc)
        self.assertEqual(mock_get_scores.call_count, 1)
        index, document = mock_upsert_document.call_args.args
        self.assertIs(index, searchindexes.DOCS_INDEX)
        self.assertEqual(document["id"], f"doc-{rfc.pk}")
        self.assertEqual(document["rfcNumber"], rfc.rfc_number)
        self.assertEqual(document["popularity"], 0.5)

    @mock.patch("ietf.doc.searchindexes.log")
    @mock.patch(
        "ietf.utils.search_provider.SearchIndex.update_documents", autospec=True
    )
    def test_partial_update_rfc_entries(self, mock_update_documents, mock_log):
        written = []

        def fake_update_documents(index, partial_documents, *, batchsize):
            written.extend(partial_documents)  # consumes the generator
            return WriteResult(written=len(written))

        mock_update_documents.side_effect = fake_update_documents
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
        searchindexes.partial_update_rfc_entries(rfcs, fields)
        self.assertEqual(
            mock_update_documents.call_args,
            mock.call(searchindexes.DOCS_INDEX, mock.ANY, batchsize=None),
        )
        self.assertEqual(written, [expected_tdata(rfc) for rfc in rfcs])

        written.clear()
        mock_update_documents.reset_mock()
        rfc = rfcs[0]
        searchindexes.partial_update_rfc_entries([rfc] * 50, fields, batchsize=20)
        self.assertEqual(
            mock_update_documents.call_args,
            mock.call(searchindexes.DOCS_INDEX, mock.ANY, batchsize=20),
        )
        self.assertEqual(written, [expected_tdata(rfc)] * 50)

        # Failures are logged by document id
        mock_update_documents.side_effect = None
        mock_update_documents.return_value = WriteResult(
            written=0, failures=[WriteFailure({"id": "doc-1234"}, "oops")]
        )
        mock_log.reset_mock()
        searchindexes.partial_update_rfc_entries([rfc], fields)
        self.assertIn(
            mock.call("Failed to update doc-1234: oops"), mock_log.call_args_list
        )

    @mock.patch("ietf.doc.searchindexes.cached_popularity_scores")
    @mock.patch("ietf.doc.searchindexes.refresh_popularity_scores")
    @mock.patch("ietf.doc.searchindexes.partial_update_rfc_entries", autospec=True)
    def test_update_rfc_popularities(
        self, mock_partial_update, mock_refresh_scores, mock_cached_scores
    ):
        scored_rfc, unscored_rfc = WgRfcFactory.create_batch(2)
        mock_refresh_scores.return_value = {scored_rfc.rfc_number: 0.75}
        rfcs = [scored_rfc, unscored_rfc]

        searchindexes.update_rfc_popularities(rfcs, batchsize=7)
        self.assertEqual(mock_partial_update.call_args, mock.call(rfcs, mock.ANY, 7))
        fields = mock_partial_update.call_args.args[1]
        self.assertEqual(list(fields.keys()), ["popularity"])
        self.assertEqual(fields["popularity"](scored_rfc), 0.75)
        self.assertIsNone(fields["popularity"](unscored_rfc))
        # Scores are loaded fresh once, not looked up in the cache per RFC
        self.assertEqual(mock_refresh_scores.call_count, 1)
        self.assertFalse(mock_cached_scores.called)

    def test_docs_index(self):
        self.assertEqual(searchindexes.DOCS_INDEX.name, "docs")
        self.assertIs(searchindexes.DOCS_INDEX.schema, searchindexes.DOCS_SCHEMA)

    def test_red_search_presets(self):
        """Red searches thd docs collection"""
        for preset in searchindexes.RED_SEARCH_PRESETS.values():
            self.assertEqual(preset["collection"], searchindexes.DOCS_INDEX.name)

    @mock.patch("ietf.doc.searchindexes.update_or_create_rfc_entry")
    def test_update_rfc_searchindex(self, mock_create_entry):
        self.assertFalse(Document.objects.filter(rfc_number=5073).exists())
        rfc = WgRfcFactory()
        searchindexes.update_rfc_searchindex(5073)
        self.assertFalse(mock_create_entry.called)
        searchindexes.update_rfc_searchindex(rfc.rfc_number)
        self.assertEqual(mock_create_entry.call_args, mock.call(rfc))

    @mock.patch("ietf.doc.searchindexes.log")
    @mock.patch("ietf.doc.searchindexes._get_popularity_scores")
    @mock.patch("ietf.utils.search_provider.upsert_presets")
    @mock.patch(
        "ietf.utils.search_provider.SearchIndex.rebuild_collection", autospec=True
    )
    def test_rebuild_searchindex(
        self, mock_rebuild_collection, mock_presets, mock_get_scores, mock_log
    ):
        rfcs = [PublishedRfcDocEventFactory().doc for _ in range(3)]
        WgDraftFactory()  # not included in the rebuild
        mock_get_scores.return_value = {}
        queries = CaptureQueriesContext(connection)
        entered = []
        rebuilds = []

        @contextmanager
        def fake_rebuild_collection(index, *, ignore_errors):
            # Entering creates the new collection. Nothing may be read before then.
            entered.append(
                {
                    "index": index,
                    "ignore_errors": ignore_errors,
                    "scores_read": mock_get_scores.called,
                    "queries": len(queries.captured_queries),
                }
            )
            rebuild = FakeRebuild()
            rebuilds.append(rebuild)
            yield rebuild
            self.assertFalse(mock_presets.called)  # presets come after the rebuild
            if ignore_errors:
                rebuild.result.failures.append(
                    WriteFailure({"rfcNumber": 1234}, "oops")
                )

        mock_rebuild_collection.side_effect = fake_rebuild_collection
        with queries:
            searchindexes.rebuild_searchindex()
        self.assertEqual(
            entered,
            [
                {
                    "index": searchindexes.DOCS_INDEX,
                    "ignore_errors": False,
                    "scores_read": False,
                    "queries": 0,
                }
            ],
        )
        self.assertGreater(len(queries.captured_queries), 0)
        self.assertEqual(
            [document["rfcNumber"] for document in rebuilds[0].loaded],
            sorted((rfc.rfc_number for rfc in rfcs), reverse=True),
        )
        self.assertEqual(rebuilds[0].batchsizes, [40])
        self.assertEqual(
            mock_presets.call_args, mock.call(searchindexes.RED_SEARCH_PRESETS)
        )

        entered.clear()
        rebuilds.clear()
        mock_presets.reset_mock()
        searchindexes.rebuild_searchindex(
            batchsize=3, ignore_errors=True, upsert_presets=False
        )
        self.assertTrue(entered[0]["ignore_errors"])
        self.assertEqual(rebuilds[0].batchsizes, [3])
        self.assertFalse(mock_presets.called)
        self.assertIn(
            mock.call("Failed to index RFC 1234: oops"), mock_log.call_args_list
        )

    @mock.patch("ietf.doc.searchindexes._get_popularity_scores")
    @mock.patch("ietf.utils.search_provider.upsert_presets")
    @mock.patch(
        "ietf.utils.search_provider.SearchIndex.rebuild_collection", autospec=True
    )
    @mock.patch(
        "ietf.utils.search_provider.SearchIndex.transition_build_collection",
        autospec=True,
    )
    def test_rebuild_searchindex_transition(
        self, mock_transition, mock_rebuild_collection, mock_presets, mock_get_scores
    ):
        rfc = PublishedRfcDocEventFactory().doc
        mock_get_scores.return_value = {}
        scores_read_on_entry = []
        rebuilds = []

        @contextmanager
        def fake_transition_build_collection(index, *, ignore_errors):
            scores_read_on_entry.append(mock_get_scores.called)
            rebuild = FakeRebuild()
            rebuilds.append(rebuild)
            yield rebuild

        mock_transition.side_effect = fake_transition_build_collection
        searchindexes.rebuild_searchindex(batchsize=3, transition=True)
        self.assertFalse(mock_rebuild_collection.called)
        self.assertEqual(
            mock_transition.call_args,
            mock.call(searchindexes.DOCS_INDEX, ignore_errors=False),
        )
        self.assertEqual(scores_read_on_entry, [False])
        self.assertEqual(
            [document["rfcNumber"] for document in rebuilds[0].loaded],
            [rfc.rfc_number],
        )
        self.assertEqual(rebuilds[0].batchsizes, [3])
        self.assertEqual(
            mock_presets.call_args, mock.call(searchindexes.RED_SEARCH_PRESETS)
        )

    @mock.patch("ietf.doc.searchindexes.log")
    @mock.patch("ietf.utils.search_provider.upsert_presets")
    @mock.patch(
        "ietf.utils.search_provider.SearchIndex.rebuild_collection", autospec=True
    )
    def test_rebuild_searchindex_failed(
        self, mock_rebuild_collection, mock_presets, mock_log
    ):
        @contextmanager
        def failing_rebuild_collection(index, *, ignore_errors):
            rebuild = FakeRebuild()
            yield rebuild
            rebuild.result.failures.append(WriteFailure({"rfcNumber": 1234}, "oops"))
            raise RebuildFailedError("failed")

        mock_rebuild_collection.side_effect = failing_rebuild_collection
        with self.assertRaises(RebuildFailedError):
            searchindexes.rebuild_searchindex()
        self.assertIn(
            mock.call("Failed to index RFC 1234: oops"), mock_log.call_args_list
        )
        # presets are left as they were
        self.assertFalse(mock_presets.called)

    @mock.patch("ietf.doc.searchindexes.update_rfc_popularities")
    def test_update_rfc_searchindex_popularities(self, mock_update_popularities):
        rfcs = WgRfcFactory.create_batch(3)
        WgDraftFactory()  # not included in the update

        searchindexes.update_rfc_searchindex_popularities()
        self.assertQuerysetEqual(
            mock_update_popularities.call_args.args[0], rfcs, ordered=False
        )
        self.assertEqual(mock_update_popularities.call_args.kwargs["batchsize"], 200)

        searchindexes.update_rfc_searchindex_popularities(batchsize=17)
        self.assertEqual(mock_update_popularities.call_args.kwargs["batchsize"], 17)
