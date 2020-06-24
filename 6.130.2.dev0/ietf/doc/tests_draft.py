# Copyright The IETF Trust 2011-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import os
import shutil
import datetime
import io
import mock

from collections import Counter
from pyquery import PyQuery

from django.urls import reverse as urlreverse
from django.conf import settings

import debug                            # pyflakes:ignore

from ietf.doc.expire import get_expired_drafts, send_expire_notice_for_draft, expire_draft
from ietf.doc.factories import IndividualDraftFactory, WgDraftFactory, RgDraftFactory, DocEventFactory
from ietf.doc.models import ( Document, DocReminder, DocEvent,
    ConsensusDocEvent, LastCallDocEvent, RelatedDocument, State, TelechatDocEvent, 
    WriteupDocEvent, DocRelationshipName, IanaExpertDocEvent )
from ietf.doc.utils import get_tags_for_stream_id, create_ballot_if_not_open
from ietf.name.models import StreamName, DocTagName
from ietf.group.factories import GroupFactory, RoleFactory
from ietf.group.models import Group, Role
from ietf.person.factories import PersonFactory
from ietf.person.models import Person, Email
from ietf.meeting.models import Meeting, MeetingTypeName
from ietf.iesg.models import TelechatDate
from ietf.utils.test_utils import login_testing_unauthorized
from ietf.utils.mail import outbox, empty_outbox, get_payload_text
from ietf.utils.test_utils import TestCase


class ChangeStateTests(TestCase):
    def test_ad_approved(self):
        # get a draft in iesg evaluation, point raised
        ad = Person.objects.get(user__username="ad")
        draft = WgDraftFactory(ad=ad,states=[('draft','active'),('draft-iesg','iesg-eva')])
        DocEventFactory(type='started_iesg_process',by=ad,doc=draft,rev=draft.rev,desc="Started IESG Process")
        draft.tags.add("ad-f-up")

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
        self.assertEqual(draft.docevent_set.count(), events_before + 2)
        self.assertTrue("Test comment" in draft.docevent_set.all()[0].desc)
        self.assertTrue("IESG state changed" in draft.docevent_set.all()[1].desc)
        
        # should have sent two emails, the second one to the iesg with approved message
        self.assertEqual(len(outbox), mailbox_before + 2)
        self.assertTrue("Approved: " in outbox[-1]['Subject'])
        self.assertTrue(draft.name in outbox[-1]['Subject'])
        self.assertTrue('iesg@' in outbox[-1]['To'])
        
    def test_change_state(self):
        ad = Person.objects.get(user__username="ad")
        draft = WgDraftFactory(name='draft-ietf-mars-test',group__acronym='mars',ad=ad,states=[('draft','active'),('draft-iesg','ad-eval')])
        DocEventFactory(type='started_iesg_process',by=ad,doc=draft,rev=draft.rev,desc="Started IESG Process")

        url = urlreverse('ietf.doc.views_draft.change_state', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "secretary", url)

        first_state = draft.get_state("draft-iesg")
        next_states = first_state.next_states.all()

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form select[name=state]')), 1)
        
        if next_states:
            self.assertEqual(len(q('[type=submit][value="%s"]' % next_states[0].name)), 1)

            
        # faulty post
        r = self.client.post(url, dict(state=State.objects.get(used=True, type="draft", slug="active").pk))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form .has-error')) > 0)
        draft = Document.objects.get(name=draft.name)
        self.assertEqual(draft.get_state("draft-iesg"), first_state)

        
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
        self.assertEqual(draft.docevent_set.count(), events_before + 2)
        self.assertTrue("Test comment" in draft.docevent_set.all()[0].desc)
        self.assertTrue("IESG state changed" in draft.docevent_set.all()[1].desc)
        self.assertEqual(len(outbox), mailbox_before + 1)
        self.assertTrue("State Update Notice" in outbox[-1]['Subject'])
        self.assertTrue('draft-ietf-mars-test@' in outbox[-1]['To'])
        self.assertTrue('mars-chairs@' in outbox[-1]['To'])
        self.assertTrue('aread@' in outbox[-1]['To'])
        
        # check that we got a previous state now
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form [type=submit][value="%s"]' % first_state.name)), 1)

    def test_pull_from_rfc_queue(self):
        ad = Person.objects.get(user__username="ad")
        draft = WgDraftFactory(ad=ad,states=[('draft-iesg','rfcqueue')])
        DocEventFactory(type='started_iesg_process',by=ad,doc=draft,rev=draft.rev,desc="Started IESG Process")

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
        self.assertTrue(len(q('form .has-error')) > 0)
        draft = Document.objects.get(name=draft.name)
        self.assertEqual(draft.get_state("draft-iana-review"), first_state)

        # change state
        r = self.client.post(url, dict(state=next_state.pk))
        self.assertEqual(r.status_code, 302)

        draft = Document.objects.get(name=draft.name)
        self.assertEqual(draft.get_state("draft-iana-review"), next_state)

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
        draft = WgDraftFactory(ad=ad,states=[('draft-iesg','ad-eval')])
        DocEventFactory(type='started_iesg_process',by=ad,doc=draft,rev=draft.rev,desc="Started IESG Process")

        self.client.login(username="secretary", password="secretary+password")
        url = urlreverse('ietf.doc.views_draft.change_state', kwargs=dict(name=draft.name))

        empty_outbox()

        self.assertTrue(not draft.latest_event(type="changed_ballot_writeup_text"))
        r = self.client.post(url, dict(state=State.objects.get(used=True, type="draft-iesg", slug="lc-req").pk))
        self.assertEqual(r.status_code,200)
        self.assertContains(r, "Your request to issue")

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
        self.assertTrue(len(q('form .has-error')) > 0)
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
                                  note="New note",
                                  telechat_date="",
                                  ))
        self.assertEqual(r.status_code, 302)

        draft = Document.objects.get(name=draft.name)
        self.assertEqual(draft.ad, new_ad)
        self.assertEqual(draft.note, "New note")
        self.assertTrue(not draft.latest_event(TelechatDocEvent, type="scheduled_for_telechat"))
        self.assertEqual(draft.docevent_set.count(), events_before + 3)
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
                    note="",
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
        telechat_event.telechat_date = datetime.date.today()-datetime.timedelta(days=7)
        telechat_event.save()
        ad = Person.objects.get(user__username="ad")
        ballot = create_ballot_if_not_open(None, draft, ad, 'approve')
        ballot.time = telechat_event.telechat_date
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
        next_week = datetime.date.today()+datetime.timedelta(days=7)
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
            group__acronym='mars',
            intended_std_level_id="ps",
            authors=[Person.objects.get(user__username='ad')],
            )
        
        url = urlreverse('ietf.doc.views_draft.edit_info', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "secretary", url)

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form select[name=intended_std_level]')), 1)
        self.assertEqual(None,q('form input[name=notify]')[0].value)

        # add
        events_before = draft.docevent_set.count()
        mailbox_before = len(outbox)

        ad = Person.objects.get(name="Areað Irector")

        r = self.client.post(url,
                             dict(intended_std_level=str(draft.intended_std_level_id),
                                  ad=ad.pk,
                                  create_in_state=State.objects.get(used=True, type="draft-iesg", slug="watching").pk,
                                  notify="test@example.com",
                                  note="This is a note",
                                  telechat_date="",
                                  ))
        self.assertEqual(r.status_code, 302)

        draft = Document.objects.get(name=draft.name)
        self.assertEqual(draft.get_state_slug("draft-iesg"), "watching")
        self.assertEqual(draft.ad, ad)
        self.assertEqual(draft.note, "This is a note")
        self.assertTrue(not draft.latest_event(TelechatDocEvent, type="scheduled_for_telechat"))
        self.assertEqual(draft.docevent_set.count(), events_before + 4)
        events = list(draft.docevent_set.order_by('time', 'id'))
        self.assertEqual(events[-4].type, "started_iesg_process")
        self.assertEqual(len(outbox), mailbox_before+1)
        self.assertTrue('IESG processing' in outbox[-1]['Subject'])
        self.assertTrue('draft-ietf-mars-test2@' in outbox[-1]['To']) 

        # Redo, starting in publication requested to make sure WG state is also set
        draft.set_state(State.objects.get(type_id='draft-iesg', slug='idexists'))
        draft.set_state(State.objects.get(type='draft-stream-ietf',slug='writeupw'))
        draft.stream = StreamName.objects.get(slug='ietf')
        draft.save_with_history([DocEvent.objects.create(doc=draft, rev=draft.rev, type="changed_stream", by=Person.objects.get(user__username="secretary"), desc="Test")])
        r = self.client.post(url,
                             dict(intended_std_level=str(draft.intended_std_level_id),
                                  ad=ad.pk,
                                  create_in_state=State.objects.get(used=True, type="draft-iesg", slug="pub-req").pk,
                                  notify="test@example.com",
                                  note="This is a note",
                                  telechat_date="",
                                  ))
        self.assertEqual(r.status_code, 302)
        draft = Document.objects.get(name=draft.name)
        self.assertEqual(draft.get_state_slug('draft-iesg'),'pub-req')
        self.assertEqual(draft.get_state_slug('draft-stream-ietf'),'sub-pub')

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
        self.saved_id_dir = settings.INTERNET_DRAFT_PATH
        self.saved_archive_dir = settings.INTERNET_DRAFT_ARCHIVE_DIR
        self.id_dir = self.tempdir('id')
        self.archive_dir = self.tempdir('id-archive')
        os.mkdir(os.path.join(self.archive_dir, "unknown_ids"))
        os.mkdir(os.path.join(self.archive_dir, "deleted_tombstones"))
        os.mkdir(os.path.join(self.archive_dir, "expired_without_tombstone"))

        settings.INTERNET_DRAFT_PATH = self.id_dir
        settings.INTERNET_DRAFT_ARCHIVE_DIR = self.archive_dir

    def tearDown(self):
        shutil.rmtree(self.id_dir)
        shutil.rmtree(self.archive_dir)
        settings.INTERNET_DRAFT_PATH = self.saved_id_dir
        settings.INTERNET_DRAFT_ARCHIVE_DIR = self.saved_archive_dir

    def write_draft_file(self, name, size):
        f = io.open(os.path.join(self.id_dir, name), 'w')
        f.write("a" * size)
        f.close()


class ResurrectTests(DraftFileMixin, TestCase):
    def test_request_resurrect(self):
        draft = WgDraftFactory(states=[('draft','expired')])

        url = urlreverse('ietf.doc.views_draft.request_resurrect', kwargs=dict(name=draft.name))
        
        login_testing_unauthorized(self, "ad", url)

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form [type=submit]')), 1)


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
        self.assertEqual(len(q('form [type=submit]')), 1)

        # complete resurrect
        events_before = draft.docevent_set.count()
        mailbox_before = len(outbox)
        
        r = self.client.post(url, dict())
        self.assertEqual(r.status_code, 302)

        draft = Document.objects.get(name=draft.name)
        self.assertEqual(draft.docevent_set.count(), events_before + 1)
        self.assertEqual(draft.latest_event().type, "completed_resurrect")
        self.assertEqual(draft.get_state_slug(), "active")
        self.assertTrue(draft.expires >= datetime.datetime.now() + datetime.timedelta(days=settings.INTERNET_DRAFT_DAYS_TO_EXPIRE - 1))
        self.assertEqual(len(outbox), mailbox_before + 1)
        self.assertTrue('Resurrection Completed' in outbox[-1]['Subject'])
        self.assertTrue('iesg-secretary' in outbox[-1]['To'])
        self.assertTrue('aread' in outbox[-1]['To'])

        # ensure file restored from archive directory
        self.assertTrue(os.path.exists(os.path.join(self.id_dir, txt)))
        self.assertTrue(not os.path.exists(os.path.join(self.archive_dir, txt)))


class ExpireIDsTests(DraftFileMixin, TestCase):
    def test_in_draft_expire_freeze(self):
        from ietf.doc.expire import in_draft_expire_freeze

        meeting = Meeting.objects.create(number="123",
                               type=MeetingTypeName.objects.get(slug="ietf"),
                               date=datetime.date.today())
        second_cut_off = meeting.get_second_cut_off()
        ietf_monday = meeting.get_ietf_monday()

        self.assertTrue(not in_draft_expire_freeze(datetime.datetime.combine(second_cut_off - datetime.timedelta(days=7), datetime.time(0, 0, 0))))
        self.assertTrue(not in_draft_expire_freeze(datetime.datetime.combine(second_cut_off, datetime.time(0, 0, 0))))
        self.assertTrue(in_draft_expire_freeze(datetime.datetime.combine(second_cut_off + datetime.timedelta(days=7), datetime.time(0, 0, 0))))
        self.assertTrue(in_draft_expire_freeze(datetime.datetime.combine(ietf_monday - datetime.timedelta(days=1), datetime.time(0, 0, 0))))
        self.assertTrue(not in_draft_expire_freeze(datetime.datetime.combine(ietf_monday, datetime.time(0, 0, 0))))
        
    def test_warn_expirable_drafts(self):
        from ietf.doc.expire import get_soon_to_expire_drafts, send_expire_warning_for_draft

        mars = GroupFactory(type_id='wg',acronym='mars')
        RoleFactory(group=mars, name_id='ad', person=Person.objects.get(user__username='ad'))
        draft = WgDraftFactory(name='draft-ietf-mars-test',group=mars)

        self.assertEqual(len(list(get_soon_to_expire_drafts(14))), 0)

        # hack into expirable state
        draft.set_state(State.objects.get(type_id='draft-iesg',slug='idexists'))
        draft.expires = datetime.datetime.now() + datetime.timedelta(days=10)
        draft.save_with_history([DocEvent.objects.create(doc=draft, rev=draft.rev, type="changed_document", by=Person.objects.get(user__username="secretary"), desc="Test")])

        self.assertEqual(len(list(get_soon_to_expire_drafts(14))), 1)
        
        # test send warning
        mailbox_before = len(outbox)

        send_expire_warning_for_draft(draft)

        self.assertEqual(len(outbox), mailbox_before + 1)
        self.assertTrue('draft-ietf-mars-test@' in outbox[-1]['To']) # Gets the authors
        self.assertTrue('mars-chairs@ietf.org' in outbox[-1]['Cc'])
        self.assertTrue('aread@' in outbox[-1]['Cc'])
        
    def test_expire_drafts(self):
        mars = GroupFactory(type_id='wg',acronym='mars')
        ad_role = RoleFactory(group=mars, name_id='ad', person=Person.objects.get(user__username='ad'))
        draft = WgDraftFactory(name='draft-ietf-mars-test',group=mars)
        DocEventFactory(type='started_iesg_process',by=ad_role.person,doc=draft,rev=draft.rev,desc="Started IESG Process")
        
        self.assertEqual(len(list(get_expired_drafts())), 0)
        
        # hack into expirable state
        draft.set_state(State.objects.get(type_id='draft-iesg',slug='idexists'))
        draft.expires = datetime.datetime.now()
        draft.save_with_history([DocEvent.objects.create(doc=draft, rev=draft.rev, type="changed_document", by=Person.objects.get(user__username="secretary"), desc="Test")])

        self.assertEqual(len(list(get_expired_drafts())), 1)

        draft.set_state(State.objects.get(used=True, type="draft-iesg", slug="watching"))

        self.assertEqual(len(list(get_expired_drafts())), 1)

        draft.set_state(State.objects.get(used=True, type="draft-iesg", slug="iesg-eva"))

        self.assertEqual(len(list(get_expired_drafts())), 0)
        
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

        expire_draft(draft)

        draft = Document.objects.get(name=draft.name)
        self.assertEqual(draft.get_state_slug(), "expired")
        self.assertEqual(draft.get_state_slug("draft-iesg"), "dead")
        self.assertTrue(draft.latest_event(type="expired_document"))
        self.assertTrue(not os.path.exists(os.path.join(self.id_dir, txt)))
        self.assertTrue(os.path.exists(os.path.join(self.archive_dir, txt)))

        draft.delete()

        rgdraft = RgDraftFactory(expires=datetime.datetime.now())
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
        
        self.assertTrue(not os.path.exists(os.path.join(self.id_dir, unknown)))
        self.assertTrue(os.path.exists(os.path.join(self.archive_dir, "unknown_ids", unknown)))

        
        # put file with malformed name (no revision)
        malformed = draft.name + ".txt"
        self.write_draft_file(malformed, 5000)

        clean_up_draft_files()
        
        self.assertTrue(not os.path.exists(os.path.join(self.id_dir, malformed)))
        self.assertTrue(os.path.exists(os.path.join(self.archive_dir, "unknown_ids", malformed)))

        
        # RFC draft
        draft.set_state(State.objects.get(used=True, type="draft", slug="rfc"))

        txt = "%s-%s.txt" % (draft.name, draft.rev)
        self.write_draft_file(txt, 5000)
        pdf = "%s-%s.pdf" % (draft.name, draft.rev)
        self.write_draft_file(pdf, 5000)

        clean_up_draft_files()
        
        self.assertTrue(not os.path.exists(os.path.join(self.id_dir, txt)))
        self.assertTrue(os.path.exists(os.path.join(self.archive_dir, txt)))

        self.assertTrue(not os.path.exists(os.path.join(self.id_dir, pdf)))
        self.assertTrue(os.path.exists(os.path.join(self.archive_dir, pdf)))

        # expire draft
        draft.set_state(State.objects.get(used=True, type="draft", slug="expired"))
        draft.expires = datetime.datetime.now() - datetime.timedelta(days=1)
        draft.save_with_history([DocEvent.objects.create(doc=draft, rev=draft.rev, type="changed_document", by=Person.objects.get(user__username="secretary"), desc="Test")])

        e = DocEvent(doc=draft, rev=draft.rev, type= "expired_document", time=draft.expires,
                     by=Person.objects.get(name="(System)"))
        e.text="Document has expired"
        e.save()

        txt = "%s-%s.txt" % (draft.name, draft.rev)
        self.write_draft_file(txt, 5000)

        clean_up_draft_files()
        
        self.assertTrue(not os.path.exists(os.path.join(self.id_dir, txt)))
        self.assertTrue(os.path.exists(os.path.join(self.archive_dir, txt)))


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
        e.expires = datetime.datetime.now() + datetime.timedelta(days=14)
        e.save()
        
        self.assertEqual(len(list(get_expired_last_calls())), 0)

        # test expired
        e = LastCallDocEvent(doc=draft, rev=draft.rev, type="sent_last_call", by=secretary)
        e.text = "Last call sent"
        e.expires = datetime.datetime.now()
        e.save()
        
        drafts = list(get_expired_last_calls())
        self.assertEqual(len(drafts), 1)

        # expire it
        mailbox_before = len(outbox)
        events_before = draft.docevent_set.count()
        
        expire_last_call(drafts[0])

        draft = Document.objects.get(name=draft.name)
        self.assertEqual(draft.get_state_slug("draft-iesg"), "writeupw")
        self.assertEqual(draft.docevent_set.count(), events_before + 1)
        self.assertEqual(len(outbox), mailbox_before + 1)
        self.assertTrue("Last Call Expired" in outbox[-1]["Subject"])
        self.assertTrue('iesg-secretary@' in outbox[-1]['Cc'])
        self.assertTrue('aread@' in outbox[-1]['To'])
        self.assertTrue('draft-ietf-mars-test@' in outbox[-1]['To'])

class IndividualInfoFormsTests(TestCase):

    def setUp(self):
        doc = WgDraftFactory(group__acronym='mars',shepherd=PersonFactory(user__username='plain',name='Plain Man').email_set.first())
        self.docname = doc.name

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
        self.assertEqual(len(q('form input[name=notify]')),1)

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
        self.assertEqual(None,q('form input[name=notify]')[0].value)

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
        self.assertTrue(len(q('form .has-error')) > 0)
        
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
        
    def test_doc_change_iesg_note(self):
        url = urlreverse('ietf.doc.views_draft.edit_iesg_note', kwargs=dict(name=self.docname))
        login_testing_unauthorized(self, "secretary", url)

        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('[type=submit]:contains("Save")')),1)

        # post
        r = self.client.post(url,dict(note='ZpyQFGmA\r\nZpyQFGmA'))
        self.assertEqual(r.status_code,302)
        doc = Document.objects.get(name=self.docname)
        self.assertEqual(doc.note,'ZpyQFGmA\nZpyQFGmA')
        self.assertTrue('ZpyQFGmA' in doc.latest_event(DocEvent,type='added_comment').desc)

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
        self.assertTrue(q('.has-error'))

        doc.set_state(State.objects.get(type_id='draft-iesg',slug='idexists'))
        r = self.client.post(url,dict())
        self.assertEqual(r.status_code,302)
        doc = Document.objects.get(name=self.docname)
        self.assertEqual(doc.ad, None)

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
        self.assertEqual(len(q('form input[id=id_shepherd]')),1)

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
        r = self.client.post(url, dict(shepherd=''))
        self.assertEqual(r.status_code, 302)
        doc = Document.objects.get(name=self.docname)
        self.assertTrue(any(['Document shepherd changed to (None)' in x.desc for x in doc.docevent_set.filter(time=doc.time,type='added_comment')]))
        
        # test buggy change
        ad = Person.objects.get(name='Areað Irector')
        two_answers = "%s,%s" % (plain_email, ad.email_set.all()[0])
        r = self.client.post(url, dict(shepherd=two_answers))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form .has-error')) > 0)

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
        self.assertTrue(q('textarea')[0].text.strip().startswith("As required by RFC 4858"))

    def test_doc_change_document_urls(self):
        url = urlreverse('ietf.doc.views_draft.edit_document_urls', kwargs=dict(name=self.docname))
  
        # get
        login_testing_unauthorized(self, "secretary", url)

        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form textarea[id=id_urls]')),1)

        # direct edit
        r = self.client.post(url, dict(urls='wiki https://wiki.org/ Wiki\nrepository https://repository.org/ Repo\n', submit="1"))
        self.assertEqual(r.status_code,302)
        doc = Document.objects.get(name=self.docname)
        self.assertTrue(doc.latest_event(DocEvent,type="changed_document").desc.startswith('Changed document URLs'))
        self.assertIn('wiki https://wiki.org/', doc.latest_event(DocEvent,type="changed_document").desc)
        self.assertIn('https://wiki.org/', [ u.url for u in doc.documenturl_set.all() ])

class SubmitToIesgTests(TestCase):

    def setUp(self):
        role=RoleFactory(group__acronym='mars',name_id='chair',person=PersonFactory(user__username='marschairman'))
        doc=WgDraftFactory(name='draft-ietf-mars-test',group=role.group,ad=Person.objects.get(user__username='ad'))
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
            self.assertEqual(len(q('form input[name="confirm"]')),1) 

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

        # It's not clear what this testing - the view can certainly
        # leave the document without an ad. This line as written only
        # checks whether the setup document had an ad or not.
        self.assertTrue(doc.ad!=None)

        new_docevents = set(doc.docevent_set.all()) - docevents_pre
        self.assertEqual(len(new_docevents),3)
        new_docevent_type_count = Counter([e.type for e in new_docevents])
        self.assertEqual(new_docevent_type_count['changed_state'],2)
        self.assertEqual(new_docevent_type_count['started_iesg_process'],1)

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
        RoleFactory(group__acronym='mars',group__list_email='mars-wg@ietf.org',person__user__username='marschairman',name_id='chair')
        draft = IndividualDraftFactory(name='draft-ietf-mars-test',notify='aliens@example.mars')

        url = urlreverse('ietf.doc.views_draft.adopt_draft', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "marschairman", url)
        
        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form select[name="group"] option')), 1) # we can only select "mars"

        # adopt in mars WG
        mailbox_before = len(outbox)
        events_before = draft.docevent_set.count()
        mars = Group.objects.get(acronym="mars")
        call_issued = State.objects.get(type='draft-stream-ietf',slug='c-adopt')
        r = self.client.post(url,
                             dict(comment="some comment",
                                  group=mars.pk,
                                  newstate=call_issued.pk,
                                  weeks="10"))
        self.assertEqual(r.status_code, 302)

        draft = Document.objects.get(pk=draft.pk)
        self.assertEqual(draft.group.acronym, "mars")
        self.assertEqual(draft.stream_id, "ietf")
        self.assertEqual(draft.docevent_set.count() - events_before, 5)
        self.assertEqual(draft.notify,"aliens@example.mars")
        self.assertEqual(len(outbox), mailbox_before + 1)
        self.assertTrue("Call For Adoption" in outbox[-1]["Subject"])
        self.assertTrue("mars-chairs@ietf.org" in outbox[-1]['To'])
        self.assertTrue("draft-ietf-mars-test@" in outbox[-1]['To'])
        self.assertTrue("mars-wg@" in outbox[-1]['To'])

        self.assertFalse(mars.list_email in draft.notify)

    def test_right_state_choices_offered(self):
        draft = IndividualDraftFactory()
        wg = GroupFactory(type_id='wg',state_id='active')
        rg = GroupFactory(type_id='rg',state_id='active')
        person = PersonFactory(user__username='person')

        self.client.login(username='person',password='person+password')
        url = urlreverse('ietf.doc.views_draft.adopt_draft', kwargs=dict(name=draft.name))

        person.role_set.create(name_id='chair',group=wg,email=person.email())
        r = self.client.get(url)
        q = PyQuery(r.content)
        self.assertTrue('(IETF)' in q('#id_newstate option').text())
        self.assertFalse('(IRTF)' in q('#id_newstate option').text())

        person.role_set.create(name_id='chair',group=Group.objects.get(acronym='irtf'),email=person.email())
        r = self.client.get(url)
        q = PyQuery(r.content)
        self.assertTrue('(IETF)' in q('#id_newstate option').text())
        self.assertTrue('(IRTF)' in q('#id_newstate option').text())

        person.role_set.filter(group__acronym='irtf').delete()
        person.role_set.create(name_id='chair',group=rg,email=person.email())
        r = self.client.get(url)
        q = PyQuery(r.content)
        self.assertTrue('(IETF)' in q('#id_newstate option').text())
        self.assertTrue('(IRTF)' in q('#id_newstate option').text())

        person.role_set.filter(group=wg).delete()
        r = self.client.get(url)
        q = PyQuery(r.content)
        self.assertFalse('(IETF)' in q('#id_newstate option').text())
        self.assertTrue('(IRTF)' in q('#id_newstate option').text())

        person.role_set.all().delete()
        person.role_set.create(name_id='secr',group=Group.objects.get(acronym='secretariat'),email=person.email())
        r = self.client.get(url)
        q = PyQuery(r.content)
        self.assertTrue('(IETF)' in q('#id_newstate option').text())
        self.assertTrue('(IRTF)' in q('#id_newstate option').text())


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
        due = datetime.datetime.now() + datetime.timedelta(weeks=10)
        self.assertTrue(due - datetime.timedelta(days=1) <= reminder[0].due <= due + datetime.timedelta(days=1))
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
        due = datetime.datetime.now() + datetime.timedelta(weeks=10)
        self.assertTrue(due - datetime.timedelta(days=1) <= reminder[0].due <= due + datetime.timedelta(days=1))
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
        self.assertTrue(len(q('form .has-error')) > 0)

class ChangeReplacesTests(TestCase):
    def setUp(self):

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
            expires = datetime.datetime.now() - datetime.timedelta(days = 365 - settings.INTERNET_DRAFT_DAYS_TO_EXPIRE),
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
        RelatedDocument.objects.create(source=self.replacea, target=self.basea.docalias.first(),
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
        r = self.client.post(url, dict(replaces='%s,%s' % (self.basea.pk, self.baseb.pk)))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Document.objects.get(name='draft-test-base-a').get_state().slug,'repl')
        self.assertEqual(Document.objects.get(name='draft-test-base-b').get_state().slug,'repl')
        self.assertEqual(len(outbox), 1)
        self.assertTrue('basea_author@' in outbox[-1]['To'])
        self.assertTrue('baseb_author@' in outbox[-1]['To'])
        self.assertTrue('replaceboth_author@' in outbox[-1]['To'])

        # Post that undoes replaceboth
        empty_outbox()
        r = self.client.post(url, dict(replaces=""))
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
        r = self.client.post(url, dict(replaces=""))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Document.objects.get(name='draft-test-base-a').get_state().slug,'active')
        self.assertTrue('basea_author@' in outbox[-1]['To'])
        self.assertTrue('replacea_author@' in outbox[-1]['To'])


    def test_review_possibly_replaces(self):
        replaced = self.basea.docalias.first()
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
