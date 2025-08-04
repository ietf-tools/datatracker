# Copyright The IETF Trust 2021, All Rights Reserved
# -*- coding: utf-8 -*-
"""Tests of nomcom management commands"""
from unittest import mock
import sys

from collections import namedtuple

from django.core.management import call_command
from django.test.utils import override_settings

from ietf.nomcom.factories import NomComFactory
from ietf.utils.test_utils import TestCase, name_of_file_containing


@override_settings(ADMINS=(('Some Admin', 'admin@example.com'),))
class FeedbackEmailTests(TestCase):
    def setUp(self):
        super().setUp()
        self.year = 2021
        self.nomcom = NomComFactory(group__acronym=f'nomcom{self.year}')

    @mock.patch('ietf.utils.management.base.send_smtp')
    def test_send_error_to_admins(self, send_smtp_mock):
        """If a nomcom chair cannot be identified, mail goes to admins

        This email should not contain either the full traceback or the original message.
        """
        # Call with the wrong nomcom year so the admin will be contacted
        with name_of_file_containing('feedback message') as filename:
            call_command('feedback_email', nomcom_year=self.year + 1, email_file=filename)

        self.assertTrue(send_smtp_mock.called)
        (msg,) = send_smtp_mock.call_args.args  # get the message to be sent
        self.assertEqual(msg['to'], 'admin@example.com', 'Email recipient should be the admins')
        self.assertIn('error', msg['subject'], 'Email subject should indicate error')
        self.assertFalse(msg.is_multipart(), 'Nomcom feedback error sent to admin should not have attachments')
        # decode=True decodes the quoted-printable encoding, including removing soft linebreaks.
        # The .decode() converts the resulting octet-stream bytes to a string
        content = msg.get_payload(decode=True).decode()
        self.assertIn('CommandError', content, 'Admin email should contain error type')
        self.assertIn('feedback_email.py', content, 'Admin email should contain file where error occurred')
        self.assertNotIn('traceback', content.lower(), 'Admin email should not contain traceback')
        self.assertNotIn(f'NomCom {self.year} does not exist', content,
                         'Admin email should not contain error message')
        # not going to check the line - that's too likely to change

    @mock.patch('ietf.utils.management.base.send_smtp')
    @mock.patch('ietf.nomcom.management.commands.feedback_email.create_feedback_email')
    def test_send_error_to_chair(self, create_feedback_mock, send_smtp_mock):
        # mock an exception in create_feedback_email()
        create_feedback_mock.side_effect = RuntimeError('mock error')

        with name_of_file_containing('feedback message') as filename:
            call_command('feedback_email', nomcom_year=self.year, email_file=filename)

        self.assertTrue(send_smtp_mock.called)
        (msg,) = send_smtp_mock.call_args.args  # get the message to be sent
        self.assertCountEqual(
            [addr.strip() for addr in msg['to'].split(',')],
            self.nomcom.chair_emails(),
            'Email recipient should be the nomcom chair(s)',
        )
        self.assertIn('error', msg['subject'], 'Email subject should indicate error')
        self.assertTrue(msg.is_multipart(), 'Chair feedback error should have attachments')
        parts = msg.get_payload()
        content = parts[0].get_payload()
        # decode=True decodes the quoted-printable encoding, including removing soft linebreaks.
        # The .decode() converts the resulting octet-stream bytes to a string
        attachment = parts[1].get_payload(decode=True).decode()
        self.assertIn('RuntimeError', content, 'Nomcom email should contain error type')
        self.assertIn('mock.py', content, 'Nomcom email should contain file where error occurred')
        self.assertIn('feedback message', attachment, 'Nomcom email should include original message')

    @mock.patch('ietf.nomcom.management.commands.feedback_email.create_feedback_email')
    def test_feedback_email(self, create_feedback_mock):
        """The feedback_email command should create feedback"""
        # mock up the return value
        create_feedback_mock.return_value = namedtuple('mock_feedback', 'author')('author@example.com')

        with name_of_file_containing('feedback message') as filename:
            call_command('feedback_email', nomcom_year=self.year, email_file=filename)

        self.assertEqual(create_feedback_mock.call_count, 1, 'create_feedback_email() should be called once')
        self.assertEqual(
            create_feedback_mock.call_args.args,
            (self.nomcom, b'feedback message'),
            'feedback_email should process the correct email for the correct nomcom'
        )

    @mock.patch('ietf.utils.management.base.send_smtp')
    def test_invalid_character_encodings(self, send_smtp_mock):
        """The feedback_email command should send a message when file input has invalid encoding"""
        # mock an exception in create_feedback_email()
        invalid_characters = b'\xfe\xff'
        with name_of_file_containing(invalid_characters, mode='wb') as filename:
            call_command('feedback_email', nomcom_year=self.year, email_file=filename)

        self.assertTrue(send_smtp_mock.called)
        (msg,) = send_smtp_mock.call_args.args  # get the message to be sent
        parts = msg.get_payload()
        self.assertEqual(len(parts), 2, 'Error email should contain message and original message')

    @mock.patch.object(sys.stdin.buffer, 'read')
    @mock.patch('ietf.utils.management.base.send_smtp')
    def test_invalid_character_encodings_via_stdin(self, send_smtp_mock, stdin_read_mock):
        """The feedback_email command should send a message when stdin input has invalid encoding"""
        # mock an exception in create_feedback_email()
        invalid_characters = b'\xfe\xff'
        stdin_read_mock.return_value = invalid_characters
        call_command('feedback_email', nomcom_year=self.year)

        self.assertTrue(send_smtp_mock.called)
        (msg,) = send_smtp_mock.call_args.args  # get the message to be sent
        parts = msg.get_payload()
        self.assertEqual(len(parts), 2, 'Error email should contain message and original message')
