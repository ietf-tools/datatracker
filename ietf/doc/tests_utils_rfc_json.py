# Copyright The IETF Trust 2026, All Rights Reserved

import json

from django.core.files.base import ContentFile
from django.core.files.storage import storages
from django.test.utils import override_settings

from ietf.doc.factories import (
    PublishedRfcDocEventFactory,
    RfcAuthorFactory,
    RfcFactory,
    WgRfcFactory,
)
from ietf.doc.models import RelatedDocument
from ietf.doc.utils_rfc_json import generate_rfc_json
from ietf.group.factories import GroupFactory
from ietf.name.models import StdLevelName
from ietf.utils.test_utils import TestCase


def _put_pub_levels(rfc_number, slug, path="input/"):
    """Write a minimal publication-std-levels.json to the red bucket."""
    red_bucket = storages["red_bucket"]
    red_bucket.save(
        f"{path}publication-std-levels.json",
        ContentFile(
            json.dumps([{"number": rfc_number, "publication_std_level": slug}])
        ),
    )


def _put_errata(rfc_number, path="other/errata.json"):
    """Write an errata.json with one entry for the given RFC."""
    red_bucket = storages["red_bucket"]
    red_bucket.save(
        path,
        ContentFile(
            json.dumps(
                [{"doc-id": f"RFC{rfc_number}", "errata_status_code": "Reported"}]
            )
        ),
    )


def _put_empty_errata(path="other/errata.json"):
    red_bucket = storages["red_bucket"]
    red_bucket.save(path, ContentFile(json.dumps([])))


def _put_april_first(rfc_number, path="input/"):
    red_bucket = storages["red_bucket"]
    red_bucket.save(
        f"{path}april-first-rfc-numbers.json",
        ContentFile(json.dumps([rfc_number])),
    )


def _read_json(rfc_number):
    from ietf.blobdb.models import Blob

    blob = Blob.objects.get(bucket="rfc", name=f"json/rfc{rfc_number}.json")
    return json.loads(bytes(blob.content))


@override_settings(
    RFCINDEX_INPUT_PATH="input/",
    ERRATA_JSON_BLOB_NAME="other/errata.json",
    RFC_EDITOR_ERRATA_BASE_URL="https://www.rfc-editor.org/errata/",
)
class GenerateRfcJsonTests(TestCase):
    def setUp(self):
        super().setUp()
        # Minimal red_bucket blobs required by all tests
        red_bucket = storages["red_bucket"]
        red_bucket.save(
            "input/april-first-rfc-numbers.json", ContentFile(json.dumps([]))
        )

    def tearDown(self):
        red_bucket = storages["red_bucket"]
        for name in [
            "input/publication-std-levels.json",
            "input/april-first-rfc-numbers.json",
            "other/errata.json",
        ]:
            try:
                red_bucket.delete(name)
            except Exception:
                pass
        super().tearDown()

    def test_missing_rfc_logs_and_returns(self):
        """Calling for a nonexistent RFC number logs and returns without raising."""
        # Should not raise; no blob should be written
        generate_rfc_json(999999, pub_levels={})
        from ietf.blobdb.models import Blob

        self.assertFalse(
            Blob.objects.filter(bucket="rfc", name="json/rfc999999.json").exists()
        )

    def test_all_fields(self):
        """All 17 JSON fields are populated correctly from a fully-populated RFC."""
        area = GroupFactory(type_id="area")
        wg = GroupFactory(type_id="wg", parent=area)
        rfc = PublishedRfcDocEventFactory(
            time="2021-05-01T00:00:00Z",
            doc=WgRfcFactory(
                group=wg,
                stream_id="ietf",
                std_level_id="ps",
                pages=42,
                abstract="Test abstract.",
                keywords=["foo", "bar"],
            ),
        ).doc
        author = RfcAuthorFactory(document=rfc, is_editor=False)
        editor = RfcAuthorFactory(document=rfc, is_editor=True)

        obsoletes_rfc = RfcFactory()
        updated_rfc = RfcFactory()
        RelatedDocument.objects.create(
            source=rfc, target=obsoletes_rfc, relationship_id="obs"
        )
        RelatedDocument.objects.create(
            source=rfc, target=updated_rfc, relationship_id="updates"
        )
        obsoleted_by_rfc = RfcFactory()
        updated_by_rfc = RfcFactory()
        RelatedDocument.objects.create(
            source=obsoleted_by_rfc, target=rfc, relationship_id="obs"
        )
        RelatedDocument.objects.create(
            source=updated_by_rfc, target=rfc, relationship_id="updates"
        )

        _put_pub_levels(rfc.rfc_number, "ps")
        _put_empty_errata()

        generate_rfc_json(rfc.rfc_number)
        data = _read_json(rfc.rfc_number)

        self.assertEqual(data["doc_id"], f"RFC{rfc.rfc_number}")
        self.assertEqual(data["title"], rfc.title)
        self.assertEqual(data["abstract"], "Test abstract.")
        self.assertEqual(data["page_count"], "42")
        self.assertEqual(data["pub_status"], "PROPOSED STANDARD")
        self.assertEqual(data["status"], "PROPOSED STANDARD")
        self.assertEqual(data["pub_date"], "May 2021")
        self.assertEqual(data["keywords"], ["foo", "bar"])
        self.assertEqual(data["see_also"], [])
        self.assertEqual(data["doi"], f"10.17487/RFC{rfc.rfc_number}")
        self.assertIsNone(data["errata_url"])
        self.assertIsNone(data["draft"])

        # authors — non-editor first (lower order), then editor
        self.assertEqual(
            data["authors"],
            [author.titlepage_name, f"{editor.titlepage_name}, Ed."],
        )

        # relationships
        self.assertIn(f"RFC{obsoletes_rfc.rfc_number}", data["obsoletes"])
        self.assertIn(f"RFC{updated_rfc.rfc_number}", data["updates"])
        self.assertIn(f"RFC{obsoleted_by_rfc.rfc_number}", data["obsoleted_by"])
        self.assertIn(f"RFC{updated_by_rfc.rfc_number}", data["updated_by"])

    def test_pub_status_differs_from_status(self):
        """pub_status reflects publication-std-levels.json; status reflects current std_level."""
        rfc = PublishedRfcDocEventFactory(
            doc=WgRfcFactory(std_level_id="hist"),
        ).doc
        # Record was published as "ps" but is now "hist"
        _put_pub_levels(rfc.rfc_number, "ps")
        _put_empty_errata()

        generate_rfc_json(rfc.rfc_number)
        data = _read_json(rfc.rfc_number)

        self.assertEqual(data["pub_status"], "PROPOSED STANDARD")
        self.assertEqual(data["status"], "HISTORIC")

    def test_errata_url_set_when_errata_exist(self):
        """errata_url is populated when errata.json has any entry for the RFC."""
        rfc = PublishedRfcDocEventFactory(doc=WgRfcFactory()).doc
        _put_pub_levels(rfc.rfc_number, "ps")
        _put_errata(rfc.rfc_number)

        generate_rfc_json(rfc.rfc_number)
        data = _read_json(rfc.rfc_number)

        self.assertEqual(
            data["errata_url"],
            f"https://www.rfc-editor.org/errata/rfc{rfc.rfc_number}",
        )

    def test_errata_url_none_when_no_errata(self):
        """errata_url is None when errata.json has no entries for the RFC."""
        rfc = PublishedRfcDocEventFactory(doc=WgRfcFactory()).doc
        _put_pub_levels(rfc.rfc_number, "ps")
        _put_empty_errata()

        generate_rfc_json(rfc.rfc_number)
        data = _read_json(rfc.rfc_number)

        self.assertIsNone(data["errata_url"])

    def test_errata_failure_yields_null_url(self):
        """If reading errata.json fails, errata_url is null and no exception is raised."""
        rfc = PublishedRfcDocEventFactory(doc=WgRfcFactory()).doc
        _put_pub_levels(rfc.rfc_number, "ps")
        # Deliberately do not put errata blob — FileNotFoundError expected

        generate_rfc_json(rfc.rfc_number)  # must not raise
        data = _read_json(rfc.rfc_number)
        self.assertIsNone(data["errata_url"])

    def test_second_call_overwrites(self):
        """Calling generate_rfc_json twice does not raise AlreadyExistsError."""
        rfc = PublishedRfcDocEventFactory(doc=WgRfcFactory()).doc
        _put_pub_levels(rfc.rfc_number, "ps")
        _put_empty_errata()

        generate_rfc_json(rfc.rfc_number)
        generate_rfc_json(rfc.rfc_number)  # must not raise

    def test_april_first_date_format(self):
        """April Fools RFCs get '1 April YYYY' date format."""
        rfc = PublishedRfcDocEventFactory(
            time="2020-04-01T12:00:00Z",
            doc=WgRfcFactory(),
        ).doc
        red_bucket = storages["red_bucket"]
        red_bucket.delete("input/april-first-rfc-numbers.json")
        _put_april_first(rfc.rfc_number)
        _put_pub_levels(rfc.rfc_number, "inf")
        _put_empty_errata()

        generate_rfc_json(rfc.rfc_number)
        data = _read_json(rfc.rfc_number)

        self.assertEqual(data["pub_date"], "1 April 2020")

    def test_non_april_first_april_date(self):
        """An April publication that is NOT in the April Fools list gets 'April YYYY'."""
        rfc = PublishedRfcDocEventFactory(
            time="2020-04-15T12:00:00Z",
            doc=WgRfcFactory(),
        ).doc
        _put_pub_levels(rfc.rfc_number, "inf")
        _put_empty_errata()

        generate_rfc_json(rfc.rfc_number)
        data = _read_json(rfc.rfc_number)

        self.assertEqual(data["pub_date"], "April 2020")

    def test_source_ietf_wg(self):
        """IETF-stream WG RFC: source is 'acronym (area)'."""
        area = GroupFactory(type_id="area")
        wg = GroupFactory(type_id="wg", parent=area)
        rfc = PublishedRfcDocEventFactory(
            doc=WgRfcFactory(group=wg, stream_id="ietf"),
        ).doc
        _put_pub_levels(rfc.rfc_number, "ps")
        _put_empty_errata()

        generate_rfc_json(rfc.rfc_number)
        data = _read_json(rfc.rfc_number)

        self.assertEqual(data["source"], f"{wg.acronym} ({area.acronym})")

    def test_source_ietf_no_wg(self):
        """IETF-stream individual RFC (group acronym 'none'): source is 'IETF - NON WORKING GROUP'."""
        rfc = PublishedRfcDocEventFactory(
            doc=RfcFactory(
                group=GroupFactory(acronym="none"),
                stream_id="ietf",
            ),
        ).doc
        _put_pub_levels(rfc.rfc_number, "inf")
        _put_empty_errata()

        generate_rfc_json(rfc.rfc_number)
        data = _read_json(rfc.rfc_number)

        self.assertEqual(data["source"], "IETF - NON WORKING GROUP")

    def test_source_iab(self):
        """IAB-stream RFC: source is 'IAB'."""
        rfc = PublishedRfcDocEventFactory(
            doc=RfcFactory(stream_id="iab"),
        ).doc
        _put_pub_levels(rfc.rfc_number, "inf")
        _put_empty_errata()

        generate_rfc_json(rfc.rfc_number)
        data = _read_json(rfc.rfc_number)

        self.assertEqual(data["source"], "IAB")

    def test_source_ise(self):
        """ISE-stream RFC: source is 'INDEPENDENT'."""
        rfc = PublishedRfcDocEventFactory(
            doc=RfcFactory(stream_id="ise"),
        ).doc
        _put_pub_levels(rfc.rfc_number, "inf")
        _put_empty_errata()

        generate_rfc_json(rfc.rfc_number)
        data = _read_json(rfc.rfc_number)

        self.assertEqual(data["source"], "INDEPENDENT")

    def test_pub_levels_passed_in(self):
        """When pub_levels is passed in, get_publication_std_levels() is not called."""
        import mock

        rfc = PublishedRfcDocEventFactory(doc=WgRfcFactory()).doc
        _put_empty_errata()

        ps_level = StdLevelName.objects.get(slug="ps")
        pub_levels = {rfc.rfc_number: ps_level}

        with mock.patch(
            "ietf.doc.utils_rfc_json.get_publication_std_levels"
        ) as mock_get:
            generate_rfc_json(rfc.rfc_number, pub_levels=pub_levels)
            mock_get.assert_not_called()

        data = _read_json(rfc.rfc_number)
        self.assertEqual(data["pub_status"], "PROPOSED STANDARD")
