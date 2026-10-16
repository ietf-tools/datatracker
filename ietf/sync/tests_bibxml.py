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
    build_bcp_bibxml,
    build_fyi_bibxml,
    build_rfc_bibxml,
    build_std_bibxml,
    get_abstract_bibxml,
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

        # Low-numbered RFC (< 1000) for the zero-padded four-digit variant
        self.low_rfc = PublishedRfcDocEventFactory(
            time="2021-04-01T12:00:00Z",
            doc__name="rfc822",
            doc__rfc_number=822,
            doc__std_level_id="std",
        ).doc

    def test_get_abstract_bibxml(self):
        # sentences separated by two spaces collapse to one
        self.assertEqual(
            get_abstract_bibxml("First sentence.  Second sentence."),
            "<abstract><t>First sentence. Second sentence.</t></abstract>",
        )
        # a blank line starts a new <t>, and line wrapping within one collapses
        self.assertEqual(
            get_abstract_bibxml(
                "First paragraph, which\nwas wrapped.\n\n Second paragraph."
            ),
            "<abstract><t>First paragraph, which was wrapped.</t>"
            "<t>Second paragraph.</t></abstract>",
        )
        # markup in the abstract is escaped, not emitted
        self.assertEqual(
            get_abstract_bibxml("Defines the <access> identifier & its use."),
            "<abstract><t>Defines the &lt;access&gt; identifier &amp; its use.</t>"
            "</abstract>",
        )
        # an abstract that is empty or only whitespace produces no element
        for empty in ["", "   ", "\n\n"]:
            self.assertEqual(get_abstract_bibxml(empty), "", f"{empty!r}")

    def test_build_rfc_bibxml_without_abstract(self):
        self.rfc.abstract = ""
        bibxml = build_rfc_bibxml(self.rfc)
        self.assertNotIn("<abstract>", bibxml)
        self.assertIsNotNone(ElementTree.fromstring(bibxml))

    def test_build_rfc_bibxml_abstract(self):
        self.rfc.abstract = "First paragraph.  Still it.\n\n Second paragraph."
        bibxml = build_rfc_bibxml(self.rfc)
        self.assertIn(
            "<abstract><t>First paragraph. Still it.</t>"
            "<t>Second paragraph.</t></abstract>",
            bibxml,
        )
        self.assertIsNotNone(ElementTree.fromstring(bibxml))

    def test_build_rfc_bibxml(self):
        bibxml = build_rfc_bibxml(self.rfc)
        self.assertIsNotNone(ElementTree.fromstring(bibxml))
        self.assertIn(f"RFC{self.rfc.rfc_number}", bibxml)
        self.assertIn(
            f"{settings.RFC_EDITOR_INFO_BASE_URL}rfc{self.rfc.rfc_number}", bibxml
        )
        self.assertIn('<date month="April" year="2021"/>', bibxml)

    def test_build_rfc_bibxml_unpadded_low_number(self):
        # A sub-1000 RFC keeps its plain anchor unless padding is requested
        bibxml = build_rfc_bibxml(self.low_rfc)
        self.assertIsNotNone(ElementTree.fromstring(bibxml))
        self.assertIn('anchor="RFC822"', bibxml)
        self.assertNotIn('anchor="RFC0822"', bibxml)
        # link and seriesInfo always use the plain number
        self.assertIn(f"{settings.RFC_EDITOR_INFO_BASE_URL}rfc822", bibxml)
        self.assertIn('<seriesInfo name="RFC" value="822"/>', bibxml)

    def test_build_rfc_bibxml_padded_low_number(self):
        # With padding the anchor is zero-padded to four digits
        bibxml = build_rfc_bibxml(self.low_rfc, four_digits=True)
        self.assertIsNotNone(ElementTree.fromstring(bibxml))
        self.assertIn('anchor="RFC0822"', bibxml)
        # link and seriesInfo still use the plain number, not the padded one
        self.assertIn(f"{settings.RFC_EDITOR_INFO_BASE_URL}rfc822", bibxml)
        self.assertIn('<seriesInfo name="RFC" value="822"/>', bibxml)

    def test_build_rfc_bibxml_padding_ignored_for_high_number(self):
        # Padding has no effect on RFCs >= 1000
        bibxml = build_rfc_bibxml(self.rfc, four_digits=True)
        self.assertIn(f'anchor="RFC{self.rfc.rfc_number}"', bibxml)

    def test_build_bcp_bibxml(self):
        bcp_number = self.bcp.name[3:]
        bibxml = build_bcp_bibxml(bcp_number)
        self.assertIsNotNone(ElementTree.fromstring(bibxml))
        self.assertIn(f"BCP{bcp_number}", bibxml)
        self.assertIn(f"{settings.RFC_EDITOR_INFO_BASE_URL}bcp{bcp_number}", bibxml)
        self.assertIn(f"RFC{self.rfc.rfc_number}", bibxml)
        self.assertIn(
            f"{settings.RFC_EDITOR_INFO_BASE_URL}rfc{self.rfc.rfc_number}", bibxml
        )
        self.assertIn('<date month="April" year="2021"/>', bibxml)

    def test_build_std_bibxml(self):
        std_number = self.std.name[3:]
        bibxml = build_std_bibxml(std_number)
        self.assertIsNotNone(ElementTree.fromstring(bibxml))
        self.assertIn(f"STD{std_number}", bibxml)
        self.assertIn(f"{settings.RFC_EDITOR_INFO_BASE_URL}std{std_number}", bibxml)
        self.assertIn(f"RFC{self.rfc.rfc_number}", bibxml)
        self.assertIn(
            f"{settings.RFC_EDITOR_INFO_BASE_URL}rfc{self.rfc.rfc_number}", bibxml
        )
        self.assertIn('<date month="April" year="2021"/>', bibxml)

    def test_build_fyi_bibxml(self):
        fyi_number = self.fyi.name[3:]
        bibxml = build_fyi_bibxml(fyi_number)
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
        bibxml = build_rfc_bibxml(self.rfc)
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
        bibxml = build_bcp_bibxml(bcp_number)
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
        bibxml = build_std_bibxml(std_number)
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
        bibxml = build_fyi_bibxml(fyi_number)
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

    def test_create_rfc_bibxml_padded_low_number(self):
        bibxml_bucket = storages["bibxml_bucket"]
        bibxml = build_rfc_bibxml(self.low_rfc, four_digits=True)
        filename = f"bibxml/rfc{self.low_rfc.rfc_number:04d}.xml"
        save_bibxml(bibxml, filename)
        with bibxml_bucket.open(filename, "rb") as f:
            bibxml = f.read().decode("utf-8")
            self.assertIsNotNone(ElementTree.fromstring(bibxml))
            self.assertIn('anchor="RFC0822"', bibxml)

    @patch("ietf.sync.bibxml.save_bibxml")
    def test_recreate_rfc_bibxml(self, mock_save_bibxml):
        recreate_rfc_bibxml()
        filename = f"bibxml/rfc{self.rfc.rfc_number}.xml"
        mock_save_bibxml.assert_any_call(ANY, filename)

    @patch("ietf.sync.bibxml.save_bibxml")
    def test_recreate_rfc_bibxml_writes_both_forms_for_low_number(
        self, mock_save_bibxml
    ):
        # A sub-1000 RFC is written both unpadded and zero-padded
        recreate_rfc_bibxml()
        mock_save_bibxml.assert_has_calls(
            [
                call(ANY, "bibxml/rfc822.xml"),
                call(ANY, "bibxml/rfc0822.xml"),
            ],
            any_order=True,
        )

    @patch("ietf.sync.bibxml.save_bibxml")
    def test_recreate_rfc_bibxml_single_form_for_high_number(self, mock_save_bibxml):
        # An RFC >= 1000 is written exactly once, with no extra padded form
        recreate_rfc_bibxml()
        written = [c.args[1] for c in mock_save_bibxml.call_args_list]
        self.assertEqual(written.count(f"bibxml/rfc{self.rfc.rfc_number}.xml"), 1)

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
