# Copyright The IETF Trust 2026, All Rights Reserved
import json
from unittest import mock

from django.core.files.base import ContentFile
from django.core.files.storage import storages
from django.test.utils import override_settings
from lxml import etree

from ietf.doc.factories import (
    BcpFactory,
    StdFactory,
    IndividualRfcFactory,
    PublishedRfcDocEventFactory,
)
from ietf.name.models import DocTagName
from ietf.sync.rfcindex import (
    create_bcp_txt_index,
    create_rfc_txt_index,
    create_rfc_xml_index,
    create_std_txt_index,
    format_rfc_number,
    get_april1_rfc_numbers,
    get_publication_std_levels,
    get_unusable_rfc_numbers,
    save_to_red_bucket,
    subseries_text_line,
)
from ietf.utils.test_utils import TestCase


class RfcIndexTests(TestCase):
    """Tests of rfc-index generation

    Tests are limited and should cover more cases. Needs:
      * test of subseries docs
      * test of related docs (obsoletes/updates + reverse directions)
      * more thorough validation of index contents

    Be careful when calling create_rfc_txt_index() or create_rfc_xml_index(). These
    will save to a storage by default, which can introduce cross-talk between tests.
    Best to patch that method with a mock.
    """

    def setUp(self):
        super().setUp()
        red_bucket = storages["red_bucket"]

        # Create an unused RFC number
        red_bucket.save(
            "input/unusable-rfc-numbers.json",
            ContentFile(json.dumps([{"number": 123, "comment": ""}])),
        )

        # actual April 1 RFC
        self.april_fools_rfc = PublishedRfcDocEventFactory(
            time="2020-04-01T12:00:00Z",
            doc=IndividualRfcFactory(
                name="rfc4560",
                rfc_number=4560,
                stream_id="ise",
                std_level_id="inf",
            ),
        ).doc
        # Set up a JSON file to flag the April 1 RFC
        red_bucket.save(
            "input/april-first-rfc-numbers.json",
            ContentFile(json.dumps([self.april_fools_rfc.rfc_number])),
        )

        # non-April Fools RFC that happens to have been published on April 1
        self.rfc = PublishedRfcDocEventFactory(
            time="2021-04-01T12:00:00Z",
            doc__name="rfc10000",
            doc__rfc_number=10000,
            doc__std_level_id="std",
        ).doc
        self.rfc.tags.add(DocTagName.objects.get(slug="errata"))

        # Create a BCP with non-April Fools RFC
        self.bcp = BcpFactory(contains=[self.rfc], name="bcp11")

        # Create a STD with non-April Fools RFC
        self.std = StdFactory(contains=[self.rfc], name="std11")

        # Set up a publication-std-levels.json file to indicate the publication
        # standard of self.rfc as different from its current value
        red_bucket.save(
            "input/publication-std-levels.json",
            ContentFile(
                json.dumps(
                    [{"number": self.rfc.rfc_number, "publication_std_level": "ps"}]
                )
            ),
        )

    def tearDown(self):
        red_bucket = storages["red_bucket"]
        red_bucket.delete("input/unusable-rfc-numbers.json")
        red_bucket.delete("input/april-first-rfc-numbers.json")
        red_bucket.delete("input/publication-std-levels.json")
        super().tearDown()

    @override_settings(RFCINDEX_INPUT_PATH="input/")
    @mock.patch("ietf.sync.rfcindex.save_to_red_bucket")
    def test_create_rfc_txt_index(self, mock_save):
        create_rfc_txt_index()
        self.assertEqual(mock_save.call_count, 1)
        self.assertEqual(mock_save.call_args[0][0], "rfc-index.txt")
        contents = mock_save.call_args[0][1]
        self.assertTrue(isinstance(contents, str))
        self.assertIn(
            "123 Not Issued.",
            contents,
        )
        # No zero prefix!
        self.assertNotIn(
            "0123 Not Issued.",
            contents,
        )
        self.assertIn(
            f"{self.april_fools_rfc.rfc_number} {self.april_fools_rfc.title}",
            contents,
        )
        self.assertIn("1 April 2020", contents)  # from the April 1 RFC
        self.assertIn(
            f"{self.rfc.rfc_number} {self.rfc.title}",
            contents,
        )
        self.assertIn("April 2021", contents)  # from the non-April 1 RFC
        self.assertNotIn("1 April 2021", contents)

    @override_settings(RFCINDEX_INPUT_PATH="input/")
    @mock.patch("ietf.sync.rfcindex.save_to_red_bucket")
    def test_create_rfc_xml_index(self, mock_save):
        create_rfc_xml_index()
        self.assertEqual(mock_save.call_count, 1)
        self.assertEqual(mock_save.call_args[0][0], "rfc-index.xml")
        contents = mock_save.call_args[0][1]
        self.assertTrue(isinstance(contents, bytes))
        ns = "{https://www.rfc-editor.org/rfc-index}"  # NOT an f-string
        index = etree.fromstring(contents)

        # We can aspire to validating the schema - currently does not conform because
        # XSD expects 4-digit RFC numbers (etc).
        #
        # xmlschema = etree.XMLSchema(etree.fromstring(
        #     Path(__file__).with_name("rfc-index.xsd").read_bytes())
        # )
        # xmlschema.assertValid(index)

        children = list(index)  # elements as list
        # Should be one rfc-not-issued-entry
        self.assertEqual(len(children), 15)
        self.assertEqual(
            [
                c.find(f"{ns}doc-id").text
                for c in children
                if c.tag == f"{ns}rfc-not-issued-entry"
            ],
            ["RFC123"],
        )
        # Should be two rfc-entries
        rfc_entries = {
            c.find(f"{ns}doc-id").text: c for c in children if c.tag == f"{ns}rfc-entry"
        }

        # Check the April Fool's entry
        april_fools_entry = rfc_entries[self.april_fools_rfc.name.upper()]
        self.assertEqual(
            april_fools_entry.find(f"{ns}title").text,
            self.april_fools_rfc.title,
        )
        self.assertEqual(
            [(c.tag, c.text) for c in april_fools_entry.find(f"{ns}date")],
            [(f"{ns}month", "April"), (f"{ns}day", "1"), (f"{ns}year", "2020")],
        )
        self.assertEqual(
            april_fools_entry.find(f"{ns}current-status").text,
            "INFORMATIONAL",
        )
        self.assertEqual(
            april_fools_entry.find(f"{ns}publication-status").text,
            "UNKNOWN",
        )

        # Check the Regular entry
        rfc_entry = rfc_entries[self.rfc.name.upper()]
        self.assertEqual(rfc_entry.find(f"{ns}title").text, self.rfc.title)
        self.assertEqual(
            rfc_entry.find(f"{ns}current-status").text, "INTERNET STANDARD"
        )
        self.assertEqual(
            rfc_entry.find(f"{ns}publication-status").text, "PROPOSED STANDARD"
        )
        self.assertEqual(
            [(c.tag, c.text) for c in rfc_entry.find(f"{ns}date")],
            [(f"{ns}month", "April"), (f"{ns}year", "2021")],
        )

    @override_settings(RFCINDEX_INPUT_PATH="input/")
    @mock.patch("ietf.sync.rfcindex.save_to_red_bucket")
    def test_create_bcp_txt_index(self, mock_save):
        create_bcp_txt_index()
        self.assertEqual(mock_save.call_count, 1)
        self.assertEqual(mock_save.call_args[0][0], "bcp-index.txt")
        contents = mock_save.call_args[0][1]
        self.assertTrue(isinstance(contents, str))
        # starts from 1
        self.assertIn(
            "[BCP1]",
            contents,
        )
        # fill up to 11
        self.assertIn(
            "[BCP10]",
            contents,
        )
        # but not to 12
        self.assertNotIn(
            "[BCP12]",
            contents,
        )
        # Test empty BCPs
        self.assertIn(
            "Best Current Practice 9 currently contains no RFCs",
            contents,
        )
        # No zero prefix!
        self.assertNotIn(
            "[BCP0001]",
            contents,
        )
        # Has BCP11 with a RFC
        self.assertIn(
            "Best Current Practice 11,",
            contents,
        )
        self.assertIn(
            f'"{self.rfc.title}"',
            contents,
        )
        self.assertIn(
            "BCP 11,",
            contents,
        )
        self.assertIn(
            f"RFC {self.rfc.rfc_number},",
            contents,
        )

    @override_settings(RFCINDEX_INPUT_PATH="input/")
    @mock.patch("ietf.sync.rfcindex.save_to_red_bucket")
    def test_create_std_txt_index(self, mock_save):
        create_std_txt_index()
        self.assertEqual(mock_save.call_count, 1)
        self.assertEqual(mock_save.call_args[0][0], "std-index.txt")
        contents = mock_save.call_args[0][1]
        self.assertTrue(isinstance(contents, str))
        # starts from 1
        self.assertIn(
            "[STD1]",
            contents,
        )
        # fill up to 11
        self.assertIn(
            "[STD10]",
            contents,
        )
        # but not to 12
        self.assertNotIn(
            "[STD12]",
            contents,
        )
        # Test empty STDs
        self.assertIn(
            "Internet Standard 9 currently contains no RFCs",
            contents,
        )
        # No zero prefix!
        self.assertNotIn(
            "[STD0001]",
            contents,
        )
        # Has STD11 with a RFC
        self.assertIn(
            "Internet Standard 11,",
            contents,
        )
        self.assertIn(
            f'"{self.rfc.title}"',
            contents,
        )
        self.assertIn(
            "STD 11,",
            contents,
        )
        self.assertIn(
            f"RFC {self.rfc.rfc_number},",
            contents,
        )


class HelperTests(TestCase):
    def test_format_rfc_number(self):
        self.assertEqual(format_rfc_number(10), "10")
        with override_settings(RFCINDEX_MATCH_LEGACY_XML=True):
            self.assertEqual(format_rfc_number(10), "0010")

    def test_save_to_red_bucket(self):
        red_bucket = storages["red_bucket"]
        with override_settings(RFCINDEX_DELETE_THEN_WRITE=False):
            save_to_red_bucket("test", "contents \U0001f600")
        # Read as binary and explicitly decode to confirm encoding
        with red_bucket.open("test", "rb") as f:
            self.assertEqual(f.read().decode("utf-8"), "contents \U0001f600")
        with override_settings(RFCINDEX_DELETE_THEN_WRITE=True):
            save_to_red_bucket("test", "new contents \U0001fae0".encode("utf-8"))
        # Read as binary and explicitly decode to confirm encoding
        with red_bucket.open("test", "rb") as f:
            self.assertEqual(f.read().decode("utf-8"), "new contents \U0001fae0")
        red_bucket.delete("test")  # clean up like a good child

    def test_get_unusable_rfc_numbers_raises(self):
        """get_unusable_rfc_numbers should bail on errors"""
        with self.assertRaises(FileNotFoundError):
            get_unusable_rfc_numbers()
        red_bucket = storages["red_bucket"]
        red_bucket.save("unusable-rfc-numbers.json", ContentFile("not json"))
        with self.assertRaises(json.JSONDecodeError):
            get_unusable_rfc_numbers()
        red_bucket.delete("unusable-rfc-numbers.json")

    def test_get_april1_rfc_numbers_raises(self):
        """get_april1_rfc_numbers should bail on errors"""
        with self.assertRaises(FileNotFoundError):
            get_april1_rfc_numbers()
        red_bucket = storages["red_bucket"]
        red_bucket.save("april-first-rfc-numbers.json", ContentFile("not json"))
        with self.assertRaises(json.JSONDecodeError):
            get_april1_rfc_numbers()
        red_bucket.delete("april-first-rfc-numbers.json")

    def test_get_publication_std_levels_raises(self):
        """get_publication_std_levels should bail on errors"""
        with self.assertRaises(FileNotFoundError):
            get_publication_std_levels()
        red_bucket = storages["red_bucket"]
        red_bucket.save("publication-std-levels.json", ContentFile("not json"))
        with self.assertRaises(json.JSONDecodeError):
            get_publication_std_levels()
        red_bucket.delete("publication-std-levels.json")

    def test_subseries_text_line(self):
        text = "foobar"
        self.assertEqual(subseries_text_line(line=text, first=True), f"   {text}")
        self.assertEqual(subseries_text_line(line=text), f"              {text}")
