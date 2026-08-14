# Copyright The IETF Trust 2009-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime
from unittest import mock

from pathlib import Path
from tempfile import TemporaryDirectory

from django.conf import settings
from django.utils import timezone

import debug    # pyflakes:ignore

from ietf.doc.factories import WgDraftFactory, RfcFactory
from ietf.doc.models import Document, RelatedDocument, State, LastCallDocEvent, NewRevisionDocEvent
from ietf.doc.storage_utils import retrieve_str
from ietf.group.factories import GroupFactory
from ietf.name.models import DocRelationshipName
from ietf.idindex.index import all_id_txt, all_id2_txt, id_index_txt
from ietf.idindex.tasks import idindex_update_task, TempFileManager
from ietf.person.factories import PersonFactory, EmailFactory
from ietf.utils.test_utils import TestCase

class IndexTests(TestCase):
    def write_draft_file(self, name, size):
        with (Path(settings.INTERNET_DRAFT_PATH) / name).open('w') as f:
            f.write("a" * size)

    def test_all_id_txt(self):
        draft = WgDraftFactory(states=[('draft','active'),('draft-iesg','lc')])

        txt = all_id_txt()

        self.assertTrue(draft.name + "-" + draft.rev in txt)
        self.assertTrue(draft.get_state("draft-iesg").name in txt)

        # not active in IESG process
        draft.set_state(State.objects.get(type_id="draft-iesg", slug="idexists"))

        txt = all_id_txt()
        self.assertTrue(draft.name + "-" + draft.rev in txt)
        self.assertTrue("Active" in txt)

        # published
        draft.set_state(State.objects.get(type="draft", slug="rfc"))
        rfc = RfcFactory(rfc_number=1234)
        draft.relateddocument_set.create(relationship_id="became_rfc", target=rfc)

        txt = all_id_txt()
        self.assertTrue(draft.name + "-" + draft.rev in txt)
        self.assertTrue("RFC\t1234" in txt)

        # replaced
        draft.set_state(State.objects.get(type="draft", slug="repl"))

        RelatedDocument.objects.create(
            relationship=DocRelationshipName.objects.get(slug="replaces"),
            source=Document.objects.create(
                type_id="draft",
                rev="00",
                name="draft-test-replacement"
            ),
            target=draft
        )

        txt = all_id_txt()
        self.assertTrue(draft.name + "-" + draft.rev in txt)
        self.assertTrue("Replaced replaced by draft-test-replacement" in txt)

    def test_all_id2_txt(self):
        draft = WgDraftFactory(
                    states=[('draft','active'),('draft-iesg','review-e')],
                    ad=PersonFactory(),
                    shepherd=EmailFactory(address='shepherd@example.com',person__name='Draft δραφτυ Shepherd'),
                    group__parent=GroupFactory(type_id='area'),
                    intended_std_level_id = 'ps',
                    authors=[EmailFactory().person]
                )
        def get_fields(content):
            self.assertTrue(draft.name + "-" + draft.rev in content)

            for line in content.splitlines():
                if line.startswith(draft.name + "-" + draft.rev):
                    return line.split("\t")

        NewRevisionDocEvent.objects.create(doc=draft, rev=draft.rev, type="new_revision", by=draft.ad)

        self.write_draft_file("%s-%s.txt" % (draft.name, draft.rev), 5000)
        self.write_draft_file("%s-%s.pdf" % (draft.name, draft.rev), 5000)

        t = get_fields(all_id2_txt())
        self.assertEqual(t[0], draft.name + "-" + draft.rev)
        self.assertEqual(t[1], "-1")
        self.assertEqual(t[2], "Active")
        self.assertEqual(t[3], "Expert Review")
        self.assertEqual(t[4], "")
        self.assertEqual(t[5], "")
        self.assertEqual(t[6], draft.latest_event(type="new_revision").time.strftime("%Y-%m-%d"))
        self.assertEqual(t[7], draft.group.acronym)
        self.assertEqual(t[8], draft.group.parent.acronym)
        self.assertEqual(t[9], str(draft.ad))
        self.assertEqual(t[10], draft.intended_std_level.name)
        self.assertEqual(t[11], "")
        self.assertEqual(t[12], ".pdf,.txt")
        self.assertEqual(t[13], draft.title)
        author = draft.documentauthor_set.order_by("order").get()
        self.assertEqual(t[14], "%s <%s>" % (author.person.plain_name(), author.email.address))
        self.assertEqual(t[15], "%s <%s>" % (draft.shepherd.person.plain_ascii(), draft.shepherd.address))
        self.assertEqual(t[16], "%s <%s>" % (draft.ad.plain_ascii(), draft.ad.email_address()))


        # test RFC
        draft.set_state(State.objects.get(type="draft", slug="rfc"))
        rfc = RfcFactory(rfc_number=1234)
        draft.relateddocument_set.create(relationship_id="became_rfc", target=rfc)
        t = get_fields(all_id2_txt())
        self.assertEqual(t[4], "1234")

        # test Replaced
        draft.set_state(State.objects.get(type="draft", slug="repl"))
        RelatedDocument.objects.create(
            relationship=DocRelationshipName.objects.get(slug="replaces"),
            source=Document.objects.create(
                type_id="draft",
                rev="00", 
                name="draft-test-replacement"
            ),
            target=draft)

        t = get_fields(all_id2_txt())
        self.assertEqual(t[5], "draft-test-replacement")

        # test Last Call
        draft.set_state(State.objects.get(type="draft", slug="active"))
        draft.set_state(State.objects.get(type="draft-iesg", slug="lc"))

        e = LastCallDocEvent.objects.create(doc=draft, rev=draft.rev, type="sent_last_call", expires=timezone.now() + datetime.timedelta(days=14), by=draft.ad)

        t = get_fields(all_id2_txt())
        self.assertEqual(t[11], e.expires.strftime("%Y-%m-%d"))


    def test_id_index_txt(self):
        draft = WgDraftFactory(states=[('draft','active')],abstract='a'*20,authors=[PersonFactory()])

        txt = id_index_txt()

        self.assertTrue(draft.name + "-" + draft.rev in txt)
        self.assertTrue(draft.title in txt)

        self.assertTrue(draft.abstract[:20] not in txt)

        txt = id_index_txt(with_abstracts=True)

        self.assertTrue(draft.abstract[:20] in txt)


class TaskTests(TestCase):
    @mock.patch("ietf.idindex.tasks.all_id_txt")
    @mock.patch("ietf.idindex.tasks.all_id2_txt")
    @mock.patch("ietf.idindex.tasks.id_index_txt")
    @mock.patch.object(TempFileManager, "__enter__")
    def test_idindex_update_task(
        self,
        temp_file_mgr_enter_mock,
        id_index_mock,
        all_id2_mock,
        all_id_mock,
    ):
        # Replace TempFileManager's __enter__() method with one that returns a mock.
        # Pass a spec to the mock so we validate that only actual methods are called.
        mgr_mock = mock.Mock(spec=TempFileManager)
        temp_file_mgr_enter_mock.return_value = mgr_mock
        
        idindex_update_task()

        self.assertEqual(all_id_mock.call_count, 1)
        self.assertEqual(all_id2_mock.call_count, 1)
        self.assertEqual(id_index_mock.call_count, 2)
        self.assertEqual(id_index_mock.call_args_list[0], (tuple(), dict()))
        self.assertEqual(
            id_index_mock.call_args_list[1], 
            (tuple(), {"with_abstracts": True}),
        )
        self.assertEqual(mgr_mock.make_temp_file.call_count, 11)
        self.assertEqual(mgr_mock.move_into_place.call_count, 11)

    def test_temp_file_manager(self):
        with TemporaryDirectory() as temp_dir:
            with TemporaryDirectory() as other_dir:
                temp_path = Path(temp_dir)
                other_path = Path(other_dir)
                with TempFileManager(temp_path) as tfm:
                    path1 = tfm.make_temp_file("yay")
                    path2 = tfm.make_temp_file("boo")  # do not keep this one
                    self.assertTrue(path1.exists())
                    self.assertTrue(path2.exists())
                    dest = temp_path / "yay.txt"
                    tfm.move_into_place(path1, dest, [other_path])
                # make sure things were cleaned up...
                self.assertFalse(path1.exists())  # moved to dest
                self.assertFalse(path2.exists())  # left behind
                # check destination contents and permissions
                self.assertEqual(dest.read_text(), "yay")
                self.assertEqual(
                    retrieve_str("indexes", "yay.txt"),
                    "yay"
                )
                self.assertEqual(dest.stat().st_mode & 0o777, 0o644)
                self.assertTrue(dest.samefile(other_path / "yay.txt"))
