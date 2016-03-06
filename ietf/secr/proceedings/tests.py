import debug                            # pyflakes:ignore
import os
import shutil

from StringIO import StringIO

from django.core.urlresolvers import reverse
from django.conf import settings

from ietf.doc.models import Document
from ietf.group.models import Group
from ietf.meeting.models import Meeting, Session
from ietf.meeting.test_data import make_meeting_test_data
from ietf.utils.test_data import make_test_data
from ietf.utils.test_utils import TestCase, unicontent

from ietf.name.models import SessionStatusName
from ietf.secr.utils.meeting import get_proceedings_path

SECR_USER='secretary'

class ProceedingsTestCase(TestCase):
    def test_main(self):
        "Main Test"
        make_test_data()
        url = reverse('proceedings')
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


class RecordingTestCase(TestCase):
    def test_page(self):
        meeting = make_meeting_test_data()
        url = reverse('proceedings_recording', kwargs={'meeting_num':meeting.number})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_post(self):
        meeting = make_meeting_test_data()
        group = Group.objects.get(acronym='mars')
        session = Session.objects.filter(meeting=meeting,group=group).first()
        # explicitly set to scheduled for this test
        status = SessionStatusName.objects.get(slug='sched')
        session.status = status
        session.save()
        url = reverse('proceedings_recording', kwargs={'meeting_num':meeting.number})
        data = dict(group=group.acronym,external_url='http://youtube.com/xyz',session=session.pk)
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.post(url,data,follow=True)
        self.assertEqual(response.status_code, 200)
        self.failUnless(group.acronym in response.content)
        
        # now test edit
        doc = session.materials.filter(type='recording').first()
        external_url = 'http://youtube.com/aaa'
        url = reverse('proceedings_recording_edit', kwargs={'meeting_num':meeting.number,'name':doc.name})
        response = self.client.post(url,dict(external_url=external_url),follow=True)
        self.assertEqual(response.status_code, 200)
        self.failUnless(external_url in response.content)


class BluesheetTestCase(TestCase):
    def setUp(self):
        self.proceedings_dir = os.path.abspath("tmp-proceedings-dir")
        if not os.path.exists(self.proceedings_dir):
            os.mkdir(self.proceedings_dir)
        settings.AGENDA_PATH = self.proceedings_dir
        
        self.interim_listing_dir = os.path.abspath("tmp-interim-listing-dir")
        if not os.path.exists(self.interim_listing_dir):
            os.mkdir(self.interim_listing_dir)
        settings.SECR_INTERIM_LISTING_DIR = self.interim_listing_dir
        
    def tearDown(self):
        shutil.rmtree(self.proceedings_dir)
        shutil.rmtree(self.interim_listing_dir)
        
    def test_upload(self):
        make_test_data()
        meeting = Meeting.objects.filter(type='interim').first()
        group = Group.objects.get(acronym='mars')
        Session.objects.create(meeting=meeting,group=group,requested_by_id=1,status_id='sched',type_id='session')
        url = reverse('proceedings_upload_unified', kwargs={'meeting_num':meeting.number,'acronym':'mars'})
        upfile = StringIO('dummy file')
        upfile.name = "scan1.pdf"
        self.client.login(username="marschairman", password="marschairman+password")
        r = self.client.post(url,
            dict(acronym='mars',meeting_id=meeting.id,material_type='bluesheets',file=upfile),follow=True)
        self.assertEqual(r.status_code, 200)
        doc = Document.objects.get(type='bluesheets')
        self.failUnless(doc.external_url in unicontent(r))
        self.failUnless(os.path.exists(os.path.join(doc.get_file_path(),doc.external_url)))
        # test that proceedings has bluesheets on it
        path = get_proceedings_path(meeting,group)
        self.failUnless(os.path.exists(path))
        with open(path) as f:
            data = f.read()
        self.failUnless(doc.external_url.encode('utf-8') in data)
        
