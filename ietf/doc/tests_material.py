# Copyright The IETF Trust 2014-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import os
import shutil
import io

from unittest.mock import call, patch
from pathlib import Path
from pyquery import PyQuery

import debug              # pyflakes:ignore

from django.conf import settings
from django.test import override_settings
from django.urls import reverse as urlreverse
from django.utils import timezone

from ietf.doc.models import Document, State, NewRevisionDocEvent
from ietf.doc.storage_utils import retrieve_str
from ietf.group.factories import RoleFactory
from ietf.group.models import Group
from ietf.meeting.factories import MeetingFactory, SessionFactory, SessionPresentationFactory
from ietf.meeting.models import Meeting, SessionPresentation, SchedulingEvent
from ietf.name.models import SessionStatusName
from ietf.person.models import Person
from ietf.utils.test_utils import TestCase, login_testing_unauthorized


class GroupMaterialTests(TestCase):
    settings_temp_path_overrides = TestCase.settings_temp_path_overrides + ['AGENDA_PATH', 'FTP_DIR']
    def setUp(self):
        super().setUp()
        self.materials_dir = self.tempdir("materials")
        self.slides_dir = Path(self.materials_dir) / "slides"
        if not self.slides_dir.exists():
            self.slides_dir.mkdir()
        self.saved_document_path_pattern = settings.DOCUMENT_PATH_PATTERN
        settings.DOCUMENT_PATH_PATTERN = self.materials_dir + "/{doc.type_id}/"
        self.assertTrue(Path(settings.FTP_DIR).exists())
        ftp_slides_dir = Path(settings.FTP_DIR) / "slides"
        if not ftp_slides_dir.exists():
            ftp_slides_dir.mkdir()

        self.meeting_slides_dir = Path(settings.AGENDA_PATH) / "42" / "slides"
        if not self.meeting_slides_dir.exists():
            self.meeting_slides_dir.mkdir(parents=True)

    def tearDown(self):
        settings.DOCUMENT_PATH_PATTERN = self.saved_document_path_pattern
        shutil.rmtree(self.materials_dir)
        super().tearDown()

    def create_slides(self):

        MeetingFactory(type_id='ietf',number='42')
        RoleFactory(name_id='chair',person__user__username='marschairman',group__type_id='wg',group__acronym='mars')
        group = Group.objects.create(type_id="team", acronym="testteam", name="Test Team", state_id="active")

        doc = Document.objects.create(name="slides-testteam-test-file", rev="01", type_id="slides", group=group)
        doc.set_state(State.objects.get(type="slides", slug="active"))
        doc.set_state(State.objects.get(type="reuse_policy", slug="multiple"))
        NewRevisionDocEvent.objects.create(doc=doc,by=Person.objects.get(name="(System)"),rev='00',type='new_revision',desc='New revision available')
        NewRevisionDocEvent.objects.create(doc=doc,by=Person.objects.get(name="(System)"),rev='01',type='new_revision',desc='New revision available')

        return doc

    def test_choose_material_type(self):
        group = Group.objects.create(type_id="team", acronym="testteam", name="Test Team", state_id="active")

        url = urlreverse('ietf.doc.views_material.choose_material_type', kwargs=dict(acronym=group.acronym))
        login_testing_unauthorized(self, "secretary", url)

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Slides")

        url = urlreverse('ietf.doc.views_material.choose_material_type', kwargs=dict(acronym='mars'))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)

    def test_upload_slides(self):
        group = Group.objects.create(type_id="team", acronym="testteam", name="Test Team", state_id="active")

        url = urlreverse('ietf.doc.views_material.edit_material', kwargs=dict(acronym=group.acronym, doc_type="slides"))
        login_testing_unauthorized(self, "secretary", url)

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        content = "%PDF-1.5\n..."
        test_file = io.StringIO(content)
        test_file.name = "unnamed.pdf"

        # faulty post
        r = self.client.post(url, dict(title="", name="", state="", material=test_file))

        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('.is-invalid')) > 0)

        test_file.seek(0)

        # post
        r = self.client.post(url, dict(title="Test File - with fancy title",
                                       abstract = "Test Abstract",
                                       name="slides-%s-test-file" % group.acronym,
                                       state=State.objects.get(type="slides", slug="active").pk,
                                       material=test_file))
        self.assertEqual(r.status_code, 302)

        doc = Document.objects.get(name="slides-%s-test-file" % group.acronym)
        self.assertEqual(doc.rev, "00")
        self.assertEqual(doc.title, "Test File - with fancy title")
        self.assertEqual(doc.get_state_slug(), "active")

        basename=f"{doc.name}-{doc.rev}.pdf"
        filepath=Path(self.materials_dir) / "slides" / basename
        with filepath.open() as f:
            self.assertEqual(f.read(), content)
        ftp_filepath=Path(settings.FTP_DIR) / "slides" / basename
        with ftp_filepath.open() as f:
            self.assertEqual(f.read(), content)
        # This test is very sloppy wrt the actual file content.
        # Working with/around that for the moment.
        self.assertEqual(retrieve_str("slides", basename), content)

        # check that posting same name is prevented
        test_file.seek(0)

        r = self.client.post(url, dict(title="Test File",
                                       name=doc.name,
                                       state=State.objects.get(type="slides", slug="active").pk,
                                       material=test_file))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(len(q('.is-invalid')) > 0)
        
    def test_change_state(self):
        doc = self.create_slides()

        url = urlreverse('ietf.doc.views_material.edit_material', kwargs=dict(name=doc.name, action="state"))
        login_testing_unauthorized(self, "secretary", url)

        # post
        r = self.client.post(url, dict(state=State.objects.get(type="slides", slug="deleted").pk))
        self.assertEqual(r.status_code, 302)
        doc = Document.objects.get(name=doc.name)
        self.assertEqual(doc.get_state_slug(), "deleted")

    @override_settings(MEETECHO_API_CONFIG="fake settings")
    @patch("ietf.doc.views_material.SlidesManager")
    def test_edit_title(self, mock_slides_manager_cls):
        doc = self.create_slides()

        url = urlreverse('ietf.doc.views_material.edit_material', kwargs=dict(name=doc.name, action="title"))
        login_testing_unauthorized(self, "secretary", url)
        self.assertFalse(mock_slides_manager_cls.called)

        # post
        r = self.client.post(url, dict(title="New title"))
        self.assertEqual(r.status_code, 302)
        doc = Document.objects.get(name=doc.name)
        self.assertEqual(doc.title, "New title")
        self.assertFalse(mock_slides_manager_cls.return_value.send_update.called)

        # assign to a session to see that it now sends updates to Meetecho
        session = SessionPresentationFactory(session__group=doc.group, document=doc).session

        # Grab the title on the slides when the API call was made (to be sure it's not before it was updated)
        titles_sent = []
        mock_slides_manager_cls.return_value.send_update.side_effect = lambda sess: titles_sent.extend(
            list(sess.presentations.values_list("document__title", flat=True))
        ) 

        r = self.client.post(url, dict(title="Newer title"))
        self.assertEqual(r.status_code, 302)
        doc = Document.objects.get(name=doc.name)
        self.assertEqual(doc.title, "Newer title")
        self.assertTrue(mock_slides_manager_cls.called)
        self.assertEqual(mock_slides_manager_cls.call_args, call(api_config="fake settings"))
        self.assertEqual(mock_slides_manager_cls.return_value.send_update.call_count, 1)
        self.assertEqual(
            mock_slides_manager_cls.return_value.send_update.call_args,
            call(session),
        )
        self.assertEqual(titles_sent, ["Newer title"])

    @override_settings(MEETECHO_API_CONFIG="fake settings")
    @patch("ietf.doc.views_material.SlidesManager")
    def test_revise(self, mock_slides_manager_cls):
        doc = self.create_slides()

        session = SessionFactory(
            name = "session-42-mars-1",
            meeting = Meeting.objects.get(number='42'),
            group = Group.objects.get(acronym='mars'),
            modified = timezone.now(),
        )
        SchedulingEvent.objects.create(
            session=session,
            status=SessionStatusName.objects.create(slug='scheduled'),
            by = Person.objects.get(user__username="marschairman"),
        )
        SessionPresentation.objects.create(session=session, document=doc, rev=doc.rev)

        url = urlreverse('ietf.doc.views_material.edit_material', kwargs=dict(name=doc.name, action="revise"))
        login_testing_unauthorized(self, "secretary", url)
        self.assertFalse(mock_slides_manager_cls.called)

        content = "some text"
        test_file = io.StringIO(content)
        test_file.name = "unnamed.txt"

        # Grab the title on the slides when the API call was made (to be sure it's not before it was updated)
        titles_sent = []
        mock_slides_manager_cls.return_value.send_update.side_effect = lambda sess: titles_sent.extend(
            list(sess.presentations.values_list("document__title", flat=True))
        ) 

        # post
        r = self.client.post(url, dict(title="New title",
                                       abstract="New abstract",
                                       state=State.objects.get(type="slides", slug="active").pk,
                                       material=test_file))
        self.assertEqual(r.status_code, 302)
        doc = Document.objects.get(name=doc.name)
        self.assertEqual(doc.rev, "02")
        self.assertEqual(doc.title, "New title")
        self.assertEqual(doc.get_state_slug(), "active")
        self.assertTrue(mock_slides_manager_cls.called)
        self.assertEqual(mock_slides_manager_cls.call_args, call(api_config="fake settings"))
        self.assertEqual(mock_slides_manager_cls.return_value.send_update.call_count, 1)
        self.assertEqual(
            mock_slides_manager_cls.return_value.send_update.call_args,
            call(session),
        )
        self.assertEqual(titles_sent, ["New title"])

        with io.open(os.path.join(doc.get_file_path(), doc.name + "-" + doc.rev + ".txt")) as f:
            self.assertEqual(f.read(), content)
        self.assertEqual(retrieve_str("slides", f"{doc.name}-{doc.rev}.txt"), content)


