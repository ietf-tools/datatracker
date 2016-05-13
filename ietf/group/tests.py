import os
from unittest import skipIf

from pyquery import PyQuery

from django.conf import settings
from django.core.urlresolvers import reverse as urlreverse
from django.db.models import Q
from django.test import Client

import debug                             # pyflakes:ignore

from ietf.group.models import Role, Group
from ietf.group.utils import get_group_role_emails, get_child_group_role_emails, get_group_ad_emails
from ietf.group.factories import GroupFactory
from ietf.utils.test_data import make_test_data
from ietf.utils.test_utils import login_testing_unauthorized, TestCase, unicontent

if   getattr(settings,'SKIP_DOT_TO_PDF', False):
    skip_dot_to_pdf = True
    skip_message = "settings.SKIP_DOT_TO_PDF = %s" % skip_dot_to_pdf
elif (  os.path.exists(settings.DOT_BINARY) and
        os.path.exists(settings.UNFLATTEN_BINARY)):
    skip_dot_to_pdf = False
    skip_message = ""
else:
    skip_dot_to_pdf = True
    skip_message = ("One or more of the binaries for dot, unflatten and ps2pdf weren't found "
                    "in the locations indicated in settings.py.")

class StreamTests(TestCase):
    def test_streams(self):
        make_test_data()
        r = self.client.get(urlreverse("ietf.group.views_stream.streams"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue("Independent Submission Editor" in unicontent(r))

    def test_stream_documents(self):
        draft = make_test_data()
        draft.stream_id = "iab"
        draft.save()

        r = self.client.get(urlreverse("ietf.group.views_stream.stream_documents", kwargs=dict(acronym="iab")))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(draft.name in unicontent(r))

    def test_stream_edit(self):
        make_test_data()

        stream_acronym = "ietf"

        url = urlreverse("ietf.group.views_stream.stream_edit", kwargs=dict(acronym=stream_acronym))
        login_testing_unauthorized(self, "secretary", url)

        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        r = self.client.post(url, dict(delegates="ad2@ietf.org"))
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Role.objects.filter(name="delegate", group__acronym=stream_acronym, email__address="ad2@ietf.org"))


@skipIf(skip_dot_to_pdf, skip_message)
class GroupDocDependencyGraphTests(TestCase):

    def test_group_document_dependency_dotfile(self):
        make_test_data()
        for group in Group.objects.filter(Q(type="wg") | Q(type="rg")):
            client = Client(Accept='text/plain')
            for url in [ urlreverse("ietf.group.views.dependencies",kwargs=dict(acronym=group.acronym,output_type="dot")),
                         urlreverse("ietf.group.views.dependencies",kwargs=dict(acronym=group.acronym,group_type=group.type_id,output_type="dot")),
                       ]:
                r = client.get(url)
                self.assertTrue(r.status_code == 200, "Failed to receive "
                    "a dot dependency graph for group: %s"%group.acronym)
                self.assertGreater(len(r.content), 0, "Dot dependency graph for group "
                    "%s has no content"%group.acronym)

    def test_group_document_dependency_pdffile(self):
        make_test_data()
        for group in Group.objects.filter(Q(type="wg") | Q(type="rg")):
            client = Client(Accept='application/pdf')
            for url in [ urlreverse("ietf.group.views.dependencies",kwargs=dict(acronym=group.acronym,output_type="pdf")),
                         urlreverse("ietf.group.views.dependencies",kwargs=dict(acronym=group.acronym,group_type=group.type_id,output_type="pdf")),
                       ]:
                r = client.get(url)
                self.assertTrue(r.status_code == 200, "Failed to receive "
                    "a pdf dependency graph for group: %s"%group.acronym)
                self.assertGreater(len(r.content), 0, "Pdf dependency graph for group "
                    "%s has no content"%group.acronym)

    def test_group_document_dependency_svgfile(self):
        make_test_data()
        for group in Group.objects.filter(Q(type="wg") | Q(type="rg")):
            client = Client(Accept='image/svg+xml')
            for url in [ urlreverse("ietf.group.views.dependencies",kwargs=dict(acronym=group.acronym,output_type="svg")),
                         urlreverse("ietf.group.views.dependencies",kwargs=dict(acronym=group.acronym,group_type=group.type_id,output_type="svg")),
                       ]:
                r = client.get(url)
                self.assertTrue(r.status_code == 200, "Failed to receive "
                    "a svg dependency graph for group: %s"%group.acronym)
                self.assertGreater(len(r.content), 0, "svg dependency graph for group "
                    "%s has no content"%group.acronym)
            

class GroupRoleEmailTests(TestCase):

    def test_group_role_emails(self):
        make_test_data()
        wgs = Group.objects.filter(type='wg')
        for wg in wgs:
            chair_emails = get_group_role_emails(wg, ['chair'])
            secr_emails  = get_group_role_emails(wg, ['secr'])
            self.assertIn("chairman", list(chair_emails)[0])
            self.assertIn("secretary", list(secr_emails)[0])
            both_emails  = get_group_role_emails(wg, ['chair', 'secr'])
            self.assertEqual(secr_emails | chair_emails, both_emails)

    def test_child_group_role_emails(self):
        make_test_data()
        areas = Group.objects.filter(type='area')
        for area in areas:
            emails = get_child_group_role_emails(area, ['chair', 'secr'])
            self.assertGreater(len(emails), 0)
            for item in emails:
                self.assertIn('@', item)

    def test_group_ad_emails(self):
        make_test_data()
        wgs = Group.objects.filter(type='wg')
        for wg in wgs:
            emails = get_group_ad_emails(wg)
            self.assertGreater(len(emails), 0)
            for item in emails:
                self.assertIn('@', item)

class GroupDerivedArchiveTests(TestCase):

    def test_group_with_mailarch(self):
        group = GroupFactory()
        group.list_archive = 'https://mailarchive.ietf.org/arch/browse/%s/'%group.acronym
        group.save()
        url = urlreverse("ietf.group.views.derived_archives",kwargs=dict(acronym=group.acronym))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(url, q('.nav-tabs .active a')[0].attrib['href'])
        self.assertTrue(group.list_archive in unicontent(r))
        self.assertTrue('web/%s/current'%group.acronym in unicontent(r))

    def test_group_without_mailarch(self):
        group = GroupFactory()
        group.list_archive = 'https://alienarchive.example.com'
        group.save()
        url = urlreverse("ietf.group.views.derived_archives",kwargs=dict(acronym=group.acronym))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertFalse(q('.nav-tabs .active'))
        self.assertTrue(group.list_archive in unicontent(r))
