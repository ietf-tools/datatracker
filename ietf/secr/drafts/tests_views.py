import datetime
import os
import shutil

from StringIO import StringIO
from django.conf import settings
from django.urls import reverse as urlreverse
from django.utils.http import urlencode

import debug                            # pyflakes:ignore

from ietf.doc.expire import expire_draft
from ietf.doc.models import State, Document
from ietf.person.models import Person
from ietf.submit.models import Preapproval
from ietf.submit.tests import submission_file
from ietf.utils.test_utils import TestCase
from ietf.utils.test_data import make_test_data
from ietf.utils.mail import empty_outbox
from ietf.secr.drafts.email import get_email_initial


SECR_USER='secretary'

class SecrDraftsTestCase(TestCase):
    def setUp(self):
        self.saved_internet_draft_path = settings.INTERNET_DRAFT_PATH
        self.repository_dir = self.tempdir('submit-repository')
        settings.INTERNET_DRAFT_PATH = self.repository_dir

        self.saved_internet_draft_archive_dir = settings.INTERNET_DRAFT_ARCHIVE_DIR
        self.archive_dir = self.tempdir('submit-archive')
        settings.INTERNET_DRAFT_ARCHIVE_DIR = self.archive_dir

        self.saved_idsubmit_manual_staging_dir = settings.IDSUBMIT_MANUAL_STAGING_DIR
        self.manual_dir =  self.tempdir('submit-manual')
        settings.IDSUBMIT_MANUAL_STAGING_DIR = self.manual_dir

    def tearDown(self):
        shutil.rmtree(self.repository_dir)
        shutil.rmtree(self.archive_dir)
        shutil.rmtree(self.manual_dir)
        settings.INTERNET_DRAFT_PATH = self.saved_internet_draft_path
        settings.INTERNET_DRAFT_ARCHIVE_DIR = self.saved_internet_draft_archive_dir
        settings.IDSUBMIT_MANUAL_STAGING_DIR = self.saved_idsubmit_manual_staging_dir
        
    def test_abstract(self):
        draft = make_test_data()
        url = urlreverse('ietf.secr.drafts.views.abstract', kwargs={'id':draft.name})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
    def test_add(self):
        draft = make_test_data()
        url = urlreverse('ietf.secr.drafts.views.add')
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
        url = urlreverse('ietf.secr.drafts.views.announce', kwargs={'id':draft.name})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        
    def test_approvals(self):
        make_test_data()
        Preapproval.objects.create(name='draft-dummy',
            by=Person.objects.get(name="(System)"))
        url = urlreverse('ietf.secr.drafts.views.approvals')
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue('draft-dummy' in response.content)
    
    def test_edit(self):
        draft = make_test_data()
        url = urlreverse('ietf.secr.drafts.views.edit', kwargs={'id':draft.name})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
    
    def test_email(self):
        # can't test this directly, test via drafts actions
        pass
    
    def test_get_email_initial(self):
        # Makes sure that a manual posting by the Secretariat of an I-D that is
        # in the RFC Editor Queue will result in notification of the RFC Editor
        draft = make_test_data()
        state = State.objects.get(type='draft-iesg',slug='rfcqueue')
        draft.set_state(state)
        data = get_email_initial(draft,action='revision')
        self.assertTrue('rfc-editor@rfc-editor.org' in data['to'])

    def test_revision(self):
        draft = make_test_data()
        url = urlreverse('ietf.secr.drafts.views.revision', kwargs={'id':draft.name})
        view_url = urlreverse('ietf.secr.drafts.views.view', kwargs={'id':draft.name})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        post_data = {
            'title': draft.title,
            'pages': str(draft.pages),
            'abstract': draft.abstract,
        }
        files = {}
        files['txt'] = submission_file(draft.name, '02', draft.group, 'txt', "test_submission.txt")
        post_data.update(files)
        response = self.client.post(url, post_data)
        self.assertRedirects(response, view_url)
        draft = Document.objects.get(name=draft.name)
        self.assertEqual(draft.rev, '02')

    def test_revision_rfcqueue(self):
        # Makes sure that a manual posting by the Secretariat of an I-D that is
        # in the RFC Editor Queue will result in notification of the RFC Editor
        draft = make_test_data()
        empty_outbox()
        state = State.objects.get(type='draft-iesg',slug='rfcqueue')
        draft.set_state(state)
        url = urlreverse('ietf.secr.drafts.views.revision', kwargs={'id':draft.name})
        self.client.login(username="secretary", password="secretary+password")
        rev = str(int(draft.rev) + 1).zfill(2)
        file = StringIO("This is a test.")
        file.name = "%s-%s.txt" % (draft.name, rev)
        post = {'title':'The Title','pages':'10','txt':file}
        response = self.client.post(url,post,follow=True)
        self.assertEqual(response.status_code, 200)
        # addresses = ','.join([ m['To'] for m in outbox ])
        # self.assertTrue('rfc-editor@rfc-editor.org' in addresses)
        
    def test_makerfc(self):
        draft = make_test_data()
        url = urlreverse('ietf.secr.drafts.views.edit', kwargs={'id':draft.name})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(draft.intended_std_level)
        
    def test_search(self):
        draft = make_test_data()
        url = urlreverse('ietf.secr.drafts.views.search')
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        post = dict(filename='draft',state=1,submit='submit')
        response = self.client.post(url, post)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(draft.name in response.content)
    
    def test_update(self):
        draft = make_test_data()
        path = os.path.join(self.repository_dir, draft.filename_with_rev())
        with open(path, 'w') as file:
            file.write('test')
        expire_draft(draft)
        url = urlreverse('ietf.secr.drafts.views.update', kwargs={'id':draft.name})
        email_url = urlreverse('ietf.secr.drafts.views.email', kwargs={'id':draft.name})
        confirm_url = urlreverse('ietf.secr.drafts.views.confirm', kwargs={'id':draft.name})
        do_action_url = urlreverse('ietf.secr.drafts.views.do_action', kwargs={'id':draft.name})
        view_url = urlreverse('ietf.secr.drafts.views.view', kwargs={'id':draft.name})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        post_data = {
            'title': draft.title,
            'pages': str(draft.pages),
            'abstract': draft.abstract,
        }
        formats = ['txt',]
        files = {}
        for format in formats:
            files[format] = submission_file(draft.name, '02', draft.group, format, "test_submission.%s" % format)
        post_data.update(files)
        response = self.client.post(url, post_data)
        self.assertRedirects(response, email_url + '?action=update&filename=%s-02' % (draft.name))
        post_data = {
            'action': 'update',
            'to': 'john@example.com',
            'cc': 'joe@example.com',
            'subject': 'test',
            'body': 'text',
            'submit': 'Save'
        }
        response = self.client.post(email_url + '?action=update&filename=%s-02' % (draft.name), post_data)
        response = self.client.post(confirm_url, post_data)
        response = self.client.post(do_action_url, post_data)
        self.assertRedirects(response, view_url)
        draft = Document.objects.get(name=draft.name)
        expires = datetime.datetime.now() + datetime.timedelta(settings.INTERNET_DRAFT_DAYS_TO_EXPIRE)
        self.assertTrue(draft.get_state_slug('draft') == 'active')
        self.assertEqual(draft.rev, '02')
        self.assertEqual(draft.expires.replace(second=0,microsecond=0), expires.replace(second=0,microsecond=0))

    def test_view(self):
        draft = make_test_data()
        url = urlreverse('ietf.secr.drafts.views.view', kwargs={'id':draft.name})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_author_delete(self):
        draft = make_test_data()
        author = draft.documentauthor_set.first()
        id = author.id
        url = urlreverse('ietf.secr.drafts.views.author_delete', kwargs={'id':draft.name, 'oid':id})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        redirect_url = urlreverse('ietf.secr.drafts.views.authors', kwargs={'id':draft.name})
        response = self.client.post(url, {'post':'yes'})
        self.assertRedirects(response, redirect_url)
        self.assertFalse(draft.documentauthor_set.filter(id=id))

    def test_resurrect(self):
        draft = make_test_data()
        path = os.path.join(self.repository_dir, draft.filename_with_rev())
        with open(path, 'w') as file:
            file.write('test')
        expire_draft(draft)
        email_url = urlreverse('ietf.secr.drafts.views.email', kwargs={'id':draft.name}) + "?action=resurrect"
        confirm_url = urlreverse('ietf.secr.drafts.views.confirm', kwargs={'id':draft.name})
        do_action_url = urlreverse('ietf.secr.drafts.views.do_action', kwargs={'id':draft.name})
        view_url = urlreverse('ietf.secr.drafts.views.view', kwargs={'id':draft.name})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(email_url)
        self.assertEqual(response.status_code, 200)
        post_data = {
            'action': 'resurrect',
            'to': 'john@example.com',
            'cc': 'joe@example.com',
            'subject': 'test',
            'body': 'draft resurrected',
            'submit': 'Save'
        }
        response = self.client.post(email_url, post_data)
        response = self.client.post(confirm_url, post_data)
        response = self.client.post(do_action_url, post_data)
        self.assertRedirects(response, view_url)
        draft = Document.objects.get(name=draft.name)
        self.assertTrue(draft.get_state_slug('draft') == 'active')

    def test_extend(self):
        draft = make_test_data()
        url = urlreverse('ietf.secr.drafts.views.extend', kwargs={'id':draft.name})
        email_url = urlreverse('ietf.secr.drafts.views.email', kwargs={'id':draft.name})
        confirm_url = urlreverse('ietf.secr.drafts.views.confirm', kwargs={'id':draft.name})
        do_action_url = urlreverse('ietf.secr.drafts.views.do_action', kwargs={'id':draft.name})
        view_url = urlreverse('ietf.secr.drafts.views.view', kwargs={'id':draft.name})
        expiration = datetime.datetime.today() + datetime.timedelta(days=180)
        expiration = expiration.replace(hour=0,minute=0,second=0,microsecond=0)
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        get_data = {            
            'action': 'extend',
            'expiration_date': expiration.strftime('%Y-%m-%d'),
        }
        post_data = {
            'action': 'extend',
            'expiration_date': expiration.strftime('%Y-%m-%d'),
            'to': 'john@example.com',
            'cc': 'joe@example.com',
            'subject': 'test',
            'body': 'draft resurrected',
            'submit': 'Save'
        }
        response = self.client.get(email_url + '?' + urlencode(get_data)) 
        self.assertEqual(response.status_code, 200)
        response = self.client.post(confirm_url, post_data)
        response = self.client.post(do_action_url, post_data)
        self.assertRedirects(response, view_url)
        draft = Document.objects.get(name=draft.name)
        self.assertTrue(draft.expires == expiration)

    def test_withdraw(self):
        draft = make_test_data()
        url = urlreverse('ietf.secr.drafts.views.withdraw', kwargs={'id':draft.name})
        email_url = urlreverse('ietf.secr.drafts.views.email', kwargs={'id':draft.name})
        confirm_url = urlreverse('ietf.secr.drafts.views.confirm', kwargs={'id':draft.name})
        do_action_url = urlreverse('ietf.secr.drafts.views.do_action', kwargs={'id':draft.name})
        view_url = urlreverse('ietf.secr.drafts.views.view', kwargs={'id':draft.name})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        get_data = {            
            'action': 'withdraw',
            'withdraw_type': 'ietf',
        }
        post_data = {
            'action': 'withdraw',
            'withdraw_type': 'ietf',
            'to': 'john@example.com',
            'cc': 'joe@example.com',
            'subject': 'test',
            'body': 'draft resurrected',
            'submit': 'Save'
        }
        response = self.client.get(email_url + '?' + urlencode(get_data)) 
        self.assertEqual(response.status_code, 200)
        response = self.client.post(confirm_url, post_data)
        response = self.client.post(do_action_url, post_data)
        self.assertRedirects(response, view_url)
        draft = Document.objects.get(name=draft.name)
        self.assertTrue(draft.get_state_slug('draft') == 'ietf-rm')

    def test_replace(self):
        draft = make_test_data()
        other_draft = Document.objects.filter(type='draft').exclude(name=draft.name).first()
        url = urlreverse('ietf.secr.drafts.views.replace', kwargs={'id':draft.name})
        email_url = urlreverse('ietf.secr.drafts.views.email', kwargs={'id':draft.name})
        confirm_url = urlreverse('ietf.secr.drafts.views.confirm', kwargs={'id':draft.name})
        do_action_url = urlreverse('ietf.secr.drafts.views.do_action', kwargs={'id':draft.name})
        view_url = urlreverse('ietf.secr.drafts.views.view', kwargs={'id':draft.name})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        get_data = {
            'action': 'replace',
            'replaced': draft.name,
            'replaced_by': other_draft.name,
        }
        post_data = {
            'action': 'replace',
            'replaced': draft.name,
            'replaced_by': other_draft.name,
            'to': 'john@example.com',
            'cc': 'joe@example.com',
            'subject': 'test',
            'body': 'draft resurrected',
            'submit': 'Save'
        }
        response = self.client.get(email_url + '?' + urlencode(get_data)) 
        self.assertEqual(response.status_code, 200)
        response = self.client.post(confirm_url, post_data)
        response = self.client.post(do_action_url, post_data)
        self.assertRedirects(response, view_url)
        draft = Document.objects.get(name=draft.name)
        self.assertTrue(draft.get_state_slug('draft') == 'repl')

