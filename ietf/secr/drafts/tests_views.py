# Copyright The IETF Trust 2013-2019, All Rights Reserved
# -*- coding: utf-8 -*-


from __future__ import absolute_import, print_function, unicode_literals

import datetime
import io
import os
import shutil
from collections import OrderedDict

from django.conf import settings
from django.urls import reverse as urlreverse
from django.utils.http import urlencode
from pyquery import PyQuery

import debug                            # pyflakes:ignore

from ietf.doc.expire import expire_draft
from ietf.doc.factories import WgDraftFactory
from ietf.doc.models import Document
from ietf.group.factories import RoleFactory
from ietf.meeting.factories import MeetingFactory
from ietf.person.factories import PersonFactory, EmailFactory
from ietf.person.models import Person
from ietf.submit.models import Preapproval
from ietf.utils.mail import outbox
from ietf.utils.test_utils import TestCase, login_testing_unauthorized
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
        draft = WgDraftFactory()
        url = urlreverse('ietf.secr.drafts.views.abstract', kwargs={'id':draft.name})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
    def test_approvals(self): 
        Preapproval.objects.create(name='draft-dummy', 
            by=Person.objects.get(name="(System)")) 
        url = urlreverse('ietf.secr.drafts.views.approvals') 
        self.client.login(username="secretary", password="secretary+password") 
        response = self.client.get(url) 
        self.assertContains(response, 'draft-dummy')

    def test_edit(self):
        draft = WgDraftFactory(states=[('draft','active'),('draft-stream-ietf','wg-doc'),('draft-iesg','ad-eval')], shepherd=EmailFactory())
        url = urlreverse('ietf.secr.drafts.views.edit', kwargs={'id':draft.name})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response = self.client.post(url,{'title':draft.title,'name':draft.name,'rev':draft.rev,'state':4,'group':draft.group.pk,'iesg_state':draft.get_state('draft-iesg').pk})
        self.assertEqual(response.status_code, 302)
        draft = Document.objects.get(pk=draft.pk)
        self.assertEqual(draft.get_state().slug,'repl')

    def test_email(self):
        # can't test this directly, test via drafts actions
        pass
    
    def test_get_email_initial(self):
        # Makes sure that a manual posting by the Secretariat of an I-D that is
        # in the RFC Editor Queue will result in notification of the RFC Editor
        draft = WgDraftFactory(authors=PersonFactory.create_batch(1),shepherd=EmailFactory())
        RoleFactory(group=draft.group, name_id='chair')
        data = get_email_initial(draft,action='extend',input={'expiration_date': '2050-01-01'})
        self.assertTrue('Extension of Expiration Date' in data['subject'])
        
    def test_makerfc(self):
        draft = WgDraftFactory(intended_std_level_id='ps')
        url = urlreverse('ietf.secr.drafts.views.edit', kwargs={'id':draft.name})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # It's not clear what this is testing. Was there supposed to be a POST here?
        self.assertTrue(draft.intended_std_level)
        
    def test_search(self):
        WgDraftFactory() # Test exercises branch that requires >1 doc found
        draft = WgDraftFactory()
        url = urlreverse('ietf.secr.drafts.views.search')
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        post = dict(filename='draft',state=1,submit='submit')
        response = self.client.post(url, post)
        self.assertContains(response, draft.name)

    def test_view(self):
        draft = WgDraftFactory()
        url = urlreverse('ietf.secr.drafts.views.view', kwargs={'id':draft.name})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_author_delete(self):
        draft = WgDraftFactory(authors=PersonFactory.create_batch(2))
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
        draft = WgDraftFactory()
        path = os.path.join(self.repository_dir, draft.filename_with_rev())
        with io.open(path, 'w') as file:
            file.write('test')
        expire_draft(draft)
        email_url = urlreverse('ietf.secr.drafts.views.email', kwargs={'id':draft.name}) + "?action=resurrect"
        confirm_url = urlreverse('ietf.secr.drafts.views.confirm', kwargs={'id':draft.name})
        do_action_url = urlreverse('ietf.secr.drafts.views.do_action', kwargs={'id':draft.name})
        view_url = urlreverse('ietf.secr.drafts.views.view', kwargs={'id':draft.name})
        subject =  'Resurrection of %s' % draft.get_base_name()
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(email_url)
        self.assertContains(response, '<title>Drafts - Email</title>')
        q = PyQuery(response.content)
        self.assertEqual(q("#id_subject").val(), subject)
        post_data = {
            'action': 'resurrect',
            'to': 'john@example.com',
            'cc': 'joe@example.com',
            'subject': subject,
            'body': 'draft resurrected',
            'submit': 'Save'
        }
        response = self.client.post(confirm_url, post_data)
        self.assertContains(response, '<title>Drafts - Confirm</title>')
        self.assertEqual(response.context['email']['subject'], subject)
        response = self.client.post(do_action_url, post_data)
        self.assertRedirects(response, view_url)
        draft = Document.objects.get(name=draft.name)
        self.assertTrue(draft.get_state_slug('draft') == 'active')
        recv = outbox[-1]
        self.assertEqual(recv['Subject'], subject)

    def test_extend(self):
        draft = WgDraftFactory()
        url = urlreverse('ietf.secr.drafts.views.extend', kwargs={'id':draft.name})
        email_url = urlreverse('ietf.secr.drafts.views.email', kwargs={'id':draft.name})
        confirm_url = urlreverse('ietf.secr.drafts.views.confirm', kwargs={'id':draft.name})
        do_action_url = urlreverse('ietf.secr.drafts.views.do_action', kwargs={'id':draft.name})
        view_url = urlreverse('ietf.secr.drafts.views.view', kwargs={'id':draft.name})
        expiration = datetime.datetime.today() + datetime.timedelta(days=180)
        expiration = expiration.replace(hour=0,minute=0,second=0,microsecond=0)
        subject = 'Extension of Expiration Date for %s' % draft.get_base_name()
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        extend_data = {
            'action': 'extend',
            'expiration_date': expiration.strftime('%Y-%m-%d'),
        }
        post_data = {
            'action': 'extend',
            'expiration_date': expiration.strftime('%Y-%m-%d'),
            'to': 'john@example.com',
            'cc': 'joe@example.com',
            'subject': subject,
            'body': 'draft extended',
            'submit': 'Save'
        }
        response = self.client.post(url, extend_data)
        self.assertRedirects(response, email_url + '?' + urlencode(extend_data))
        response = self.client.post(confirm_url, post_data)
        self.assertContains(response, '<title>Drafts - Confirm</title>')
        self.assertEqual(response.context['email']['subject'], subject)
        response = self.client.post(do_action_url, post_data)
        self.assertRedirects(response, view_url)
        draft = Document.objects.get(name=draft.name)
        self.assertTrue(draft.expires == expiration)
        recv = outbox[-1]
        self.assertEqual(recv['Subject'], subject)

    def test_withdraw(self):
        draft = WgDraftFactory()
        url = urlreverse('ietf.secr.drafts.views.withdraw', kwargs={'id':draft.name})
        email_url = urlreverse('ietf.secr.drafts.views.email', kwargs={'id':draft.name})
        confirm_url = urlreverse('ietf.secr.drafts.views.confirm', kwargs={'id':draft.name})
        do_action_url = urlreverse('ietf.secr.drafts.views.do_action', kwargs={'id':draft.name})
        view_url = urlreverse('ietf.secr.drafts.views.view', kwargs={'id':draft.name})
        subject = 'Withdraw of %s' % draft.get_base_name()
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        withdraw_data = OrderedDict([('action', 'withdraw'), ('withdraw_type', 'ietf')])
        post_data = {
            'action': 'withdraw',
            'withdraw_type': 'ietf',
            'to': 'john@example.com',
            'cc': 'joe@example.com',
            'subject': subject,
            'body': 'draft resurrected',
            'submit': 'Save'
        }
        response = self.client.post(url, withdraw_data)
        self.assertRedirects(response, email_url + '?' + urlencode(withdraw_data))
        response = self.client.post(confirm_url, post_data)
        self.assertContains(response, '<title>Drafts - Confirm</title>')
        self.assertEqual(response.context['email']['subject'], subject)
        response = self.client.post(do_action_url, post_data)
        self.assertRedirects(response, view_url)
        draft = Document.objects.get(name=draft.name)
        self.assertTrue(draft.get_state_slug('draft') == 'ietf-rm')
        recv = outbox[-1]
        self.assertEqual(recv['Subject'], subject)

    def test_authors(self):
        draft = WgDraftFactory()
        person = PersonFactory()
        url = urlreverse('ietf.secr.drafts.views.authors',kwargs={'id':draft.name})
        login_testing_unauthorized(self, "secretary", url)
        response = self.client.get(url)
        self.assertEqual(response.status_code,200)
        response = self.client.post(url, {'submit':'Done'})
        self.assertEqual(response.status_code,302)
        response = self.client.post(url, {'person':'%s - (%s)'%(person.plain_name(),person.pk),'email':person.email_set.first().pk})
        self.assertEqual(response.status_code,302)
        self.assertTrue(draft.documentauthor_set.filter(person=person).exists)

    def test_dates(self):
        MeetingFactory(type_id='ietf',date=datetime.datetime.today()+datetime.timedelta(days=14))
        url = urlreverse('ietf.secr.drafts.views.dates')
        login_testing_unauthorized(self, "secretary", url)
        response = self.client.get(url)
        self.assertEqual(response.status_code,200)
    
    def test_nudge_report(self):
        url = urlreverse('ietf.secr.drafts.views.nudge_report')
        login_testing_unauthorized(self, "secretary", url)
        response = self.client.get(url)
        self.assertEqual(response.status_code,200)
