# Copyright The IETF Trust 2011-2023, All Rights Reserved
# -*- coding: utf-8 -*-


import os
import datetime
import io
import mock

from collections import Counter
from pathlib import Path
from pyquery import PyQuery

from django.db.models import Q
from django.urls import reverse as urlreverse
from django.conf import settings
from django.utils import timezone
from django.utils.html import escape

import debug                            # pyflakes:ignore

from ietf.doc.expire import expirable_drafts, get_expired_drafts, send_expire_notice_for_draft, expire_draft
from ietf.doc.factories import EditorialDraftFactory, IndividualDraftFactory, WgDraftFactory, RgDraftFactory, DocEventFactory
from ietf.doc.models import ( Document, DocReminder, DocEvent,
    ConsensusDocEvent, LastCallDocEvent, RelatedDocument, State, TelechatDocEvent, 
    WriteupDocEvent, DocRelationshipName, IanaExpertDocEvent )
from ietf.doc.utils import get_tags_for_stream_id, create_ballot_if_not_open
from ietf.doc.views_draft import AdoptDraftForm
from ietf.name.models import DocTagName, RoleName
from ietf.group.factories import GroupFactory, RoleFactory
from ietf.group.models import Group, Role
from ietf.person.factories import PersonFactory, EmailFactory
from ietf.person.models import Person, Email
from ietf.meeting.models import Meeting, MeetingTypeName
from ietf.iesg.models import TelechatDate
from ietf.utils.test_utils import login_testing_unauthorized
from ietf.utils.mail import outbox, empty_outbox, get_payload_text
from ietf.utils.test_utils import TestCase
from ietf.utils.timezone import date_today, datetime_from_date, DEADLINE_TZINFO


class ChangeStateTests(TestCase):
    def test_ad_approved(self):
        # get a draft in iesg evaluation, point raised
        ad = Person.objects.get(user__username="ad")
        draft = WgDraftFactory(ad=ad,states=[('draft','active'),('draft-iesg','iesg-eva')])
        DocEventFactory(type='started_iesg_process',by=ad,doc=draft,rev=draft.rev,desc="Started IESG Process")
        draft.tags.add("ad-f-up")
        draft.action_holders.add(ad)

        url = urlreverse('ietf.doc.views_draft.change_state', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "ad", url)
        
        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form select[name=state]')), 1)
        
        events_before = draft.docevent_set.count()
        mailbox_before = len(outbox)
        
        # set it to approved with no substate
        r = self.client.post(url,
                             dict(state=State.objects.get(used=True, type="draft-iesg", slug="approved").pk,
                                  substate="",
                                  comment="Test comment"))
        self.assertEqual(r.status_code, 302)

        draft = Document.objects.get(name=draft.name)
        
        # should now be in approved with no substate
        self.assertEqual(draft.get_state_slug("draft-iesg"), "approved")
        self.assertTrue(not draft.tags.filter(slug="approved"))
        self.assertFalse(draft.tags.exists())
        self.assertEqual(draft.docevent_set.count(), events_before + 3)
        self.assertTrue("Test comment" in draft.docevent_set.all()[0].desc)
        self.assertTrue("Removed all action holders" in draft.docevent_set.all()[1].desc)
        self.assertTrue("IESG state changed" in draft.docevent_set.all()[2].desc)
        self.assertCountEqual(draft.action_holders.all(), [])

        # should have sent two emails, the second one to the iesg with approved message
        self.assertEqual(len(outbox), mailbox_before + 2)
        self.assertTrue("Approved: " in outbox[-1]['Subject'])
        self.assertTrue(draft.name in outbox[-1]['Subject'])
        self.assertTrue('iesg@' in outbox[-1]['To'])
        
    def test_change_state(self):
        ad = Person.objects.get(user__username="ad")
        draft = WgDraftFactory(
            name='draft-ietf-mars-test',
            group__acronym='mars',
            ad=ad,
            authors=PersonFactory.create_batch(3),
            states=[('draft','active'),('draft-iesg','ad-eval')]
        )
        DocEventFactory(type='started_iesg_process',by=ad,doc=draft,rev=draft.rev,desc="Started IESG Process")
        draft.action_holders.add(ad)

        url = urlreverse('ietf.doc.views_draft.change_state', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "ad", url)

        first_state = draft.get_state("draft-iesg")
        next_states = first_state.next_states.all()

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form select[name=state]')), 1)
        
        if next_states:
            self.assertEqual(len(q('[type=submit]:contains("%s")' % next_states[0].name)), 1)

            
        # faulty post
        r = self.client.post(url, dict(state=State.objects.get(used=True, type="draft", slug="active").pk))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form .is-invalid')) > 0)
        draft = Document.objects.get(name=draft.name)
        self.assertEqual(draft.get_state("draft-iesg"), first_state)
        self.assertCountEqual(draft.action_holders.all(), [ad])
        
        # change state
        events_before = draft.docevent_set.count()
        mailbox_before = len(outbox)
        draft.tags.add("ad-f-up")
        
        r = self.client.post(url,
                             dict(state=State.objects.get(used=True, type="draft-iesg", slug="review-e").pk,
                                  substate="need-rev",
                                  comment="Test comment"))
        self.assertEqual(r.status_code, 302)

        draft = Document.objects.get(name=draft.name)
        self.assertEqual(draft.get_state_slug("draft-iesg"), "review-e")
        self.assertTrue(not draft.tags.filter(slug="ad-f-up"))
        self.assertTrue(draft.tags.filter(slug="need-rev"))
        self.assertCountEqual(draft.action_holders.all(), [ad] + draft.authors())
        self.assertEqual(draft.docevent_set.count(), events_before + 3)
        self.assertTrue("Test comment" in draft.docevent_set.all()[0].desc)
        self.assertTrue("Changed action holders" in draft.docevent_set.all()[1].desc)
        self.assertTrue("IESG state changed" in draft.docevent_set.all()[2].desc)
        self.assertEqual(len(outbox), mailbox_before + 1)
        self.assertTrue("State Update Notice" in outbox[-1]['Subject'])
        self.assertTrue('draft-ietf-mars-test@' in outbox[-1]['To'])
        self.assertTrue('mars-chairs@' in outbox[-1]['To'])
        self.assertTrue('aread@' in outbox[-1]['To'])
        
        # check that we got a previous state now
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form [type=submit]:contains("%s")' % first_state.name)), 1)

        # try to change to an AD-forbidden state
        r = self.client.post(url, dict(state=State.objects.get(used=True, type='draft-iesg', slug='ann').pk, comment='Test comment'))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(q('form .invalid-feedback'))

        # try again as secretariat
        self.client.logout()
        login_testing_unauthorized(self, 'secretary', url)
        r = self.client.post(url, dict(state=State.objects.get(used=True, type='draft-iesg', slug='ann').pk, comment='Test comment'))
        self.assertEqual(r.status_code, 302)
        draft = Document.objects.get(name=draft.name)
        self.assertEqual(draft.get_state_slug('draft-iesg'), 'ann')

    def test_pull_from_rfc_queue(self):
        ad = Person.objects.get(user__username="ad")
        draft = WgDraftFactory(
            ad=ad,
            authors=PersonFactory.create_batch(3),
            states=[('draft-iesg','rfcqueue')],
        )
        DocEventFactory(type='started_iesg_process',by=ad,doc=draft,rev=draft.rev,desc="Started IESG Process")
        draft.action_holders.add(*(draft.authors()))

        url = urlreverse('ietf.doc.views_draft.change_state', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "secretary", url)

        # change state
        mailbox_before = len(outbox)

        r = self.client.post(url,
                             dict(state=State.objects.get(used=True, type="draft-iesg", slug="review-e").pk,
                                  substate="",
                                  comment="Test comment"))
        self.assertEqual(r.status_code, 302)

        draft = Document.objects.get(name=draft.name)
        self.assertEqual(draft.get_state_slug("draft-iesg"), "review-e")
        self.assertCountEqual(draft.action_holders.all(), [ad])
        self.assertEqual(len(outbox), mailbox_before + 2)

        self.assertTrue(draft.name in outbox[-1]['Subject'])
        self.assertTrue("changed state" in outbox[-1]['Subject'])
        self.assertTrue("is no longer" in str(outbox[-1]))
        self.assertTrue("Test comment" in str(outbox[-1]))
        self.assertTrue("rfc-editor@" in outbox[-1]['To'])
        self.assertTrue("iana@" in outbox[-1]['To'])

        self.assertTrue("Datatracker State Update Notice:" in outbox[-2]['Subject'])
        self.assertTrue("aread@" in outbox[-2]['To'])
        

    def test_change_iana_state(self):
        draft = WgDraftFactory()

        first_state = State.objects.get(used=True, type="draft-iana-review", slug="need-rev")
        next_state = State.objects.get(used=True, type="draft-iana-review", slug="ok-noact")
        draft.set_state(first_state)

        url = urlreverse('ietf.doc.views_draft.change_iana_state', kwargs=dict(name=draft.name, state_type="iana-review"))
        login_testing_unauthorized(self, "iana", url)

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form select[name=state]')), 1)
        
        # faulty post
        r = self.client.post(url, dict(state="foobarbaz"))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form .is-invalid')) > 0)
        draft = Document.objects.get(name=draft.name)
        self.assertEqual(draft.get_state("draft-iana-review"), first_state)

        # change state
        r = self.client.post(url, dict(state=next_state.pk))
        self.assertEqual(r.status_code, 302)

        draft = Document.objects.get(name=draft.name)
        self.assertEqual(draft.get_state("draft-iana-review"), next_state)

    def test_change_iana_expert_review_state(self):
        draft = WgDraftFactory()

        first_state = State.objects.get(used=True, type='draft-iana-experts', slug='reviews-assigned')
        next_state = State.objects.get(used=True, type='draft-iana-experts', slug='reviewers-ok')

        draft.set_state(first_state)

        url = urlreverse('ietf.doc.views_draft.change_iana_state', kwargs=dict(name=draft.name, state_type="iana-experts"))
        login_testing_unauthorized(self, 'iana', url)

        empty_outbox()
        r = self.client.post(url, dict(state=next_state.pk))
        self.assertEqual(r.status_code, 302)

        draft = Document.objects.get(name=draft.name)
        self.assertEqual(draft.get_state("draft-iana-experts"), next_state)

        self.assertEqual(len(outbox),1)

    def test_add_expert_review_comment(self):
        draft = WgDraftFactory()
        url = urlreverse('ietf.doc.views_draft.add_iana_experts_comment',kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, 'iana', url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        r = self.client.post(url,dict(comment='!2ab3x#1'))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(draft.latest_event(IanaExpertDocEvent,type='comment').desc,'!2ab3x#1')


    def test_request_last_call(self):
        ad = Person.objects.get(user__username="ad")
        draft = WgDraftFactory(
            ad=ad,
            authors=PersonFactory.create_batch(3),
            states=[('draft-iesg','ad-eval')],
        )
        DocEventFactory(type='started_iesg_process',by=ad,doc=draft,rev=draft.rev,desc="Started IESG Process")
        draft.action_holders.add(*(draft.authors()))

        self.client.login(username="secretary", password="secretary+password")
        url = urlreverse('ietf.doc.views_draft.change_state', kwargs=dict(name=draft.name))

        empty_outbox()

        self.assertTrue(not draft.latest_event(type="changed_ballot_writeup_text"))
        r = self.client.post(url, dict(state=State.objects.get(used=True, type="draft-iesg", slug="lc-req").pk))
        self.assertEqual(r.status_code,200)
        self.assertContains(r, "Your request to issue")

        draft = Document.objects.get(name=draft.name)

        # last call text
        e = draft.latest_event(WriteupDocEvent, type="changed_last_call_text")
        self.assertTrue(e)
        self.assertTrue("The IESG has received" in e.text)
        self.assertTrue(draft.title in e.text)
        self.assertTrue(draft.get_absolute_url() in e.text)

        # approval text
        e = draft.latest_event(WriteupDocEvent, type="changed_ballot_approval_text")
        self.assertTrue(e)
        self.assertTrue("The IESG has approved" in e.text)
        self.assertTrue(draft.title in e.text)
        self.assertTrue(draft.get_absolute_url() in e.text)

        # ballot writeup
        e = draft.latest_event(WriteupDocEvent, type="changed_ballot_writeup_text")
        self.assertTrue(e)
        self.assertTrue("Technical Summary" in e.text)

        # mail notice
        self.assertEqual(len(outbox), 2) 

        self.assertTrue("Datatracker State Update" in outbox[0]['Subject'])
        self.assertTrue("aread@" in outbox[0]['To'])

        self.assertTrue("Last Call:" in outbox[1]['Subject'])
        self.assertTrue('iesg-secretary@' in outbox[1]['To'])
        self.assertTrue('aread@' in outbox[1]['Cc'])

        # comment
        self.assertTrue("Last call was requested" in draft.latest_event().desc)
        
        # action holders
        self.assertCountEqual(draft.action_holders.all(), [ad])
        
    def test_iesg_state_edit_button(self):
        ad = Person.objects.get(user__username="ad")
        draft = WgDraftFactory(ad=ad,states=[('draft','active'),('draft-iesg','ad-eval')])

        url = urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=draft.name))
        self.client.login(username="ad", password="ad+password")

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertIn("Edit", q('tr:contains("IESG state")').text())

        draft.set_state(State.objects.get(used=True, type="draft-iesg", slug="dead"))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertNotIn("Edit", q('tr:contains("IESG state")').text())


class EditInfoTests(TestCase):
    def test_edit_info(self):
        draft = WgDraftFactory(intended_std_level_id='ps',states=[('draft','active'),('draft-iesg','iesg-eva')])
        url = urlreverse('ietf.doc.views_draft.edit_info', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "secretary", url)

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form select[name=intended_std_level]')), 1)

        prev_ad = draft.ad
        # faulty post
        r = self.client.post(url, dict(ad="123456789"))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form .is-invalid')) > 0)
        draft = Document.objects.get(name=draft.name)
        self.assertEqual(draft.ad, prev_ad)

        # edit info
        events_before = draft.docevent_set.count()
        mailbox_before = len(outbox)

        new_ad = Person.objects.get(name="Ad No1")

        r = self.client.post(url,
                             dict(intended_std_level=str(draft.intended_std_level.pk),
                                  stream=draft.stream_id,
                                  ad=str(new_ad.pk),
                                  notify="test@example.com",
                                  telechat_date="",
                                  ))
        self.assertEqual(r.status_code, 302)

        draft = Document.objects.get(name=draft.name)
        self.assertEqual(draft.ad, new_ad)
        self.assertTrue(not draft.latest_event(TelechatDocEvent, type="scheduled_for_telechat"))
        self.assertEqual(draft.docevent_set.count(), events_before + 2)
        self.assertEqual(len(outbox), mailbox_before + 1)
        self.assertTrue(draft.name in outbox[-1]['Subject'])

    def test_edit_telechat_date(self):
        ad = Person.objects.get(user__username="ad")
        draft = WgDraftFactory(ad=ad,intended_std_level_id='ps',states=[('draft','active'),('draft-iesg','iesg-eva')])
        
        url = urlreverse('ietf.doc.views_draft.edit_info', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "secretary", url)

        data = dict(intended_std_level=str(draft.intended_std_level_id),
                    stream=draft.stream_id,
                    ad=str(draft.ad_id),
                    notify=draft.notify,
                    )

        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        # add to telechat
        mailbox_before=len(outbox)
        self.assertTrue(not draft.latest_event(TelechatDocEvent, type="scheduled_for_telechat"))
        data["telechat_date"] = TelechatDate.objects.active()[0].date.isoformat()
        r = self.client.post(url, data)
        self.assertEqual(r.status_code, 302)

        draft = Document.objects.get(name=draft.name)
        self.assertTrue(draft.latest_event(TelechatDocEvent, type="scheduled_for_telechat"))
        self.assertEqual(draft.latest_event(TelechatDocEvent, type="scheduled_for_telechat").telechat_date, TelechatDate.objects.active()[0].date)
        self.assertEqual(len(outbox),mailbox_before+1)
        self.assertTrue("Telechat update" in outbox[-1]['Subject'])
        self.assertTrue('iesg@' in outbox[-1]['To'])
        self.assertTrue('iesg-secretary@' in outbox[-1]['To'])

        # change telechat
        mailbox_before=len(outbox)
        data["telechat_date"] = TelechatDate.objects.active()[1].date.isoformat()
        r = self.client.post(url, data)
        self.assertEqual(r.status_code, 302)

        draft = Document.objects.get(name=draft.name)
        telechat_event = draft.latest_event(TelechatDocEvent, type="scheduled_for_telechat")
        self.assertEqual(telechat_event.telechat_date, TelechatDate.objects.active()[1].date)
        self.assertFalse(telechat_event.returning_item)
        self.assertEqual(len(outbox),mailbox_before+1)
        self.assertTrue("Telechat update" in outbox[-1]['Subject'])

        # change to a telechat that should cause returning item to be auto-detected
        # First, make it appear that the previous telechat has already passed
        telechat_event.telechat_date = date_today() - datetime.timedelta(days=7)
        telechat_event.save()
        ad = Person.objects.get(user__username="ad")
        ballot = create_ballot_if_not_open(None, draft, ad, 'approve')
        ballot.time = datetime_from_date(telechat_event.telechat_date)
        ballot.save()

        r = self.client.post(url, data)
        self.assertEqual(r.status_code, 302)

        draft = Document.objects.get(name=draft.name)
        telechat_event = draft.latest_event(TelechatDocEvent, type="scheduled_for_telechat")
        self.assertEqual(telechat_event.telechat_date, TelechatDate.objects.active()[1].date)
        self.assertTrue(telechat_event.returning_item)

        # remove from agenda
        mailbox_before=len(outbox)
        data["telechat_date"] = ""
        r = self.client.post(url, data)
        self.assertEqual(r.status_code, 302)

        draft = Document.objects.get(name=draft.name)
        self.assertTrue(not draft.latest_event(TelechatDocEvent, type="scheduled_for_telechat").telechat_date)
        self.assertEqual(len(outbox),mailbox_before+1)
        self.assertTrue("Telechat update" in outbox[-1]['Subject'])

        # Put it on an agenda that's very soon from now
        next_week = date_today() + datetime.timedelta(days=7)
        td =  TelechatDate.objects.active()[0]
        td.date = next_week
        td.save()
        data["telechat_date"] = next_week.isoformat()
        r = self.client.post(url,data)
        self.assertEqual(r.status_code, 302)
        self.assertIn("may not leave enough time", get_payload_text(outbox[-1]))

    def test_start_iesg_process_on_draft(self):
        draft = WgDraftFactory(
            name="draft-ietf-mars-test2",
            group__acronym="mars",
            intended_std_level_id="ps",
            authors=[Person.objects.get(user__username="ad")],
        )

        url = urlreverse("ietf.doc.views_draft.edit_info", kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "secretary", url)

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q("form select[name=intended_std_level]")), 1)
        self.assertEqual("", q("form textarea[name=notify]")[0].value.strip())

        events_before = list(draft.docevent_set.values_list("id", flat=True))
        mailbox_before = len(outbox)

        ad = Person.objects.get(name="Areað Irector")

        r = self.client.post(
            url,
            dict(
                intended_std_level=str(draft.intended_std_level_id),
                ad=ad.pk,
                notify="test@example.com",
                telechat_date="",
            ),
        )
        self.assertEqual(r.status_code, 302)

        draft = Document.objects.get(name=draft.name)
        self.assertEqual(draft.get_state_slug("draft-iesg"), "pub-req")
        self.assertEqual(draft.get_state_slug("draft-stream-ietf"), "sub-pub")
        self.assertEqual(draft.ad, ad)
        self.assertTrue(
            not draft.latest_event(TelechatDocEvent, type="scheduled_for_telechat")
        )
        # check that the expected events were created (don't insist on ordering)
        self.assertCountEqual(
            draft.docevent_set.exclude(id__in=events_before).values_list("type", flat=True),
            [
                "changed_action_holders",  # action holders set to AD
                "changed_document",  # WG state set to sub-pub
                "changed_document",  # AD set
                "changed_document",  # state change notice email set
                "started_iesg_process",  # IESG state is now pub-req
            ],
        )
        self.assertCountEqual(draft.action_holders.all(), [draft.ad])
        self.assertEqual(len(outbox), mailbox_before + 1)
        self.assertTrue("IESG processing" in outbox[-1]["Subject"])
        self.assertTrue("draft-ietf-mars-test2@" in outbox[-1]["To"])

    def test_edit_consensus(self):
        draft = WgDraftFactory()
        
        url = urlreverse('ietf.doc.views_draft.edit_consensus', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "secretary", url)

        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        # post
        self.assertTrue(not draft.latest_event(ConsensusDocEvent, type="changed_consensus"))
        r = self.client.post(url, dict(consensus="Yes"))
        self.assertEqual(r.status_code, 302)
        draft = Document.objects.get(name=draft.name)
        self.assertEqual(draft.latest_event(ConsensusDocEvent, type="changed_consensus").consensus, True)

        # reset
        e = DocEvent(doc=draft, rev=draft.rev, by=Person.objects.get(name="(System)"), type='changed_document')
        e.desc = "Intended Status changed to <b>%s</b> from %s"% (draft.intended_std_level_id, 'bcp')
        e.save()

        draft.intended_std_level_id = 'bcp'
        draft.save_with_history([e])
        r = self.client.post(url, dict(consensus="Unknown"))
        self.assertEqual(r.status_code, 403) # BCPs must have a consensus

        e = DocEvent(doc=draft, rev=draft.rev, by=Person.objects.get(name="(System)"), type='changed_document')
        e.desc = "Intended Status changed to <b>%s</b> from %s"% (draft.intended_std_level_id, 'inf')
        e.save()

        draft.intended_std_level_id = 'inf'
        draft.save_with_history([e])
        r = self.client.post(url, dict(consensus="Unknown"))
        self.assertEqual(r.status_code, 302)
        draft = Document.objects.get(name=draft.name)
        self.assertEqual(draft.latest_event(ConsensusDocEvent, type="changed_consensus").consensus, None)


class DraftFileMixin():
    '''A mixin to setup temporary draft directories and files'''
    def setUp(self):
        super().setUp()
        (Path(settings.INTERNET_DRAFT_ARCHIVE_DIR) / "unknown_ids").mkdir()
        (Path(settings.INTERNET_DRAFT_ARCHIVE_DIR) / "deleted_tombstones").mkdir()
        (Path(settings.INTERNET_DRAFT_ARCHIVE_DIR) / "expired_without_tombstone").mkdir()

    def write_draft_file(self, name, size):
        with (Path(settings.INTERNET_DRAFT_PATH) / name).open('w') as f:
            f.write("a" * size)


class ResurrectTests(DraftFileMixin, TestCase):
    def test_request_resurrect(self):
        draft = WgDraftFactory(states=[('draft','expired')])

        url = urlreverse('ietf.doc.views_draft.request_resurrect', kwargs=dict(name=draft.name))
        
        login_testing_unauthorized(self, "ad", url)

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('#content form [type=submit]')), 1)


        # request resurrect
        events_before = draft.docevent_set.count()
        mailbox_before = len(outbox)
        
        r = self.client.post(url, dict())
        self.assertEqual(r.status_code, 302)

        draft = Document.objects.get(name=draft.name)
        self.assertEqual(draft.docevent_set.count(), events_before + 1)
        e = draft.latest_event(type="requested_resurrect")
        self.assertTrue(e)
        self.assertEqual(e.by, Person.objects.get(name="Areað Irector"))
        self.assertTrue("Resurrection" in e.desc)
        self.assertEqual(len(outbox), mailbox_before + 1)
        self.assertTrue("Resurrection" in outbox[-1]['Subject'])
        self.assertTrue('internet-drafts@' in outbox[-1]['To'])

    def test_resurrect(self):
        ad = Person.objects.get(name="Areað Irector")
        draft = WgDraftFactory(ad=ad,states=[('draft','active')])
        DocEventFactory(doc=draft,type="requested_resurrect",by=ad)

        # create file and expire draft
        txt = "%s-%s.txt" % (draft.name, draft.rev)
        self.write_draft_file(txt, 5000)
        expire_draft(draft)

        # normal get
        url = urlreverse('ietf.doc.views_draft.resurrect', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "secretary", url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('#content form [type=submit]')), 1)

        # complete resurrect
        events_before = draft.docevent_set.count()
        mailbox_before = len(outbox)
        
        r = self.client.post(url, dict())
        self.assertEqual(r.status_code, 302)

        draft = Document.objects.get(name=draft.name)
        self.assertEqual(draft.docevent_set.count(), events_before + 1)
        self.assertEqual(draft.latest_event().type, "completed_resurrect")
        self.assertEqual(draft.get_state_slug(), "active")
        self.assertTrue(draft.expires >= timezone.now() + datetime.timedelta(days=settings.INTERNET_DRAFT_DAYS_TO_EXPIRE - 1))
        self.assertEqual(len(outbox), mailbox_before + 1)
        self.assertTrue('Resurrection Completed' in outbox[-1]['Subject'])
        self.assertTrue('iesg-secretary' in outbox[-1]['To'])
        self.assertTrue('aread' in outbox[-1]['To'])

        # ensure file restored from archive directory
        self.assertTrue(os.path.exists(os.path.join(settings.INTERNET_DRAFT_PATH, txt)))
        self.assertTrue(not os.path.exists(os.path.join(settings.INTERNET_DRAFT_ARCHIVE_DIR, txt)))


class ExpireIDsTests(DraftFileMixin, TestCase):
    def test_in_draft_expire_freeze(self):
        from ietf.doc.expire import in_draft_expire_freeze

        # If there is no "next" meeting, we mustn't be in a freeze
        self.assertTrue(not in_draft_expire_freeze())

        meeting = Meeting.objects.create(number="123",
                               type=MeetingTypeName.objects.get(slug="ietf"),
                               date=date_today())
        second_cut_off = meeting.get_second_cut_off()
        ietf_monday = meeting.get_ietf_monday()

        self.assertFalse(in_draft_expire_freeze((second_cut_off - datetime.timedelta(days=7)).replace(hour=0, minute=0, second=0)))
        self.assertFalse(in_draft_expire_freeze(second_cut_off.replace(hour=0, minute=0, second=0)))
        self.assertTrue(in_draft_expire_freeze((second_cut_off + datetime.timedelta(days=7)).replace(hour=0, minute=0, second=0)))
        self.assertTrue(in_draft_expire_freeze(
            datetime.datetime.combine(
                ietf_monday - datetime.timedelta(days=1),
                datetime.time(0, 0, 0),
                tzinfo=datetime.timezone.utc,
            )
        ))
        self.assertFalse(in_draft_expire_freeze(
            datetime.datetime.combine(ietf_monday, datetime.time(0, 0, 0), tzinfo=datetime.timezone.utc)
        ))
        
    def test_warn_expirable_drafts(self):
        from ietf.doc.expire import get_soon_to_expire_drafts, send_expire_warning_for_draft

        mars = GroupFactory(type_id='wg',acronym='mars')
        RoleFactory(group=mars, name_id='ad', person=Person.objects.get(user__username='ad'))
        draft = WgDraftFactory(name='draft-ietf-mars-test',group=mars)

        self.assertEqual(len(list(get_soon_to_expire_drafts(14))), 0)

        # hack into expirable state to expire in 10 days
        draft.set_state(State.objects.get(type_id='draft-iesg',slug='idexists'))
        draft.expires = timezone.now() + datetime.timedelta(days=10)
        draft.save_with_history([DocEvent.objects.create(doc=draft, rev=draft.rev, type="changed_document", by=Person.objects.get(user__username="secretary"), desc="Test")])

        self.assertEqual(len(list(get_soon_to_expire_drafts(14))), 1)
        
        # test send warning
        mailbox_before = len(outbox)

        send_expire_warning_for_draft(draft)

        self.assertEqual(len(outbox), mailbox_before + 1)
        self.assertTrue('draft-ietf-mars-test@' in outbox[-1]['To']) # Gets the authors
        self.assertTrue('mars-chairs@ietf.org' in outbox[-1]['Cc'])
        self.assertTrue('aread@' in outbox[-1]['Cc'])
        
        # hack into expirable state to expire in 10 hours
        draft.expires = timezone.now() + datetime.timedelta(hours=10)
        draft.save_with_history([DocEvent.objects.create(doc=draft, rev=draft.rev, type="changed_document", by=Person.objects.get(user__username="secretary"), desc="Test")])
        
        # test send warning is not sent for a document so close to expiration
        mailbox_before = len(outbox)
        send_expire_warning_for_draft(draft)
        self.assertEqual(len(outbox), mailbox_before)

        # Check that we don't sent expiration warnings for dead or replaced drafts
        old_state = draft.get_state_slug("draft-iesg")
        mailbox_before = len(outbox)
        draft.set_state(State.objects.get(type_id="draft-iesg",slug="dead"))
        send_expire_warning_for_draft(draft)
        self.assertEqual(len(outbox), mailbox_before,"Sent expiration warning for dead draft")
        draft.set_state(State.objects.get(type_id="draft-iesg",slug=old_state))

        mailbox_before = len(outbox)
        draft.set_state(State.objects.get(type_id="draft",slug="repl"))
        send_expire_warning_for_draft(draft)
        self.assertEqual(len(outbox), mailbox_before,"Sent expiration warning for replaced draft")

    def test_expire_drafts(self):
        mars = GroupFactory(type_id='wg',acronym='mars')
        ad = Person.objects.get(user__username='ad')
        ad_role = RoleFactory(group=mars, name_id='ad', person=ad)
        draft = WgDraftFactory(name='draft-ietf-mars-test',group=mars,ad=ad)
        DocEventFactory(type='started_iesg_process',by=ad_role.person,doc=draft,rev=draft.rev,desc="Started IESG Process")
        
        self.assertEqual(len(list(get_expired_drafts())), 0)
        
        # hack into expirable state
        draft.set_state(State.objects.get(type_id='draft-iesg',slug='idexists'))
        draft.expires = timezone.now()
        draft.save_with_history([DocEvent.objects.create(doc=draft, rev=draft.rev, type="changed_document", by=Person.objects.get(user__username="secretary"), desc="Test")])

        self.assertEqual(len(list(get_expired_drafts())), 1)

        draft.set_state(State.objects.get(used=True, type="draft-iesg", slug="iesg-eva"))

        self.assertEqual(len(list(get_expired_drafts())), 0)
        
        draft.action_holders.set([draft.ad])
        
        # test notice
        mailbox_before = len(outbox)

        send_expire_notice_for_draft(draft)

        self.assertEqual(len(outbox), mailbox_before + 1)
        self.assertTrue("expired" in outbox[-1]["Subject"])
        self.assertTrue('draft-ietf-mars-test@' in outbox[-1]['To']) # gets authors
        self.assertTrue('mars-chairs@ietf.org' in outbox[-1]['Cc'])
        self.assertTrue('aread@' in outbox[-1]['Cc'])

        # test expiry
        txt = "%s-%s.txt" % (draft.name, draft.rev)
        self.write_draft_file(txt, 5000)

        self.assertFalse(expirable_drafts(Document.objects.filter(pk=draft.pk)).exists())
        draft.set_state(State.objects.get(used=True, type="draft-iesg", slug="idexists"))
        self.assertTrue(expirable_drafts(Document.objects.filter(pk=draft.pk)).exists())
        expire_draft(draft)

        draft = Document.objects.get(name=draft.name)
        self.assertEqual(draft.get_state_slug(), "expired")
        self.assertEqual(draft.get_state_slug("draft-iesg"), "idexists")
        self.assertTrue(draft.latest_event(type="expired_document"))
        self.assertEqual(draft.action_holders.count(), 0)
        self.assertIn('Removed all action holders', draft.latest_event(type='changed_action_holders').desc)
        self.assertTrue(not os.path.exists(os.path.join(settings.INTERNET_DRAFT_PATH, txt)))
        self.assertTrue(os.path.exists(os.path.join(settings.INTERNET_DRAFT_ARCHIVE_DIR, txt)))

        draft.delete()

        rgdraft = RgDraftFactory(expires=timezone.now())
        self.assertEqual(len(list(get_expired_drafts())), 1)
        for slug in ('iesg-rev','irsgpoll'):
            rgdraft.set_state(State.objects.get(type_id='draft-stream-irtf',slug=slug))
            self.assertEqual(len(list(get_expired_drafts())), 0)


    def test_clean_up_draft_files(self):
        draft = WgDraftFactory()
        
        from ietf.doc.expire import clean_up_draft_files

        # put unknown file
        unknown = "draft-i-am-unknown-01.txt"
        self.write_draft_file(unknown, 5000)

        clean_up_draft_files()
        
        self.assertTrue(not os.path.exists(os.path.join(settings.INTERNET_DRAFT_PATH, unknown)))
        self.assertTrue(os.path.exists(os.path.join(settings.INTERNET_DRAFT_ARCHIVE_DIR, "unknown_ids", unknown)))

        
        # put file with malformed name (no revision)
        malformed = draft.name + ".txt"
        self.write_draft_file(malformed, 5000)

        clean_up_draft_files()
        
        self.assertTrue(not os.path.exists(os.path.join(settings.INTERNET_DRAFT_PATH, malformed)))
        self.assertTrue(os.path.exists(os.path.join(settings.INTERNET_DRAFT_ARCHIVE_DIR, "unknown_ids", malformed)))

        
        # RFC draft
        draft.set_state(State.objects.get(used=True, type="draft", slug="rfc"))

        txt = "%s-%s.txt" % (draft.name, draft.rev)
        self.write_draft_file(txt, 5000)
        pdf = "%s-%s.pdf" % (draft.name, draft.rev)
        self.write_draft_file(pdf, 5000)

        clean_up_draft_files()
        
        self.assertTrue(not os.path.exists(os.path.join(settings.INTERNET_DRAFT_PATH, txt)))
        self.assertTrue(os.path.exists(os.path.join(settings.INTERNET_DRAFT_ARCHIVE_DIR, txt)))

        self.assertTrue(not os.path.exists(os.path.join(settings.INTERNET_DRAFT_PATH, pdf)))
        self.assertTrue(os.path.exists(os.path.join(settings.INTERNET_DRAFT_ARCHIVE_DIR, pdf)))

        # expire draft
        draft.set_state(State.objects.get(used=True, type="draft", slug="expired"))
        draft.expires = timezone.now() - datetime.timedelta(days=1)
        draft.save_with_history([DocEvent.objects.create(doc=draft, rev=draft.rev, type="changed_document", by=Person.objects.get(user__username="secretary"), desc="Test")])

        e = DocEvent(doc=draft, rev=draft.rev, type= "expired_document", time=draft.expires,
                     by=Person.objects.get(name="(System)"))
        e.text="Document has expired"
        e.save()

        txt = "%s-%s.txt" % (draft.name, draft.rev)
        self.write_draft_file(txt, 5000)

        clean_up_draft_files()
        
        self.assertTrue(not os.path.exists(os.path.join(settings.INTERNET_DRAFT_PATH, txt)))
        self.assertTrue(os.path.exists(os.path.join(settings.INTERNET_DRAFT_ARCHIVE_DIR, txt)))


class ExpireLastCallTests(TestCase):
    def test_expire_last_call(self):
        from ietf.doc.lastcall import get_expired_last_calls, expire_last_call
        
        # check that non-expirable drafts aren't expired

        ad = Person.objects.get(user__username='ad')
        draft = WgDraftFactory(ad=ad,name='draft-ietf-mars-test')
        draft.set_state(State.objects.get(used=True, type="draft-iesg", slug="lc"))

        secretary = Person.objects.get(name="Sec Retary")
        
        self.assertEqual(len(list(get_expired_last_calls())), 0)

        e = LastCallDocEvent(doc=draft, rev=draft.rev, type="sent_last_call", by=secretary)
        e.text = "Last call sent"
        e.expires = timezone.now() + datetime.timedelta(days=14)
        e.save()
        
        self.assertEqual(len(list(get_expired_last_calls())), 0)

        # test expired
        e = LastCallDocEvent(doc=draft, rev=draft.rev, type="sent_last_call", by=secretary)
        e.text = "Last call sent"
        e.expires = timezone.now()
        e.save()
        
        drafts = list(get_expired_last_calls())
        self.assertEqual(len(drafts), 1)

        # expire it
        mailbox_before = len(outbox)
        events_before = draft.docevent_set.count()

        expire_last_call(drafts[0])

        draft = Document.objects.get(name=draft.name)
        self.assertEqual(draft.get_state_slug("draft-iesg"), "writeupw")
        self.assertEqual(draft.docevent_set.count(), events_before + 2)
        self.assertCountEqual(draft.action_holders.all(), [ad])
        self.assertIn('Changed action holders', draft.latest_event(type='changed_action_holders').desc)
        self.assertEqual(len(outbox), mailbox_before + 1)
        self.assertTrue("Last Call Expired" in outbox[-1]["Subject"])
        self.assertTrue('iesg-secretary@' in outbox[-1]['Cc'])
        self.assertTrue('aread@' in outbox[-1]['To'])
        self.assertTrue('draft-ietf-mars-test@' in outbox[-1]['To'])

    def test_expire_last_call_with_downref(self):
        from ietf.doc.lastcall import get_expired_last_calls, expire_last_call

        secretary = Person.objects.get(name="Sec Retary")
        ad = Person.objects.get(user__username='ad')
        draft = WgDraftFactory(ad=ad,name='draft-ietf-mars-test')
        draft.set_state(State.objects.get(used=True, type="draft-iesg", slug="lc"))

        e = LastCallDocEvent(doc=draft, rev=draft.rev, type="sent_last_call", by=secretary)
        e.text = "Last call sent"
        e.desc = "Blah, blah, blah.\n\nThis document makes the following downward references (downrefs):\n  ** Downref: Normative reference to an Experimental RFC: RFC 4764"
        e.expires = timezone.now()
        e.save()
        
        drafts = list(get_expired_last_calls())
        self.assertEqual(len(drafts), 1)

        mailbox_before = len(outbox)
        expire_last_call(drafts[0])

        d = Document.objects.get(name=draft.name)
        self.assertEqual(len(outbox), mailbox_before + 2)
        self.assertTrue("Review Downrefs From Expired Last Call" in outbox[-1]["Subject"])
        self.assertTrue(d.ad.email().address in outbox[-1]['To'])
        self.assertCountEqual(d.action_holders.all(), [ad])
        self.assertIn('Changed action holders', d.latest_event(type='changed_action_holders').desc)

class IndividualInfoFormsTests(TestCase):

    def setUp(self):
        super().setUp()
        doc = WgDraftFactory(group__acronym='mars',shepherd=PersonFactory(user__username='plain',name='Plain Man').email_set.first())
        self.docname = doc.name
        self.doc_group = doc.group

    def test_doc_change_stream(self):
        url = urlreverse('ietf.doc.views_draft.change_stream', kwargs=dict(name=self.docname))
        login_testing_unauthorized(self, "secretary", url)

        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('[type=submit]:contains("Save")')), 1)

        # shift to ISE stream
        empty_outbox()
        r = self.client.post(url,dict(stream="ise",comment="7gRMTjBM"))
        self.assertEqual(r.status_code,302)
        doc = Document.objects.get(name=self.docname)
        self.assertEqual(doc.stream_id,'ise')
        self.assertEqual(len(outbox), 1)
        self.assertTrue('Stream Change Notice' in outbox[0]['Subject'])
        self.assertTrue('rfc-ise@' in outbox[0]['To'])
        self.assertTrue('iesg@' in outbox[0]['To'])
        self.assertTrue('7gRMTjBM' in str(outbox[0]))
        self.assertTrue('7gRMTjBM' in doc.latest_event(DocEvent,type='added_comment').desc)

        # shift to an unknown stream (it must be possible to throw a document out of any stream)
        empty_outbox()
        r = self.client.post(url,dict(stream=""))
        self.assertEqual(r.status_code,302)
        doc = Document.objects.get(name=self.docname)
        self.assertEqual(doc.stream,None)
        self.assertTrue('rfc-ise@' in outbox[0]['To'])

    def test_doc_change_notify(self):
        url = urlreverse('ietf.doc.views_doc.edit_notify', kwargs=dict(name=self.docname))
        login_testing_unauthorized(self, "secretary", url)

        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form textarea[name=notify]')), 1)

        # Provide a list
        r = self.client.post(url,dict(notify="TJ2APh2P@ietf.org",save_addresses="1"))
        self.assertEqual(r.status_code,302)
        doc = Document.objects.get(name=self.docname)
        self.assertEqual(doc.notify,'TJ2APh2P@ietf.org')
        
        # Ask the form to regenerate the list
        r = self.client.post(url,dict(regenerate_addresses="1"))
        self.assertEqual(r.status_code,200)
        doc = Document.objects.get(name=self.docname)
        # Regenerate does not save!
        self.assertEqual(doc.notify,'TJ2APh2P@ietf.org')
        q = PyQuery(r.content)
        self.assertEqual("", q('form textarea[name=notify]')[0].value.strip())

    def test_doc_change_intended_status(self):
        url = urlreverse('ietf.doc.views_draft.change_intention', kwargs=dict(name=self.docname))
        login_testing_unauthorized(self, "secretary", url)

        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('[type=submit]:contains("Save")')), 1)

        # don't allow status level to be cleared
        r = self.client.post(url,dict(intended_std_level=""))
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form .is-invalid')) > 0)
        
        # change intended status level
        messages_before = len(outbox)
        r = self.client.post(url,dict(intended_std_level="bcp",comment="ZpyQFGmA"))
        self.assertEqual(r.status_code,302)
        doc = Document.objects.get(name=self.docname)
        self.assertEqual(doc.intended_std_level_id,'bcp')
        self.assertEqual(len(outbox),messages_before+1)
        self.assertTrue('Intended Status ' in outbox[-1]['Subject'])
        self.assertTrue('mars-chairs@' in outbox[-1]['To'])
        self.assertTrue('ZpyQFGmA' in str(outbox[-1]))

        self.assertTrue('ZpyQFGmA' in doc.latest_event(DocEvent,type='added_comment').desc)
       
    def test_doc_change_telechat_date(self):
        url = urlreverse('ietf.doc.views_doc.telechat_date', kwargs=dict(name=self.docname))
        login_testing_unauthorized(self, "secretary", url)

        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('[type=submit]:contains("Save")')), 1)

        # set a date
        empty_outbox()
        doc = Document.objects.get(name=self.docname)
        self.assertFalse(doc.latest_event(TelechatDocEvent, "scheduled_for_telechat"))
        telechat_date = TelechatDate.objects.active().order_by('date')[0].date
        r = self.client.post(url,dict(telechat_date=telechat_date.isoformat()))
        self.assertEqual(r.status_code,302)
        doc = Document.objects.get(name=self.docname)
        self.assertEqual(doc.latest_event(TelechatDocEvent, "scheduled_for_telechat").telechat_date,telechat_date)
        self.assertEqual(len(outbox), 1)
        self.assertTrue('Telechat update notice' in outbox[0]['Subject'])
        self.assertTrue('iesg@' in outbox[0]['To'])
        self.assertTrue('iesg-secretary@' in outbox[0]['To'])

        # Take the doc back off any telechat
        r = self.client.post(url,dict(telechat_date=""))
        self.assertEqual(r.status_code, 302)
        doc = Document.objects.get(name=self.docname)
        self.assertEqual(doc.latest_event(TelechatDocEvent, "scheduled_for_telechat").telechat_date,None)
        
    def test_doc_change_ad(self):
        url = urlreverse('ietf.doc.views_draft.edit_ad', kwargs=dict(name=self.docname))
        login_testing_unauthorized(self, "secretary", url)

        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form select[name=ad]')),1)
        
        # change ads
        ad2 = Person.objects.get(name='Ad No2')
        r = self.client.post(url,dict(ad=str(ad2.pk)))
        self.assertEqual(r.status_code,302)
        doc = Document.objects.get(name=self.docname)
        self.assertEqual(doc.ad,ad2)
        self.assertTrue(doc.latest_event(DocEvent,type="added_comment").desc.startswith('Shepherding AD changed'))

        doc.set_state(State.objects.get(type_id='draft-iesg',slug='lc'))
        r = self.client.post(url,dict())
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)
        self.assertTrue(q('.is-invalid'))

        doc.set_state(State.objects.get(type_id='draft-iesg',slug='idexists'))
        r = self.client.post(url,dict())
        self.assertEqual(r.status_code,302)
        doc = Document.objects.get(name=self.docname)
        self.assertEqual(doc.ad, None)

    def test_doc_change_ad_allows_pre_ad(self):
        """Pre-ADs can be responsible for documents"""
        # create a pre-AD
        doc = Document.objects.get(name=self.docname)
        pre_ad = RoleFactory(name_id='pre-ad', group=doc.group.parent).person

        url = urlreverse('ietf.doc.views_draft.edit_ad', kwargs=dict(name=self.docname))
        self.client.login(username='secretary', password='secretary+password')

        # test get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(
            len(q(f'form select[name=ad] option[value="{pre_ad.pk}"]')), 1,
            'Pre-AD should be an option for assignment',
        )

        # test post
        r = self.client.post(url, dict(ad=str(pre_ad.pk)))
        self.assertEqual(r.status_code, 302)
        doc = Document.objects.get(pk=doc.pk)  # refresh
        self.assertEqual(doc.ad, pre_ad, 'Pre-AD was not actually assigned')

    def test_doc_change_shepherd(self):
        doc = Document.objects.get(name=self.docname)
        doc.shepherd = None
        doc.save_with_history([DocEvent.objects.create(doc=doc, rev=doc.rev, type="changed_shepherd", by=Person.objects.get(user__username="secretary"), desc="Test")])

        url = urlreverse('ietf.doc.views_draft.edit_shepherd',kwargs=dict(name=self.docname))
        
        login_testing_unauthorized(self, "plain", url)

        r = self.client.get(url)
        self.assertEqual(r.status_code,403)

        # get as the secretariat (and remain secretariat)
        login_testing_unauthorized(self, "secretary", url)

        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form select[id=id_shepherd]')),1)

        # change the shepherd
        plain_email = Email.objects.get(person__name="Plain Man")
        r = self.client.post(url, dict(shepherd=plain_email.pk))
        self.assertEqual(r.status_code,302)
        doc = Document.objects.get(name=self.docname)
        self.assertEqual(doc.shepherd, plain_email)
        comment_events = doc.docevent_set.filter(time=doc.time,type="added_comment")
        comments = '::'.join([x.desc for x in comment_events])
        self.assertTrue('Document shepherd changed to Plain Man' in comments)
        self.assertTrue('Notification list changed' in comments)

        # save the form without changing the email (nothing should be saved)
        r = self.client.post(url, dict(shepherd=plain_email.pk))
        self.assertEqual(r.status_code, 302)
        doc = Document.objects.get(name=self.docname)
        self.assertEqual(set(comment_events), set(doc.docevent_set.filter(time=doc.time,type="added_comment")))
        r = self.client.get(url)
        self.assertTrue(any(['no changes have been made' in m.message for m in r.context['messages']]))

        # Remove the shepherd
        r = self.client.post(url, dict(shepherd=[]))
        self.assertEqual(r.status_code, 302)
        doc = Document.objects.get(name=self.docname)
        self.assertTrue(any(['Document shepherd changed to (None)' in x.desc for x in doc.docevent_set.filter(time=doc.time,type='added_comment')]))
        
        # test buggy change
        ad = Person.objects.get(name='Areað Irector')
        two_answers = "%s,%s" % (plain_email, ad.email_set.all()[0])
        r = self.client.post(url, dict(shepherd=two_answers))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form .is-invalid')) > 0)

    def test_doc_change_shepherd_email(self):
        doc = Document.objects.get(name=self.docname)
        doc.shepherd = None
        doc.save_with_history([DocEvent.objects.create(doc=doc, rev=doc.rev, type="changed_shepherd", by=Person.objects.get(user__username="secretary"), desc="Test")])

        url = urlreverse('ietf.doc.views_draft.change_shepherd_email',kwargs=dict(name=self.docname))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)

        doc.shepherd = Email.objects.get(person__user__username="ad1")
        doc.save_with_history([DocEvent.objects.create(doc=doc, rev=doc.rev, type="changed_shepherd", by=Person.objects.get(user__username="secretary"), desc="Test")])

        login_testing_unauthorized(self, "plain", url)

        doc.shepherd = Email.objects.get(person__user__username="plain")
        doc.save_with_history([DocEvent.objects.create(doc=doc, rev=doc.rev, type="changed_shepherd", by=Person.objects.get(user__username="secretary"), desc="Test")])

        new_email = Email.objects.create(address="anotheremail@example.com", person=doc.shepherd.person, origin=doc.shepherd.person.user.username)

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        # change the shepherd email
        r = self.client.post(url, dict(shepherd=new_email))
        self.assertEqual(r.status_code, 302)
        doc = Document.objects.get(name=self.docname)
        self.assertEqual(doc.shepherd, new_email)
        comment_event = doc.latest_event(DocEvent, type="added_comment")
        self.assertTrue(comment_event.desc.startswith('Document shepherd email changed'))

        # save the form without changing the email (nothing should be saved)
        r = self.client.post(url, dict(shepherd=new_email))
        self.assertEqual(r.status_code, 302)
        doc = Document.objects.get(name=self.docname)
        self.assertEqual(comment_event, doc.latest_event(DocEvent, type="added_comment"))

    def test_doc_view_shepherd_writeup_templates(self):
        url = urlreverse(
            "ietf.doc.views_doc.document_shepherd_writeup_template",
            kwargs=dict(type="group"),
        )

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('h1:contains("for Group Documents")')), 1)

        url = urlreverse(
            "ietf.doc.views_doc.document_shepherd_writeup_template",
            kwargs=dict(type="individual"),
        )

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('h1:contains("for Individual Documents")')), 1)

    def test_doc_view_shepherd_writeup(self):
        url = urlreverse('ietf.doc.views_doc.document_shepherd_writeup',kwargs=dict(name=self.docname))
  
        # get as a shepherd
        self.client.login(username="plain", password="plain+password")

        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('#content a:contains("Edit")')), 1)

        # Try again when no longer a shepherd.

        doc = Document.objects.get(name=self.docname)
        doc.shepherd = None
        doc.save_with_history([DocEvent.objects.create(doc=doc, rev=doc.rev, type="changed_shepherd", by=Person.objects.get(user__username="secretary"), desc="Test")])
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('#content a:contains("Edit")')), 0)

    def test_doc_change_shepherd_writeup(self):
        url = urlreverse('ietf.doc.views_draft.edit_shepherd_writeup',kwargs=dict(name=self.docname))
  
        # get
        login_testing_unauthorized(self, "secretary", url)

        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form textarea[id=id_content]')),1)

        # direct edit
        r = self.client.post(url,dict(content='here is a new writeup',submit_response="1"))
        self.assertEqual(r.status_code,302)
        doc = Document.objects.get(name=self.docname)
        self.assertTrue(doc.latest_event(WriteupDocEvent,type="changed_protocol_writeup").text.startswith('here is a new writeup'))

        # file upload
        test_file = io.StringIO("This is a different writeup.")
        test_file.name = "unnamed"
        r = self.client.post(url,dict(txt=test_file,submit_response="1"))
        self.assertEqual(r.status_code, 302)
        doc = Document.objects.get(name=self.docname)
        self.assertTrue(doc.latest_event(WriteupDocEvent,type="changed_protocol_writeup").text.startswith('This is a different writeup.'))

        # template reset
        r = self.client.post(url,dict(txt=test_file,reset_text="1"))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(q('textarea')[0].text.strip().startswith("# Document Shepherd Write-Up")) # TODO: This is a poor test of whether the reset did anything

    def test_edit_doc_extresources(self):
        url = urlreverse('ietf.doc.views_draft.edit_doc_extresources', kwargs=dict(name=self.docname))

        login_testing_unauthorized(self, "secretary", url)

        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form textarea[id=id_resources]')),1)

        badlines = (
            'github_repo https://github3.com/some/repo',
            'github_org https://github.com/not/an_org',
            'github_notify  badaddr',
            'website /not/a/good/url',
            'notavalidtag blahblahblah',
        )

        for line in badlines:
            r = self.client.post(url, dict(resources=line, submit="1"))
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            self.assertTrue(q('.invalid-feedback'))

        goodlines = """
            github_repo https://github.com/some/repo Some display text
            github_org https://github.com/totally_some_org
            github_username githubuser
            webpage http://example.com/http/is/fine
        """

        r = self.client.post(url, dict(resources=goodlines, submit="1"))
        self.assertEqual(r.status_code,302)
        doc = Document.objects.get(name=self.docname)
        self.assertEqual(doc.latest_event(DocEvent,type="changed_document").desc[:35], 'Changed document external resources')
        self.assertIn('github_username githubuser', doc.latest_event(DocEvent,type="changed_document").desc)
        self.assertEqual(doc.docextresource_set.count(), 4)
        self.assertEqual(doc.docextresource_set.get(name__slug='github_repo').display_name, 'Some display text')
        self.assertIn(doc.docextresource_set.first().name.slug,str(doc.docextresource_set.first()))

    # This is in views_doc, not views_draft, but there's already mixing and this keeps it with similar tests
    def do_doc_change_action_holders_test(self, username):
        # Set up people related to the doc to be sure shortcut buttons appear.
        doc = Document.objects.get(name=self.docname)
        doc.documentauthor_set.create(person=PersonFactory())
        doc.ad = Person.objects.get(user__username='ad')
        doc.shepherd = EmailFactory()
        doc.save_with_history([DocEvent.objects.create(doc=doc, rev=doc.rev, type="changed_shepherd", by=Person.objects.get(user__username="secretary"), desc="Test")])
        RoleFactory(name_id='chair', person=PersonFactory(), group=doc.group)
        RoleFactory(name_id='techadv', person=PersonFactory(), group=doc.group)
        RoleFactory(name_id='editor', person=PersonFactory(), group=doc.group)
        RoleFactory(name_id='secr', person=PersonFactory(), group=doc.group)
        some_other_chair = RoleFactory(name_id="chair").person

        url = urlreverse('ietf.doc.views_doc.edit_action_holders', kwargs=dict(name=doc.name))
        login_testing_unauthorized(self, some_other_chair.user.username, url)  # other chair can't edit action holders
        login_testing_unauthorized(self, username, url)
        
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form input[id=id_reason]')), 1)
        self.assertEqual(len(q('form select[id=id_action_holders]')), 1)
        for role_name in [
            'Author',
            'Responsible AD',
            'Shepherd',
            'Group Chair',
            'Group Tech Advisor',
            'Group Editor',
            'Group Secretary',
        ]:
            self.assertEqual(len(q('button:contains("Add %s")' % role_name)), 1, 
                             'Expected "Add %s" button' % role_name)
            self.assertEqual(len(q('button:contains("Remove %s")' % role_name)), 1,
                             'Expected "Remove %s" button for' % role_name)

        def _test_changing_ah(action_holders, reason):
            r = self.client.post(url, dict(
                reason=reason,
                action_holders=[str(p.pk) for p in action_holders],
            ))
            self.assertEqual(r.status_code, 302)
            doc = Document.objects.get(name=self.docname)
            self.assertCountEqual(doc.action_holders.all(), action_holders)
            event = doc.latest_event(type='changed_action_holders')
            self.assertIn(reason, event.desc)
            if action_holders:
                for ah in action_holders:
                    self.assertIn(ah.plain_name(), event.desc)
            else:
                self.assertIn('Removed all', event.desc)

        _test_changing_ah([doc.ad, doc.shepherd.person], 'this is a first test')
        _test_changing_ah([doc.ad], 'this is a second test')
        _test_changing_ah(doc.authors(), 'authors can do it, too')
        _test_changing_ah([], 'clear it back out')

    def test_doc_change_action_holders_as_doc_manager(self):
        # create a test RoleName and put it in the docman_roles for the document group
        RoleName.objects.create(slug="wrangler", name="Wrangler", used=True)
        self.doc_group.features.docman_roles.append("wrangler")
        self.doc_group.features.save()
        wrangler = RoleFactory(group=self.doc_group, name_id="wrangler").person
        self.do_doc_change_action_holders_test(wrangler.user.username)

    def test_doc_change_action_holders_as_secretary(self):
        self.do_doc_change_action_holders_test('secretary')

    def test_doc_change_action_holders_as_ad(self):
        self.do_doc_change_action_holders_test('ad')

    def do_doc_remind_action_holders_test(self, username):
        doc = Document.objects.get(name=self.docname)
        doc.action_holders.set(PersonFactory.create_batch(3))
        some_other_chair = RoleFactory(name_id="chair").person
    
        url = urlreverse('ietf.doc.views_doc.remind_action_holders', kwargs=dict(name=doc.name))
        
        login_testing_unauthorized(self, some_other_chair.user.username, url)  # other chair can't send reminder
        login_testing_unauthorized(self, username, url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form textarea[id=id_note]')), 1)
        self.assertEqual(len(q('button:contains("Send")')), 1)
        for ah in doc.action_holders.all():
            self.assertContains(r, escape(ah.name))

        empty_outbox()
        r = self.client.post(url, dict(note='this is my note'))  # note should be < 78 chars to avoid wrapping
        self.assertEqual(r.status_code, 302)

        self.assertEqual(len(outbox), 1)
        for ah in doc.action_holders.all():
            self.assertIn('Reminder: action needed', outbox[0]['Subject'])
            self.assertIn(ah.email_address(), outbox[0]['To'])
            self.assertIn(doc.display_name(), outbox[0].as_string())
            self.assertIn(doc.get_absolute_url(), outbox[0].as_string())
            self.assertIn('this is my note', outbox[0].as_string())

        # check that nothing is sent when no action holders
        doc.action_holders.clear()
        self.client.post(url)
        self.assertEqual(len(outbox), 1)  # still 1

    def test_doc_remind_action_holders_as_doc_manager(self):
        # create a test RoleName and put it in the docman_roles for the document group
        RoleName.objects.create(slug="wrangler", name="Wrangler", used=True)
        self.doc_group.features.docman_roles.append("wrangler")
        self.doc_group.features.save()
        wrangler = RoleFactory(group=self.doc_group, name_id="wrangler").person
        self.do_doc_remind_action_holders_test(wrangler.user.username)

    def test_doc_remind_action_holders_as_ad(self):
        self.do_doc_remind_action_holders_test('ad')

    def test_doc_remind_action_holders_as_secretary(self):
        self.do_doc_remind_action_holders_test('secretary')

class SubmitToIesgTests(TestCase):

    def setUp(self):
        super().setUp()
        role=RoleFactory(group__acronym='mars',name_id='chair',person=PersonFactory(user__username='marschairman'))
        doc=WgDraftFactory(
            name='draft-ietf-mars-test',
            group=role.group,
            ad=Person.objects.get(user__username='ad'),
            authors=PersonFactory.create_batch(3),
        )
        self.docname=doc.name

    def test_verify_permissions(self):

        def verify_fail(username):
            if username:
                self.client.login(username=username, password=username+"+password")
            r = self.client.get(url)
            self.assertEqual(r.status_code,404)

        def verify_can_see(username):
            self.client.login(username=username, password=username+"+password")
            r = self.client.get(url)
            self.assertEqual(r.status_code,200)
            q = PyQuery(r.content)
            self.assertEqual(len(q('form button[name="confirm"]')),1)

        url = urlreverse('ietf.doc.views_draft.to_iesg', kwargs=dict(name=self.docname))

        for username in [None,'plain','iana','iab chair']:
            verify_fail(username)

        for username in ['marschairman','secretary','ad']:
            verify_can_see(username)
        
    def test_cancel_submission(self):
        url = urlreverse('ietf.doc.views_draft.to_iesg', kwargs=dict(name=self.docname))
        self.client.login(username="marschairman", password="marschairman+password")

        r = self.client.post(url, dict(cancel="1"))
        self.assertEqual(r.status_code, 302)

        doc = Document.objects.get(name=self.docname)
        self.assertEqual(doc.get_state_slug('draft-iesg'),'idexists')
        self.assertCountEqual(doc.action_holders.all(), [])

    def test_confirm_submission(self):
        url = urlreverse('ietf.doc.views_draft.to_iesg', kwargs=dict(name=self.docname))
        self.client.login(username="marschairman", password="marschairman+password")

        doc = Document.objects.get(name=self.docname)
        docevents_pre = set(doc.docevent_set.all())
        mailbox_before = len(outbox)

        r = self.client.post(url, dict(confirm="1"))
        self.assertEqual(r.status_code, 302)

        doc = Document.objects.get(name=self.docname)
        self.assertTrue(doc.get_state('draft-iesg').slug=='pub-req')
        self.assertTrue(doc.get_state('draft-stream-ietf').slug=='sub-pub')

        self.assertCountEqual(doc.action_holders.all(), [doc.ad])

        new_docevents = set(doc.docevent_set.all()) - docevents_pre
        self.assertEqual(len(new_docevents), 4)
        new_docevent_type_count = Counter([e.type for e in new_docevents])
        self.assertEqual(new_docevent_type_count['changed_state'],2)
        self.assertEqual(new_docevent_type_count['started_iesg_process'],1)
        self.assertEqual(new_docevent_type_count['changed_action_holders'], 1)

        self.assertEqual(len(outbox), mailbox_before + 1)
        self.assertTrue("Publication has been requested" in outbox[-1]['Subject'])
        self.assertTrue("aread@" in outbox[-1]['To'])
        self.assertTrue("iesg-secretary@" in outbox[-1]['Cc'])

    def test_confirm_submission_no_doc_ad(self):
        url = urlreverse('ietf.doc.views_draft.to_iesg', kwargs=dict(name=self.docname))
        self.client.login(username="marschairman", password="marschairman+password")

        doc = Document.objects.get(name=self.docname)
        RoleFactory(name_id='ad', group=doc.group, person=doc.ad)
        e = DocEvent(type="changed_document", by=doc.ad, doc=doc, rev=doc.rev, desc="Remove doc AD")
        e.save()
        doc.ad = None
        doc.save_with_history([e])

        docevents_pre = set(doc.docevent_set.all())
        mailbox_before = len(outbox)

        r = self.client.post(url, dict(confirm="1"))
        self.assertEqual(r.status_code, 302)

        doc = Document.objects.get(name=self.docname)
        self.assertTrue(doc.get_state('draft-iesg').slug=='pub-req')
        self.assertTrue(doc.get_state('draft-stream-ietf').slug=='sub-pub')

        self.assertCountEqual(doc.action_holders.all(), [doc.ad])

        new_docevents = set(doc.docevent_set.all()) - docevents_pre
        self.assertEqual(len(new_docevents), 5)
        new_docevent_type_count = Counter([e.type for e in new_docevents])
        self.assertEqual(new_docevent_type_count['changed_state'],2)
        self.assertEqual(new_docevent_type_count['started_iesg_process'],1)
        self.assertEqual(new_docevent_type_count['changed_action_holders'], 1)
        self.assertEqual(new_docevent_type_count['changed_document'], 1)

        self.assertEqual(len(outbox), mailbox_before + 1)
        self.assertTrue("Publication has been requested" in outbox[-1]['Subject'])
        self.assertTrue("aread@" in outbox[-1]['To'])
        self.assertTrue("iesg-secretary@" in outbox[-1]['Cc'])



class RequestPublicationTests(TestCase):
    @mock.patch('ietf.sync.rfceditor.requests.post', autospec=True)
    def test_request_publication(self, mockobj):
        mockobj.return_value.text = b'OK'
        mockobj.return_value.status_code = 200
        #
        draft = IndividualDraftFactory(stream_id='iab',group__acronym='iab',intended_std_level_id='inf',states=[('draft-stream-iab','approved')])

        url = urlreverse('ietf.doc.views_draft.request_publication', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "iab-chair", url)

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        subject = q('input#id_subject')[0].get("value")
        self.assertTrue("Document Action" in subject)
        body = q('#id_body').text()
        self.assertTrue("Informational" in body)
        self.assertTrue("IAB" in body)

        # approve
        mailbox_before = len(outbox)

        r = self.client.post(url, dict(subject=subject, body=body))
        self.assertEqual(r.status_code, 302)

        draft = Document.objects.get(name=draft.name)
        self.assertEqual(draft.get_state_slug("draft-stream-iab"), "rfc-edit")

        self.assertEqual(len(outbox), mailbox_before + 2)

        self.assertTrue("Document Action" in outbox[-2]['Subject'])
        self.assertTrue("rfc-editor@" in outbox[-2]['To'])

        self.assertTrue("Document Action" in outbox[-1]['Subject'])
        self.assertTrue("drafts-approval@icann.org" in outbox[-1]['To'])

        self.assertTrue("Document Action" in draft.message_set.order_by("-time")[0].subject)

class ReleaseDraftTests(TestCase):
    def test_release_wg_draft(self):
        chair_role = RoleFactory(group__type_id='wg',name_id='chair') 
        draft = WgDraftFactory(group = chair_role.group)
        draft.tags.set(DocTagName.objects.filter(slug__in=('sh-f-up','w-merge'))) 
        other_chair_role = RoleFactory(group__type_id='wg',name_id='chair')

        url = urlreverse('ietf.doc.views_draft.release_draft', kwargs=dict(name=draft.name))

        r = self.client.get(url)
        self.assertEqual(r.status_code, 302) # redirect to login

        self.client.login(username=other_chair_role.person.user.username,password=other_chair_role.person.user.username+"+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 403)

        self.client.logout()
        self.client.login(username=chair_role.person.user.username, password=chair_role.person.user.username+"+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        events_before = list(draft.docevent_set.all())
        empty_outbox()
        r = self.client.post(url,{"comment": "Here are some comments"})
        self.assertEqual(r.status_code, 302)
        draft = Document.objects.get(pk=draft.pk)
        self.assertEqual(draft.stream, None)
        self.assertEqual(draft.group.type_id, "individ")
        self.assertFalse(draft.get_state('draft-stream-ietf'))
        self.assertEqual(len(outbox),3)
        subjects = [msg["Subject"] for msg in outbox]
        cat_subjects = "".join(subjects)
        self.assertIn("Tags changed", cat_subjects)
        self.assertIn("State Update", cat_subjects)
        self.assertIn("Stream Change", cat_subjects)
        descs = sorted([event.desc for event in set(list(draft.docevent_set.all())) - set(events_before)])
        self.assertEqual("Changed stream to <b>None</b> from IETF",descs[0])
        self.assertEqual("Here are some comments",descs[1])
        self.assertEqual("State changed to <b>None</b> from WG Document",descs[2])
        self.assertEqual("Tags Awaiting Merge with Other Document, Document Shepherd Followup cleared.",descs[3])

    def test_release_rg_draft(self):
        chair_role = RoleFactory(group__type_id='rg',name_id='chair')
        draft = RgDraftFactory(group = chair_role.group)
        url = urlreverse('ietf.doc.views_draft.release_draft', kwargs=dict(name=draft.name))
        self.client.login(username=chair_role.person.user.username, password=chair_role.person.user.username+"+password")
        r = self.client.post(url,{"comment": "Here are some comments"})
        self.assertEqual(r.status_code, 302)
        draft = Document.objects.get(pk=draft.pk)
        self.assertEqual(draft.stream, None)
        self.assertEqual(draft.group.type_id, "individ")
        self.assertFalse(draft.get_state('draft-stream-irtf'))

    def test_release_ise_draft(self):
        ise = Role.objects.get(name_id='chair', group__acronym='ise')
        draft = IndividualDraftFactory(stream_id='ise')
        draft.set_state(State.objects.get(type_id='draft-stream-ise',slug='ise-rev'))
        draft.tags.set(DocTagName.objects.filter(slug='w-dep'))
        url = urlreverse('ietf.doc.views_draft.release_draft', kwargs=dict(name=draft.name))

        self.client.login(username=ise.person.user.username, password=ise.person.user.username+'+password')

        events_before = list(draft.docevent_set.all())
        empty_outbox()
        r = self.client.post(url,{"comment": "Here are some comments"})
        self.assertEqual(r.status_code, 302)
        draft = Document.objects.get(pk=draft.pk)
        self.assertEqual(draft.stream, None)
        self.assertEqual(draft.group.type_id, "individ")
        self.assertFalse(draft.get_state('draft-stream-ise'))
        self.assertEqual(len(outbox),3)
        subjects = [msg["Subject"] for msg in outbox]
        cat_subjects = "".join(subjects)
        self.assertIn("Tags changed", cat_subjects)
        self.assertIn("State Update", cat_subjects)
        self.assertIn("Stream Change", cat_subjects)
        descs = sorted([event.desc for event in set(list(draft.docevent_set.all())) - set(events_before)])
        self.assertEqual("Changed stream to <b>None</b> from ISE",descs[0])
        self.assertEqual("Here are some comments",descs[1])
        self.assertEqual("State changed to <b>None</b> from In ISE Review",descs[2])
        self.assertEqual("Tag Waiting for Dependency on Other Document cleared.",descs[3])

class AdoptDraftTests(TestCase):
    def test_adopt_document(self):
        stream_state_type_slug = {
            "wg": "draft-stream-ietf",
            "ag": "draft-stream-ietf",
            "rg": "draft-stream-irtf",
            "rag": "draft-stream-irtf",
            "edwg": "draft-stream-editorial",
        }
        for type_id in ("wg", "ag", "rg", "rag", "edwg"):
            chair_role = RoleFactory(group__type_id=type_id,name_id='chair')
            draft = IndividualDraftFactory(notify=f'{type_id}group@example.mars')

            url = urlreverse('ietf.doc.views_draft.adopt_draft', kwargs=dict(name=draft.name))
            self.client.logout()
            login_testing_unauthorized(self, chair_role.person.user.username, url)

            # get
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)

            # call for adoption
            group_type_can_call_for_adoption = State.objects.filter(type_id=stream_state_type_slug[type_id],slug="c-adopt").exists()
            if group_type_can_call_for_adoption:
                empty_outbox()
                events_before = draft.docevent_set.count()
                call_issued = State.objects.get(type=stream_state_type_slug[type_id],slug='c-adopt')
                r = self.client.post(url,
                                    dict(comment="some comment",
                                        group=chair_role.group.pk,
                                        newstate=call_issued.pk,
                                        weeks="10"))
                self.assertEqual(r.status_code, 302)

                draft = Document.objects.get(pk=draft.pk)
                self.assertEqual(draft.get_state_slug(stream_state_type_slug[type_id]), "c-adopt")
                self.assertEqual(draft.group, chair_role.group)
                self.assertEqual(draft.stream_id, stream_state_type_slug[type_id][13:]) # trim off "draft-stream-"
                self.assertEqual(draft.docevent_set.count() - events_before, 5)
                self.assertEqual(len(outbox), 1)
                self.assertTrue("Call For Adoption" in outbox[-1]["Subject"])
                self.assertTrue(f"{chair_role.group.acronym}-chairs@" in outbox[-1]['To'])
                self.assertTrue(f"{draft.name}@" in outbox[-1]['To'])
                self.assertTrue(f"{chair_role.group.acronym}@" in outbox[-1]['To'])

            # adopt
            empty_outbox()
            events_before = draft.docevent_set.count()
            # There are several possible states that a stream can adopt into - we will only test one per stream
            stream_adopt_state_slug =  "wg-doc" if type_id in ("wg", "ag") else "active"
            stream_adopt_state = State.objects.get(type=stream_state_type_slug[type_id],slug=stream_adopt_state_slug)
            r = self.client.post(url,
                                dict(comment="some comment",
                                    group=chair_role.group.pk,
                                    newstate=stream_adopt_state.pk,
                                    weeks="10"))
            self.assertEqual(r.status_code, 302)

            draft = Document.objects.get(pk=draft.pk)
            self.assertEqual(draft.get_state_slug(stream_state_type_slug[type_id]), stream_adopt_state_slug)
            self.assertEqual(draft.group, chair_role.group)
            self.assertEqual(draft.stream_id, stream_state_type_slug[type_id][13:]) # trim off "draft-stream-"
            if type_id in ("wg", "ag"):
                self.assertEqual(
                    Counter(list(draft.docevent_set.values_list('type',flat=True))[events_before:]),
                    Counter({'changed_group': 1, 'changed_stream': 1, 'new_revision': 1})
                )
            else:
                self.assertEqual(
                    Counter(list(draft.docevent_set.values_list('type',flat=True))[events_before:]),
                    Counter({'changed_state': 1, 'added_comment': 1, 'changed_group': 1, 'changed_document': 1, 'changed_stream': 1, 'new_revision': 1})
                )
            self.assertEqual(len(outbox), 1 if type_id in ["wg", "ag"] else 2)
            self.assertTrue(stream_adopt_state.name in outbox[-1]["Subject"])
            self.assertTrue(f"{chair_role.group.acronym}-chairs@" in outbox[-1]['To'])
            self.assertTrue(f"{draft.name}@" in outbox[-1]['To'])
            self.assertTrue(f"{chair_role.group.acronym}@" in outbox[-1]['To'])
            if type_id not in ["wg", "ag"]:
                self.assertTrue(outbox[-2]["Subject"].endswith("to Informational"))
                # recipient fields tested elsewhere


class AdoptDraftFormTests(TestCase):
    def setUp(self):
        super().setUp()
        # test_data.py made a WG already, and made all the GroupFeatures
        # This will detect changes in that assumption
        self.chair_roles = {
            "wg": Group.objects.filter(
                type__features__acts_like_wg=True, state="active"
            )
            .get()
            .role_set.get(name_id="chair")
        }
        # This set of tests currently assumes all document adopting group types have "chair" in thier docman roles,
        # and only tests that the form acts correctly for chairs. It should be expanded to use all the roles it finds
        # in the group of docman roles (which comes from the production database by way of ietf/name/fixtures/names.json)
        for type_id in ["ag", "rg", "rag", "edwg"]:
            self.chair_roles[type_id] = RoleFactory(
                group__type_id=type_id, name_id="chair"
            )

    def test_form_init(self):
        secretariat = Person.objects.get(user__username="secretary")
        f = AdoptDraftForm(user=secretariat.user)
        form_offers_groups = f.fields["group"].queryset
        self.assertEqual(
            set(form_offers_groups.all()),
            set(
                Group.objects.filter(type__features__acts_like_wg=True, state="active")
            ),
        )
        self.assertEqual(form_offers_groups.count(), 5)
        form_offers_states = State.objects.filter(
            pk__in=[t[0] for t in f.fields["newstate"].choices[1:]]
        )
        self.assertEqual(
            Counter(form_offers_states.values_list("type_id", flat=True)),
            Counter(
                {
                    "draft-stream-irtf": 14,
                    "draft-stream-ietf": 12,
                    "draft-stream-editorial": 5,
                }
            ),
        )

        irtf_chair = Person.objects.get(user__username="irtf-chair")
        f = AdoptDraftForm(user=irtf_chair.user)
        form_offers_groups = f.fields["group"].queryset
        self.assertEqual(
            set(form_offers_groups.all()),
            set(Group.objects.filter(type_id__in=("rag", "rg"), state="active")),
        )
        self.assertEqual(form_offers_groups.count(), 2)
        form_offers_states = State.objects.filter(
            pk__in=[t[0] for t in f.fields["newstate"].choices[1:]]
        )
        self.assertEqual(
            set(form_offers_states.values_list("type_id", flat=True)),
            set(["draft-stream-irtf"]),
        )

        stream_state_type_slug = {
            "wg": "draft-stream-ietf",
            "ag": "draft-stream-ietf",
            "rg": "draft-stream-irtf",
            "rag": "draft-stream-irtf",
            "edwg": "draft-stream-editorial",
        }
        for type_id in self.chair_roles:
            f = AdoptDraftForm(user=self.chair_roles[type_id].person.user)
            form_offers_groups = f.fields["group"].queryset
            self.assertEqual(form_offers_groups.get(), self.chair_roles[type_id].group)
            form_offers_states = State.objects.filter(
                pk__in=[t[0] for t in f.fields["newstate"].choices[1:]]
            )
            self.assertEqual(
                set(form_offers_states.values_list("type_id", flat=True)),
                set([stream_state_type_slug[type_id]]),
            )

        edwgchair_role = self.chair_roles["edwg"]
        RoleFactory(group__type_id="wg", person=edwgchair_role.person, name_id="chair")
        RoleFactory(group__type_id="rg", person=edwgchair_role.person, name_id="chair")
        f = AdoptDraftForm(user=edwgchair_role.person.user)
        form_offers_groups = f.fields["group"].queryset
        self.assertEqual(
            set(form_offers_groups.values_list("type_id", flat=True)),
            set(["edwg", "wg", "rg"]),
        )
        self.assertEqual(form_offers_groups.count(), 3)
        form_offers_states = State.objects.filter(
            pk__in=[t[0] for t in f.fields["newstate"].choices[1:]]
        )
        self.assertEqual(
            set(form_offers_states.values_list("type_id", flat=True)),
            set(["draft-stream-irtf", "draft-stream-ietf", "draft-stream-editorial"]),
        )

        also_chairs_wg = RoleFactory(
            group__type_id="wg", person=irtf_chair, name_id="chair"
        )
        f = AdoptDraftForm(user=irtf_chair.user)
        form_offers_groups = f.fields["group"].queryset
        self.assertEqual(
            set(form_offers_groups.all()),
            set(
                Group.objects.filter(
                    Q(type_id__in=("rag", "rg")) | Q(pk=also_chairs_wg.group.pk),
                    state="active",
                )
            ),
        )
        self.assertEqual(form_offers_groups.count(), 4)
        form_offers_states = State.objects.filter(
            pk__in=[t[0] for t in f.fields["newstate"].choices[1:]]
        )
        self.assertEqual(
            set(form_offers_states.values_list("type_id", flat=True)),
            set(["draft-stream-irtf", "draft-stream-ietf"]),
        )

class ChangeStreamStateTests(TestCase):
    def test_set_tags(self):
        role = RoleFactory(name_id='chair',group__acronym='mars',group__list_email='mars-wg@ietf.org',person__user__username='marschairman',person__name='WG Cháir Man')
        RoleFactory(name_id='delegate',group=role.group,person__user__email='marsdelegate@example.org')
        draft = WgDraftFactory(group=role.group,shepherd=PersonFactory(user__username='plain',user__email='plain@example.com').email_set.first())
        draft.tags.set(DocTagName.objects.filter(slug="w-expert"))
        draft.group.unused_tags.add("w-refdoc")

        url = urlreverse('ietf.doc.views_draft.change_stream_state', kwargs=dict(name=draft.name, state_type="draft-stream-ietf"))
        login_testing_unauthorized(self, "marschairman", url)
        
        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        # make sure the unused tags are hidden
        unused = draft.group.unused_tags.values_list("slug", flat=True)
        for t in q("input[name=tags]"):
            self.assertTrue(t.attrib["value"] not in unused)

        # set tags
        mailbox_before = len(outbox)
        events_before = draft.docevent_set.count()
        r = self.client.post(url,
                             dict(new_state=draft.get_state("draft-stream-%s" % draft.stream_id).pk,
                                  comment="some comment",
                                  weeks="10",
                                  tags=["need-aut", "sheph-u"],
                                  ))
        self.assertEqual(r.status_code, 302)

        draft = Document.objects.get(pk=draft.pk)
        self.assertEqual(draft.tags.count(), 2)
        self.assertEqual(draft.tags.filter(slug="w-expert").count(), 0)
        self.assertEqual(draft.tags.filter(slug="need-aut").count(), 1)
        self.assertEqual(draft.tags.filter(slug="sheph-u").count(), 1)
        self.assertEqual(draft.docevent_set.count() - events_before, 2)
        self.assertEqual(len(outbox), mailbox_before + 1)
        self.assertTrue("tags changed" in outbox[-1]["Subject"].lower())
        self.assertTrue("mars-chairs@ietf.org" in outbox[-1].as_string())
        self.assertTrue("marsdelegate@example.org" in outbox[-1].as_string())
        self.assertTrue("plain@example.com" in outbox[-1].as_string())

    def test_set_initial_state(self):
        role = RoleFactory(name_id='chair',group__acronym='mars',group__list_email='mars-wg@ietf.org',person__user__username='marschairman',person__name='WG Cháir Man')
        RoleFactory(name_id='delegate',group=role.group,person__user__email='marsdelegate@ietf.org')
        draft = WgDraftFactory(group=role.group)
        draft.states.all().delete()

        url = urlreverse('ietf.doc.views_draft.change_stream_state', kwargs=dict(name=draft.name, state_type="draft-stream-ietf"))
        login_testing_unauthorized(self, "marschairman", url)
        
        # set a state when no state exists
        old_state = draft.get_state("draft-stream-%s" % draft.stream_id )
        self.assertEqual(old_state,None)
        new_state = State.objects.get(used=True, type="draft-stream-%s" % draft.stream_id, slug="parked")
        empty_outbox()
        events_before = draft.docevent_set.count()

        r = self.client.post(url,
                             dict(new_state=new_state.pk,
                                  comment="some comment",
                                  weeks="10",
                                  tags=[t.pk for t in draft.tags.filter(slug__in=get_tags_for_stream_id(draft.stream_id))],
                                  ))
        self.assertEqual(r.status_code, 302)

        draft = Document.objects.get(pk=draft.pk)
        self.assertEqual(draft.get_state("draft-stream-%s" % draft.stream_id), new_state)
        self.assertEqual(draft.docevent_set.count() - events_before, 2)
        reminder = DocReminder.objects.filter(event__doc=draft, type="stream-s")
        self.assertEqual(len(reminder), 1)
        due = timezone.now().astimezone(DEADLINE_TZINFO) + datetime.timedelta(weeks=10)
        self.assertTrue(
            due - datetime.timedelta(days=1) <= reminder[0].due <= due + datetime.timedelta(days=1),
            f'Due date {reminder[0].due} should be {due} +/- 1 day'
        )
        self.assertEqual(len(outbox), 1)
        self.assertTrue("state changed" in outbox[0]["Subject"].lower())
        self.assertTrue("mars-chairs@ietf.org" in outbox[0].as_string())
        self.assertTrue("marsdelegate@ietf.org" in outbox[0].as_string())

    def test_set_state(self):
        role = RoleFactory(name_id='chair',group__acronym='mars',group__list_email='mars-wg@ietf.org',person__user__username='marschairman',person__name='WG Cháir Man')
        RoleFactory(name_id='delegate',group=role.group,person__user__email='marsdelegate@ietf.org')
        draft = WgDraftFactory(group=role.group)

        url = urlreverse('ietf.doc.views_draft.change_stream_state', kwargs=dict(name=draft.name, state_type="draft-stream-ietf"))
        login_testing_unauthorized(self, "marschairman", url)
        
        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        # make sure the unused states are hidden
        unused = draft.group.unused_states.values_list("pk", flat=True)
        for t in q("select[name=new_state]").find("option[name=tags]"):
            self.assertTrue(t.attrib["value"] not in unused)
        self.assertEqual(len(q('select[name=new_state]')), 1)

        # set new state
        old_state = draft.get_state("draft-stream-%s" % draft.stream_id )
        new_state = State.objects.get(used=True, type="draft-stream-%s" % draft.stream_id, slug="parked")
        self.assertNotEqual(old_state, new_state)
        empty_outbox()
        events_before = draft.docevent_set.count()

        r = self.client.post(url,
                             dict(new_state=new_state.pk,
                                  comment="some comment",
                                  weeks="10",
                                  tags=[t.pk for t in draft.tags.filter(slug__in=get_tags_for_stream_id(draft.stream_id))],
                                  ))
        self.assertEqual(r.status_code, 302)

        draft = Document.objects.get(pk=draft.pk)
        self.assertEqual(draft.get_state("draft-stream-%s" % draft.stream_id), new_state)
        self.assertEqual(draft.docevent_set.count() - events_before, 2)
        reminder = DocReminder.objects.filter(event__doc=draft, type="stream-s")
        self.assertEqual(len(reminder), 1)
        due = timezone.now().astimezone(DEADLINE_TZINFO) + datetime.timedelta(weeks=10)
        self.assertTrue(
            due - datetime.timedelta(days=1) <= reminder[0].due <= due + datetime.timedelta(days=1),
            f'Due date {reminder[0].due} should be {due} +/- 1 day'
        )
        self.assertEqual(len(outbox), 1)
        self.assertTrue("state changed" in outbox[0]["Subject"].lower())
        self.assertTrue("mars-chairs@ietf.org" in outbox[0].as_string())
        self.assertTrue("marsdelegate@ietf.org" in outbox[0].as_string())

    def test_pubreq_validation(self):
        role = RoleFactory(name_id='chair',group__acronym='mars',group__list_email='mars-wg@ietf.org',person__user__username='marschairman',person__name='WG Cháir Man')
        RoleFactory(name_id='delegate',group=role.group,person__user__email='marsdelegate@ietf.org')
        draft = WgDraftFactory(group=role.group)

        url = urlreverse('ietf.doc.views_draft.change_stream_state', kwargs=dict(name=draft.name, state_type="draft-stream-ietf"))
        login_testing_unauthorized(self, "marschairman", url)
        
        old_state = draft.get_state("draft-stream-%s" % draft.stream_id )
        new_state = State.objects.get(used=True, type="draft-stream-%s" % draft.stream_id, slug="sub-pub")
        self.assertNotEqual(old_state, new_state)

        r = self.client.post(url,
                             dict(new_state=new_state.pk,
                                  comment="some comment",
                                  weeks="10",
                                  tags=[t.pk for t in draft.tags.filter(slug__in=get_tags_for_stream_id(draft.stream_id))],
                                  ))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form .is-invalid')) > 0)

class ChangeReplacesTests(TestCase):
    def setUp(self):
        super().setUp()
        role = RoleFactory(name_id='chair',group__acronym='mars',group__list_email='mars-wg@ietf.org',person__user__username='marschairman',person__name='WG Cháir Man')
        RoleFactory(name_id='delegate',group=role.group,person__user__email='marsdelegate@ietf.org')
        #draft = WgDraftFactory(group=role.group)

        mars_wg = Group.objects.get(acronym='mars')

        self.basea = WgDraftFactory(
            name="draft-test-base-a",
            title="Base A",
            group=mars_wg,
        )
        p = PersonFactory(name="basea_author")
        e = Email.objects.create(address="basea_author@example.com", person=p, origin=p.user.username)
        self.basea.documentauthor_set.create(person=p, email=e, order=1)

        self.baseb = WgDraftFactory(
            name="draft-test-base-b",
            title="Base B",
            group=mars_wg,
            expires = timezone.now() - datetime.timedelta(days = 365 - settings.INTERNET_DRAFT_DAYS_TO_EXPIRE),
        )
        p = PersonFactory(name="baseb_author")
        e = Email.objects.create(address="baseb_author@example.com", person=p, origin=p.user.username)
        self.baseb.documentauthor_set.create(person=p, email=e, order=1)

        self.replacea = WgDraftFactory(
            name="draft-test-replace-a",
            title="Replace Base A",
            group=mars_wg,
        )
        p = PersonFactory(name="replacea_author")
        e = Email.objects.create(address="replacea_author@example.com", person=p, origin=p.user.username)
        self.replacea.documentauthor_set.create(person=p, email=e, order=1)
 
        self.replaceboth = WgDraftFactory(
            name="draft-test-replace-both",
            title="Replace Base A and Base B",
            group=mars_wg,
        )
        p = PersonFactory(name="replaceboth_author")
        e = Email.objects.create(address="replaceboth_author@example.com", person=p, origin=p.user.username)
        self.replaceboth.documentauthor_set.create(person=p, email=e, order=1)
 
        self.basea.set_state(State.objects.get(used=True, type="draft", slug="active"))
        self.baseb.set_state(State.objects.get(used=True, type="draft", slug="expired"))
        self.replacea.set_state(State.objects.get(used=True, type="draft", slug="active"))
        self.replaceboth.set_state(State.objects.get(used=True, type="draft", slug="active"))


    def test_change_replaces(self):
        url = urlreverse('ietf.doc.views_draft.replaces', kwargs=dict(name=self.replacea.name))
        login_testing_unauthorized(self, "secretary", url)

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('[type=submit]:contains("Save")')), 1)
        
        # Post that says replacea replaces base a
        empty_outbox()
        RelatedDocument.objects.create(source=self.replacea, target=self.basea,
                                       relationship=DocRelationshipName.objects.get(slug="possibly-replaces"))
        self.assertEqual(self.basea.get_state().slug,'active')
        r = self.client.post(url, dict(replaces=self.basea.pk))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(RelatedDocument.objects.filter(relationship__slug='replaces',source=self.replacea).count(),1) 
        self.assertEqual(Document.objects.get(name='draft-test-base-a').get_state().slug,'repl')
        self.assertTrue(not RelatedDocument.objects.filter(relationship='possibly-replaces', source=self.replacea))
        self.assertEqual(len(outbox), 1)
        self.assertTrue('replacement status updated' in outbox[-1]['Subject'])
        self.assertTrue('replacea_author@' in outbox[-1]['To'])
        self.assertTrue('basea_author@' in outbox[-1]['To'])

        empty_outbox()
        # Post that says replaceboth replaces both base a and base b
        url = urlreverse('ietf.doc.views_draft.replaces', kwargs=dict(name=self.replaceboth.name))
        self.assertEqual(self.baseb.get_state().slug,'expired')
        r = self.client.post(url, dict(replaces=[self.basea.pk, self.baseb.pk]))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Document.objects.get(name='draft-test-base-a').get_state().slug,'repl')
        self.assertEqual(Document.objects.get(name='draft-test-base-b').get_state().slug,'repl')
        self.assertEqual(len(outbox), 1)
        self.assertTrue('basea_author@' in outbox[-1]['To'])
        self.assertTrue('baseb_author@' in outbox[-1]['To'])
        self.assertTrue('replaceboth_author@' in outbox[-1]['To'])

        # Post that undoes replaceboth
        empty_outbox()
        r = self.client.post(url, dict(replaces=[]))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Document.objects.get(name='draft-test-base-a').get_state().slug,'repl') # Because A is still also replaced by replacea
        self.assertEqual(Document.objects.get(name='draft-test-base-b').get_state().slug,'expired')
        self.assertEqual(len(outbox), 1)
        self.assertTrue('basea_author@' in outbox[-1]['To'])
        self.assertTrue('baseb_author@' in outbox[-1]['To'])
        self.assertTrue('replaceboth_author@' in outbox[-1]['To'])

        # Post that undoes replacea
        empty_outbox()
        url = urlreverse('ietf.doc.views_draft.replaces', kwargs=dict(name=self.replacea.name))
        r = self.client.post(url, dict(replaces=[]))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Document.objects.get(name='draft-test-base-a').get_state().slug,'active')
        self.assertTrue('basea_author@' in outbox[-1]['To'])
        self.assertTrue('replacea_author@' in outbox[-1]['To'])


    def test_review_possibly_replaces(self):
        replaced = self.basea
        RelatedDocument.objects.create(source=self.replacea, target=replaced,
                                       relationship=DocRelationshipName.objects.get(slug="possibly-replaces"))

        url = urlreverse('ietf.doc.views_draft.review_possibly_replaces', kwargs=dict(name=self.replacea.name))
        login_testing_unauthorized(self, "secretary", url)

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form[name=review-suggested-replaces]')), 1)

        r = self.client.post(url, dict(replaces=[replaced.pk]))
        self.assertEqual(r.status_code, 302)
        self.assertTrue(not self.replacea.related_that_doc("possibly-replaces"))
        self.assertEqual(len(self.replacea.related_that_doc("replaces")), 1)
        self.assertEqual(Document.objects.get(pk=self.basea.pk).get_state().slug, 'repl')

class MoreReplacesTests(TestCase):

    def test_stream_state_changes_when_replaced(self):
        self.client.login(username='secretary',password='secretary+password')
        for stream in ('iab','irtf','ise'):
            old_doc = IndividualDraftFactory(stream_id=stream)
            old_doc.set_state(State.objects.get(type_id='draft-stream-%s'%stream, slug='ise-rev' if stream=='ise' else 'active'))
            new_doc = IndividualDraftFactory(stream_id=stream)

            url = urlreverse('ietf.doc.views_draft.replaces', kwargs=dict(name=new_doc.name))
            r = self.client.post(url, dict(replaces=old_doc.pk))
            self.assertEqual(r.status_code,302)
            old_doc = Document.objects.get(name=old_doc.name)
            self.assertEqual(old_doc.get_state_slug('draft'),'repl')
            self.assertEqual(old_doc.get_state_slug('draft-stream-%s'%stream),'repl')

class ShepherdWriteupTests(TestCase):

    def test_shepherd_writeup_generation(self):
        ind_draft = IndividualDraftFactory(stream_id='ietf')
        wg_draft = WgDraftFactory()

        url = urlreverse('ietf.doc.views_draft.edit_shepherd_writeup', kwargs=dict(name=ind_draft.name))
        login_testing_unauthorized(self, "secretary", url)
        r = self.client.get(url)
        self.assertContains(r, "for Individual Documents", status_code=200)
        r = self.client.post(url,dict(reset_text=''))
        self.assertContains(r, "for Individual Documents", status_code=200)
        url = urlreverse('ietf.doc.views_draft.edit_shepherd_writeup', kwargs=dict(name=wg_draft.name))
        r = self.client.get(url)
        self.assertContains(r, "for Group Documents", status_code=200)
        r = self.client.post(url,dict(reset_text=''))
        self.assertContains(r, "for Group Documents", status_code=200)

class EditorialDraftMetadataTests(TestCase):
    def test_editorial_metadata(self):
        draft = EditorialDraftFactory()
        url = urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=draft.name))
        r = self.client.get(url)
        q = PyQuery(r.content)
        top_level_metadata_headings = q("tbody>tr>th:first-child").text()
        self.assertNotIn("IESG", top_level_metadata_headings)
        self.assertNotIn("IANA", top_level_metadata_headings)
