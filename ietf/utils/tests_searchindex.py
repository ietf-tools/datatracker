# Copyright The IETF Trust 2026, All Rights Reserved
from unittest import mock

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
    @mock.patch("ietf.utils.searchindex.typesense.Client")
    def test_update_or_create_rfc_entry(self, mock_ts_client_constructor):
        not_rfc = WgDraftFactory()
        assert isinstance(not_rfc, Document)
        with self.assertRaises(AssertionError):
            searchindex.update_or_create_rfc_entry(not_rfc)
        self.assertFalse(mock_ts_client_constructor.called)

        invalid_rfc = WgRfcFactory(name="rfc1000000", rfc_number=None)
        assert isinstance(invalid_rfc, Document)
        with self.assertRaises(AssertionError):
            searchindex.update_or_create_rfc_entry(invalid_rfc)
        self.assertFalse(mock_ts_client_constructor.called)

        rfc = PublishedRfcDocEventFactory().doc
        assert isinstance(rfc, Document)
        searchindex.update_or_create_rfc_entry(rfc)
        self.assertTrue(mock_ts_client_constructor.called)
        # walk the tree down to the method we expected to be called...
        mock_upsert = mock_ts_client_constructor.return_value.collections[
            "frogs"
        ].documents.upsert  # matches value in override_settings above
        self.assertTrue(mock_upsert.called)
        upserted_dict = mock_upsert.call_args[0][0]
        # Check a few values, not exhaustive
        self.assertEqual(upserted_dict["id"], f"doc-{rfc.pk}")
        self.assertEqual(upserted_dict["rfcNumber"], rfc.rfc_number)
        self.assertEqual(
            upserted_dict["abstract"], searchindex._sanitize_text(rfc.abstract)
        )
        self.assertNotIn("adName", upserted_dict)
        self.assertNotIn("content", upserted_dict)  # no blob
        self.assertNotIn("subseries", upserted_dict)

        # repeat, this time with contents, an AD, and subseries docs
        mock_upsert.reset_mock()
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
        searchindex.update_or_create_rfc_entry(rfc)
        self.assertTrue(mock_upsert.called)
        upserted_dict = mock_upsert.call_args[0][0]
        # Check a few values, not exhaustive
        self.assertEqual(
            upserted_dict["content"],
            searchindex._sanitize_text("The contents of this RFC"),
        )
        self.assertEqual(upserted_dict["adName"], "Alfred D. Rector")
        self.assertIn("subseries", upserted_dict)
        ss_dict = upserted_dict["subseries"]
        # We should get one of the two subseries docs, but neither is more correct
        # than the other...
        self.assertTrue(
            any(
                ss_dict == {"acronym": ss_type, "number": 1234, "total": 1}
                for ss_type in ["bcp", "std"]
            )
        )

        # Finally, delete the contents blob and make sure things don't blow up 
        mock_upsert.reset_mock()
        Blob.objects.get(bucket="rfc", name=f"txt/{rfc.name}.txt").delete()
        searchindex.update_or_create_rfc_entry(rfc)
        self.assertTrue(mock_upsert.called)
        upserted_dict = mock_upsert.call_args[0][0]
        self.assertNotIn("content", upserted_dict)
