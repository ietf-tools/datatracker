# Copyright The IETF Trust 2026, All Rights Reserved
from unittest import mock
from django.test.utils import override_settings

from .searchindex import _sanitize_text, update_or_create_rfc_entry
from .test_utils import TestCase
from ..doc.factories import WgDraftFactory, WgRfcFactory, PublishedRfcDocEventFactory
from ..doc.models import Document
from ..doc.storage_utils import store_str


class SearchindexTests(TestCase):
    def test_sanitize_text(self):
        dirty_text = """
        
        This is text.  It + is <---- full    of \tprobl.....ems! Fix it. 
        """
        sanitized = "This is text It is full of problems Fix it."
        self.assertEqual(_sanitize_text(dirty_text), sanitized)

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
            update_or_create_rfc_entry(not_rfc)
        self.assertFalse(mock_ts_client_constructor.called)

        invalid_rfc = WgRfcFactory(name="rfc1000000", rfc_number=None)
        assert isinstance(invalid_rfc, Document)
        with self.assertRaises(AssertionError):
            update_or_create_rfc_entry(invalid_rfc)
        self.assertFalse(mock_ts_client_constructor.called)

        rfc = PublishedRfcDocEventFactory().doc
        assert isinstance(rfc, Document)
        update_or_create_rfc_entry(rfc)
        self.assertTrue(mock_ts_client_constructor.called)
        # walk the tree down to the method we expected to be called...
        mock_upsert = (
            mock_ts_client_constructor
            .return_value
            .collections["frogs"]  # matches value in override_settings above
            .documents
            .upsert
        )
        self.assertTrue(mock_upsert.called)
        upserted_dict = mock_upsert.call_args[0][0]
        # Check a few values, not exhaustive
        self.assertEqual(upserted_dict["id"], f"doc-{rfc.pk}")
        self.assertEqual(upserted_dict["rfcNumber"], rfc.rfc_number)
        self.assertEqual(upserted_dict["abstract"], _sanitize_text(rfc.abstract))
        self.assertNotIn("content", upserted_dict, None)  # no blob

        # repeat, this time with contents
        mock_upsert.reset_mock()
        store_str(
            kind="rfc",
            name=f"txt/{rfc.name}.txt",
            content="The contents of this RFC",
            doc_name=rfc.name,
            doc_rev=rfc.rev,  # expected to be None
        )
        update_or_create_rfc_entry(rfc)
        self.assertTrue(mock_upsert.called)
        upserted_dict = mock_upsert.call_args[0][0]
        # Check a few values, not exhaustive
        self.assertEqual(
            upserted_dict["content"],
            _sanitize_text("The contents of this RFC"),
        )
