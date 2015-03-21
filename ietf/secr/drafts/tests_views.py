import os
import shutil

from StringIO import StringIO
from django.conf import settings
from django.core.urlresolvers import reverse as urlreverse

from ietf.utils.test_utils import TestCase
from ietf.person.models import Person
from ietf.submit.models import Preapproval
from ietf.utils.test_data import make_test_data

#from pyquery import PyQuery

SECR_USER='secretary'

class MainTestCase(TestCase):
    def setUp(self):
        self.repository_dir = os.path.abspath("tmp-submit-repository-dir")
        os.mkdir(self.repository_dir)
        settings.INTERNET_DRAFT_PATH = self.repository_dir

        self.archive_dir = os.path.abspath("tmp-submit-archive-dir")
        os.mkdir(self.archive_dir)
        settings.INTERNET_DRAFT_ARCHIVE_DIR = self.archive_dir

    def tearDown(self):
        shutil.rmtree(self.repository_dir)
        shutil.rmtree(self.archive_dir)
        
    def test_abstract(self):
        draft = make_test_data()
        url = urlreverse('drafts_abstract', kwargs={'id':draft.name})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
    def test_add(self):
        draft = make_test_data()
        url = urlreverse('drafts_add')
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        # dummy upload file
        txt_file = StringIO('This is a simple text file.')
        txt_file.name = "draft-dummy-00.txt"
        
        post = dict(title='A test draft',
            group=draft.group.pk,
            start_date='2015-01-01',
            pages='10',
            txt=txt_file
        )
        response = self.client.post(url,post)
        self.assertEqual(response.status_code, 302)
        
    def test_announce(self):
        draft = make_test_data()
        url = urlreverse('drafts_announce', kwargs={'id':draft.name})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        
    def test_approvals(self):
        make_test_data()
        Preapproval.objects.create(name='draft-dummy',
            by=Person.objects.get(name="(System)"))
        url = urlreverse('drafts_approvals')
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue('draft-dummy' in response.content)
    
    def test_edit(self):
        draft = make_test_data()
        url = urlreverse('drafts_edit', kwargs={'id':draft.name})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
    
    def test_email(self):
        # can't test this directly, test via drafts actions
        pass
    
    def test_makerfc(self):
        draft = make_test_data()
        url = urlreverse('drafts_edit', kwargs={'id':draft.name})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(draft.intended_std_level)
        
    def test_search(self):
        draft = make_test_data()
        url = urlreverse('drafts')
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        post = dict(filename='draft',state=1,submit='submit')
        response = self.client.post(url,post)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(draft.name in response.content)
    
    def test_update(self):
        draft = make_test_data()
        url = urlreverse('drafts_update', kwargs={'id':draft.name})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
    def test_view(self):
        draft = make_test_data()
        url = urlreverse('drafts_view', kwargs={'id':draft.name})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

