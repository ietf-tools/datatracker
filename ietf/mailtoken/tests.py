from django.core.urlresolvers import reverse as urlreverse

from ietf.utils.test_utils import TestCase
from ietf.utils.test_data import make_test_data
from ietf.mailtoken.models import Recipient

class EventMailTests(TestCase):

    def setUp(self):
        make_test_data()

    def test_show_tokens(self):

        url = urlreverse('ietf.mailtoken.views.show_tokens')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue('ballot_saved_cc' in r.content)
   
        url = urlreverse('ietf.mailtoken.views.show_tokens',kwargs=dict(mailtoken_slug='ballot_saved_cc'))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue('ballot_saved_cc' in r.content)

    def test_show_recipients(self):

        url = urlreverse('ietf.mailtoken.views.show_recipients')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue('doc_group_mail_list' in r.content)
   
        url = urlreverse('ietf.mailtoken.views.show_recipients',kwargs=dict(recipient_slug='doc_group_mail_list'))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue('doc_group_mail_list' in r.content)

class RecipientTests(TestCase):

    def test_recipient_functions(self):
        draft = make_test_data()
        recipient = Recipient.objects.first()
        for funcname in [name for name in dir(recipient) if name.startswith('gather_')]:
            func=getattr(recipient,funcname)
            func(**{'doc':draft,'group':draft.group})
