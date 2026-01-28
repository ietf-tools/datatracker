# Copyright The IETF Trust 2025, All Rights Reserved
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.conf import settings
from django.core.files.base import ContentFile
from django.db.models import Max
from django.db.models.functions import Coalesce
from django.test.utils import override_settings
from django.urls import reverse as urlreverse

from ietf.blobdb.models import Blob
from ietf.doc.factories import IndividualDraftFactory, WgDraftFactory, WgRfcFactory
from ietf.doc.models import RelatedDocument, Document
from ietf.group.factories import RoleFactory, GroupFactory
from ietf.person.factories import PersonFactory
from ietf.utils.test_utils import APITestCase, reload_db_objects


class RpcApiTests(APITestCase):
    @override_settings(APP_API_TOKENS={"ietf.api.views_rpc": ["valid-token"]})
    def test_draftviewset_references(self):
        viewname = "ietf.api.purple_api.draft-references"

        # non-existent draft
        bad_id = Document.objects.aggregate(unused_id=Coalesce(Max("id"), 0) + 100)[
            "unused_id"
        ]
        url = urlreverse(viewname, kwargs={"doc_id": bad_id})
        # Without credentials
        r = self.client.get(url)
        self.assertEqual(r.status_code, 403)
        # Add credentials
        r = self.client.get(url, headers={"X-Api-Key": "valid-token"})
        self.assertEqual(r.status_code, 404)

        # draft without any normative references
        draft = IndividualDraftFactory()
        draft = reload_db_objects(draft)
        url = urlreverse(viewname, kwargs={"doc_id": draft.id})
        r = self.client.get(url)
        self.assertEqual(r.status_code, 403)
        r = self.client.get(url, headers={"X-Api-Key": "valid-token"})
        self.assertEqual(r.status_code, 200)
        refs = r.json()
        self.assertEqual(refs, [])

        # draft without any normative references but with an informative reference
        draft_foo = IndividualDraftFactory()
        draft_foo = reload_db_objects(draft_foo)
        RelatedDocument.objects.create(
            source=draft, target=draft_foo, relationship_id="refinfo"
        )
        url = urlreverse(viewname, kwargs={"doc_id": draft.id})
        r = self.client.get(url)
        self.assertEqual(r.status_code, 403)
        r = self.client.get(url, headers={"X-Api-Key": "valid-token"})
        self.assertEqual(r.status_code, 200)
        refs = r.json()
        self.assertEqual(refs, [])

        # draft with a normative reference
        draft_bar = IndividualDraftFactory()
        draft_bar = reload_db_objects(draft_bar)
        RelatedDocument.objects.create(
            source=draft, target=draft_bar, relationship_id="refnorm"
        )
        url = urlreverse(viewname, kwargs={"doc_id": draft.id})
        r = self.client.get(url)
        self.assertEqual(r.status_code, 403)
        r = self.client.get(url, headers={"X-Api-Key": "valid-token"})
        self.assertEqual(r.status_code, 200)
        refs = r.json()
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0]["id"], draft_bar.id)
        self.assertEqual(refs[0]["name"], draft_bar.name)

    @override_settings(APP_API_TOKENS={"ietf.api.views_rpc": ["valid-token"]})
    def test_notify_rfc_published(self):
        url = urlreverse("ietf.api.purple_api.notify_rfc_published")
        area = GroupFactory(type_id="area")
        rfc_group = GroupFactory(type_id="wg")
        draft_ad = RoleFactory(group=area, name_id="ad").person
        rfc_ad = PersonFactory()
        draft_authors = PersonFactory.create_batch(2)
        rfc_authors = PersonFactory.create_batch(3)
        draft = WgDraftFactory(
            group__parent=area, authors=draft_authors, ad=draft_ad, stream_id="ietf"
        )
        rfc_stream_id = "ise"
        assert isinstance(draft, Document), "WgDraftFactory should generate a Document"
        unused_rfc_number = (
            Document.objects.filter(rfc_number__isnull=False).aggregate(
                unused_rfc_number=Max("rfc_number") + 1
            )["unused_rfc_number"]
            or 10000
        )

        post_data = {
            "published": "2025-12-17T20:29:00Z",
            "draft_name": draft.name,
            "draft_rev": draft.rev,
            "rfc_number": unused_rfc_number,
            "title": "RFC " + draft.title,
            "authors": [
                {
                    "titlepage_name": f"titlepage {author.name}",
                    "is_editor": False,
                    "person": author.pk,
                    "email": author.email_address(),
                    "affiliation": "Some Affiliation",
                    "country": "CA",
                }
                for author in rfc_authors
            ],
            "group": rfc_group.acronym,
            "stream": rfc_stream_id,
            "abstract": "RFC version of " + draft.abstract,
            "pages": draft.pages + 10,
            "std_level": "ps",
            "ad": rfc_ad.pk,
            "obsoletes": [],
            "updates": [],
            "subseries": [],
        }
        r = self.client.post(url, data=post_data, format="json")
        self.assertEqual(r.status_code, 403)

        r = self.client.post(
            url, data=post_data, format="json", headers={"X-Api-Key": "valid-token"}
        )
        self.assertEqual(r.status_code, 200)
        rfc = Document.objects.filter(rfc_number=unused_rfc_number).first()
        self.assertIsNotNone(rfc)
        self.assertEqual(rfc.came_from_draft(), draft)
        self.assertEqual(
            rfc.docevent_set.filter(
                type="published_rfc", time="2025-12-17T20:29:00Z"
            ).count(),
            1,
        )
        self.assertEqual(rfc.title, "RFC " + draft.title)
        self.assertEqual(rfc.documentauthor_set.count(), 0)
        self.assertEqual(
            list(
                rfc.rfcauthor_set.values(
                    "titlepage_name",
                    "is_editor",
                    "person",
                    "email",
                    "affiliation",
                    "country",
                )
            ),
            [
                {
                    "titlepage_name": f"titlepage {author.name}",
                    "is_editor": False,
                    "person": author.pk,
                    "email": author.email_address(),
                    "affiliation": "Some Affiliation",
                    "country": "CA",
                }
                for author in rfc_authors
            ],
        )
        self.assertEqual(rfc.group, rfc_group)
        self.assertEqual(rfc.stream_id, rfc_stream_id)
        self.assertEqual(rfc.abstract, "RFC version of " + draft.abstract)
        self.assertEqual(rfc.pages, draft.pages + 10)
        self.assertEqual(rfc.std_level_id, "ps")
        self.assertEqual(rfc.ad, rfc_ad)
        self.assertEqual(rfc.related_that_doc("obs"), [])
        self.assertEqual(rfc.related_that_doc("updates"), [])
        self.assertEqual(rfc.part_of(), [])
        self.assertEqual(draft.get_state().slug, "rfc")
        # todo test non-empty relationships
        # todo test references (when updating that is part of the handling)

    @override_settings(APP_API_TOKENS={"ietf.api.views_rpc": ["valid-token"]})
    def test_upload_rfc_files(self):
        def _valid_post_data():
            """Generate a valid post data dict

            Each API call needs a fresh set of files, so don't reuse the return
            value from this for multiple calls!
            """
            return {
                "rfc": rfc.rfc_number,
                "contents": [
                    ContentFile(b"This is .xml", "myfile.xml"),
                    ContentFile(b"This is .txt", "myfile.txt"),
                    ContentFile(b"This is .html", "myfile.html"),
                    ContentFile(b"This is .pdf", "myfile.pdf"),
                    ContentFile(b"This is .json", "myfile.json"),
                    ContentFile(b"This is .notprepped.xml", "myfile.notprepped.xml"),
                ],
                "replace": False,
            }

        url = urlreverse("ietf.api.purple_api.upload_rfc_files")
        unused_rfc_number = (
            Document.objects.filter(rfc_number__isnull=False).aggregate(
                unused_rfc_number=Max("rfc_number") + 1
            )["unused_rfc_number"]
            or 10000
        )

        rfc = WgRfcFactory(rfc_number=unused_rfc_number)
        assert isinstance(rfc, Document), "WgRfcFactory should generate a Document"
        with TemporaryDirectory() as rfc_dir:
            settings.RFC_PATH = rfc_dir  # affects overridden settings
            rfc_path = Path(rfc_dir)
            (rfc_path / "prerelease").mkdir()
            content = StringIO("XML content\n")
            content.name = "myrfc.xml"

            # no api key
            r = self.client.post(url, _valid_post_data(), format="multipart")
            self.assertEqual(r.status_code, 403)

            # invalid RFC
            r = self.client.post(
                url,
                _valid_post_data() | {"rfc": unused_rfc_number + 1},
                format="multipart",
                headers={"X-Api-Key": "valid-token"},
            )
            self.assertEqual(r.status_code, 400)

            # empty files
            r = self.client.post(
                url,
                _valid_post_data() | {
                    "contents": [
                        ContentFile(b"", "myfile.xml"),
                        ContentFile(b"", "myfile.txt"),
                        ContentFile(b"", "myfile.html"),
                        ContentFile(b"", "myfile.pdf"),
                        ContentFile(b"", "myfile.json"),
                        ContentFile(b"", "myfile.notprepped.xml"),
                    ]
                },
                format="multipart",
                headers={"X-Api-Key": "valid-token"},
            )
            self.assertEqual(r.status_code, 400)

            # bad file type
            r = self.client.post(
                url,
                _valid_post_data() | {
                    "contents": [
                        ContentFile(b"Some content", "myfile.jpg"),
                    ]
                },
                format="multipart",
                headers={"X-Api-Key": "valid-token"},
            )
            self.assertEqual(r.status_code, 400)

            # Put a file in the way. Post should fail because replace = False
            file_in_the_way = (rfc_path / f"rfc{unused_rfc_number}.txt")
            file_in_the_way.touch()
            r = self.client.post(
                url,
                _valid_post_data(),
                format="multipart",
                headers={"X-Api-Key": "valid-token"},
            )
            self.assertEqual(r.status_code, 409)  # conflict
            file_in_the_way.unlink()
            
            # Put a blob in the way. Post should fail because replace = False
            blob_in_the_way = Blob.objects.create(
                bucket="rfc", name=f"txt/rfc{unused_rfc_number}.txt", content=b""
            )
            r = self.client.post(
                url,
                _valid_post_data(),
                format="multipart",
                headers={"X-Api-Key": "valid-token"},
            )
            self.assertEqual(r.status_code, 409)  # conflict
            blob_in_the_way.delete()

            # valid post
            r = self.client.post(
                url,
                _valid_post_data(),
                format="multipart",
                headers={"X-Api-Key": "valid-token"},
            )
            self.assertEqual(r.status_code, 200)
            for extension in ["xml", "txt", "html", "pdf", "json"]:
                filename = f"rfc{unused_rfc_number}.{extension}"
                self.assertEqual(
                    (rfc_path / filename)
                    .read_text(),
                    f"This is .{extension}",
                    f"{extension} file should contain the expected content",
                )
                self.assertEqual(
                    bytes(
                        Blob.objects.get(
                            bucket="rfc", name=f"{extension}/{filename}"
                        ).content
                    ),
                    f"This is .{extension}".encode("utf-8"),
                    f"{extension} blob should contain the expected content",
                )
            # special case for notprepped
            notprepped_fn = f"rfc{unused_rfc_number}.notprepped.xml"
            self.assertEqual(
                (
                    rfc_path / "prerelease" / notprepped_fn
                ).read_text(),
                "This is .notprepped.xml",
                ".notprepped.xml file should contain the expected content",
            )
            self.assertEqual(
                bytes(
                    Blob.objects.get(
                        bucket="rfc", name=f"notprepped/{notprepped_fn}"
                    ).content
                ),
                b"This is .notprepped.xml",
                ".notprepped.xml blob should contain the expected content",
            )

            # re-post with replace = False should now fail
            r = self.client.post(
                url,
                _valid_post_data(),
                format="multipart",
                headers={"X-Api-Key": "valid-token"},
            )
            self.assertEqual(r.status_code, 409)  # conflict
            
            # re-post with replace = True should succeed
            r = self.client.post(
                url,
                _valid_post_data() | {"replace": True},
                format="multipart",
                headers={"X-Api-Key": "valid-token"},
            )
            self.assertEqual(r.status_code, 200)  # conflict
