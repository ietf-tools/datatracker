# Copyright The IETF Trust 2024, All Rights Reserved

import io
import os
import mock

from django.urls import reverse as urlreverse
from django.conf import settings

from ietf.utils.test_utils import TestCase
from ietf.utils.timezone import datetime_today
from ietf.utils.test_utils import unicontent

from .factories import DocumentFactory, IndividualDraftFactory, WgRfcFactory
from .models import Document
from .tasks import expire_ids_task, notify_expirations_task
from .tasks import generate_idnits2_rfcs_obsoleted_task, generate_idnits2_rfc_status_task
from .tasks import generate_bibxml_files_for_all_drafts_task, generate_bibxml_files_for_recent_drafts_task

class TaskTests(TestCase):

    @mock.patch("ietf.doc.tasks.in_draft_expire_freeze")
    @mock.patch("ietf.doc.tasks.get_expired_drafts")
    @mock.patch("ietf.doc.tasks.expirable_drafts")
    @mock.patch("ietf.doc.tasks.send_expire_notice_for_draft")
    @mock.patch("ietf.doc.tasks.expire_draft")
    @mock.patch("ietf.doc.tasks.clean_up_draft_files")
    def test_expire_ids_task(
        self,
        clean_up_draft_files_mock,
        expire_draft_mock,
        send_expire_notice_for_draft_mock,
        expirable_drafts_mock,
        get_expired_drafts_mock,
        in_draft_expire_freeze_mock,
    ):
        # set up mocks
        in_draft_expire_freeze_mock.return_value = False
        doc, other_doc = DocumentFactory.create_batch(2)
        doc.expires = datetime_today()
        get_expired_drafts_mock.return_value = [doc, other_doc]
        expirable_drafts_mock.side_effect = [
            Document.objects.filter(pk=doc.pk),
            Document.objects.filter(pk=other_doc.pk),
        ]
        
        # call task
        expire_ids_task()
        
        # check results
        self.assertTrue(in_draft_expire_freeze_mock.called)
        self.assertEqual(expirable_drafts_mock.call_count, 2)
        self.assertEqual(send_expire_notice_for_draft_mock.call_count, 1)
        self.assertEqual(send_expire_notice_for_draft_mock.call_args[0], (doc,))
        self.assertEqual(expire_draft_mock.call_count, 1)
        self.assertEqual(expire_draft_mock.call_args[0], (doc,))
        self.assertTrue(clean_up_draft_files_mock.called)

        # test that an exception is raised
        in_draft_expire_freeze_mock.side_effect = RuntimeError
        with self.assertRaises(RuntimeError):(
            expire_ids_task())

    @mock.patch("ietf.doc.tasks.send_expire_warning_for_draft")
    @mock.patch("ietf.doc.tasks.get_soon_to_expire_drafts")
    def test_notify_expirations_task(self, get_drafts_mock, send_warning_mock):
        # Set up mocks
        get_drafts_mock.return_value = ["sentinel"]
        notify_expirations_task()
        self.assertEqual(send_warning_mock.call_count, 1)
        self.assertEqual(send_warning_mock.call_args[0], ("sentinel",))


class Idnits2SupportTests(TestCase):
    settings_temp_path_overrides = TestCase.settings_temp_path_overrides + ['DERIVED_DIR']

    def test_generate_idnits2_rfcs_obsoleted_task(self):
        rfc = WgRfcFactory(rfc_number=1001)
        WgRfcFactory(rfc_number=1003,relations=[('obs',rfc)])
        rfc = WgRfcFactory(rfc_number=1005)
        WgRfcFactory(rfc_number=1007,relations=[('obs',rfc)])
        url = urlreverse('ietf.doc.views_doc.idnits2_rfcs_obsoleted')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)
        generate_idnits2_rfcs_obsoleted_task()
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content, b'1001 1003\n1005 1007\n')
        
    def test_generate_idnits2_rfc_status_task(self):
        for slug in ('bcp', 'ds', 'exp', 'hist', 'inf', 'std', 'ps', 'unkn'):
            WgRfcFactory(std_level_id=slug)
        url = urlreverse('ietf.doc.views_doc.idnits2_rfc_status')
        r = self.client.get(url)
        self.assertEqual(r.status_code,404)
        generate_idnits2_rfc_status_task()
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        blob = unicontent(r).replace('\n','')
        self.assertEqual(blob[6312-1],'O')


class BIBXMLSupportTests(TestCase):
    def test_generate_bibxml_files_for_all_drafts_task(self):
        draft = IndividualDraftFactory.create()
        filename = 'reference.I-D.%s-%s.xml' % (draft.name, draft.rev)
        bibxmldir = os.path.join(settings.BIBXML_BASE_PATH, 'bibxml-ids')
        os.mkdir(bibxmldir)
        filepath = os.path.join(bibxmldir, filename)
        self.assertFalse(os.path.exists(filepath))
        generate_bibxml_files_for_all_drafts_task()
        self.assertTrue(os.path.exists(filepath))
        with io.open(filepath, encoding='utf-8') as f:
            content = f.read()
        self.assertIn(draft.title, content)

    def test_generate_bibxml_files_for_recent_drafts_task(self):
        draft = IndividualDraftFactory.create()
        filename = 'reference.I-D.%s-%s.xml' % (draft.name, draft.rev)
        bibxmldir = os.path.join(settings.BIBXML_BASE_PATH, 'bibxml-ids')
        os.mkdir(bibxmldir)
        filepath = os.path.join(bibxmldir, filename)
        self.assertFalse(os.path.exists(filepath))
        generate_bibxml_files_for_recent_drafts_task(days=7)
        self.assertTrue(os.path.exists(filepath))
        with io.open(filepath, encoding='utf-8') as f:
            content = f.read()
        self.assertIn(draft.title, content)

    def test_generate_bibxml_files_for_recent_drafts_task_with_bad_vakue(self):
        bibxmldir = os.path.join(settings.BIBXML_BASE_PATH, 'bibxml-ids')
        os.mkdir(bibxmldir)
        with self.assertRaises(ValueError):
            generate_bibxml_files_for_recent_drafts_task(days=0)
