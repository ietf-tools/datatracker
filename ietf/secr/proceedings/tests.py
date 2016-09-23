import debug                            # pyflakes:ignore
import os
import shutil

from django.conf import settings
from django.core.urlresolvers import reverse

from ietf.group.models import Group
from ietf.meeting.models import Session
from ietf.meeting.test_data import make_meeting_test_data
from ietf.utils.test_data import make_test_data
from ietf.utils.test_utils import TestCase

from ietf.name.models import SessionStatusName
from ietf.meeting.factories import SessionFactory

from ietf.secr.proceedings.proc_utils import create_proceedings

SECR_USER='secretary'

class ProceedingsTestCase(TestCase):
    def test_main(self):
        "Main Test"
        make_test_data()
        url = reverse('proceedings')
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # test chair access
        self.client.logout()
        self.client.login(username="marschairman", password="marschairman+password")
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

class OldProceedingsTestCase(TestCase):
    ''' Ensure coverage of fragments of old proceedings generation until those are removed ''' 
    def setUp(self):
        self.session = SessionFactory(meeting__type_id='ietf')
        self.proceedings_dir = os.path.abspath("tmp-proceedings-dir")

        # This unintuitive bit is a consequence of the surprising implementation of meeting.get_materials_path
        self.saved_agenda_path = settings.AGENDA_PATH
        settings.AGENDA_PATH= self.proceedings_dir

        target_path = self.session.meeting.get_materials_path()
        if not os.path.exists(target_path):
            os.makedirs(target_path)

    def tearDown(self):
        shutil.rmtree(self.proceedings_dir)
        settings.AGENDA_PATH = self.saved_agenda_path

    def test_old_generate(self):
        create_proceedings(self.session.meeting,self.session.group,is_final=True)
