# Copyright The IETF Trust 2015-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from django.urls import reverse as urlreverse

from ietf.utils.test_utils import TestCase

class EventMailTests(TestCase):

    def test_show_triggers(self):

        url = urlreverse('ietf.mailtrigger.views.show_triggers')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'iesg_ballot_saved')
   
        url = urlreverse('ietf.mailtrigger.views.show_triggers',kwargs=dict(mailtrigger_slug='iesg_ballot_saved'))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'iesg_ballot_saved')

    def test_show_recipients(self):

        url = urlreverse('ietf.mailtrigger.views.show_recipients')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'doc_group_mail_list')
   
        url = urlreverse('ietf.mailtrigger.views.show_recipients',kwargs=dict(recipient_slug='doc_group_mail_list'))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'doc_group_mail_list')

    def test_clean_duplicates_unquoted_commas_and_suffixes(self):
        from ietf.mailtrigger.models import clean_duplicates
        # Addresses with unquoted commas and suffixes must be recovered and properly quoted
        addrs = [
            'Dane Foster, Ph.D. <dane@example.com>',
            'User Lname, Ph.D <user@example.com>',
            '"User Lname" <user@example.com>',
        ]
        cleaned = clean_duplicates(addrs)
        self.assertIn('"Dane Foster, Ph.D." <dane@example.com>', cleaned)
        # Multiple addresses for the same recipient are collapsed
        self.assertEqual(len([a for a in cleaned if 'user@example.com' in a]), 1)

    def test_gather_submission_authors_with_phd(self):
        from ietf.person.factories import PersonFactory, EmailFactory
        from ietf.submit.factories import SubmissionFactory
        from ietf.mailtrigger.models import Recipient

        person = PersonFactory(name="Dane Foster, Ph.D.")
        email = EmailFactory(person=person, address="dane.foster@example.com")
        sub = SubmissionFactory(
            authors=[
                {"name": "Dane Foster, Ph.D.", "email": email.address},
                {"name": "No DB, Ph.D.", "email": "nodb@example.com"},
            ]
        )
        recip = Recipient.objects.get(slug="submission_authors")
        addrs = recip.gather(submission=sub)
        # Registered person gets plain name formatted email
        self.assertIn(f"{person.plain_name()} <{email.address}>", addrs)
        # Unregistered author gets properly quoted formataddr
        self.assertIn('"No DB, Ph.D." <nodb@example.com>', addrs)


