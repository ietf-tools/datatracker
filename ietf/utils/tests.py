import os.path
from smtplib import SMTPRecipientsRefused

from django.conf import settings
from django.test import TestCase

from ietf.utils.management.commands import pyflakes
from ietf.utils.mail import send_mail_text, outbox, SMTPSomeRefusedRecipients, smtp_error_logging

class PyFlakesTestCase(TestCase):

    def test_pyflakes(self):
        path = os.path.join(settings.BASE_DIR)
        warnings = []
        warnings = pyflakes.checkPaths([path], verbosity=0)
        self.assertEqual([str(w) for w in warnings], [])

class TestSMTPServer(TestCase):

    def test_address_rejected(self):

        def send_mail(to):
           send_mail_text(None, to=to, frm=None, subject="Test for rejection", txt="dummy body")

        with self.assertRaises(SMTPSomeRefusedRecipients):
           send_mail('good@example.com,poison@example.com')

        with self.assertRaises(SMTPRecipientsRefused):
            send_mail('poison@example.com')

        len_before = len(outbox)
        with smtp_error_logging(send_mail) as send:
           send('good@example.com,poison@example.com')
        self.assertEqual(len(outbox),len_before+2)
        self.assertTrue('Some recipients were refused' in outbox[-1]['Subject'])

        len_before = len(outbox)
        with smtp_error_logging(send_mail) as send:
           send('poison@example.com')
        self.assertEqual(len(outbox),len_before+2)
        self.assertTrue('error while sending email' in outbox[-1]['Subject'])
        