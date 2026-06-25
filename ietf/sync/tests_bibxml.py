# Copyright The IETF Trust 2026, All Rights Reserved
from unittest.mock import call, patch, ANY
from xml.etree import ElementTree

from django.conf import settings
from django.core.files.storage import storages
from django.test.utils import override_settings

from ietf.doc.factories import (
    BcpFactory,
    FyiFactory,
    PublishedRfcDocEventFactory,
    StdFactory,
)
from ietf.sync.bibxml import (
    get_bcp_bibxml,
    get_fyi_bibxml,
    get_rfc_bibxml,
    get_std_bibxml,
    recreate_rfc_bibxml,
    recreate_rfcsubseries_bibxml,
    save_bibxml,
    save_to_bucket,
)
from ietf.utils.test_utils import TestCase


class BibXmlTests(TestCase):
    """Tests BibXML generation."""

    def setUp(self):
        super().setUp()

        # non-April Fools RFC that happens to have been published on April 1
        self.rfc = PublishedRfcDocEventFactory(
            time="2021-04-01T12:00:00Z",
            doc__name="rfc10000",
            doc__rfc_number=10000,
            doc__std_level_id="std",
        ).doc

        # Create a BCP with non-April Fools RFC
        self.bcp = BcpFactory(contains=[self.rfc], name="bcp44")

        # Create a STD with non-April Fools RFC
        self.std = StdFactory(contains=[self.rfc], name="std46")

        # Create a FYI with non-April Fools RFC
        self.fyi = FyiFactory(contains=[self.rfc], name="fyi3")

    def test_get_rfc_bibxml(self):
        bibxml = get_rfc_bibxml(self.rfc.rfc_number)
        self.assertIsNotNone(ElementTree.fromstring(bibxml))
        self.assertIn(f"RFC{self.rfc.rfc_number}", bibxml)
        self.assertIn(
            f"{settings.RFC_EDITOR_INFO_BASE_URL}rfc{self.rfc.rfc_number}", bibxml
        )
        self.assertIn('<date month="April" year="2021"/>', bibxml)

    def test_get_bcp_bibxml(self):
        bcp_number = self.bcp.name[3:]
        bibxml = get_bcp_bibxml(bcp_number)
        self.assertIsNotNone(ElementTree.fromstring(bibxml))
        self.assertIn(f"BCP{bcp_number}", bibxml)
        self.assertIn(f"{settings.RFC_EDITOR_INFO_BASE_URL}bcp{bcp_number}", bibxml)
        self.assertIn(f"RFC{self.rfc.rfc_number}", bibxml)
        self.assertIn(
            f"{settings.RFC_EDITOR_INFO_BASE_URL}rfc{self.rfc.rfc_number}", bibxml
        )
        self.assertIn('<date month="April" year="2021"/>', bibxml)

    def test_get_std_bibxml(self):
        std_number = self.std.name[3:]
        bibxml = get_std_bibxml(std_number)
        self.assertIsNotNone(ElementTree.fromstring(bibxml))
        self.assertIn(f"STD{std_number}", bibxml)
        self.assertIn(f"{settings.RFC_EDITOR_INFO_BASE_URL}std{std_number}", bibxml)
        self.assertIn(f"RFC{self.rfc.rfc_number}", bibxml)
        self.assertIn(
            f"{settings.RFC_EDITOR_INFO_BASE_URL}rfc{self.rfc.rfc_number}", bibxml
        )
        self.assertIn('<date month="April" year="2021"/>', bibxml)

    def test_get_fyi_bibxml(self):
        fyi_number = self.fyi.name[3:]
        bibxml = get_fyi_bibxml(fyi_number)
        self.assertIsNotNone(ElementTree.fromstring(bibxml))
        self.assertIn(f"FYI{fyi_number}", bibxml)
        self.assertIn(f"{settings.RFC_EDITOR_INFO_BASE_URL}fyi{fyi_number}", bibxml)
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
        bibxml = get_rfc_bibxml(self.rfc.rfc_number)
        filename = f"bibxml/rfc{self.rfc.rfc_number}.xml"
        save_bibxml(bibxml, filename)
        with bibxml_bucket.open(filename, "rb") as f:
            bibxml = f.read().decode("utf-8")
            self.assertIsNotNone(ElementTree.fromstring(bibxml))
            self.assertIn(f"RFC{self.rfc.rfc_number}", bibxml)
            self.assertIn(
                f"{settings.RFC_EDITOR_INFO_BASE_URL}rfc{self.rfc.rfc_number}", bibxml
            )
            self.assertIn('<date month="April" year="2021"/>', bibxml)

    def test_create_bcp_bibxml(self):
        bibxml_bucket = storages["bibxml_bucket"]
        bcp_number = self.bcp.name[3:]
        bibxml = get_bcp_bibxml(bcp_number)
        filename = f"bibxml-rfcsubseries/bcp{bcp_number}.xml"
        save_bibxml(bibxml, filename)
        with bibxml_bucket.open(filename, "rb") as f:
            bibxml = f.read().decode("utf-8")
            self.assertIsNotNone(ElementTree.fromstring(bibxml))
            self.assertIn(f"BCP{bcp_number}", bibxml)
            self.assertIn(
                f"{settings.RFC_EDITOR_INFO_BASE_URL}rfc{self.rfc.rfc_number}", bibxml
            )
            self.assertIn(f'<seriesInfo name="BCP" value="{bcp_number}"/>', bibxml)
            self.assertIn('<date month="April" year="2021"/>', bibxml)

    def test_create_std_bibxml(self):
        bibxml_bucket = storages["bibxml_bucket"]
        std_number = self.std.name[3:]
        bibxml = get_std_bibxml(std_number)
        filename = f"bibxml-rfcsubseries/std{std_number}.xml"
        save_bibxml(bibxml, filename)
        with bibxml_bucket.open(filename, "rb") as f:
            bibxml = f.read().decode("utf-8")
            self.assertIsNotNone(ElementTree.fromstring(bibxml))
            self.assertIn(f"STD{std_number}", bibxml)
            self.assertIn(
                f"{settings.RFC_EDITOR_INFO_BASE_URL}rfc{self.rfc.rfc_number}", bibxml
            )
            self.assertIn(f'<seriesInfo name="STD" value="{std_number}"/>', bibxml)
            self.assertIn('<date month="April" year="2021"/>', bibxml)

    def test_create_fyi_bibxml(self):
        bibxml_bucket = storages["bibxml_bucket"]
        fyi_number = self.fyi.name[3:]
        bibxml = get_fyi_bibxml(fyi_number)
        filename = f"bibxml-rfcsubseries/fyi{fyi_number}.xml"
        save_bibxml(bibxml, filename)
        with bibxml_bucket.open(filename, "rb") as f:
            bibxml = f.read().decode("utf-8")
            self.assertIsNotNone(ElementTree.fromstring(bibxml))
            self.assertIn(f"FYI{fyi_number}", bibxml)
            self.assertIn(
                f"{settings.RFC_EDITOR_INFO_BASE_URL}rfc{self.rfc.rfc_number}", bibxml
            )
            self.assertIn(f'<seriesInfo name="FYI" value="{fyi_number}"/>', bibxml)
            self.assertIn('<date month="April" year="2021"/>', bibxml)

    @patch("ietf.sync.bibxml.save_bibxml")
    def test_recreate_rfc_bibxml(self, mock_save_bibxml):
        recreate_rfc_bibxml()
        filename = f"bibxml/rfc{self.rfc.rfc_number}.xml"
        mock_save_bibxml.assert_called_with(ANY, filename)

    @patch("ietf.sync.bibxml.save_bibxml")
    def test_recreate_rfcsubseries_bibxml(self, mock_save_bibxml):
        recreate_rfcsubseries_bibxml()
        bcp_filename = f"bibxml-rfcsubseries/bcp{self.bcp.name[3:]}.xml"
        std_filename = f"bibxml-rfcsubseries/std{self.std.name[3:]}.xml"
        fyi_filename = f"bibxml-rfcsubseries/fyi{self.fyi.name[3:]}.xml"
        mock_save_bibxml.assert_has_calls(
            [
                call(ANY, bcp_filename),
                call(ANY, std_filename),
                call(ANY, fyi_filename),
            ]
        )
