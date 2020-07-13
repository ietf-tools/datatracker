# Copyright The IETF Trust 2019, All Rights Reserved
# -*- coding: utf-8 -*-


# import datetime
# from pyquery import PyQuery

import debug                            # pyflakes:ignore

import datetime

from django.urls import reverse as urlreverse

from ietf.utils.mail import outbox, empty_outbox, get_payload_text
from ietf.utils.test_utils import TestCase, unicontent, login_testing_unauthorized
from ietf.doc.factories import IndividualDraftFactory, WgDraftFactory, RgDraftFactory, RgRfcFactory, BallotDocEventFactory, IRSGBallotDocEventFactory, BallotPositionDocEventFactory
from ietf.doc.models import BallotDocEvent, BallotPositionDocEvent
from ietf.doc.utils import create_ballot_if_not_open, close_ballot
from ietf.person.utils import get_active_irsg, get_active_ads
from ietf.group.factories import RoleFactory
from ietf.person.models import Person


class IssueIRSGBallotTests(TestCase):

    def test_issue_ballot_button(self):

        # creates empty drafts with lots of values filled in
        individual_draft = IndividualDraftFactory()
        wg_draft = WgDraftFactory()
        rg_draft = RgDraftFactory()
        rg_rfc = RgRfcFactory()

        # login as an IRTF chair
        self.client.login(username='irtf-chair', password='irtf-chair+password')

        url = urlreverse('ietf.doc.views_doc.document_main',kwargs=dict(name=individual_draft.name))
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        self.assertNotIn("Issue IRSG ballot", unicontent(r))

        url = urlreverse('ietf.doc.views_doc.document_main',kwargs=dict(name=wg_draft.name))
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        self.assertNotIn("Issue IRSG ballot", unicontent(r))

        url = urlreverse('ietf.doc.views_doc.document_main',kwargs=dict(name=rg_draft.name))
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        self.assertIn("Issue IRSG ballot", unicontent(r))

        url = urlreverse('ietf.doc.views_doc.document_main',kwargs=dict(name=rg_rfc.name))
        r = self.client.get(url, follow = True)
        self.assertEqual(r.status_code,200)
        self.assertNotIn("Issue IRSG ballot", unicontent(r))        

        self.client.logout()
        url = urlreverse('ietf.doc.views_doc.document_main',kwargs=dict(name=rg_draft.name))
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        self.assertNotIn("Issue IRSG ballot", unicontent(r))

    def test_close_ballot_button(self):

        # creates empty drafts with lots of values filled in
        rg_draft1 = RgDraftFactory()
        rg_draft2 = RgDraftFactory()
        rg_rfc = RgRfcFactory()
        iesgmember = get_active_ads()[0]

        # Login as the IRTF chair
        self.client.login(username='irtf-chair', password='irtf-chair+password')

        # Set the two IRTF ballots in motion

        # Get the page with the Issue IRSG Ballot Yes/No buttons
        url = urlreverse('ietf.doc.views_ballot.issue_irsg_ballot',kwargs=dict(name=rg_draft1.name))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        # Press the Yes button
        r = self.client.post(url,dict(irsg_button="Yes", duedate="2038-01-19"))
        self.assertEqual(r.status_code, 302)
        self.assertTrue(rg_draft1.ballot_open('irsg-approve'))

        # Get the page with the Issue IRSG Ballot Yes/No buttons
        url = urlreverse('ietf.doc.views_ballot.issue_irsg_ballot',kwargs=dict(name=rg_draft2.name))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        # Press the Yes button
        r = self.client.post(url,dict(irsg_button="Yes", duedate="2038-01-18"))
        self.assertEqual(r.status_code, 302)
        self.assertTrue(rg_draft2.ballot_open('irsg-approve'))

        # Logout - the Close button should not be available
        self.client.logout()
        url = urlreverse('ietf.doc.views_doc.document_main',kwargs=dict(name=rg_draft1.name))
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        self.assertNotIn("Close IRSG ballot", unicontent(r))

        # Login as an IESG member to see if the ballot close button appears
        self.client.login(username=iesgmember.user.username, password=iesgmember.user.username+"password")
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        self.assertNotIn("Close IRSG ballot", unicontent(r))

        # Try to get the ballot closing page directly
        url = urlreverse('ietf.doc.views_ballot.close_irsg_ballot',kwargs=dict(name=rg_draft1.name))
        r = self.client.get(url)
        self.assertNotEqual(r.status_code, 200)

        self.client.logout()

        # Login again as the IRTF chair
        self.client.login(username='irtf-chair', password='irtf-chair+password')

        # The close button should now be available
        url = urlreverse('ietf.doc.views_doc.document_main',kwargs=dict(name=rg_draft1.name))
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        self.assertIn("Close IRSG ballot", unicontent(r))

        # Get the page with the Close IRSG Ballot Yes/No buttons
        url = urlreverse('ietf.doc.views_ballot.close_irsg_ballot',kwargs=dict(name=rg_draft1.name))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        # Press the Yes button
        r = self.client.post(url,dict(irsg_button="Yes"))
        self.assertEqual(r.status_code,302)
        # Expect the draft not to have an open IRSG ballot anymore
        self.assertFalse(rg_draft1.ballot_open('irsg-approve'))

        # Login as the Secretariat
        self.client.login(username='secretary', password='secretary+password')

        # The close button should now be available
        url = urlreverse('ietf.doc.views_doc.document_main',kwargs=dict(name=rg_draft2.name))
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        self.assertIn("Close IRSG ballot", unicontent(r))

        # Get the page with the Close IRSG Ballot Yes/No buttons
        url = urlreverse('ietf.doc.views_ballot.close_irsg_ballot',kwargs=dict(name=rg_draft2.name))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        # Press the Yes button
        r = self.client.post(url,dict(irsg_button="Yes"))
        self.assertEqual(r.status_code,302)
        # Expect the draft not to have an open IRSG ballot anymore
        self.assertFalse(rg_draft2.ballot_open('irsg-approve'))

        # Individual, IETF, and RFC docs should not show the Close button.  Sample test using IRTF RFC:
        url = urlreverse('ietf.doc.views_doc.document_main',kwargs=dict(name=rg_rfc.name))
        r = self.client.get(url, follow = True)
        self.assertEqual(r.status_code,200)
        self.assertNotIn("Close IRSG ballot", unicontent(r))        


    def test_issue_ballot(self):

        # Just testing IRTF drafts
        rg_draft1 = RgDraftFactory()
        rg_draft2 = RgDraftFactory()
        iesgmember = get_active_ads()[0]

        # login as an IRTF chair (who is a user who can issue an IRSG ballot)
        self.client.login(username='irtf-chair', password='irtf-chair+password')

        # Get the page with the Issue IRSG Ballot Yes/No buttons
        url = urlreverse('ietf.doc.views_ballot.issue_irsg_ballot',kwargs=dict(name=rg_draft1.name))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        # Buttons present?
        self.assertIn("irsg_button", unicontent(r))

        # Press the No button - expect nothing but a redirect back to the draft's main page
        r = self.client.post(url,dict(irsg_button="No"))
        self.assertEqual(r.status_code, 302)

        # Press the Yes button
        r = self.client.post(url,dict(irsg_button="Yes", duedate="2038-01-19"))
        self.assertEqual(r.status_code, 302)
        ballot_created = list(BallotDocEvent.objects.filter(doc=rg_draft1,
                                                type="created_ballot"))
        self.assertNotEqual(len(ballot_created), 0)

        # Having issued a ballot, the Issue IRSG ballot button should be gone
        url = urlreverse('ietf.doc.views_doc.document_main',kwargs=dict(name=rg_draft1.name))
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        self.assertNotIn("Issue IRSG ballot", unicontent(r))

        # The IRSG evaluation record tab should exist
        self.assertIn("IRSG evaluation record", unicontent(r))
        # The IRSG evaluation record tab should not indicate unavailability
        self.assertNotIn("IRSG Evaluation Ballot has not been created yet", unicontent(r))

        # We should find an IRSG member's name on the IRSG evaluation tab regardless of any positions taken or not
        url = urlreverse('ietf.doc.views_doc.document_irsg_ballot',kwargs=dict(name=rg_draft1.name))
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        irsgmembers = get_active_irsg()
        self.assertNotEqual(len(irsgmembers), 0)
        self.assertIn(irsgmembers[0].name, unicontent(r))

        # Having issued a ballot, it should appear on the IRSG Ballot Status page
        url = urlreverse('ietf.doc.views_ballot.irsg_ballot_status')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        # Does the draft name appear on the page?
        self.assertIn(rg_draft1.name, unicontent(r))

        self.client.logout()

        # Test that an IESG member cannot issue an IRSG ballot
        self.client.login(username=iesgmember.user.username, password=iesgmember.user.username+"password")

        url = urlreverse('ietf.doc.views_ballot.issue_irsg_ballot',kwargs=dict(name=rg_draft2.name))
        r = self.client.get(url)
        self.assertNotEqual(r.status_code, 200)
        # Buttons present?
        self.assertNotIn("irsg_button", unicontent(r))

        # Attempt to press the Yes button anyway
        r = self.client.post(url,dict(irsg_button="Yes", duedate="2038-01-19"))
        self.assertTrue(r.status_code == 302 and "/accounts/login" in r['Location'])

        self.client.logout()

        # Test that the Secretariat can issue an IRSG ballot
        self.client.login(username="secretary", password="secretary+password")

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        # Buttons present?
        self.assertIn("irsg_button", unicontent(r))

        # Press the Yes button
        r = self.client.post(url,dict(irsg_button="Yes", duedate="2038-01-19"))
        self.assertEqual(r.status_code, 302)

        self.client.logout()


    def test_edit_ballot_position_permissions(self):
        rg_draft = RgDraftFactory()
        wg_draft = WgDraftFactory()
        ad = RoleFactory(group__type_id='area',name_id='ad')
        pre_ad = RoleFactory(group__type_id='area',name_id='pre-ad')
        irsgmember = get_active_irsg()[0]
        secr = RoleFactory(group__acronym='secretariat',name_id='secr')
        wg_ballot = create_ballot_if_not_open(None, wg_draft, ad.person, 'approve')
        due = datetime.date.today()+datetime.timedelta(days=14)
        rg_ballot = create_ballot_if_not_open(None, rg_draft, secr.person, 'irsg-approve', due)

        url = urlreverse('ietf.doc.views_ballot.edit_position', kwargs=dict(name=wg_draft.name, ballot_id=wg_ballot.pk))

        # Pre-ADs can see
        login_testing_unauthorized(self, pre_ad.person.user.username, url)

        # But Pre-ADs cannot take a position
        r = self.client.post(url, dict(position="discuss", discuss="Test discuss text"))
        self.assertEqual(r.status_code, 403)

        self.client.logout()

        # ADs can see and take a position
        login_testing_unauthorized(self, ad.person.user.username, url)
        r = self.client.post(url, dict(position="discuss", discuss="Test discuss text"))
        self.assertTrue(r.status_code == 302 and "/accounts/login" not in r['Location'])

        # IESG members should not be able to take positions on IRSG ballots
        url = urlreverse('ietf.doc.views_ballot.edit_position', kwargs=dict(name=rg_draft.name, ballot_id=rg_ballot.pk))
        r = self.client.post(url, dict(position="yes"))
        self.assertEqual(r.status_code, 403)
        self.client.logout()

        # IRSG members should be able to enter a position on IRSG ballots
        login_testing_unauthorized(self, irsgmember.user.username, url)
        r = self.client.post(url, dict(position="yes"))
        self.assertTrue(r.status_code == 302 and "/accounts/login" not in r['Location'])


    def test_iesg_ballot_no_irsg_actions(self):
        ad = Person.objects.get(user__username="ad")
        wg_draft = IndividualDraftFactory(ad=ad)
        irsgmember = get_active_irsg()[0]

        url = urlreverse('ietf.doc.views_ballot.ballot_writeupnotes', kwargs=dict(name=wg_draft.name))

        # IRSG members should not be able to issue IESG ballots
        login_testing_unauthorized(self, irsgmember.user.username, url)
        r = self.client.post(url, dict(
            ballot_writeup="This is a test.",
            issue_ballot="1"))
        self.assertNotEqual(r.status_code, 200)

        self.client.logout()
        login_testing_unauthorized(self, "ad", url)

        # But IESG members can
        r = self.client.post(url, dict(
            ballot_writeup="This is a test.",
            issue_ballot="1"))
        self.assertEqual(r.status_code, 200)

        self.client.logout()

        # Now that the ballot is issued, see if an IRSG member can take a position or close the ballot
        ballot = wg_draft.active_ballot()
        url = urlreverse('ietf.doc.views_ballot.edit_position', kwargs=dict(name=wg_draft.name, ballot_id=ballot.pk))
        login_testing_unauthorized(self, irsgmember.user.username, url)

        r = self.client.post(url, dict(position="discuss", discuss="Test discuss text"))
        self.assertEqual(r.status_code, 403)

class BaseManipulationTests():

    def test_issue_ballot(self):
        draft = RgDraftFactory()
        url = urlreverse('ietf.doc.views_ballot.issue_irsg_ballot',kwargs=dict(name=draft.name))
        due = datetime.date.today()+datetime.timedelta(days=14)
        empty_outbox()

        login_testing_unauthorized(self, self.username , url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        r = self.client.post(url,{'irsg_button':'No', 'duedate':due })
        self.assertEqual(r.status_code, 302)
        self.assertIsNone(draft.ballot_open('irsg-approve'))

        # No notifications should have been generated yet
        self.assertEqual(len(outbox), 0)

        r = self.client.post(url,{'irsg_button':'Yes', 'duedate':due })
        self.assertEqual(r.status_code,302)
        self.assertIsNotNone(draft.ballot_open('irsg-approve'))

        # Should have sent a notification about the new ballot
        self.assertEqual(len(outbox), 1)
        msg = outbox[0]
        self.assertIn('IRSG ballot issued', msg['Subject'])
        self.assertIn('iesg-secretary@ietf.org', msg['From'])
        # Notifications are also sent to various doc-related addresses, not tested here
        self.assertIn('irsg@irtf.org', msg['To'])
        self.assertIn('irtf-chair@irtf.org', msg['CC'])
        self.assertIn(str(due), get_payload_text(msg))  # ensure duedate is included

    def test_take_and_email_position(self):
        draft = RgDraftFactory()
        ballot = IRSGBallotDocEventFactory(doc=draft)
        url = urlreverse('ietf.doc.views_ballot.edit_position', kwargs=dict(name=draft.name, ballot_id=ballot.pk)) + self.balloter
        empty_outbox()

        login_testing_unauthorized(self, self.username, url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        r = self.client.post(url, dict(position='yes', comment='oib239sb', send_mail='Save and send email'))
        self.assertEqual(r.status_code, 302)
        e = draft.latest_event(BallotPositionDocEvent)
        self.assertEqual(e.pos.slug,'yes')
        self.assertEqual(e.comment, 'oib239sb')

        url = urlreverse('ietf.doc.views_ballot.send_ballot_comment', kwargs=dict(name=draft.name, ballot_id=ballot.pk)) + self.balloter

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        r = self.client.post(url, dict(cc_choices=['doc_authors','doc_group_chairs','doc_group_mail_list'], body="Stuff"))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(len(outbox),1)
        self.assertNotIn('discuss-criteria', get_payload_text(outbox[0]))

    def test_close_ballot(self):
        draft = RgDraftFactory()
        IRSGBallotDocEventFactory(doc=draft)
        url = urlreverse('ietf.doc.views_ballot.close_irsg_ballot', kwargs=dict(name=draft.name))
        empty_outbox()

        login_testing_unauthorized(self, self.username, url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        r = self.client.post(url,dict(irsg_button='No'))
        self.assertEqual(r.status_code, 302)
        self.assertIsNotNone(draft.ballot_open('irsg-approve'))

        # Should not have generated a notification yet
        self.assertEqual(len(outbox), 0)

        r = self.client.post(url,dict(irsg_button='Yes'))
        self.assertEqual(r.status_code, 302)
        self.assertIsNone(draft.ballot_open('irsg-approve'))

        # Closing the ballot should have generated a notification
        self.assertEqual(len(outbox), 1)
        msg = outbox[0]
        self.assertIn('IRSG ballot closed', msg['Subject'])
        self.assertIn('iesg-secretary@ietf.org', msg['From'])
        # Notifications are also sent to various doc-related addresses, not tested here
        self.assertIn('irsg@irtf.org', msg['To'])
        self.assertIn('irtf-chair@irtf.org', msg['CC'])

    def test_view_outstanding_ballots(self):
        draft = RgDraftFactory()
        IRSGBallotDocEventFactory(doc=draft)
        url = urlreverse('ietf.doc.views_ballot.irsg_ballot_status')

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertIn(draft.name, unicontent(r))

        close_ballot(draft, Person.objects.get(user__username=self.username), 'irsg-approve')
        r = self.client.get(url)
        self.assertNotIn(draft.name, unicontent(r))


class IRTFChairTests(BaseManipulationTests, TestCase):

    def setUp(self):
        self.username = 'irtf-chair'
        self.balloter = ''

class SecretariatTests(BaseManipulationTests, TestCase):

    def setUp(self):
        self.username = 'secretary'
        self.balloter = '?balloter={}'.format(Person.objects.get(user__username='irtf-chair').pk)


class IRSGMemberTests(TestCase):

    def setUp(self):
        self.username = get_active_irsg()[0].user.username

    def test_cant_issue_irsg_ballot(self):
        draft = RgDraftFactory()
        due = datetime.date.today()+datetime.timedelta(days=14)
        url = urlreverse('ietf.doc.views_ballot.close_irsg_ballot', kwargs=dict(name=draft.name))

        self.client.login(username = self.username, password = self.username+'+password')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 403)

        r = self.client.post(url,{'irsg_button':'Yes', 'duedate':due })
        self.assertEqual(r.status_code, 403)

    def test_cant_close_irsg_ballot(self):
        draft = RgDraftFactory()
        IRSGBallotDocEventFactory(doc=draft)
        url = urlreverse('ietf.doc.views_ballot.close_irsg_ballot', kwargs=dict(name=draft.name))

        self.client.login(username = self.username, password = self.username+'+password')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 403)

        r = self.client.post(url,dict(irsg_button='Yes'))
        self.assertEqual(r.status_code, 403)

    def test_cant_take_position_on_iesg_ballot(self):
        draft = WgDraftFactory()
        ballot = BallotDocEventFactory(doc=draft)
        url = urlreverse('ietf.doc.views_ballot.edit_position', kwargs=dict(name=draft.name, ballot_id=ballot.pk))

        self.client.login(username = self.username, password = self.username+'+password')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        r = self.client.post(url, dict(position='yes', comment='oib239sb', send_mail='Save and send email'))
        self.assertEqual(r.status_code, 403)

    def test_take_and_email_position(self):
        draft = RgDraftFactory()
        ballot = IRSGBallotDocEventFactory(doc=draft)
        url = urlreverse('ietf.doc.views_ballot.edit_position', kwargs=dict(name=draft.name, ballot_id=ballot.pk))
        empty_outbox()

        login_testing_unauthorized(self, self.username, url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        r = self.client.post(url, dict(position='yes', comment='oib239sb', send_mail='Save and send email'))
        self.assertEqual(r.status_code, 302)
        e = draft.latest_event(BallotPositionDocEvent)
        self.assertEqual(e.pos.slug,'yes')
        self.assertEqual(e.comment, 'oib239sb')

        url = urlreverse('ietf.doc.views_ballot.send_ballot_comment', kwargs=dict(name=draft.name, ballot_id=ballot.pk))

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        r = self.client.post(url, dict(cc_choices=['doc_authors','doc_group_chairs','doc_group_mail_list'], body="Stuff"))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(len(outbox),1)

class IESGMemberTests(TestCase):

    def test_cant_take_position_on_irtf_ballot(self):
        draft = RgDraftFactory()
        ballot = IRSGBallotDocEventFactory(doc=draft)
        url = urlreverse('ietf.doc.views_ballot.edit_position', kwargs=dict(name=draft.name, ballot_id=ballot.pk))

        self.assertEqual(self.client.login(username = 'ad', password = 'ad+password'), True)
        
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        r = self.client.post(url, dict(position='yes', comment='oib239sb', send_mail='Save and send email'))
        self.assertEqual(r.status_code, 403)

class NobodyTests(TestCase):

    def can_see_IRSG_tab(self):
        draft=RgDraftFactory()
        ballot = IRSGBallotDocEventFactory(doc=draft)
        BallotPositionDocEventFactory(ballot=ballot, by=get_active_irsg()[0], pos_id='yes', comment='b2390sn3')

        url = urlreverse('ietf.doc.views_doc.document_irsg_ballot',kwargs=dict(name=draft.name))
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        self.assertIn('b2390sn3',unicontent(r))

    def test_cant_take_position_on_irtf_ballot(self):
        draft = RgDraftFactory()
        ballot = IRSGBallotDocEventFactory(doc=draft)
        url = urlreverse('ietf.doc.views_ballot.edit_position', kwargs=dict(name=draft.name, ballot_id=ballot.pk))

        r = self.client.get(url)
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/login', r['Location'])

        r = self.client.post(url, dict(position='yes', comment='oib239sb', send_mail='Save and send email'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/login', r['Location'])
