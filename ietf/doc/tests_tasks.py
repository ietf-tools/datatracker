# Copyright The IETF Trust 2024, All Rights Reserved
import mock

from ietf.utils.test_utils import TestCase
from ietf.utils.timezone import datetime_today

from .factories import DocumentFactory
from .models import Document
from .tasks import expire_ids_task, notify_expirations_task


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
