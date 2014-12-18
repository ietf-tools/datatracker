# Copyright The IETF Trust 2011, All Rights Reserved

import os, shutil
from StringIO import StringIO
from pyquery import PyQuery

from django.conf import settings
from django.core.urlresolvers import reverse as urlreverse

from ietf.doc.models import Document, State, DocAlias
from ietf.group.models import Group
from ietf.utils.test_utils import TestCase, login_testing_unauthorized

class GroupMaterialTests(TestCase):
    def setUp(self):
        self.materials_dir = os.path.abspath("tmp-document-dir")
        os.mkdir(self.materials_dir)
        os.mkdir(os.path.join(self.materials_dir, "slides"))
        settings.DOCUMENT_PATH_PATTERN = self.materials_dir + "/{doc.type_id}/"

    def tearDown(self):
        shutil.rmtree(self.materials_dir)

    def create_slides(self):
        group = Group.objects.create(type_id="team", acronym="testteam", name="Test Team", state_id="active")

        doc = Document.objects.create(name="slides-testteam-test-file", rev="00", type_id="slides", group=group)
        doc.set_state(State.objects.get(type="slides", slug="active"))
        DocAlias.objects.create(name=doc.name, document=doc)

        return doc

    def test_choose_material_type(self):
        group = Group.objects.create(type_id="team", acronym="testteam", name="Test Team", state_id="active")

        url = urlreverse('ietf.doc.views_material.choose_material_type', kwargs=dict(acronym=group.acronym))
        login_testing_unauthorized(self, "secretary", url)

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue("Slides" in r.content)

    def test_upload_slides(self):
        group = Group.objects.create(type_id="team", acronym="testteam", name="Test Team", state_id="active")

        url = urlreverse('group_new_material', kwargs=dict(acronym=group.acronym, doc_type="slides"))
        login_testing_unauthorized(self, "secretary", url)

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        content = "%PDF-1.5\n..."
        test_file = StringIO(content)
        test_file.name = "unnamed.pdf"

        # faulty post
        r = self.client.post(url, dict(title="", name="", state="", material=test_file))

        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form ul.errorlist')) > 0)

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

        with open(os.path.join(self.materials_dir, "slides", doc.name + "-" + doc.rev + ".pdf")) as f:
            self.assertEqual(f.read(), content)

        # check that posting same name is prevented
        test_file.seek(0)

        r = self.client.post(url, dict(title="Test File",
                                       name=doc.name,
                                       state=State.objects.get(type="slides", slug="active").pk,
                                       material=test_file))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(len(q('form ul.errorlist')) > 0)
        
    def test_change_state(self):
        doc = self.create_slides()

        url = urlreverse('material_edit', kwargs=dict(name=doc.name, action="state"))
        login_testing_unauthorized(self, "secretary", url)

        # post
        r = self.client.post(url, dict(state=State.objects.get(type="slides", slug="deleted").pk))
        self.assertEqual(r.status_code, 302)
        doc = Document.objects.get(name=doc.name)
        self.assertEqual(doc.get_state_slug(), "deleted")

    def test_edit_title(self):
        doc = self.create_slides()

        url = urlreverse('material_edit', kwargs=dict(name=doc.name, action="title"))
        login_testing_unauthorized(self, "secretary", url)

        # post
        r = self.client.post(url, dict(title="New title"))
        self.assertEqual(r.status_code, 302)
        doc = Document.objects.get(name=doc.name)
        self.assertEqual(doc.title, "New title")

    def test_revise(self):
        doc = self.create_slides()

        url = urlreverse('material_edit', kwargs=dict(name=doc.name, action="revise"))
        login_testing_unauthorized(self, "secretary", url)

        content = "some text"
        test_file = StringIO(content)
        test_file.name = "unnamed.txt"

        # post
        r = self.client.post(url, dict(title="New title",
                                       abstract="New abstract",
                                       state=State.objects.get(type="slides", slug="active").pk,
                                       material=test_file))
        self.assertEqual(r.status_code, 302)
        doc = Document.objects.get(name=doc.name)
        self.assertEqual(doc.rev, "01")
        self.assertEqual(doc.title, "New title")
        self.assertEqual(doc.get_state_slug(), "active")

        with open(os.path.join(self.materials_dir, "slides", doc.name + "-" + doc.rev + ".txt")) as f:
            self.assertEqual(f.read(), content)

