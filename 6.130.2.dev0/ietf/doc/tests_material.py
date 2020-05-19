# Copyright The IETF Trust 2014-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import os
import shutil
import datetime
import io

from pyquery import PyQuery

import debug              # pyflakes:ignore

from django.conf import settings
from django.urls import reverse as urlreverse

from ietf.doc.models import Document, State, DocAlias, NewRevisionDocEvent
from ietf.group.factories import RoleFactory
from ietf.group.models import Group
from ietf.meeting.factories import MeetingFactory
from ietf.meeting.models import Meeting, Session, SessionPresentation, SchedulingEvent
from ietf.name.models import SessionStatusName
from ietf.person.models import Person
from ietf.utils.test_utils import TestCase, login_testing_unauthorized


class GroupMaterialTests(TestCase):
    def setUp(self):
        self.materials_dir = self.tempdir("materials")
        self.slides_dir = os.path.join(self.materials_dir, "slides")
        if not os.path.exists(self.slides_dir):
            os.mkdir(self.slides_dir)
        self.saved_document_path_pattern = settings.DOCUMENT_PATH_PATTERN
        settings.DOCUMENT_PATH_PATTERN = self.materials_dir + "/{doc.type_id}/"

        self.agenda_dir = self.tempdir("agenda")
        self.meeting_slides_dir = os.path.join(self.agenda_dir, "42", "slides")
        if not os.path.exists(self.meeting_slides_dir):
            os.makedirs(self.meeting_slides_dir)
        self.saved_agenda_path = settings.AGENDA_PATH
        settings.AGENDA_PATH = self.agenda_dir

    def tearDown(self):
        settings.DOCUMENT_PATH_PATTERN = self.saved_document_path_pattern
        shutil.rmtree(self.materials_dir)
        settings.AGENDA_PATH = self.saved_agenda_path
        shutil.rmtree(self.agenda_dir)

    def create_slides(self):

        MeetingFactory(type_id='ietf',number='42')
        RoleFactory(name_id='chair',person__user__username='marschairman',group__type_id='wg',group__acronym='mars')
        group = Group.objects.create(type_id="team", acronym="testteam", name="Test Team", state_id="active")

        doc = Document.objects.create(name="slides-testteam-test-file", rev="01", type_id="slides", group=group)
        doc.set_state(State.objects.get(type="slides", slug="active"))
        doc.set_state(State.objects.get(type="reuse_policy", slug="multiple"))
        DocAlias.objects.create(name=doc.name).docs.add(doc)
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
        self.assertTrue(len(q('.has-error')) > 0)

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

        with io.open(os.path.join(self.materials_dir, "slides", doc.name + "-" + doc.rev + ".pdf")) as f:
            self.assertEqual(f.read(), content)

        # check that posting same name is prevented
        test_file.seek(0)

        r = self.client.post(url, dict(title="Test File",
                                       name=doc.name,
                                       state=State.objects.get(type="slides", slug="active").pk,
                                       material=test_file))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(len(q('.has-error')) > 0)
        
    def test_change_state(self):
        doc = self.create_slides()

        url = urlreverse('ietf.doc.views_material.edit_material', kwargs=dict(name=doc.name, action="state"))
        login_testing_unauthorized(self, "secretary", url)

        # post
        r = self.client.post(url, dict(state=State.objects.get(type="slides", slug="deleted").pk))
        self.assertEqual(r.status_code, 302)
        doc = Document.objects.get(name=doc.name)
        self.assertEqual(doc.get_state_slug(), "deleted")

    def test_edit_title(self):
        doc = self.create_slides()

        url = urlreverse('ietf.doc.views_material.edit_material', kwargs=dict(name=doc.name, action="title"))
        login_testing_unauthorized(self, "secretary", url)

        # post
        r = self.client.post(url, dict(title="New title"))
        self.assertEqual(r.status_code, 302)
        doc = Document.objects.get(name=doc.name)
        self.assertEqual(doc.title, "New title")

    def test_revise(self):
        doc = self.create_slides()

        session = Session.objects.create(
            name = "session-42-mars-1",
            meeting = Meeting.objects.get(number='42'),
            group = Group.objects.get(acronym='mars'),
            modified = datetime.datetime.now(),
            type_id='regular',
        )
        SchedulingEvent.objects.create(
            session=session,
            status=SessionStatusName.objects.create(slug='scheduled'),
            by = Person.objects.get(user__username="marschairman"),
        )
        SessionPresentation.objects.create(session=session, document=doc, rev=doc.rev)

        url = urlreverse('ietf.doc.views_material.edit_material', kwargs=dict(name=doc.name, action="revise"))
        login_testing_unauthorized(self, "secretary", url)

        content = "some text"
        test_file = io.StringIO(content)
        test_file.name = "unnamed.txt"

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

        with io.open(os.path.join(doc.get_file_path(), doc.name + "-" + doc.rev + ".txt")) as f:
            self.assertEqual(f.read(), content)

