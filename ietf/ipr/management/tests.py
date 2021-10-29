# Copyright The IETF Trust 2021, All Rights Reserved
# -*- coding: utf-8 -*-
"""Tests of ipr management commands"""
import mock

from django.core.management import call_command
from django.test.utils import override_settings

from ietf.utils.test_utils import TestCase, name_of_file_containing


@override_settings(ADMINS=(('Some Admin', 'admin@example.com'),))
class ProcessEmailTests(TestCase):
    @mock.patch('ietf.ipr.management.commands.process_email.process_response_email')
    def test_process_email(self, process_mock):
        """The process_email command should process the correct email"""
        with name_of_file_containing('contents') as filename:
            call_command('process_email', email_file=filename)
        self.assertEqual(process_mock.call_count, 1, 'process_response_email should be called once')
        self.assertEqual(
            process_mock.call_args.args,
            ('contents',),
            'process_response_email should receive the correct contents'
        )

    @mock.patch('ietf.utils.management.base.send_smtp')
    @mock.patch('ietf.ipr.management.commands.process_email.process_response_email')
    def test_send_error_to_admin(self, process_mock, send_smtp_mock):
        """The process_email command should email the admins on error"""
        # arrange an mock error during processing
        process_mock.side_effect = RuntimeError('mock error')

        with name_of_file_containing('contents') as filename:
            call_command('process_email', email_file=filename)

        self.assertTrue(send_smtp_mock.called)
        (msg,) = send_smtp_mock.call_args.args
        self.assertEqual(msg['to'], 'admin@example.com', 'Admins should be emailed on error')
        self.assertIn('error', msg['subject'].lower(), 'Error email subject should indicate error')
        self.assertTrue(msg.is_multipart(), 'Error email should have attachments')
        parts = msg.get_payload()
        self.assertEqual(len(parts), 3, 'Error email should contain message, traceback, and original message')
        content = parts[0].get_payload()
        traceback = parts[1].get_payload()
        original = parts[2].get_payload(decode=True).decode()  # convert octet-stream to string
        self.assertIn('RuntimeError', content, 'Error type should be included in error email')
        self.assertIn('mock.py', content, 'File where error occurred should be included in error email')
        self.assertIn('traceback', traceback.lower(), 'Traceback should be attached to error email')
        self.assertEqual(original, 'contents', 'Original message should be attached to error email')
