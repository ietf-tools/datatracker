# Copyright The IETF Trust 2024, All Rights Reserved

import debug    # pyflakes:ignore
import datetime
import mock

from pathlib import Path

from django.conf import settings
from django.utils import timezone

from ietf.utils.test_utils import TestCase
from ietf.utils.timezone import datetime_today

from .factories import DocumentFactory, NewRevisionDocEventFactory
from .models import Document, NewRevisionDocEvent
from .tasks import (
    expire_ids_task,
    expire_last_calls_task,
    generate_draft_bibxml_files_task,
    generate_idnits2_rfcs_obsoleted_task,
    generate_idnits2_rfc_status_task,
    notify_expirations_task,
)

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
        with self.assertRaises(RuntimeError):
            expire_ids_task()

    @mock.patch("ietf.doc.tasks.send_expire_warning_for_draft")
    @mock.patch("ietf.doc.tasks.get_soon_to_expire_drafts")
    def test_notify_expirations_task(self, get_drafts_mock, send_warning_mock):
        # Set up mocks
        get_drafts_mock.return_value = ["sentinel"]
        notify_expirations_task()
        self.assertEqual(send_warning_mock.call_count, 1)
        self.assertEqual(send_warning_mock.call_args[0], ("sentinel",))

    @mock.patch("ietf.doc.tasks.expire_last_call")
    @mock.patch("ietf.doc.tasks.get_expired_last_calls")
    def test_expire_last_calls_task(self, mock_get_expired, mock_expire):
        docs = DocumentFactory.create_batch(3)
        mock_get_expired.return_value = docs
        expire_last_calls_task()
        self.assertTrue(mock_get_expired.called)
        self.assertEqual(mock_expire.call_count, 3)
        self.assertEqual(mock_expire.call_args_list[0], mock.call(docs[0]))
        self.assertEqual(mock_expire.call_args_list[1], mock.call(docs[1]))
        self.assertEqual(mock_expire.call_args_list[2], mock.call(docs[2]))
    
        # Check that it runs even if exceptions occur
        mock_get_expired.reset_mock()
        mock_expire.reset_mock()
        mock_expire.side_effect = ValueError
        expire_last_calls_task()
        self.assertTrue(mock_get_expired.called)
        self.assertEqual(mock_expire.call_count, 3)
        self.assertEqual(mock_expire.call_args_list[0], mock.call(docs[0]))
        self.assertEqual(mock_expire.call_args_list[1], mock.call(docs[1]))
        self.assertEqual(mock_expire.call_args_list[2], mock.call(docs[2]))


class Idnits2SupportTests(TestCase):
    settings_temp_path_overrides = TestCase.settings_temp_path_overrides + ['DERIVED_DIR']

    @mock.patch("ietf.doc.tasks.generate_idnits2_rfcs_obsoleted")
    def test_generate_idnits2_rfcs_obsoleted_task(self, mock_generate):
        mock_generate.return_value = "dåtå"
        generate_idnits2_rfcs_obsoleted_task()
        self.assertEqual(mock_generate.call_count, 1)
        self.assertEqual(
            "dåtå".encode("utf8"),
            (Path(settings.DERIVED_DIR) / "idnits2-rfcs-obsoleted").read_bytes(),
        )

    @mock.patch("ietf.doc.tasks.generate_idnits2_rfc_status")
    def test_generate_idnits2_rfc_status_task(self, mock_generate):
        mock_generate.return_value = "dåtå"
        generate_idnits2_rfc_status_task()
        self.assertEqual(mock_generate.call_count, 1)
        self.assertEqual(
            "dåtå".encode("utf8"),
            (Path(settings.DERIVED_DIR) / "idnits2-rfc-status").read_bytes(),
        )


class BIBXMLSupportTests(TestCase):
    def setUp(self):
        super().setUp()
        now = timezone.now()
        self.very_old_event = NewRevisionDocEventFactory(
            time=now - datetime.timedelta(days=1000), rev="17"
        )
        self.old_event = NewRevisionDocEventFactory(
            time=now - datetime.timedelta(days=8), rev="03"
        )
        self.young_event = NewRevisionDocEventFactory(
            time=now - datetime.timedelta(days=6), rev="06"
        )
        # a couple that should always be ignored
        NewRevisionDocEventFactory(
            time=now - datetime.timedelta(days=6), rev="09", doc__type_id="rfc"  # not a draft
        )
        NewRevisionDocEventFactory(
            type="changed_document",  # not a "new_revision" type
            time=now - datetime.timedelta(days=6),
            rev="09",
            doc__type_id="rfc",
        )
        # Get rid of the "00" events created by the factories -- they're just noise for this test
        NewRevisionDocEvent.objects.filter(rev="00").delete()

    @mock.patch("ietf.doc.tasks.ensure_draft_bibxml_path_exists")
    @mock.patch("ietf.doc.tasks.update_or_create_draft_bibxml_file")
    def test_generate_bibxml_files_for_all_drafts_task(self, mock_create, mock_ensure_path):
        generate_draft_bibxml_files_task(process_all=True)
        self.assertTrue(mock_ensure_path.called)
        self.assertCountEqual(
            mock_create.call_args_list,
            [
                mock.call(self.young_event.doc, self.young_event.rev),
                mock.call(self.old_event.doc, self.old_event.rev),
                mock.call(self.very_old_event.doc, self.very_old_event.rev),
            ],
        )
        mock_create.reset_mock()
        mock_ensure_path.reset_mock()

        # everything should still be tried, even if there's an exception
        mock_create.side_effect = RuntimeError
        generate_draft_bibxml_files_task(process_all=True)
        self.assertTrue(mock_ensure_path.called)
        self.assertCountEqual(
            mock_create.call_args_list,
            [
                mock.call(self.young_event.doc, self.young_event.rev),
                mock.call(self.old_event.doc, self.old_event.rev),
                mock.call(self.very_old_event.doc, self.very_old_event.rev),
            ],
        )

    @mock.patch("ietf.doc.tasks.ensure_draft_bibxml_path_exists")
    @mock.patch("ietf.doc.tasks.update_or_create_draft_bibxml_file")
    def test_generate_bibxml_files_for_recent_drafts_task(self, mock_create, mock_ensure_path):
        # default args - look back 7 days
        generate_draft_bibxml_files_task()
        self.assertTrue(mock_ensure_path.called)
        self.assertCountEqual(
            mock_create.call_args_list, [mock.call(self.young_event.doc, self.young_event.rev)]
        )
        mock_create.reset_mock()
        mock_ensure_path.reset_mock()

        # shorter lookback
        generate_draft_bibxml_files_task(days=5)
        self.assertTrue(mock_ensure_path.called)
        self.assertCountEqual(mock_create.call_args_list, [])
        mock_create.reset_mock()
        mock_ensure_path.reset_mock()

        # longer lookback
        generate_draft_bibxml_files_task(days=9)
        self.assertTrue(mock_ensure_path.called)
        self.assertCountEqual(
            mock_create.call_args_list,
            [
                mock.call(self.young_event.doc, self.young_event.rev),
                mock.call(self.old_event.doc, self.old_event.rev),
            ],
        )

    @mock.patch("ietf.doc.tasks.ensure_draft_bibxml_path_exists")
    @mock.patch("ietf.doc.tasks.update_or_create_draft_bibxml_file")
    def test_generate_bibxml_files_for_recent_drafts_task_with_bad_value(self, mock_create, mock_ensure_path):
        with self.assertRaises(ValueError):
            generate_draft_bibxml_files_task(days=0)
        self.assertFalse(mock_create.called)
        self.assertFalse(mock_ensure_path.called)
