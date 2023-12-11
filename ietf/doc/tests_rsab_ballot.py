# Copyright The IETF Trust 2022, All Rights Reserved
# -*- coding: utf-8 -*-

# import datetime
# from pyquery import PyQuery

import debug  # pyflakes:ignore

from django.urls import reverse as urlreverse

from ietf.utils.mail import outbox, empty_outbox, get_payload_text
from ietf.utils.test_utils import TestCase, unicontent, login_testing_unauthorized
from ietf.doc.factories import (
    EditorialDraftFactory,
    EditorialRfcFactory,
    IndividualDraftFactory,
    WgDraftFactory,
    RgDraftFactory,
    BallotDocEventFactory,
    IRSGBallotDocEventFactory,
    BallotPositionDocEventFactory,
)
from ietf.doc.models import BallotPositionDocEvent
from ietf.doc.utils import create_ballot_if_not_open, close_ballot
from ietf.person.utils import get_active_rsab, get_active_ads, get_active_irsg
from ietf.group.factories import RoleFactory
from ietf.group.models import Group, Role
from ietf.person.models import Person


class IssueRSABBallotTests(TestCase):
    def test_issue_ballot_button_presence(self):

        individual_draft = IndividualDraftFactory()
        wg_draft = WgDraftFactory()
        rg_draft = RgDraftFactory()
        ed_draft = EditorialDraftFactory()
        ed_rfc = EditorialRfcFactory()

        # login as an RSAB chair
        self.client.login(username="rsab-chair", password="rsab-chair+password")

        for name in [
            doc.name
            for doc in (individual_draft, wg_draft, rg_draft, ed_rfc)
        ]:
            url = urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=name))
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            self.assertNotIn("Issue RSAB ballot", unicontent(r))

        url = urlreverse(
            "ietf.doc.views_doc.document_main", kwargs=dict(name=ed_draft.name)
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertIn("Issue RSAB ballot", unicontent(r))

        self.client.logout()
        url = urlreverse(
            "ietf.doc.views_doc.document_main", kwargs=dict(name=ed_draft.name)
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("Issue RSAB ballot", unicontent(r))

    def test_close_ballot_button_presence(self):
        individual_draft = IndividualDraftFactory()
        wg_draft = WgDraftFactory()
        rg_draft = RgDraftFactory()
        ed_draft = EditorialDraftFactory()
        ed_rfc = EditorialRfcFactory()
        iesgmember = get_active_ads()[0]
        irsgmember = get_active_irsg()[0]

        BallotDocEventFactory(doc=ed_draft, ballot_type__slug="rsab-approve")

        url = urlreverse(
            "ietf.doc.views_doc.document_main", kwargs=dict(name=ed_draft.name)
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("Close RSAB ballot", unicontent(r))

        # Login as other body balloters to see if the ballot close button appears
        for member in (iesgmember, irsgmember):
            url = urlreverse(
                "ietf.doc.views_doc.document_main", kwargs=dict(name=ed_draft.name)
            )
            self.client.login(
                username=member.user.username,
                password=member.user.username + "+password",
            )
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            self.assertNotIn("Close RSAB ballot", unicontent(r))

            # Try to get the ballot closing page directly
            url = urlreverse(
                "ietf.doc.views_ballot.close_rsab_ballot",
                kwargs=dict(name=ed_draft.name),
            )
            r = self.client.get(url)
            self.assertNotEqual(r.status_code, 200)
            self.client.logout()

        # Login as the RSAB chair
        self.client.login(username="rsab-chair", password="rsab-chair+password")

        # The close button should now be available
        url = urlreverse(
            "ietf.doc.views_doc.document_main", kwargs=dict(name=ed_draft.name)
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertIn("Close RSAB ballot", unicontent(r))

        # Get the page with the Close RSAB Ballot Yes/No buttons
        url = urlreverse(
            "ietf.doc.views_ballot.close_rsab_ballot", kwargs=dict(name=ed_draft.name)
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        # Login as the Secretariat
        self.client.logout()
        self.client.login(username="secretary", password="secretary+password")

        # The close button should be available
        url = urlreverse(
            "ietf.doc.views_doc.document_main", kwargs=dict(name=ed_draft.name)
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertIn("Close RSAB ballot", unicontent(r))

        # Individual, IETF, and RFC docs should not show the Close button.
        for draft in (individual_draft, wg_draft, rg_draft, ed_rfc):
            url = urlreverse(
                "ietf.doc.views_doc.document_main", kwargs=dict(name=draft.name)
            )
            r = self.client.get(url, follow=True)
            self.assertEqual(r.status_code, 200)
            self.assertNotIn("Close RSAB ballot", unicontent(r))

    # TODO: This has a lot of redundancy with the BaseManipulation tests that should be refactored to speed tests up.
    def test_issue_ballot(self):

        ed_draft1 = EditorialDraftFactory()
        ed_draft2 = EditorialDraftFactory()
        iesgmember = get_active_ads()[0]

        self.assertFalse(ed_draft1.ballot_open("rsab-approve"))

        self.client.login(username="rsab-chair", password="rsab-chair+password")
        url = urlreverse(
            "ietf.doc.views_ballot.issue_rsab_ballot", kwargs=dict(name=ed_draft1.name)
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        # Buttons present?
        self.assertIn("rsab_button", unicontent(r))

        # Press the No button - expect nothing but a redirect back to the draft's main page
        r = self.client.post(url, dict(rsab_button="No"))
        self.assertEqual(r.status_code, 302)

        # Press the Yes button
        r = self.client.post(url, dict(rsab_button="Yes"))
        self.assertEqual(r.status_code, 302)
        self.assertTrue(ed_draft1.ballot_open("rsab-approve"))

        # Having issued a ballot, the Issue RSAB ballot button should be gone
        url = urlreverse(
            "ietf.doc.views_doc.document_main", kwargs=dict(name=ed_draft1.name)
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("Issue RSAB ballot", unicontent(r))

        # The RSAB evaluation record tab should exist
        self.assertIn("RSAB evaluation record", unicontent(r))
        # The RSAB evaluation record tab should not indicate unavailability
        self.assertNotIn(
            "RSAB Evaluation Ballot has not been created yet", unicontent(r)
        )  # TODO: why is this a thing? We don't ever show the tab unless there's a ballot. May need to reconsider how we treat the IESG.

        # We should find an RSAB member's name on the RSAB evaluation tab regardless of any positions taken or not
        url = urlreverse(
            "ietf.doc.views_doc.document_rsab_ballot", kwargs=dict(name=ed_draft1.name)
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        rsabmembers = get_active_rsab()
        self.assertNotEqual(len(rsabmembers), 0)
        for member in rsabmembers:
            self.assertIn(member.name, unicontent(r))

        # Having issued a ballot, it should appear on the RSAB Ballot Status page
        url = urlreverse("ietf.doc.views_ballot.rsab_ballot_status")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        # Does the draft name appear on the page?
        self.assertIn(ed_draft1.name, unicontent(r))

        self.client.logout()

        # Test that an IESG member cannot issue an RSAB ballot
        self.client.login(
            username=iesgmember.user.username,
            password=iesgmember.user.username + "password",
        )

        url = urlreverse(
            "ietf.doc.views_ballot.issue_rsab_ballot", kwargs=dict(name=ed_draft2.name)
        )
        r = self.client.get(url)
        self.assertNotEqual(r.status_code, 200)
        # Buttons present?
        self.assertNotIn("rsab_button", unicontent(r))

        # Attempt to press the Yes button anyway
        r = self.client.post(url, dict(rsab_button="Yes"))
        self.assertTrue(r.status_code == 302 and "/accounts/login" in r["Location"])

    def test_edit_ballot_position_permissions(self):
        ed_draft = EditorialDraftFactory()
        ad = RoleFactory(group__type_id="area", name_id="ad")
        pre_ad = RoleFactory(group__type_id="area", name_id="pre-ad")
        irsgmember = get_active_irsg()[0]
        rsab_chair = Role.objects.get(group__acronym="rsab", name="chair")
        ballot = create_ballot_if_not_open(
            None, ed_draft, rsab_chair.person, "rsab-approve"
        )

        url = urlreverse(
            "ietf.doc.views_ballot.edit_position",
            kwargs=dict(name=ed_draft.name, ballot_id=ballot.pk),
        )

        for person in (ad.person, pre_ad.person, irsgmember):
            self.client.login(
                username=person.user.username,
                password=f"{person.user.username}+password",
            )
            r = self.client.post(
                url, dict(position="concern", discuss="Test discuss text")
            )
            self.assertEqual(r.status_code, 403)
            self.client.logout()

    def test_iesg_ballot_no_rsab_actions(self):
        ad = Person.objects.get(user__username="ad")
        wg_draft = IndividualDraftFactory(ad=ad)
        RoleFactory.create_batch(
            2, name_id="member", group=Group.objects.get(acronym="rsab")
        )
        rsabmember = get_active_rsab()[0]

        url = urlreverse(
            "ietf.doc.views_ballot.ballot_writeupnotes", kwargs=dict(name=wg_draft.name)
        )

        # RSAB members should not be able to issue IESG ballots
        login_testing_unauthorized(self, rsabmember.user.username, url)
        r = self.client.post(
            url, dict(ballot_writeup="This is a test.", issue_ballot="1")
        )
        self.assertNotEqual(r.status_code, 200)

        self.client.logout()
        login_testing_unauthorized(self, "ad", url)

        BallotDocEventFactory(doc=wg_draft)

        # rsab members (who are not also IESG members) can't take positions
        ballot = wg_draft.active_ballot()
        url = urlreverse(
            "ietf.doc.views_ballot.edit_position",
            kwargs=dict(name=wg_draft.name, ballot_id=ballot.pk),
        )
        self.client.logout()
        login_testing_unauthorized(self, rsabmember.user.username, url)

        r = self.client.post(url, dict(position="discuss", discuss="Test discuss text"))
        self.assertEqual(r.status_code, 403)


class BaseManipulationTests:
    def test_issue_ballot(self):
        draft = EditorialDraftFactory()
        url = urlreverse(
            "ietf.doc.views_ballot.issue_rsab_ballot", kwargs=dict(name=draft.name)
        )
        empty_outbox()

        login_testing_unauthorized(self, self.username, url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        r = self.client.post(url, {"rsab_button": "No"})
        self.assertEqual(r.status_code, 302)
        self.assertIsNone(draft.ballot_open("rsab-approve"))

        # No notifications should have been generated yet
        self.assertEqual(len(outbox), 0)

        r = self.client.post(url, {"rsab_button": "Yes"})
        self.assertEqual(r.status_code, 302)
        self.assertIsNotNone(draft.ballot_open("rsab-approve"))

        # Should have sent a notification about the new ballot
        self.assertEqual(len(outbox), 1)
        msg = outbox[0]
        self.assertIn("RSAB ballot issued", msg["Subject"])
        self.assertIn("iesg-secretary@ietf.org", msg["From"])
        self.assertIn(draft.name, msg["Cc"])
        self.assertIn("rsab@rfc-editor.org", msg["To"])

    def test_take_and_email_position(self):
        draft = EditorialDraftFactory()
        ballot = BallotDocEventFactory(doc=draft, ballot_type__slug="rsab-approve")
        url = (
            urlreverse(
                "ietf.doc.views_ballot.edit_position",
                kwargs=dict(name=draft.name, ballot_id=ballot.pk),
            )
            + self.balloter
        )
        empty_outbox()

        login_testing_unauthorized(self, self.username, url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        r = self.client.post(
            url,
            dict(position="yes", comment="oib239sb", send_mail="Save and send email"),
        )
        self.assertEqual(r.status_code, 302)
        e = draft.latest_event(BallotPositionDocEvent)
        self.assertEqual(e.pos.slug, "yes")
        self.assertEqual(e.comment, "oib239sb")

        url = (
            urlreverse(
                "ietf.doc.views_ballot.send_ballot_comment",
                kwargs=dict(name=draft.name, ballot_id=ballot.pk),
            )
            + self.balloter
        )

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        r = self.client.post(
            url,
            dict(
                cc_choices=["doc_authors", "doc_group_chairs", "doc_group_mail_list"],
                body="Stuff",
            ),
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(len(outbox), 1)
        self.assertNotIn("discuss-criteria", get_payload_text(outbox[0]))

    def test_close_ballot(self):
        draft = EditorialDraftFactory()
        BallotDocEventFactory(doc=draft, ballot_type__slug="rsab-approve")
        url = urlreverse(
            "ietf.doc.views_ballot.close_rsab_ballot", kwargs=dict(name=draft.name)
        )
        empty_outbox()

        login_testing_unauthorized(self, self.username, url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        r = self.client.post(url, dict(rsab_button="No"))
        self.assertEqual(r.status_code, 302)
        self.assertIsNotNone(draft.ballot_open("rsab-approve"))

        # Should not have generated a notification yet
        self.assertEqual(len(outbox), 0)

        r = self.client.post(url, dict(rsab_button="Yes"))
        self.assertEqual(r.status_code, 302)
        self.assertIsNone(draft.ballot_open("rsab-approve"))

        # Closing the ballot should have generated a notification
        self.assertEqual(len(outbox), 1)
        msg = outbox[0]
        self.assertIn("RSAB ballot closed", msg["Subject"])
        self.assertIn("iesg-secretary@ietf.org", msg["From"])
        self.assertIn("rsab@rfc-editor.org", msg["To"])
        self.assertIn(f"{draft.name}@ietf.org", msg["Cc"])

    def test_view_outstanding_ballots(self):
        draft = EditorialDraftFactory()
        BallotDocEventFactory(doc=draft, ballot_type__slug="rsab-approve")
        url = urlreverse("ietf.doc.views_ballot.rsab_ballot_status")

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertIn(draft.name, unicontent(r))

        close_ballot(
            draft, Person.objects.get(user__username=self.username), "rsab-approve"
        )
        r = self.client.get(url)
        self.assertNotIn(draft.name, unicontent(r))


class RSABChairTests(BaseManipulationTests, TestCase):
    def setUp(self):
        super().setUp()
        self.username = "rsab-chair"
        self.balloter = ""


class SecretariatTests(BaseManipulationTests, TestCase):
    def setUp(self):
        super().setUp()
        self.username = "secretary"
        self.balloter = "?balloter={}".format(
            Person.objects.get(user__username="rsab-chair").pk
        )


class RSABMemberTests(TestCase):
    def setUp(self):
        super().setUp()
        self.username = RoleFactory(
            group__acronym="rsab", name_id="member"
        ).person.user.username

    def test_cant_issue_rsab_ballot(self):
        draft = EditorialDraftFactory()
        url = urlreverse(
            "ietf.doc.views_ballot.issue_rsab_ballot", kwargs=dict(name=draft.name)
        )

        self.client.login(username=self.username, password=self.username + "+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 403)

        r = self.client.post(url, {"rsab_button": "Yes"})
        self.assertEqual(r.status_code, 403)

    def test_cant_close_rsab_ballot(self):
        draft = EditorialDraftFactory()
        BallotDocEventFactory(doc=draft, ballot_type__slug="rsab-approve")
        url = urlreverse(
            "ietf.doc.views_ballot.close_rsab_ballot", kwargs=dict(name=draft.name)
        )

        self.client.login(username=self.username, password=self.username + "+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 403)

        r = self.client.post(url, dict(rsab_button="Yes"))
        self.assertEqual(r.status_code, 403)

    def test_cant_act_on_other_bodies_ballots(self):
        ietf_doc = WgDraftFactory()
        irtf_doc = RgDraftFactory()

        self.client.login(username=self.username, password=f"{self.username}+password")

        url = urlreverse(
            "ietf.doc.views_ballot.ballot_writeupnotes", kwargs=dict(name=ietf_doc.name)
        )
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(
            self.client.post(
                url,
                dict(ballot_writeup="This is a simple test.", save_ballot_writeup="1"),
            ).status_code,
            403,
        )

        url = urlreverse(
            "ietf.doc.views_ballot.issue_irsg_ballot", kwargs=dict(name=irtf_doc.name)
        )
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(
            self.client.post(
                url, dict(irsg_button="Yes", duedate="2038-01-19")
            ).status_code,
            403,
        )

        for name, ballot_id in [
            (ietf_doc.name, BallotDocEventFactory(doc=ietf_doc).pk),
            (irtf_doc.name, IRSGBallotDocEventFactory(doc=irtf_doc).pk),
        ]:
            url = urlreverse(
                "ietf.doc.views_ballot.edit_position",
                kwargs=dict(name=name, ballot_id=ballot_id),
            )
            self.assertEqual(
                self.client.get(url).status_code, 200
            )  # TODO : WHAT?! : This is strange, and probably tied up badly with pre-ad, and it should change.
            self.assertEqual(
                self.client.post(
                    url,
                    dict(position="yes"),
                ).status_code,
                403,
            )

        url = urlreverse(
            "ietf.doc.views_ballot.close_irsg_ballot", kwargs=dict(name=irtf_doc.name)
        )
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(
            self.client.post(url, dict(irsg_button="Yes")).status_code, 403
        )

        # Closing iesg ballots happens as a side-effect of secretariat actions with access testing done elsewhere

    def test_take_and_email_position(self):
        draft = EditorialDraftFactory()
        ballot = BallotDocEventFactory(doc=draft, ballot_type__slug="rsab-approve")
        url = urlreverse(
            "ietf.doc.views_ballot.edit_position",
            kwargs=dict(name=draft.name, ballot_id=ballot.pk),
        )
        empty_outbox()

        login_testing_unauthorized(self, self.username, url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        r = self.client.post(
            url,
            dict(position="yes", comment="oib239sb", send_mail="Save and send email"),
        )
        self.assertEqual(r.status_code, 302)
        e = draft.latest_event(BallotPositionDocEvent)
        self.assertEqual(e.pos.slug, "yes")
        self.assertEqual(e.comment, "oib239sb")

        url = urlreverse(
            "ietf.doc.views_ballot.send_ballot_comment",
            kwargs=dict(name=draft.name, ballot_id=ballot.pk),
        )

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        r = self.client.post(
            url,
            dict(
                cc_choices=["doc_authors", "doc_group_chairs", "doc_group_mail_list"],
                body="Stuff",
            ),
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(len(outbox), 1)


class NobodyTests(TestCase):
    def setUp(self):
        super().setUp()
        self.draft = EditorialDraftFactory()
        self.ballot = BallotDocEventFactory(
            doc=self.draft, ballot_type__slug="rsab-approve"
        )
        BallotPositionDocEventFactory(
            ballot=self.ballot,
            by=get_active_rsab()[0],
            pos_id="yes",
            comment="b2390sn3",
        )

    def can_see_RSAB_tab(self):
        url = urlreverse(
            "ietf.doc.views_doc.document_rsab_ballot", kwargs=dict(name=self.draft.name)
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertIn("b2390sn3", unicontent(r))

    def test_cant_take_position_on_irtf_ballot(self):

        url = urlreverse(
            "ietf.doc.views_ballot.edit_position",
            kwargs=dict(name=self.draft.name, ballot_id=self.ballot.pk),
        )

        r = self.client.get(url)
        self.assertEqual(r.status_code, 302)
        self.assertIn("/accounts/login", r["Location"])

        r = self.client.post(
            url,
            dict(position="yes", comment="oib239sb", send_mail="Save and send email"),
        )
        self.assertEqual(r.status_code, 302)
        self.assertIn("/accounts/login", r["Location"])
