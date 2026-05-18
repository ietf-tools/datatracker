# Copyright The IETF Trust 2026, All Rights Reserved
from unittest.mock import patch
from xml.etree import ElementTree

from django.conf import settings
from django.core.files.storage import storages
from django.test.utils import override_settings

from ietf.doc.factories import PublishedRfcDocEventFactory
from ietf.sync.bibxml import (
    create_rfc_bibxml,
    get_rfc_bibxml,
    recreate_rfc_bibxml,
    save_to_bucket,
)
from ietf.utils.test_utils import TestCase


class BibXmlTests(TestCase):
    """Tests BibXML generation."""

    def setUp(self):
        super().setUp()

        self.rfc = PublishedRfcDocEventFactory(
            time="2021-04-01T12:00:00Z",
            doc__name="rfc10000",
            doc__rfc_number=10000,
            doc__std_level_id="std",
        ).doc

    def test_get_rfc_bibxml(self):
        bibxml = get_rfc_bibxml(self.rfc.rfc_number)
        self.assertIsNotNone(ElementTree.fromstring(bibxml))
        self.assertIn(f"RFC{self.rfc.rfc_number}", bibxml)
        self.assertIn(
            f"{settings.RFC_EDITOR_INFO_BASE_URL}rfc{self.rfc.rfc_number}", bibxml
        )
        self.assertIn('<date month="April" year="2021"/>', bibxml)

    def test_save_to_bucket(self):
        bibxml_bucket = storages["bibxml_bucket"]
        with override_settings(BIBXML_DELETE_THEN_WRITE=False):
            save_to_bucket("test", "contents \U0001f600")
        # Read as binary and explicitly decode to confirm encoding
        with bibxml_bucket.open("test", "rb") as f:
            self.assertEqual(f.read().decode("utf-8"), "contents \U0001f600")
        with override_settings(BIBXML_DELETE_THEN_WRITE=True):
            save_to_bucket("test", "new contents \U0001fae0".encode("utf-8"))
        # Read as binary and explicitly decode to confirm encoding
        with bibxml_bucket.open("test", "rb") as f:
            self.assertEqual(f.read().decode("utf-8"), "new contents \U0001fae0")
        bibxml_bucket.delete("test")  # clean up like a good child

    def test_create_rfc_bibxml(self):
        bibxml_bucket = storages["bibxml_bucket"]
        create_rfc_bibxml(self.rfc.rfc_number)
        with bibxml_bucket.open(f"bibxml/rfc{self.rfc.rfc_number}.xml", "rb") as f:
            bibxml = f.read().decode("utf-8")
            self.assertIsNotNone(ElementTree.fromstring(bibxml))
            self.assertIn(f"RFC{self.rfc.rfc_number}", bibxml)
            self.assertIn(
                f"{settings.RFC_EDITOR_INFO_BASE_URL}rfc{self.rfc.rfc_number}", bibxml
            )
            self.assertIn('<date month="April" year="2021"/>', bibxml)

    @patch("ietf.sync.bibxml.create_rfc_bibxml")
    def test_recreate_rfc_bibxml(self, mock_create_rfc_bibxml):
        recreate_rfc_bibxml()
        mock_create_rfc_bibxml.assert_called_with(self.rfc.rfc_number)
