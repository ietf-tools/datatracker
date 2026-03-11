# Copyright The IETF Trust 2026, All Rights Reserved
import json
from io import StringIO
from unittest import mock

from django.core.files.storage import storages
from django.test.utils import override_settings
from lxml import etree

from ietf.doc.factories import PublishedRfcDocEventFactory, IndividualRfcFactory
from ietf.sync.rfcindex import create_rfc_txt_index, create_rfc_xml_index
from ietf.utils.test_utils import TestCase


class RfcIndexTests(TestCase):
    """Tests of rfc-index generation

    Tests are very limited and should cover more cases.

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
            StringIO(json.dumps([{"number": 123, "comment": ""}])),
        )

        # actual April 1 RFC
        self.april_fools_rfc = PublishedRfcDocEventFactory(
            time="2020-04-01T12:00:00Z",
            doc=IndividualRfcFactory(stream_id="ise", std_level_id="inf"),
        ).doc
        # Set up a JSON file to flag the April 1 RFC
        red_bucket.save(
            "input/april-first-rfc-numbers.json",
            StringIO(json.dumps([self.april_fools_rfc.rfc_number])),
        )

        # non-April Fools RFC that happens to have been published on April 1
        self.rfc = PublishedRfcDocEventFactory(
            time="2021-04-01T12:00:00Z", doc__std_level_id="std"
        ).doc
        # Set up a publication-std-levels.json file to indicate the publication
        # standard of self.rfc as different from its current value
        red_bucket.save(
            "input/publication-std-levels.json",
            StringIO(
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
        contents = mock_save.call_args[0][1].read()
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
        contents = mock_save.call_args[0][1].read()
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
        self.assertEqual(len(children), 3)
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
