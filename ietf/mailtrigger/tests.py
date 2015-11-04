from django.core.urlresolvers import reverse as urlreverse

from ietf.utils.test_utils import TestCase, unicontent
from ietf.utils.test_data import make_test_data

class EventMailTests(TestCase):

    def setUp(self):
        make_test_data()

    def test_show_triggers(self):

        url = urlreverse('ietf.mailtrigger.views.show_triggers')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue('ballot_saved' in unicontent(r))
   
        url = urlreverse('ietf.mailtrigger.views.show_triggers',kwargs=dict(mailtrigger_slug='ballot_saved'))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue('ballot_saved' in unicontent(r))

    def test_show_recipients(self):

        url = urlreverse('ietf.mailtrigger.views.show_recipients')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue('doc_group_mail_list' in unicontent(r))
   
        url = urlreverse('ietf.mailtrigger.views.show_recipients',kwargs=dict(recipient_slug='doc_group_mail_list'))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue('doc_group_mail_list' in unicontent(r))

