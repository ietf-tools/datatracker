# Copyright The IETF Trust 2013-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime
import mock

from pyquery import PyQuery

import debug                            # pyflakes:ignore

from django.test import RequestFactory
from django.utils.text import slugify
from django.urls import reverse as urlreverse
from django.utils import timezone

from ietf.doc.models import (Document, State, DocEvent,
                             BallotPositionDocEvent, LastCallDocEvent, WriteupDocEvent, TelechatDocEvent)
from ietf.doc.factories import (DocumentFactory, IndividualDraftFactory, IndividualRfcFactory, WgDraftFactory,
                                BallotPositionDocEventFactory, BallotDocEventFactory, IRSGBallotDocEventFactory)
from ietf.doc.templatetags.ietf_filters import can_defer
from ietf.doc.utils import create_ballot_if_not_open
from ietf.doc.views_ballot import parse_ballot_edit_return_point
from ietf.doc.views_doc import document_ballot_content
from ietf.group.models import Group, Role
from ietf.group.factories import GroupFactory, RoleFactory, ReviewTeamFactory
from ietf.ipr.factories import HolderIprDisclosureFactory
from ietf.name.models import BallotPositionName
from ietf.iesg.models import TelechatDate
from ietf.person.models import Person, PersonalApiKey
from ietf.person.factories import PersonFactory
from ietf.person.utils import get_active_ads
from ietf.utils.test_utils import TestCase, login_testing_unauthorized
from ietf.utils.mail import outbox, empty_outbox, get_payload_text
from ietf.utils.text import unwrap
from ietf.utils.timezone import date_today, datetime_today


class EditPositionTests(TestCase):
    def test_edit_position(self):
        ad = Person.objects.get(user__username="ad")
        draft = IndividualDraftFactory(ad=ad,stream_id='ietf')
        ballot = create_ballot_if_not_open(None, draft, ad, 'approve')
        url = urlreverse('ietf.doc.views_ballot.edit_position', kwargs=dict(name=draft.name,
                                                          ballot_id=ballot.pk))
        login_testing_unauthorized(self, "ad", url)

        ad = Person.objects.get(name="Areað Irector")
        
        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form input[name=position]')) > 0)
        self.assertEqual(len(q('form textarea[name=comment]')), 1)

        # vote
        events_before = draft.docevent_set.count()
        
        r = self.client.post(url, dict(position="discuss",
                                       discuss=" This is a discussion test. \n ",
                                       comment=" This is a test. \n "))
        self.assertEqual(r.status_code, 302)

        pos = draft.latest_event(BallotPositionDocEvent, balloter=ad)
        self.assertEqual(pos.pos.slug, "discuss")
        self.assertTrue(" This is a discussion test." in pos.discuss)
        self.assertTrue(pos.discuss_time != None)
        self.assertTrue(" This is a test." in pos.comment)
        self.assertTrue(pos.comment_time != None)
        self.assertTrue("New position" in pos.desc)
        self.assertEqual(draft.docevent_set.count(), events_before + 3)

        # recast vote
        events_before = draft.docevent_set.count()
        r = self.client.post(url, dict(position="noobj"))
        self.assertEqual(r.status_code, 302)

        draft = Document.objects.get(name=draft.name)
        pos = draft.latest_event(BallotPositionDocEvent, balloter=ad)
        self.assertEqual(pos.pos.slug, "noobj")
        self.assertEqual(draft.docevent_set.count(), events_before + 1)
        self.assertTrue("Position for" in pos.desc)
        
        # clear vote
        events_before = draft.docevent_set.count()
        r = self.client.post(url, dict(position="norecord"))
        self.assertEqual(r.status_code, 302)

        draft = Document.objects.get(name=draft.name)
        pos = draft.latest_event(BallotPositionDocEvent, balloter=ad)
        self.assertEqual(pos.pos.slug, "norecord")
        self.assertEqual(draft.docevent_set.count(), events_before + 1)
        self.assertTrue("Position for" in pos.desc)

        # change comment
        events_before = draft.docevent_set.count()
        r = self.client.post(url, dict(position="norecord", comment="New comment."))
        self.assertEqual(r.status_code, 302)

        draft = Document.objects.get(name=draft.name)
        pos = draft.latest_event(BallotPositionDocEvent, balloter=ad)
        self.assertEqual(pos.pos.slug, "norecord")
        self.assertEqual(draft.docevent_set.count(), events_before + 2)
        self.assertTrue("Ballot comment text updated" in pos.desc)
        
    def test_api_set_position(self):
        ad = Person.objects.get(name="Areað Irector")
        draft = WgDraftFactory(ad=ad)
        url = urlreverse('ietf.doc.views_ballot.api_set_position')
        create_ballot_if_not_open(None, draft, ad, 'approve')
        ad.user.last_login = timezone.now()
        ad.user.save()
        apikey = PersonalApiKey.objects.create(endpoint=url, person=ad)

        # vote
        events_before = draft.docevent_set.count()
        mailbox_before = len(outbox)

        r = self.client.post(url, dict(
                                        apikey=apikey.hash(),
                                        doc=draft.name,
                                        position="discuss",
                                        discuss=" This is a discussion test. \n ",
                                        comment=" This is a test. \n ")
            )
        self.assertContains(r, "Done")

        pos = draft.latest_event(BallotPositionDocEvent, balloter=ad)
        self.assertEqual(pos.pos.slug, "discuss")
        self.assertTrue(" This is a discussion test." in pos.discuss)
        self.assertTrue(pos.discuss_time != None)
        self.assertTrue(" This is a test." in pos.comment)
        self.assertTrue(pos.comment_time != None)
        self.assertTrue("New position" in pos.desc)
        self.assertEqual(draft.docevent_set.count(), events_before + 3)
        self.assertEqual(len(outbox), mailbox_before + 1)

        # recast vote
        events_before = draft.docevent_set.count()
        mailbox_before = len(outbox)
        r = self.client.post(url, dict(apikey=apikey.hash(), doc=draft.name, position="noobj"))
        self.assertEqual(r.status_code, 200)

        draft = Document.objects.get(name=draft.name)
        pos = draft.latest_event(BallotPositionDocEvent, balloter=ad)
        self.assertEqual(pos.pos.slug, "noobj")
        self.assertEqual(draft.docevent_set.count(), events_before + 1)
        self.assertTrue("Position for" in pos.desc)
        self.assertEqual(len(outbox), mailbox_before + 1)
        m = outbox[-1]
        self.assertIn('No Objection', m['Subject'])
        self.assertIn('iesg@', m['To'])
        self.assertIn(draft.name, m['Cc'])
        self.assertIn(draft.group.acronym+'-chairs@', m['Cc'])

        # clear vote
        events_before = draft.docevent_set.count()
        mailbox_before = len(outbox)
        r = self.client.post(url, dict(apikey=apikey.hash(), doc=draft.name, position="norecord"))
        self.assertEqual(r.status_code, 200)

        draft = Document.objects.get(name=draft.name)
        pos = draft.latest_event(BallotPositionDocEvent, balloter=ad)
        self.assertEqual(pos.pos.slug, "norecord")
        self.assertEqual(draft.docevent_set.count(), events_before + 1)
        self.assertTrue("Position for" in pos.desc)
        self.assertEqual(len(outbox), mailbox_before + 1)
        m = outbox[-1]
        self.assertIn('No Record', m['Subject'])

        # change comment
        events_before = draft.docevent_set.count()
        mailbox_before = len(outbox)
        r = self.client.post(url, dict(apikey=apikey.hash(), doc=draft.name, position="norecord", comment="New comment."))
        self.assertEqual(r.status_code, 200)

        draft = Document.objects.get(name=draft.name)
        pos = draft.latest_event(BallotPositionDocEvent, balloter=ad)
        self.assertEqual(pos.pos.slug, "norecord")
        self.assertEqual(draft.docevent_set.count(), events_before + 2)
        self.assertTrue("Ballot comment text updated" in pos.desc)
        self.assertEqual(len(outbox), mailbox_before + 1)
        m = outbox[-1]
        self.assertIn('COMMENT', m['Subject'])
        self.assertIn('New comment', get_payload_text(m))


    def test_edit_position_as_secretary(self):
        draft = IndividualDraftFactory()
        ad = Person.objects.get(user__username="ad")
        ballot = create_ballot_if_not_open(None, draft, ad, 'approve')
        url = urlreverse('ietf.doc.views_ballot.edit_position', kwargs=dict(name=draft.name, ballot_id=ballot.pk))
        ad = Person.objects.get(name="Areað Irector")
        url += "?balloter=%s" % ad.pk
        login_testing_unauthorized(self, "secretary", url)

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form input[name=position]')) > 0)

        # vote on behalf of AD
        # events_before = draft.docevent_set.count()
        r = self.client.post(url, dict(position="discuss", discuss="Test discuss text"))
        self.assertEqual(r.status_code, 302)

        pos = draft.latest_event(BallotPositionDocEvent, balloter=ad)
        self.assertEqual(pos.pos.slug, "discuss")
        self.assertEqual(pos.discuss, "Test discuss text")
        self.assertTrue("New position" in pos.desc)
        self.assertTrue("by Sec" in pos.desc)

    def test_cannot_edit_position_as_pre_ad(self):
        draft = IndividualDraftFactory()
        ad = Person.objects.get(user__username="ad")
        ballot = create_ballot_if_not_open(None, draft, ad, 'approve')
        url = urlreverse('ietf.doc.views_ballot.edit_position', kwargs=dict(name=draft.name, ballot_id=ballot.pk))
        
        # transform to pre-ad
        ad_role = Role.objects.filter(name="ad")[0]
        ad_role.name_id = "pre-ad"
        ad_role.save()

        # we can see
        login_testing_unauthorized(self, ad_role.person.user.username, url)

        # but not touch
        r = self.client.post(url, dict(position="discuss", discuss="Test discuss text"))
        self.assertEqual(r.status_code, 403)
        
    # N.B. This test needs to be rewritten to exercise all types of ballots (iesg, irsg, rsab)
    # and test against the output of the mailtriggers instead of looking for hardcoded values
    # in the To and CC results. See #7864
    def test_send_ballot_comment(self):
        ad = Person.objects.get(user__username="ad")
        draft = WgDraftFactory(ad=ad,group__acronym='mars')
        draft.notify = "somebody@example.com"
        draft.save_with_history([DocEvent.objects.create(doc=draft, rev=draft.rev, type="changed_document", by=Person.objects.get(user__username="secretary"), desc="Test")])

        ballot = create_ballot_if_not_open(None, draft, ad, 'approve')

        BallotPositionDocEvent.objects.create(
            doc=draft, rev=draft.rev, type="changed_ballot_position",
            by=ad, balloter=ad, ballot=ballot, pos=BallotPositionName.objects.get(slug="discuss"),
            discuss="This draft seems to be lacking a clearer title?",
            discuss_time=timezone.now(),
            comment="Test!",
            comment_time=timezone.now())
        
        url = urlreverse('ietf.doc.views_ballot.send_ballot_comment', kwargs=dict(name=draft.name,
                                                                ballot_id=ballot.pk))
        login_testing_unauthorized(self, "ad", url)

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form input[name="extra_cc"]')) > 0)

        # send
        mailbox_before = len(outbox)

        r = self.client.post(url, dict(extra_cc="test298347@example.com", cc_choices=['doc_notify','doc_group_chairs']))
        self.assertEqual(r.status_code, 302)

        self.assertEqual(len(outbox), mailbox_before + 1)
        m = outbox[-1]
        self.assertTrue("COMMENT" in m['Subject'])
        self.assertTrue("DISCUSS" in m['Subject'])
        self.assertTrue(draft.name in m['Subject'])
        self.assertTrue("clearer title" in str(m))
        self.assertTrue("Test!" in str(m))
        self.assertTrue("iesg@" in m['To'])
        # cc_choice doc_group_chairs
        self.assertTrue("mars-chairs@" in m['Cc'])
        # cc_choice doc_notify
        self.assertTrue("somebody@example.com" in m['Cc'])
        # cc_choice doc_group_email_list was not selected
        self.assertFalse(draft.group.list_email in m['Cc'])
        # extra-cc    
        self.assertTrue("test298347@example.com" in m['Cc'])

        r = self.client.post(url, dict(cc=""))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(len(outbox), mailbox_before + 2)
        m = outbox[-1]
        self.assertTrue("iesg@" in m['To'])
        self.assertFalse(m['Cc'] and draft.group.list_email in m['Cc'])


class BallotWriteupsTests(TestCase):
    def test_edit_last_call_text(self):
        draft = IndividualDraftFactory(ad=Person.objects.get(user__username='ad'),states=[('draft','active'),('draft-iesg','ad-eval')])
        url = urlreverse('ietf.doc.views_ballot.lastcalltext', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "secretary", url)

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('textarea[name=last_call_text]')), 1)
        self.assertTrue(q('[type=submit]:contains("Save")'))
        # we're Secretariat, so we got The Link
        self.assertEqual(len(q('a:contains("Issue last call")')), 1)
        
        # subject error
        r = self.client.post(url, dict(
                last_call_text="Subject: test\r\nhello\r\n\r\n",
                save_last_call_text="1"))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form .is-invalid')) > 0)

        # save
        r = self.client.post(url, dict(
                last_call_text="This is a simple test.",
                save_last_call_text="1"))
        self.assertEqual(r.status_code, 200)
        draft = Document.objects.get(name=draft.name)
        self.assertTrue("This is a simple test" in draft.latest_event(WriteupDocEvent, type="changed_last_call_text").text)

        # test regenerate
        r = self.client.post(url, dict(
                last_call_text="This is a simple test.",
                regenerate_last_call_text="1"))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        text = q("[name=last_call_text]").text()
        self.assertTrue("Subject: Last Call" in text)


    def test_request_last_call(self):
        ad = Person.objects.get(user__username="ad")
        draft = IndividualDraftFactory(ad=ad,states=[('draft-iesg','iesg-eva')])
        url = urlreverse('ietf.doc.views_ballot.lastcalltext', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "secretary", url)

        # give us an announcement to send
        r = self.client.post(url, dict(regenerate_last_call_text="1"))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        text = q("[name=last_call_text]").text()

        mailbox_before = len(outbox)

        # send
        r = self.client.post(url, dict(
                last_call_text=text,
                send_last_call_request="1"))
        draft = Document.objects.get(name=draft.name)
        self.assertEqual(draft.get_state_slug("draft-iesg"), "lc-req")
        self.assertCountEqual(draft.action_holders.all(), [ad])
        self.assertIn('Changed action holders', draft.latest_event(type='changed_action_holders').desc)
        self.assertEqual(len(outbox), mailbox_before + 1)
        self.assertTrue("Last Call" in outbox[-1]['Subject'])
        self.assertTrue(draft.name in outbox[-1]['Subject'])
        self.assertTrue('iesg-secretary@' in outbox[-1]['To'])
        self.assertTrue('aread@' in outbox[-1]['Cc'])

    def test_edit_ballot_writeup(self):
        draft = IndividualDraftFactory(states=[('draft','active'),('draft-iesg','iesg-eva')])
        url = urlreverse('ietf.doc.views_ballot.ballot_writeupnotes', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "secretary", url)

        # add a IANA review note
        draft.set_state(State.objects.get(used=True, type="draft-iana-review", slug="not-ok"))
        DocEvent.objects.create(type="iana_review",
                                doc=draft,
                                rev=draft.rev,
                                by=Person.objects.get(user__username="iana"),
                                desc="IANA does not approve of this document, it does not make sense.",
                                )

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('textarea[name=ballot_writeup]')), 1)
        self.assertTrue(q('[type=submit]:contains("Save")'))
        self.assertContains(r, "IANA does not")

        # save
        r = self.client.post(url, dict(
                ballot_writeup="This is a simple test.",
                save_ballot_writeup="1"))
        self.assertEqual(r.status_code, 200)
        d = Document.objects.get(name=draft.name)
        self.assertTrue("This is a simple test" in d.latest_event(WriteupDocEvent, type="changed_ballot_writeup_text").text)
        self.assertTrue('iesg-eva' == d.get_state_slug('draft-iesg'))

    def test_edit_ballot_writeup_already_approved(self):
        draft = IndividualDraftFactory(states=[('draft','active'),('draft-iesg','approved')])
        url = urlreverse('ietf.doc.views_ballot.ballot_writeupnotes', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "secretary", url)

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('textarea[name=ballot_writeup]')), 1)
        self.assertTrue(q('[type=submit]:contains("Save")'))

        # save
        r = self.client.post(url, dict(
                ballot_writeup="This is a simple test.",
                save_ballot_writeup="1"))
        self.assertEqual(r.status_code, 200)
        d = Document.objects.get(name=draft.name)
        self.assertTrue('approved' == d.get_state_slug('draft-iesg'))

    def test_edit_ballot_rfceditornote(self):
        draft = IndividualDraftFactory()
        url = urlreverse('ietf.doc.views_ballot.ballot_rfceditornote', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "secretary", url)

        # add a note to the RFC Editor
        WriteupDocEvent.objects.create(
            doc=draft,
            rev=draft.rev,
            desc="Changed text",
            type="changed_rfc_editor_note_text",
            text="This is a note for the RFC Editor.",
            by=Person.objects.get(name="(System)"))

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('textarea[name=rfc_editor_note]')), 1)
        self.assertTrue(q('[type=submit]:contains("Save")'))
        self.assertContains(r, "<label class=\"form-label\">RFC Editor Note</label>")
        self.assertContains(r, "This is a note for the RFC Editor")

        # save with a note
        empty_outbox()
        r = self.client.post(url, dict(
                rfc_editor_note="This is a simple test.",
                save_ballot_rfceditornote="1"))
        self.assertEqual(r.status_code, 302)
        draft = Document.objects.get(name=draft.name)
        self.assertTrue(draft.has_rfc_editor_note())
        self.assertTrue("This is a simple test" in draft.latest_event(WriteupDocEvent, type="changed_rfc_editor_note_text").text)
        self.assertEqual(len(outbox), 0)

        # clear the existing note
        r = self.client.post(url, dict(
                rfc_editor_note=" ",
                clear_ballot_rfceditornote="1"))
        self.assertEqual(r.status_code, 200)
        draft = Document.objects.get(name=draft.name)
        self.assertFalse(draft.has_rfc_editor_note())

        # Add a note after the doc is approved
        empty_outbox()
        draft.set_state(State.objects.get(type='draft-iesg',slug='approved'))
        r = self.client.post(url, dict(
                rfc_editor_note='This is a new note.',
                save_ballot_rfceditornote="1"))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(len(outbox),1)
        self.assertIn('RFC Editor note changed',outbox[-1]['Subject'])

    def test_issue_ballot(self):
        ad = Person.objects.get(user__username="ad")
        for case in ('none','past','future'):
            draft = IndividualDraftFactory(ad=ad)
            if case in ('past','future'):
                LastCallDocEvent.objects.create(
                    by=Person.objects.get(name='(System)'),
                    type='sent_last_call',
                    doc=draft,
                    rev=draft.rev,
                    desc='issued last call',
                    expires = timezone.now()+datetime.timedelta(days = 1 if case=='future' else -1)
                )
            url = urlreverse('ietf.doc.views_ballot.ballot_writeupnotes', kwargs=dict(name=draft.name))
            login_testing_unauthorized(self, "ad", url)


            empty_outbox()
            
            r = self.client.post(url, dict(
                    ballot_writeup="This is a test.",
                    issue_ballot="1"))
            self.assertEqual(r.status_code, 200)
            draft = Document.objects.get(name=draft.name)

            self.assertTrue(draft.latest_event(type="sent_ballot_announcement"))
            self.assertEqual(len(outbox), 2)
            self.assertTrue('Ballot issued:' in outbox[-2]['Subject'])
            self.assertTrue('iesg@' in outbox[-2]['To'])
            self.assertTrue('Ballot issued:' in outbox[-1]['Subject'])
            self.assertTrue('drafts-eval@' in outbox[-1]['To'])
            self.assertTrue('X-IETF-Draft-string' in outbox[-1])
            if case=='none':
                self.assertNotIn('call expire', get_payload_text(outbox[-1]))
            elif case=='past':
                self.assertIn('call expired', get_payload_text(outbox[-1]))
            else:
                self.assertIn('call expires', get_payload_text(outbox[-1]))
            self.client.logout()

    def test_issue_ballot_auto_state_change(self):
        ad = Person.objects.get(user__username="ad")
        draft = IndividualDraftFactory(ad=ad, states=[('draft','active'),('draft-iesg','writeupw')])
        url = urlreverse('ietf.doc.views_ballot.ballot_writeupnotes', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "secretary", url)

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('textarea[name=ballot_writeup]')), 1)
        self.assertFalse(q('[class=form-text]:contains("not completed IETF Last Call")'))
        self.assertTrue(q('[type=submit]:contains("Save")'))
        self.assertCountEqual(draft.action_holders.all(), [])

        # save
        r = self.client.post(url, dict(
                ballot_writeup="This is a simple test.",
                issue_ballot="1"))
        self.assertEqual(r.status_code, 200)
        d = Document.objects.get(name=draft.name)
        self.assertTrue('iesg-eva' == d.get_state_slug('draft-iesg'))
        self.assertCountEqual(draft.action_holders.all(), [ad])

    def test_issue_ballot_warn_if_early(self):
        ad = Person.objects.get(user__username="ad")
        draft = IndividualDraftFactory(ad=ad, states=[('draft','active'),('draft-iesg','lc')])
        url = urlreverse('ietf.doc.views_ballot.ballot_writeupnotes', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "secretary", url)

        # expect warning about issuing a ballot before IETF Last Call is done
        # No last call has yet been issued
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('textarea[name=ballot_writeup]')), 1)
        self.assertTrue(q('[class=text-danger]:contains("not completed IETF Last Call")'))
        self.assertTrue(q('[type=submit]:contains("Save")'))

        # Last call exists but hasn't expired
        LastCallDocEvent.objects.create(
            doc=draft,
            expires=datetime_today()+datetime.timedelta(days=14),
            by=Person.objects.get(name="(System)")
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(q('[class=text-danger]:contains("not completed IETF Last Call")'))

        # Last call exists and has expired
        LastCallDocEvent.objects.filter(doc=draft).update(expires=datetime_today()-datetime.timedelta(days=2))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertFalse(q('[class=text-danger]:contains("not completed IETF Last Call")'))

        for state_slug in ["lc", "ad-eval"]:
            draft.set_state(State.objects.get(type="draft-iesg",slug=state_slug))
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            self.assertTrue(q('[class=text-danger]:contains("It would be unexpected to issue a ballot while in this state.")'))

        draft.set_state(State.objects.get(type="draft-iesg",slug="writeupw"))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertFalse(q('[class=text-danger]:contains("It would be unexpected to issue a ballot while in this state.")'))         
                         

    def test_edit_approval_text(self):
        ad = Person.objects.get(user__username="ad")
        draft = WgDraftFactory(ad=ad,states=[('draft','active'),('draft-iesg','iesg-eva')],intended_std_level_id='ps',group__parent=Group.objects.get(acronym='farfut'))
        url = urlreverse('ietf.doc.views_ballot.ballot_approvaltext', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "secretary", url)

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('textarea[name=approval_text]')), 1)
        self.assertTrue(q('[type=submit]:contains("Save")'))

        # save
        r = self.client.post(url, dict(
                approval_text="This is a simple test.",
                save_approval_text="1"))
        self.assertEqual(r.status_code, 200)
        draft = Document.objects.get(name=draft.name)
        self.assertTrue("This is a simple test" in draft.latest_event(WriteupDocEvent, type="changed_ballot_approval_text").text)

        # test regenerate
        r = self.client.post(url, dict(regenerate_approval_text="1"))
        self.assertEqual(r.status_code, 200)
        draft = Document.objects.get(name=draft.name)        
        self.assertTrue("Subject: Protocol Action" in draft.latest_event(WriteupDocEvent, type="changed_ballot_approval_text").text)

        # test regenerate when it's a disapprove
        draft.set_state(State.objects.get(used=True, type="draft-iesg", slug="nopubadw"))

        r = self.client.post(url, dict(regenerate_approval_text="1"))
        self.assertEqual(r.status_code, 200)
        draft = Document.objects.get(name=draft.name)
        self.assertIn("NOT be published", unwrap(draft.latest_event(WriteupDocEvent, type="changed_ballot_approval_text").text))

        # test regenerate when it's a conflict review
        draft.group = Group.objects.get(type="individ")
        draft.stream_id = "irtf"
        draft.set_state(State.objects.get(used=True, type="draft-iesg", slug="iesg-eva"))
        draft.save_with_history([DocEvent.objects.create(doc=draft, rev=draft.rev, type="changed_document", by=Person.objects.get(user__username="secretary"), desc="Test")])

        r = self.client.post(url, dict(regenerate_approval_text="1"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue("Subject: Results of IETF-conflict review" in draft.latest_event(WriteupDocEvent, type="changed_ballot_approval_text").text)
        
    def test_edit_verify_permissions(self):

        def verify_fail(username, url):
            if username:
                self.client.login(username=username, password=username+"+password")
            r = self.client.get(url)
            self.assertEqual(r.status_code,403)

        def verify_can_see(username, url):
            self.client.login(username=username, password=username+"+password")
            r = self.client.get(url)
            self.assertEqual(r.status_code,200)
            q = PyQuery(r.content)
            self.assertEqual(len(q("<textarea class=\"form-control\"")),1) 

        for username in ['plain','marschairman']:
            PersonFactory(user__username=username)
        mars = GroupFactory(acronym='mars',type_id='wg')
        RoleFactory(group=mars,person=Person.objects.get(user__username='marschairman'),name_id='chair')
        ad = Person.objects.get(user__username="ad")
        draft = WgDraftFactory(group=mars,ad=ad,states=[('draft','active'),('draft-iesg','ad-eval')])

        events = []
        
        e = WriteupDocEvent()
        e.type = "changed_ballot_approval_text"
        e.by = Person.objects.get(name="(System)")
        e.doc = draft
        e.rev = draft.rev
        e.desc = "Ballot approval text was generated"
        e.text = "Test approval text."
        e.save()
        events.append(e)

        e = WriteupDocEvent()
        e.type = "changed_ballot_writeup_text"
        e.by = Person.objects.get(name="(System)")
        e.doc = draft
        e.rev = draft.rev
        e.desc = "Ballot writeup was generated"
        e.text = "Test ballot writeup text."
        e.save()
        events.append(e)

        e = WriteupDocEvent()
        e.type = "changed_ballot_rfceditornote_text"
        e.by = Person.objects.get(name="(System)")
        e.doc = draft
        e.rev = draft.rev
        e.desc = "RFC Editor Note for ballot was generated"
        e.text = "Test note to the RFC Editor text."
        e.save()
        events.append(e)

        # IETF Stream Documents
        for p in ['ietf.doc.views_ballot.ballot_approvaltext','ietf.doc.views_ballot.ballot_writeupnotes','ietf.doc.views_ballot.ballot_rfceditornote']:
            url = urlreverse(p, kwargs=dict(name=draft.name))

            for username in ['plain','marschairman','iab-chair','irtf-chair','ise','iana']:
                verify_fail(username, url)

            for username in ['secretary','ad']:
                verify_can_see(username, url)

        # RFC Editor Notes for documents in the IAB Stream
        draft.stream_id = 'iab'
        draft.save_with_history(events)
        url = urlreverse('ietf.doc.views_ballot.ballot_rfceditornote', kwargs=dict(name=draft.name))

        for username in ['plain','marschairman','ad','irtf-chair','ise','iana']:
            verify_fail(username, url)

        for username in ['secretary','iab-chair']:
            verify_can_see(username, url)

        # RFC Editor Notes for documents in the IRTF Stream
        e = DocEvent(doc=draft, rev=draft.rev, by=Person.objects.get(name="(System)"), type='changed_stream')
        e.desc = "Changed stream to <b>%s</b>" % 'irtf'
        e.save()

        draft.stream_id = 'irtf'
        draft.save_with_history([e])
        url = urlreverse('ietf.doc.views_ballot.ballot_rfceditornote', kwargs=dict(name=draft.name))

        for username in ['plain','marschairman','ad','iab-chair','ise','iana']:
            verify_fail(username, url)

        for username in ['secretary','irtf chair']:
            verify_can_see(username, url)

        # RFC Editor Notes for documents in the IAB Stream
        e = DocEvent(doc=draft, rev=draft.rev, by=Person.objects.get(name="(System)"), type='changed_stream')
        e.desc = "Changed stream to <b>%s</b>" % 'ise'
        e.save()

        draft.stream_id = 'ise'
        draft.save_with_history([e])
        url = urlreverse('ietf.doc.views_ballot.ballot_rfceditornote', kwargs=dict(name=draft.name))

        for username in ['plain','marschairman','ad','iab-chair','irtf-chair','iana']:
            verify_fail(username, url)

        for username in ['secretary','ise']:
            verify_can_see(username, url)

class ApproveBallotTests(TestCase):
    @mock.patch('ietf.sync.rfceditor.requests.post', autospec=True)
    def test_approve_ballot(self, mock_urlopen):
        mock_urlopen.return_value.text = b'OK'
        mock_urlopen.return_value.status_code = 200
        #
        ad = Person.objects.get(name="Areað Irector")
        draft = IndividualDraftFactory(ad=ad, intended_std_level_id='ps')
        draft.set_state(State.objects.get(used=True, type="draft-iesg", slug="iesg-eva")) # make sure it's approvable

        url = urlreverse('ietf.doc.views_ballot.approve_ballot', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "secretary", url)

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(q('[type=submit]:contains("send announcement")'))
        self.assertEqual(len(q('form pre:contains("Subject: Protocol Action")')), 1)
        self.assertEqual(len(q('form pre:contains("This is a note for the RFC Editor")')), 0)

        # add a note to the RFC Editor
        WriteupDocEvent.objects.create(
            doc=draft,
            rev=draft.rev,
            desc="Changed text",
            type="changed_rfc_editor_note_text",
            text="This is a note for the RFC Editor.",
            by=Person.objects.get(name="(System)"))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(q('[type=submit]:contains("send announcement")'))
        self.assertEqual(len(q('form pre:contains("Subject: Protocol Action")')), 1)
        self.assertEqual(len(q('form pre:contains("This is a note for the RFC Editor")')), 1)

        # approve
        mailbox_before = len(outbox)

        r = self.client.post(url)
        self.assertEqual(r.status_code, 302)

        draft = Document.objects.get(name=draft.name)
        self.assertEqual(draft.get_state_slug("draft-iesg"), "ann")
        self.assertEqual(len(outbox), mailbox_before + 2)
        self.assertTrue("Protocol Action" in outbox[-2]['Subject'])
        self.assertTrue("ietf-announce" in outbox[-2]['To'])
        self.assertTrue("rfc-editor" in outbox[-2]['Cc'])
        # the IANA copy
        self.assertTrue("Protocol Action" in outbox[-1]['Subject'])
        self.assertTrue(not outbox[-1]['CC'])
        self.assertTrue('drafts-approval@icann.org' in outbox[-1]['To'])
        self.assertTrue("Protocol Action" in draft.message_set.order_by("-time")[0].subject)
        # in 'ann' state, action holders should be empty
        self.assertCountEqual(draft.action_holders.all(), [])

    def test_disapprove_ballot(self):
        # This tests a codepath that is not used in production
        # and that has already had some drift from usefulness (it results in a
        # older-style conflict review response). 
        ad = Person.objects.get(name="Areað Irector")
        draft = IndividualDraftFactory(ad=ad)
        draft.set_state(State.objects.get(used=True, type="draft-iesg", slug="nopubadw"))
        draft.action_holders.set([ad])

        url = urlreverse('ietf.doc.views_ballot.approve_ballot', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "secretary", url)

        # disapprove (the Martians aren't going to be happy)
        mailbox_before = len(outbox)

        r = self.client.post(url, dict())
        self.assertEqual(r.status_code, 302)

        draft = Document.objects.get(name=draft.name)
        self.assertEqual(draft.get_state_slug("draft-iesg"), "dead")
        self.assertEqual(len(outbox), mailbox_before + 1)
        self.assertTrue("NOT be published" in str(outbox[-1]))
        self.assertCountEqual(draft.action_holders.all(), [])
        self.assertIn('Removed all action holders', draft.latest_event(type='changed_action_holders').desc)

    def test_clear_ballot(self):
        draft = IndividualDraftFactory()
        ad = Person.objects.get(user__username="ad")
        ballot = create_ballot_if_not_open(None, draft, ad, 'approve')
        old_ballot_id = ballot.id
        draft.set_state(State.objects.get(used=True, type="draft-iesg", slug="iesg-eva")) 
        url = urlreverse('ietf.doc.views_ballot.clear_ballot', kwargs=dict(name=draft.name,ballot_type_slug="approve"))
        login_testing_unauthorized(self, "secretary", url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        r = self.client.post(url,{})
        self.assertEqual(r.status_code, 302)
        ballot = draft.ballot_open('approve')
        self.assertIsNotNone(ballot)
        self.assertEqual(ballot.ballotpositiondocevent_set.count(),0)
        self.assertNotEqual(old_ballot_id, ballot.id)
        # It's not valid to clear a ballot of a type where there's no matching state
        url = urlreverse('ietf.doc.views_ballot.clear_ballot', kwargs=dict(name=draft.name,ballot_type_slug="statchg"))
        r = self.client.post(url,{})
        self.assertEqual(r.status_code, 404)
 

    def test_ballot_downref_approve(self):
        ad = Person.objects.get(name="Areað Irector")
        draft = IndividualDraftFactory(ad=ad, intended_std_level_id='ps')
        draft.set_state(State.objects.get(used=True, type="draft-iesg", slug="ann")) # make sure it's approved
        LastCallDocEvent.objects.create(
                  by=Person.objects.get(name='(System)'),
                  type='sent_last_call',
                  doc=draft,
                  rev=draft.rev,
                  desc='issued last call',
                  expires = timezone.now()-datetime.timedelta(days=14) )
        WriteupDocEvent.objects.create(
                  by=Person.objects.get(name='(System)'),
                  doc=draft,
                  rev=draft.rev,
                  type='changed_last_call_text',
                  desc='Last call announcement was changed',
                  text='this is simple last call text.' )
        rfc = IndividualRfcFactory.create(
                  name = "rfc6666",
                  stream_id='ise',
                  states=[('draft','rfc'),('draft-iesg','pub')],
                  std_level_id='inf', )

        url = urlreverse('ietf.doc.views_ballot.approve_downrefs', kwargs=dict(name=draft.name))

        # Only Secretariat can use this URL
        login_testing_unauthorized(self, "ad", url)
        r = self.client.get(url)
        self.assertContains(r, "Restricted to role: Secretariat", status_code=403)

        # There are no downrefs, the page should say so
        login_testing_unauthorized(self, "secretary", url)
        r = self.client.get(url)
        self.assertContains(r, "No downward references for")

        # Add a downref, the page should ask if it should be added to the registry
        rel = draft.relateddocument_set.create(target=rfc, relationship_id='refnorm')
        d = [rdoc for rdoc in draft.relateddocument_set.all() if rel.is_approved_downref()]
        original_len = len(d)
        r = self.client.get(url)
        self.assertContains(r, "normatively references rfc6666")

        # POST with the downref checked
        r = self.client.post(url, dict(checkboxes=rel.pk))
        self.assertEqual(r.status_code, 302)

        # Confirm an entry was added to the downref registry
        d = [rdoc for rdoc in draft.relateddocument_set.all() if rel.is_approved_downref()]
        self.assertTrue(len(d) > original_len, "The downref approval was not added")

class MakeLastCallTests(TestCase):
    def test_make_last_call(self):
        ad = Person.objects.get(user__username="ad")
        draft = WgDraftFactory(name='draft-ietf-mars-test',group__acronym='mars',ad=ad,states=[('draft-iesg','lc-req')],intended_std_level_id='ps')
        HolderIprDisclosureFactory(docs=[draft])

        url = urlreverse('ietf.doc.views_ballot.make_last_call', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "secretary", url)

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('input[name=last_call_sent_date]')), 1)

        # make last call
        mailbox_before = len(outbox)

        expire_date = q('input[name=last_call_expiration_date]')[0].get("value")
        
        r = self.client.post(url,
                             dict(last_call_sent_date=q('input[name=last_call_sent_date]')[0].get("value"),
                                  last_call_expiration_date=expire_date
                                  ))
        self.assertEqual(r.status_code, 302)

        draft = Document.objects.get(name=draft.name)
        self.assertEqual(draft.get_state_slug("draft-iesg"), "lc")
        self.assertEqual(draft.latest_event(LastCallDocEvent, "sent_last_call").expires.strftime("%Y-%m-%d"), expire_date)
        self.assertCountEqual(draft.action_holders.all(), [ad])

        self.assertEqual(len(outbox), mailbox_before + 2)

        self.assertTrue("Last Call" in outbox[-2]['Subject'])
        self.assertTrue("ietf-announce@" in outbox[-2]['To'])
        for prefix in ['draft-ietf-mars-test','mars-chairs','aread']:
            self.assertTrue(prefix+"@" in outbox[-2]['Cc'])
        self.assertIn("The following IPR Declarations", get_payload_text(outbox[-2]))

        self.assertTrue("Last Call" in outbox[-1]['Subject'])
        self.assertTrue("drafts-lastcall@icann.org" in outbox[-1]['To'])

        self.assertTrue("Last Call" in draft.message_set.order_by("-time")[0].subject)

    def test_make_last_call_yang_document(self):
        yd = ReviewTeamFactory(acronym='yangdoctors')
        secr_email = RoleFactory(group=yd,name_id='secr').person.email().address
        draft = WgDraftFactory()
        submission = draft.submission_set.create(
            state_id = 'posted',
            name = draft.name,
            group = draft.group,
            rev = draft.rev,
            authors = '[]',
        )
        submission.checks.create(
            checker = 'yang validation',
            passed = True,
        )


        url = urlreverse('ietf.doc.views_ballot.make_last_call', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, 'secretary', url)

        mailbox_before = len(outbox)

        last_call_sent_date = date_today()
        expire_date = last_call_sent_date+datetime.timedelta(days=14)
        
        r = self.client.post(url,
                             dict(last_call_sent_date=last_call_sent_date,
                                  last_call_expiration_date=expire_date
                                  ))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(len(outbox), mailbox_before + 3) 
        self.assertIn("ietf-announce@", outbox[-3]['To'])
        self.assertIn("drafts-lastcall@icann.org", outbox[-2]['To'])
        self.assertIn(secr_email, outbox[-1]['To'])


class DeferUndeferTestCase(TestCase):
    def helper_test_defer(self,name):

        doc = Document.objects.get(name=name)
        url = urlreverse('ietf.doc.views_ballot.defer_ballot',kwargs=dict(name=doc.name))

        login_testing_unauthorized(self, "ad", url)

        # Verify that you can't defer a document that's not on a telechat
        r = self.client.post(url,dict())
        self.assertEqual(r.status_code, 404)

        # Put the document on a telechat
        dates = TelechatDate.objects.active().order_by("date")
        first_date = dates[0].date
        second_date = dates[1].date

        e = TelechatDocEvent(type="scheduled_for_telechat",
                             doc = doc,
                             rev = doc.rev,
                             by = Person.objects.get(name="Areað Irector"),
                             telechat_date = first_date,
                             returning_item = False, 
                            )
        e.save()

        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('[type=submit]:contains("Defer ballot")')),1)

        # defer
        mailbox_before = len(outbox)
        self.assertEqual(doc.telechat_date(), first_date)
        r = self.client.post(url,dict())
        self.assertEqual(r.status_code, 302)
        doc = Document.objects.get(name=name)
        self.assertEqual(doc.telechat_date(), second_date)
        self.assertFalse(doc.returning_item())
        defer_states = dict(draft=['draft-iesg','defer'],conflrev=['conflrev','defer'],statchg=['statchg','defer'])
        if doc.type_id in defer_states:
           self.assertEqual(doc.get_state(defer_states[doc.type_id][0]).slug,defer_states[doc.type_id][1])
        self.assertTrue(doc.active_defer_event())
        if doc.type_id == 'draft':
            self.assertCountEqual(doc.action_holders.all(), [doc.ad])
            self.assertIn('Changed action holders', doc.latest_event(type='changed_action_holders').desc)
        else:
            self.assertIsNone(doc.latest_event(type='changed_action_holders'))
    
        self.assertEqual(len(outbox), mailbox_before + 2)

        self.assertTrue('Telechat update' in outbox[-2]['Subject'])
        self.assertTrue('iesg-secretary@' in outbox[-2]['To'])
        self.assertTrue('iesg@' in outbox[-2]['To'])

        self.assertTrue("Deferred" in outbox[-1]['Subject'])
        self.assertTrue(doc.file_tag() in outbox[-1]['Subject'])
        self.assertTrue('iesg@' in outbox[-1]['To'])

        # Ensure it's not possible to defer again
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)
        r = self.client.post(url,dict())
        self.assertEqual(r.status_code, 404) 


    def helper_test_undefer(self,name):

        doc = Document.objects.get(name=name)
        url = urlreverse('ietf.doc.views_ballot.undefer_ballot',kwargs=dict(name=doc.name))

        login_testing_unauthorized(self, "ad", url)

        # some additional setup
        dates = TelechatDate.objects.active().order_by("date")
        first_date = dates[0].date
        second_date = dates[1].date

        e = TelechatDocEvent(type="scheduled_for_telechat",
                             doc = doc,
                             rev = doc.rev,
                             by = Person.objects.get(name="Areað Irector"),
                             telechat_date = second_date,
                             returning_item = True, 
                            )
        e.save()
        defer_states = dict(draft=['draft-iesg','defer'],conflrev=['conflrev','defer'],statchg=['statchg','defer'])
        if doc.type_id in defer_states:
            doc.set_state(State.objects.get(used=True, type=defer_states[doc.type_id][0],slug=defer_states[doc.type_id][1]))

        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('[type=submit]:contains("Undefer ballot")')),1)

        # undefer
        mailbox_before = len(outbox)
        self.assertEqual(doc.telechat_date(), second_date)
        r = self.client.post(url,dict())
        self.assertEqual(r.status_code, 302)
        doc = Document.objects.get(name=name)
        self.assertEqual(doc.telechat_date(), first_date)
        self.assertTrue(doc.returning_item()) 
        undefer_states = dict(draft=['draft-iesg','iesg-eva'],conflrev=['conflrev','iesgeval'],statchg=['statchg','iesgeval'])
        if doc.type_id in undefer_states:
           self.assertEqual(doc.get_state(undefer_states[doc.type_id][0]).slug,undefer_states[doc.type_id][1])
        self.assertFalse(doc.active_defer_event())
        if doc.type_id == 'draft':
            self.assertCountEqual(doc.action_holders.all(), [doc.ad])
            self.assertIn('Changed action holders', doc.latest_event(type='changed_action_holders').desc)
        else:
            self.assertIsNone(doc.latest_event(type='changed_action_holders'))
        self.assertEqual(len(outbox), mailbox_before + 2)
        self.assertTrue("Telechat update" in outbox[-2]['Subject'])
        self.assertTrue('iesg-secretary@' in outbox[-2]['To'])
        self.assertTrue('iesg@' in outbox[-2]['To'])
        self.assertTrue("Undeferred" in outbox[-1]['Subject'])
        self.assertTrue(doc.file_tag() in outbox[-1]['Subject'])
        self.assertTrue('iesg@' in outbox[-1]['To'])

        # Ensure it's not possible to undefer again
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)
        r = self.client.post(url,dict())
        self.assertEqual(r.status_code, 404) 

    def test_defer_draft(self):
        self.helper_test_defer('draft-ietf-mars-test')

    def test_defer_conflict_review(self):
        self.helper_test_defer('conflict-review-imaginary-irtf-submission')

    def test_defer_status_change(self):
        self.helper_test_defer('status-change-imaginary-mid-review')

    def test_undefer_draft(self):
        self.helper_test_undefer('draft-ietf-mars-test')

    def test_undefer_conflict_review(self):
        self.helper_test_undefer('conflict-review-imaginary-irtf-submission')

    def test_undefer_status_change(self):
        self.helper_test_undefer('status-change-imaginary-mid-review')

    # when charters support being deferred, be sure to test them here

    def setUp(self):
        super().setUp()
        IndividualDraftFactory(name='draft-ietf-mars-test',states=[('draft','active'),('draft-iesg','iesg-eva')],
                               ad=Person.objects.get(user__username='ad'))
        DocumentFactory(type_id='statchg',name='status-change-imaginary-mid-review',states=[('statchg','iesgeval')])
        DocumentFactory(type_id='conflrev',name='conflict-review-imaginary-irtf-submission',states=[('conflrev','iesgeval')])

class IetfFiltersTests(TestCase):
    def test_can_defer(self):
        secretariat = Person.objects.get(user__username="secretary").user
        ad = Person.objects.get(user__username="ad").user
        irtf_chair = Person.objects.get(user__username="irtf-chair").user
        rsab_chair = Person.objects.get(user__username="rsab-chair").user
        irsg_member = RoleFactory(group__type_id="rg", name_id="chair").person.user
        rsab_member = RoleFactory(group=Group.objects.get(acronym="rsab"), name_id="member").person.user
        nobody = PersonFactory().user

        users = set([secretariat, ad, irtf_chair, rsab_chair, irsg_member, rsab_member, nobody])

        iesg_ballot = BallotDocEventFactory(doc__stream_id='ietf')
        self.assertTrue(can_defer(secretariat, iesg_ballot.doc))
        self.assertTrue(can_defer(ad, iesg_ballot.doc))
        for user in users - set([secretariat, ad]):
            self.assertFalse(can_defer(user, iesg_ballot.doc))

        irsg_ballot = IRSGBallotDocEventFactory(doc__stream_id='irtf')
        for user in users:
            self.assertFalse(can_defer(user, irsg_ballot.doc))

        rsab_ballot = BallotDocEventFactory(ballot_type__slug='rsab-approve', doc__stream_id='editorial')
        for user in users:
            self.assertFalse(can_defer(user, rsab_ballot.doc))        

    def test_can_clear_ballot(self):
        pass # Right now, can_clear_ballot is implemented by can_defer

class RegenerateLastCallTestCase(TestCase):

    def test_regenerate_last_call(self):
        draft = WgDraftFactory.create(
                    stream_id='ietf',
                    states=[('draft','active'),('draft-iesg','pub-req')],
                    intended_std_level_id='ps',
                )
    
        url = urlreverse('ietf.doc.views_ballot.lastcalltext', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "secretary", url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        r = self.client.post(url, dict(regenerate_last_call_text="1"))
        self.assertEqual(r.status_code, 200)
        draft = Document.objects.get(name=draft.name)
        lc_text = draft.latest_event(WriteupDocEvent, type="changed_last_call_text").text
        self.assertTrue("Subject: Last Call" in lc_text)
        self.assertFalse("contains these normative down" in lc_text)

        rfc = IndividualRfcFactory.create(
                  rfc_number=6666,
                  stream_id='ise',
                  states=[('draft','rfc'),('draft-iesg','pub')],
                  std_level_id='inf',
              )

        draft.relateddocument_set.create(target=rfc,relationship_id='refnorm')

        r = self.client.post(url, dict(regenerate_last_call_text="1"))
        self.assertEqual(r.status_code, 200)
        draft = Document.objects.get(name=draft.name)
        lc_text = draft.latest_event(WriteupDocEvent, type="changed_last_call_text").text
        self.assertTrue("contains these normative down" in lc_text)
        self.assertTrue("rfc6666" in lc_text)
        self.assertTrue("Independent Submission" in lc_text)

        draft.relateddocument_set.create(target=rfc, relationship_id='downref-approval')

        r = self.client.post(url, dict(regenerate_last_call_text="1"))
        self.assertEqual(r.status_code, 200)
        draft = Document.objects.get(name=draft.name)
        lc_text = draft.latest_event(WriteupDocEvent, type="changed_last_call_text").text
        self.assertFalse("contains these normative down" in lc_text)
        self.assertFalse("rfc6666" in lc_text)


class BallotContentTests(TestCase):
    def test_ballotpositiondocevent_any_email_sent(self):
        now = timezone.now()  # be sure event timestamps are at distinct times
        bpde_with_null_send_email = BallotPositionDocEventFactory(
            time=now - datetime.timedelta(minutes=30),
            send_email=None,
        )
        ballot = bpde_with_null_send_email.ballot
        balloter = bpde_with_null_send_email.balloter
        self.assertIsNone(
            bpde_with_null_send_email.any_email_sent(),
            'Result is None when only send_email is None',
        )

        self.assertIsNone(
            BallotPositionDocEventFactory(
                ballot=ballot,
                balloter=balloter,
                time=now - datetime.timedelta(minutes=29),
                send_email=None,
            ).any_email_sent(),
            'Result is None when all send_email values are None',
        )

        # test with assertIs instead of assertFalse to distinguish None from False
        self.assertIs(
            BallotPositionDocEventFactory(
                ballot=ballot,
                balloter=balloter,
                time=now - datetime.timedelta(minutes=28),
                send_email=False,
            ).any_email_sent(),
            False,
            'Result is False when current send_email is False'
        )

        self.assertIs(
            BallotPositionDocEventFactory(
                ballot=ballot,
                balloter=balloter,
                time=now - datetime.timedelta(minutes=27),
                send_email=None,
            ).any_email_sent(),
            False,
            'Result is False when earlier send_email is False'
        )

        self.assertIs(
            BallotPositionDocEventFactory(
                ballot=ballot,
                balloter=balloter,
                time=now - datetime.timedelta(minutes=26),
                send_email=True,
            ).any_email_sent(),
            True,
            'Result is True when current send_email is True'
        )

        self.assertIs(
            BallotPositionDocEventFactory(
                ballot=ballot,
                balloter=balloter,
                time=now - datetime.timedelta(minutes=25),
                send_email=None,
            ).any_email_sent(),
            True,
            'Result is True when earlier send_email is True and current is None'
        )

        self.assertIs(
            BallotPositionDocEventFactory(
                ballot=ballot,
                balloter=balloter,
                time=now - datetime.timedelta(minutes=24),
                send_email=False,
            ).any_email_sent(),
            True,
            'Result is True when earlier send_email is True and current is False'
        )

    def _assertBallotMessage(self, q, balloter, expected):
        heading = q(f'div.h5[id$="_{slugify(balloter.plain_name())}"]')
        self.assertEqual(len(heading), 1)
        # <div.h5> is followed by a panel with the message of interest, so use next()
        next = heading.next()
        self.assertEqual(
            len(next.find(
                f'*[title="{expected}"]'
            )),
            1,
        )

    def test_document_ballot_content_email_sent(self):
        """Ballot content correctly describes whether email is requested for each position"""
        ballot = BallotDocEventFactory()
        balloters = get_active_ads()
        self.assertGreaterEqual(len(balloters), 6,
                                'Oops! Need to create additional active balloters for test')

        # send_email is True
        BallotPositionDocEventFactory(
            ballot=ballot,
            balloter=balloters[0],
            pos_id='discuss',
            discuss='Discussion text',
            discuss_time=timezone.now(),
            send_email=True,
        )
        BallotPositionDocEventFactory(
            ballot=ballot,
            balloter=balloters[1],
            pos_id='noobj',
            comment='Commentary',
            comment_time=timezone.now(),
            send_email=True,
        )

        # send_email False
        BallotPositionDocEventFactory(
            ballot=ballot,
            balloter=balloters[2],
            pos_id='discuss',
            discuss='Discussion text',
            discuss_time=timezone.now(),
            send_email=False,
        )
        BallotPositionDocEventFactory(
            ballot=ballot,
            balloter=balloters[3],
            pos_id='noobj',
            comment='Commentary',
            comment_time=timezone.now(),
            send_email=False,
        )

        # send_email False but earlier position had send_email True
        BallotPositionDocEventFactory(
            ballot=ballot,
            balloter=balloters[4],
            pos_id='discuss',
            discuss='Discussion text',
            discuss_time=timezone.now() - datetime.timedelta(days=1),
            send_email=True,
        )
        BallotPositionDocEventFactory(
            ballot=ballot,
            balloter=balloters[4],
            pos_id='discuss',
            discuss='Discussion text',
            discuss_time=timezone.now(),
            send_email=False,
        )
        BallotPositionDocEventFactory(
            ballot=ballot,
            balloter=balloters[5],
            pos_id='noobj',
            comment='Commentary',
            comment_time=timezone.now() - datetime.timedelta(days=1),
            send_email=True,
        )
        BallotPositionDocEventFactory(
            ballot=ballot,
            balloter=balloters[5],
            pos_id='noobj',
            comment='Commentary',
            comment_time=timezone.now(),
            send_email=False,
        )

        # Create a few positions with non-active-ad people. These will be treated
        # as "old" ballot positions because the people are not in the list returned
        # by get_active_ads()
        #
        # Some faked non-ASCII names wind up with plain names that cannot be slugified.
        # This causes test failure because that slug is used in an HTML element ID.
        # Until that's fixed, set the plain names to something guaranteed unique so
        # the test does not randomly fail.
        no_email_balloter = BallotPositionDocEventFactory(
            ballot=ballot,
            balloter__plain='plain name1',
            pos_id='discuss',
            discuss='Discussion text',
            discuss_time=timezone.now(),
            send_email=False,
        ).balloter
        send_email_balloter = BallotPositionDocEventFactory(
            ballot=ballot,
            balloter__plain='plain name2',
            pos_id='discuss',
            discuss='Discussion text',
            discuss_time=timezone.now(),
            send_email=True,
        ).balloter
        prev_send_email_balloter = BallotPositionDocEventFactory(
            ballot=ballot,
            balloter__plain='plain name3',
            pos_id='discuss',
            discuss='Discussion text',
            discuss_time=timezone.now() - datetime.timedelta(days=1),
            send_email=True,
        ).balloter
        BallotPositionDocEventFactory(
            ballot=ballot,
            balloter=prev_send_email_balloter,
            pos_id='discuss',
            discuss='Discussion text',
            discuss_time=timezone.now(),
            send_email=False,
        )

        content = document_ballot_content(
            request=RequestFactory(),
            doc=ballot.doc,
            ballot_id=ballot.pk,
        )
        q = PyQuery(content)
        self._assertBallotMessage(q, balloters[0], 'Email requested to be sent for this discuss')
        self._assertBallotMessage(q, balloters[1], 'Email requested to be sent for this comment')
        self._assertBallotMessage(q, balloters[2], 'No email send requests for this discuss')
        self._assertBallotMessage(q, balloters[3], 'No email send requests for this comment')
        self._assertBallotMessage(q, balloters[4], 'Email requested to be sent for earlier discuss')
        self._assertBallotMessage(q, balloters[5], 'Email requested to be sent for earlier comment')
        self._assertBallotMessage(q, no_email_balloter, 'No email send requests for this ballot position')
        self._assertBallotMessage(q, send_email_balloter, 'Email requested to be sent for this ballot position')
        self._assertBallotMessage(q, prev_send_email_balloter, 'Email requested to be sent for earlier ballot position')

    def test_document_ballot_content_without_send_email_values(self):
        """Ballot content correctly indicates lack of send_email field in records"""
        ballot = BallotDocEventFactory()
        balloters = get_active_ads()
        self.assertGreaterEqual(len(balloters), 2,
                                'Oops! Need to create additional active balloters for test')
        BallotPositionDocEventFactory(
            ballot=ballot,
            balloter=balloters[0],
            pos_id='discuss',
            discuss='Discussion text',
            discuss_time=timezone.now(),
            send_email=None,
        )
        BallotPositionDocEventFactory(
            ballot=ballot,
            balloter=balloters[1],
            pos_id='noobj',
            comment='Commentary',
            comment_time=timezone.now(),
            send_email=None,
        )
        old_balloter = BallotPositionDocEventFactory(
            ballot=ballot,
            balloter__plain='plain name',  # ensure plain name is slugifiable
            pos_id='discuss',
            discuss='Discussion text',
            discuss_time=timezone.now(),
            send_email=None,
        ).balloter

        content = document_ballot_content(
            request=RequestFactory(),
            doc=ballot.doc,
            ballot_id=ballot.pk,
        )
        q = PyQuery(content)
        self._assertBallotMessage(q, balloters[0], 'No discuss send log available')
        self._assertBallotMessage(q, balloters[1], 'No comment send log available')
        self._assertBallotMessage(q, old_balloter, 'No ballot position send log available')

class ReturnToUrlTests(TestCase):
    def test_invalid_return_to_url(self):
        with self.assertRaises(ValueError):
            parse_ballot_edit_return_point('/', 'draft-ietf-opsawg-ipfix-tcpo-v6eh', '998718')

        with self.assertRaises(ValueError):
            parse_ballot_edit_return_point('/a-route-that-does-not-exist/', 'draft-ietf-opsawg-ipfix-tcpo-v6eh', '998718')

        with self.assertRaises(ValueError):
            parse_ballot_edit_return_point('https://example.com/phishing', 'draft-ietf-opsawg-ipfix-tcpo-v6eh', '998718')

    def test_valid_default_return_to_url(self):
        self.assertEqual(parse_ballot_edit_return_point(
            None,
            'draft-ietf-opsawg-ipfix-tcpo-v6eh',
            '998718'
        ), '/doc/draft-ietf-opsawg-ipfix-tcpo-v6eh/ballot/998718/')
        
    def test_valid_return_to_url(self):
        self.assertEqual(parse_ballot_edit_return_point(
            '/doc/draft-ietf-opsawg-ipfix-tcpo-v6eh/ballot/998718/',
            'draft-ietf-opsawg-ipfix-tcpo-v6eh',
            '998718'
        ), '/doc/draft-ietf-opsawg-ipfix-tcpo-v6eh/ballot/998718/')
