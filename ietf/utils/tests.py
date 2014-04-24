import os.path

from django.conf import settings
from django.test import TestCase

from ietf.utils.management.commands import pyflakes
from ietf.utils.mail import send_mail_text, outbox 

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

        len_before = len(outbox)
        send_mail('good@example.com,poison@example.com')
        self.assertEqual(len(outbox),len_before+2)
        self.assertTrue('Some recipients were refused' in outbox[-1]['Subject'])

        len_before = len(outbox)
        send_mail('poison@example.com')
        self.assertEqual(len(outbox),len_before+2)
        self.assertTrue('error while sending email' in outbox[-1]['Subject'])
        
