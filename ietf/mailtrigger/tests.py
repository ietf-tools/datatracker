# Copyright The IETF Trust 2015-2019, All Rights Reserved
from django.urls import reverse as urlreverse

from ietf.utils.test_utils import TestCase, unicontent

class EventMailTests(TestCase):

    def test_show_triggers(self):

        url = urlreverse('ietf.mailtrigger.views.show_triggers')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'ballot_saved')
   
        url = urlreverse('ietf.mailtrigger.views.show_triggers',kwargs=dict(mailtrigger_slug='ballot_saved'))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'ballot_saved')

    def test_show_recipients(self):

        url = urlreverse('ietf.mailtrigger.views.show_recipients')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'doc_group_mail_list')
   
        url = urlreverse('ietf.mailtrigger.views.show_recipients',kwargs=dict(recipient_slug='doc_group_mail_list'))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'doc_group_mail_list')

