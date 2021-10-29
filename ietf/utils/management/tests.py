# Copyright The IETF Trust 2013-2020, All Rights Reserved
# -*- coding: utf-8 -*-

import mock

from django.core.management import call_command, CommandError
from django.test import override_settings


from ietf.utils.mail import outbox, empty_outbox
from ietf.utils.management.base import EmailOnFailureCommand
from ietf.utils.test_utils import TestCase


@mock.patch.object(EmailOnFailureCommand, 'handle')
class EmailOnFailureCommandTests(TestCase):
    def test_calls_handle(self, handle_method):
        call_command(EmailOnFailureCommand())
        self.assertEqual(handle_method.call_count, 1)

    def test_sends_email(self, handle_method):
        handle_method.side_effect = CommandError('error during the command')
        empty_outbox()
        admins = (
            ('admin one', 'admin1@example.com'),
            ('admin two', 'admin2@example.com'),
        )
        with override_settings(ADMINS=admins, SERVER_EMAIL='server@example.com'):
            call_command(EmailOnFailureCommand())
        self.assertEqual(len(outbox), 1)
        msg = outbox[0]
        self.assertEqual(msg['to'], 'admin1@example.com, admin2@example.com',
                         'Outgoing email recipients did not default to settings.ADMINS')
        self.assertEqual(msg['from'], 'server@example.com',
                         'Outgoing email sender did not default to settings.SERVER_EMAIL')
        self.assertTrue(msg.is_multipart())
        parts = msg.get_payload()
        self.assertEqual(len(parts), 2)
        self.assertIn('error during the command', parts[0].get_content())
        self.assertIn('error during the command', parts[1].get_content())
        self.assertIn('Traceback', parts[1].get_content())

    def test_disable_email(self, handle_method):
        handle_method.side_effect = CommandError('error during the command')
        empty_outbox()
        with self.assertRaises(CommandError):
            call_command(EmailOnFailureCommand(), '--no-failure-email')
        self.assertEqual(len(outbox), 0)

    def test_customize_email(self, handle_method):
        class _SubclassCommand(EmailOnFailureCommand):
            failure_message = 'simple message with the {error} and {other}\n'
            failure_recipients = 'someone@example.com'
            failure_subject = 'subject of the email'
            def make_failure_message(self, error, **extra):
                msg = super().make_failure_message(error, other='additional info', **extra)
                msg.add_attachment('attached\n')
                return msg

        handle_method.side_effect = CommandError('error during the command')
        empty_outbox()
        with override_settings(
                ADMINS=('a1', 'admin@example.com'),
                SERVER_EMAIL='server@example.com',
        ):
            call_command(_SubclassCommand())
        self.assertEqual(len(outbox), 1)
        msg = outbox[0]
        self.assertEqual(msg['to'], 'someone@example.com',
                         'Outgoing email recipients were not customized')
        self.assertEqual(msg['from'], 'server@example.com',
                         'Outgoing email sender did not default to settings.SERVER_EMAIL')
        self.assertEqual(msg['subject'], 'subject of the email',
                         'Outgoing email subject was not customized')
        self.assertTrue(msg.is_multipart())
        parts = msg.get_payload()
        self.assertEqual(len(parts), 3, 'Attachment was not added')
        self.assertEqual(
            parts[0].get_content(),
            'simple message with the error during the command and additional info\n',
        )
        self.assertIn('error during the command', parts[1].get_content())
        self.assertIn('Traceback', parts[1].get_content())
        self.assertEqual('attached\n', parts[2].get_content())

    def test_disable_traceback(self, handle_method):
        """Traceback should not be included when disabled"""
        class _SubclassCommand(EmailOnFailureCommand):
            failure_email_includes_traceback = False

        handle_method.side_effect = CommandError('error during the command')
        empty_outbox()
        with override_settings(
                ADMINS=('a1', 'admin@example.com'),
                SERVER_EMAIL='server@example.com',
        ):
            call_command(_SubclassCommand())
        self.assertEqual(len(outbox), 1)
        msg = outbox[0]
        if msg.is_multipart():
            parts = msg.get_payload()
            self.assertEqual(len(parts), 1, 'Traceback should not be attached')
            content = parts[0].get_content()
        else:
            content = msg.get_payload()
        self.assertNotIn('Traceback', content)

