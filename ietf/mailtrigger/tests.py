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

    def test_gather_submission_authors_with_comma_and_suffix(self):
        from email.utils import getaddresses
        from ietf.person.factories import PersonFactory, EmailFactory
        from ietf.submit.factories import SubmissionFactory
        from ietf.mailtrigger.models import Recipient
        from ietf.mailtrigger.utils import gather_address_lists

        person = PersonFactory(name="Dane Foster, Ph.D.")
        email = EmailFactory(person=person, address="dane.foster@example.com")
        sub = SubmissionFactory(
            authors=[
                {"name": "Dane Foster, Ph.D.", "email": email.address},
                {"name": "User LName, Ph.D.", "email": "user@example.com"},
            ]
        )
        recip = Recipient.objects.get(slug="submission_authors")
        addrs = recip.gather(submission=sub)

        # Registered person gets clean plain name without dangling comma
        self.assertIn(f"{person.plain_name()} <{email.address}>", addrs)
        # Unregistered author gets properly quoted formataddr
        self.assertIn('"User LName, Ph.D." <user@example.com>', addrs)

        # When used in sub_announced_to_authors mail trigger, recipients must not split on commas (issue #11844)
        addr_lists = gather_address_lists("sub_announced_to_authors", submission=sub)
        parsed = getaddresses(addr_lists.to)
        # Each recipient must be parsed as a single address rather than splitting on the comma into two
        user_entries = [entry for entry in parsed if entry[1] == "user@example.com"]
        self.assertEqual(len(user_entries), 1)
        self.assertEqual(user_entries[0][0], "User LName, Ph.D.")



