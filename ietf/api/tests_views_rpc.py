# Copyright The IETF Trust 2025, All Rights Reserved
import datetime
from io import StringIO
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.db.models import Max
from django.db.models.functions import Coalesce
from django.test.utils import override_settings
from django.urls import reverse as urlreverse
import mock
from django.utils import timezone

from ietf.api.views_rpc import DestinationHelperMixin
from ietf.blobdb.models import Blob
from ietf.doc.factories import (
    IndividualDraftFactory,
    RfcFactory,
    WgDraftFactory,
    WgRfcFactory,
)
from ietf.doc.models import RelatedDocument, Document
from ietf.group.factories import RoleFactory, GroupFactory
from ietf.person.factories import PersonFactory
from ietf.sync.rfcindex import rfcindex_is_dirty
from ietf.utils.models import DirtyBits
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
    @mock.patch("ietf.doc.tasks.signal_update_rfc_metadata_task.delay")
    def test_notify_rfc_published(self, mock_task_delay):
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
        updates = RfcFactory.create_batch(2)
        obsoletes = RfcFactory.create_batch(2)
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
            "obsoletes": [o.rfc_number for o in obsoletes],
            "updates": [o.rfc_number for o in updates],
            "subseries": [],
        }
        r = self.client.post(url, data=post_data, format="json")
        self.assertEqual(r.status_code, 403)

        # Put a file in the way. Post should fail because files exists
        rfc_path = Path(settings.RFC_PATH)
        (rfc_path / "prerelease").mkdir()
        file_in_the_way = rfc_path / f"rfc{unused_rfc_number}.txt"
        file_in_the_way.touch()
        r = self.client.post(
            url, data=post_data, format="json", headers={"X-Api-Key": "valid-token"}
        )
        self.assertEqual(r.status_code, 409)  # conflict
        file_in_the_way.unlink()

        # Put a blob in the way. Post should fail because replace = False
        blob_in_the_way = Blob.objects.create(
            bucket="rfc", name=f"txt/rfc{unused_rfc_number}.txt", content=b""
        )
        r = self.client.post(
            url, data=post_data, format="json", headers={"X-Api-Key": "valid-token"}
        )
        self.assertEqual(r.status_code, 409)  # conflict
        blob_in_the_way.delete()

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
            [
                {
                    "titlepage_name": ra.titlepage_name,
                    "is_editor": ra.is_editor,
                    "person": ra.person,
                    "email": ra.email,
                    "affiliation": ra.affiliation,
                    "country": ra.country,
                }
                for ra in rfc.rfcauthor_set.all()
            ],
            [
                {
                    "titlepage_name": f"titlepage {author.name}",
                    "is_editor": False,
                    "person": author,
                    "email": author.email(),
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
        self.assertEqual(set(rfc.related_that_doc("obs")), set([o for o in obsoletes]))
        self.assertEqual(
            set(rfc.related_that_doc("updates")), set([o for o in updates])
        )
        self.assertEqual(rfc.part_of(), [])
        self.assertEqual(draft.get_state().slug, "rfc")
        # todo test non-empty relationships
        # todo test references (when updating that is part of the handling)

        self.assertTrue(mock_task_delay.called)
        mock_args, mock_kwargs = mock_task_delay.call_args
        self.assertIn("rfc_number_list", mock_kwargs)
        expected_rfc_number_list = [rfc.rfc_number]
        expected_rfc_number_list.extend([d.rfc_number for d in updates + obsoletes])
        expected_rfc_number_list = sorted(set(expected_rfc_number_list))
        self.assertEqual(mock_kwargs["rfc_number_list"], expected_rfc_number_list)

    @override_settings(APP_API_TOKENS={"ietf.api.views_rpc": ["valid-token"]})
    @mock.patch("ietf.api.views_rpc.rebuild_reference_relations_task")
    @mock.patch("ietf.api.views_rpc.update_rfc_searchindex_task")
    @mock.patch("ietf.api.views_rpc.trigger_red_precomputer_task")
    def test_upload_rfc_files(
        self,
        mock_trigger_red_task,
        mock_update_searchindex_task,
        mock_rebuild_relations,
    ):
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
        updates = RfcFactory.create_batch(2)
        obsoletes = RfcFactory.create_batch(2)

        rfc = WgRfcFactory()
        for r in obsoletes:
            rfc.relateddocument_set.create(relationship_id="obs", target=r)
        for r in updates:
            rfc.relateddocument_set.create(relationship_id="updates", target=r)
        assert isinstance(rfc, Document), "WgRfcFactory should generate a Document"
        rfc_path = Path(settings.RFC_PATH)
        (rfc_path / "prerelease").mkdir()
        content = StringIO("XML content\n")
        content.name = "myrfc.xml"

        # no api key
        r = self.client.post(url, _valid_post_data(), format="multipart")
        self.assertEqual(r.status_code, 403)
        self.assertFalse(mock_update_searchindex_task.delay.called)

        # invalid RFC
        r = self.client.post(
            url,
            _valid_post_data() | {"rfc": rfc.rfc_number + 10},
            format="multipart",
            headers={"X-Api-Key": "valid-token"},
        )
        self.assertEqual(r.status_code, 400)
        self.assertFalse(mock_update_searchindex_task.delay.called)

        # empty files
        r = self.client.post(
            url,
            _valid_post_data()
            | {
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
        self.assertFalse(mock_update_searchindex_task.delay.called)

        # bad file type
        r = self.client.post(
            url,
            _valid_post_data()
            | {
                "contents": [
                    ContentFile(b"Some content", "myfile.jpg"),
                ]
            },
            format="multipart",
            headers={"X-Api-Key": "valid-token"},
        )
        self.assertEqual(r.status_code, 400)
        self.assertFalse(mock_update_searchindex_task.delay.called)

        # Put a file in the way. Post should fail because replace = False
        file_in_the_way = rfc_path / f"{rfc.name}.txt"
        file_in_the_way.touch()
        r = self.client.post(
            url,
            _valid_post_data(),
            format="multipart",
            headers={"X-Api-Key": "valid-token"},
        )
        self.assertEqual(r.status_code, 409)  # conflict
        self.assertFalse(mock_update_searchindex_task.delay.called)
        file_in_the_way.unlink()

        # Put a blob in the way. Post should fail because replace = False
        blob_in_the_way = Blob.objects.create(
            bucket="rfc", name=f"txt/{rfc.name}.txt", content=b""
        )
        r = self.client.post(
            url,
            _valid_post_data(),
            format="multipart",
            headers={"X-Api-Key": "valid-token"},
        )
        self.assertEqual(r.status_code, 409)  # conflict
        self.assertFalse(mock_update_searchindex_task.delay.called)
        blob_in_the_way.delete()

        # valid post
        mock_trigger_red_task.delay.reset_mock()
        r = self.client.post(
            url,
            _valid_post_data(),
            format="multipart",
            headers={"X-Api-Key": "valid-token"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            mock_update_searchindex_task.delay.call_args,
            mock.call(rfc.rfc_number),
        )
        for extension in ["xml", "txt", "html", "pdf", "json"]:
            filename = f"{rfc.name}.{extension}"
            self.assertEqual(
                (rfc_path / filename).read_text(),
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
        notprepped_fn = f"{rfc.name}.notprepped.xml"
        self.assertEqual(
            (rfc_path / "prerelease" / notprepped_fn).read_text(),
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
        # Confirm that the red precomputer was triggered correctly
        self.assertTrue(mock_trigger_red_task.delay.called)
        _, mock_kwargs = mock_trigger_red_task.delay.call_args
        self.assertIn("rfc_number_list", mock_kwargs)
        expected_rfc_number_list = [rfc.rfc_number]
        expected_rfc_number_list.extend([d.rfc_number for d in updates + obsoletes])
        expected_rfc_number_list = sorted(set(expected_rfc_number_list))
        self.assertEqual(mock_kwargs["rfc_number_list"], expected_rfc_number_list)
        # Confirm that the search index update task was called correctly
        self.assertTrue(mock_update_searchindex_task.delay.called)
        # Confirm reference relations rebuild task was called correctly
        self.assertTrue(mock_rebuild_relations.delay.called)
        _, mock_kwargs = mock_rebuild_relations.delay.call_args
        self.assertIn("doc_names", mock_kwargs)
        self.assertEqual(mock_kwargs["doc_names"], [rfc.name])

        # re-post with replace = False should now fail
        mock_update_searchindex_task.reset_mock()
        r = self.client.post(
            url,
            _valid_post_data(),
            format="multipart",
            headers={"X-Api-Key": "valid-token"},
        )
        self.assertEqual(r.status_code, 409)  # conflict
        self.assertFalse(mock_update_searchindex_task.delay.called)

        # re-post with replace = True should succeed
        r = self.client.post(
            url,
            _valid_post_data() | {"replace": True},
            format="multipart",
            headers={"X-Api-Key": "valid-token"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(mock_update_searchindex_task.delay.called)
        self.assertEqual(
            mock_update_searchindex_task.delay.call_args,
            mock.call(rfc.rfc_number),
        )

    @override_settings(APP_API_TOKENS={"ietf.api.views_rpc": ["valid-token"]})
    def test_refresh_rfc_index(self):
        DirtyBits.objects.create(
            slug=DirtyBits.Slugs.RFCINDEX,
            dirty_time=timezone.now() - datetime.timedelta(days=1),
            processed_time=timezone.now() - datetime.timedelta(hours=12),
        )
        self.assertFalse(rfcindex_is_dirty())
        url = urlreverse("ietf.api.purple_api.refresh_rfc_index")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
        response = self.client.get(url, headers={"X-Api-Key": "invalid-token"})
        self.assertEqual(response.status_code, 403)
        response = self.client.get(url, headers={"X-Api-Key": "valid-token"})
        self.assertEqual(response.status_code, 405)
        self.assertFalse(rfcindex_is_dirty())
        response = self.client.post(url, headers={"X-Api-Key": "valid-token"})
        self.assertEqual(response.status_code, 202)
        self.assertTrue(rfcindex_is_dirty())

    def test_destination_helper_mixin_fs_destination(self):
        file_list = [f"rfc31337.{ext}" for ext in ["txt", "xml", "pdf", "html"]]
        for filename in file_list:
            self.assertEqual(
                DestinationHelperMixin().fs_destination(filename),
                Path(f"{settings.RFC_PATH}") / filename,
            )
        # noteprepped xml
        filename = "rfc31337.notprepped.xml"
        self.assertEqual(
            DestinationHelperMixin().fs_destination(filename),
            Path(f"{settings.RFC_PATH}/prerelease") / filename,
        )

    def test_destination_helper_mixin_blob_destination(self):
        file_list = {ext: f"rfc31337.{ext}" for ext in ["txt", "xml", "pdf", "html"]}
        for file_type, filename in file_list.items():
            self.assertEqual(
                DestinationHelperMixin().blob_destination(filename),
                f"{file_type}/{filename}",
            )
        # noteprepped xml
        filename = "rfc31337.notprepped.xml"
        self.assertEqual(
            DestinationHelperMixin().blob_destination(filename),
            f"notprepped/{filename}",
        )

    @override_settings(APP_API_TOKENS={"ietf.api.views_rpc": ["valid-token"]})
    @mock.patch("ietf.api.views_rpc.process_rpc_queue_task.delay")
    def test_process_rpc_queue(self, mock_task_delay):
        url = urlreverse("ietf.api.purple_api.process_rpc_queue")
        queue_entries = [
            {
                "id": 9850,
                "name": "draft-ietf-netmod-system-config",
                "title": "System-defined Configuration",
                "draft_url": "http://localhost:8000/doc/draft-ietf-netmod-system-config-20",
                "disposition": "in_progress",
                "external_deadline": None,
                "labels": [],
                "cluster": None,
                "assignment_set": [
                    {
                        "id": 434,
                        "rfc_to_be": 9850,
                        "role": "first_editor",
                        "state": "in_progress",
                    }
                ],
                "actionholder_set": [],
                "pending_activities": [],
                "rfc_number": None,
                "pages": 33,
                "enqueued_at": "2026-01-26T12:00:00Z",
                "final_approval": [],
                "iana_status": {
                    "slug": "completed",
                    "name": "completed",
                    "desc": "IANA has completed actions in draft",
                },
                "blocking_reasons": [],
                "authors": [{"titlepage_name": "Q. Ma", "is_editor": True}],
                "approval_log_message": [],
                "stream": "ietf",
                "group": "netmod",
                "group_name": "Network Modeling",
                "std_level": "ps",
                "references": [],
                "rev": "20",
            }
        ]
        queue_data = {"data": queue_entries}

        # no credentials
        response = self.client.post(
            url, data=queue_data, content_type="application/json"
        )
        self.assertEqual(response.status_code, 403)
        mock_task_delay.assert_not_called()

        # invalid token
        response = self.client.post(
            url,
            data=queue_data,
            content_type="application/json",
            headers={"X-Api-Key": "invalid-token"},
        )
        self.assertEqual(response.status_code, 403)
        mock_task_delay.assert_not_called()

        # valid token, wrong method
        response = self.client.get(url, headers={"X-Api-Key": "valid-token"})
        self.assertEqual(response.status_code, 405)
        mock_task_delay.assert_not_called()

        # valid token, missing "data" field
        response = self.client.post(
            url,
            data={},
            content_type="application/json",
            headers={"X-Api-Key": "valid-token"},
        )
        self.assertEqual(response.status_code, 400)
        mock_task_delay.assert_not_called()

        # valid token, POST with data
        response = self.client.post(
            url,
            data=queue_data,
            content_type="application/json",
            headers={"X-Api-Key": "valid-token"},
        )
        self.assertEqual(response.status_code, 202)
        mock_task_delay.assert_called_once_with(queue_entries)
