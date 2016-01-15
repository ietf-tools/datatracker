# -*- coding: utf-8 -*-
import os
import shutil
import datetime
import StringIO
from pyquery import PyQuery

from django.core.urlresolvers import reverse as urlreverse
from django.conf import settings

import debug                            # pyflakes:ignore

from ietf.doc.models import ( Document, DocAlias, DocReminder, DocumentAuthor, DocEvent,
    ConsensusDocEvent, LastCallDocEvent, RelatedDocument, State, TelechatDocEvent, 
    WriteupDocEvent, BallotDocEvent, DocRelationshipName)
from ietf.doc.utils import get_tags_for_stream_id
from ietf.name.models import StreamName, IntendedStdLevelName, DocTagName
from ietf.group.models import Group
from ietf.person.models import Person, Email
from ietf.meeting.models import Meeting, MeetingTypeName
from ietf.iesg.models import TelechatDate
from ietf.utils.test_utils import login_testing_unauthorized, unicontent
from ietf.utils.test_data import make_test_data
from ietf.utils.mail import outbox, empty_outbox
from ietf.utils.test_utils import TestCase


class ChangeStateTests(TestCase):
    def test_change_state(self):
        draft = make_test_data()
        draft.set_state(State.objects.get(used=True, type="draft-iesg", slug="ad-eval"))

        url = urlreverse('doc_change_state', kwargs=dict(name=draft.name))
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
                                  substate="point",
                                  comment="Test comment"))
        self.assertEqual(r.status_code, 302)

        draft = Document.objects.get(name=draft.name)
        self.assertEqual(draft.get_state_slug("draft-iesg"), "review-e")
        self.assertTrue(not draft.tags.filter(slug="ad-f-up"))
        self.assertTrue(draft.tags.filter(slug="point"))
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
        draft = make_test_data()
        draft.set_state(State.objects.get(used=True, type="draft-iesg", slug="rfcqueue"))

        url = urlreverse('doc_change_state', kwargs=dict(name=draft.name))
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

        self.assertTrue("ID Tracker State Update Notice:" in outbox[-2]['Subject'])
        self.assertTrue("aread@" in outbox[-2]['To'])
        

    def test_change_iana_state(self):
        draft = make_test_data()

        first_state = State.objects.get(used=True, type="draft-iana-review", slug="need-rev")
        next_state = State.objects.get(used=True, type="draft-iana-review", slug="ok-noact")
        draft.set_state(first_state)

        url = urlreverse('doc_change_iana_state', kwargs=dict(name=draft.name, state_type="iana-review"))
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

    def test_request_last_call(self):
        draft = make_test_data()
        draft.set_state(State.objects.get(used=True, type="draft-iesg", slug="ad-eval"))

        self.client.login(username="secretary", password="secretary+password")
        url = urlreverse('doc_change_state', kwargs=dict(name=draft.name))

        empty_outbox()

        self.assertTrue(not draft.latest_event(type="changed_ballot_writeup_text"))
        r = self.client.post(url, dict(state=State.objects.get(used=True, type="draft-iesg", slug="lc-req").pk))
        self.assertTrue("Your request to issue" in unicontent(r))

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

        self.assertTrue("ID Tracker State Update" in outbox[0]['Subject'])
        self.assertTrue("aread@" in outbox[0]['To'])

        self.assertTrue("Last Call:" in outbox[1]['Subject'])
        self.assertTrue('iesg-secretary@' in outbox[1]['To'])
        self.assertTrue('aread@' in outbox[1]['Cc'])

        # comment
        self.assertTrue("Last call was requested" in draft.latest_event().desc)
        

class EditInfoTests(TestCase):
    def test_edit_info(self):
        draft = make_test_data()
        url = urlreverse('doc_edit_info', kwargs=dict(name=draft.name))
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
        draft = make_test_data()
        
        url = urlreverse('doc_edit_info', kwargs=dict(name=draft.name))
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
        ballot = draft.latest_event(BallotDocEvent, type="created_ballot")
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

    def test_start_iesg_process_on_draft(self):
        make_test_data()

        draft = Document.objects.create(
            name="draft-ietf-mars-test2",
            time=datetime.datetime.now(),
            type_id="draft",
            title="Testing adding a draft",
            stream=None,
            group=Group.objects.get(acronym="mars"),
            abstract="Test test test.",
            rev="01",
            pages=2,
            intended_std_level_id="ps",
            shepherd=None,
            ad=None,
            expires=datetime.datetime.now() + datetime.timedelta(days=settings.INTERNET_DRAFT_DAYS_TO_EXPIRE),
            )
        DocAlias.objects.create(
            document=draft,
            name=draft.name,
            )

        DocumentAuthor.objects.create(
            document=draft,
            author=Email.objects.get(address="aread@ietf.org"),
            order=1
            )
        
        url = urlreverse('doc_edit_info', kwargs=dict(name=draft.name))
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
        self.assertEqual(draft.docevent_set.count(), events_before + 3)
        events = list(draft.docevent_set.order_by('time', 'id'))
        self.assertEqual(events[-3].type, "started_iesg_process")
        self.assertEqual(len(outbox), mailbox_before+1)
        self.assertTrue('IESG processing' in outbox[-1]['Subject'])
        self.assertTrue('draft-ietf-mars-test2@' in outbox[-1]['To']) 

        # Redo, starting in publication requested to make sure WG state is also set
        draft.unset_state('draft-iesg')
        draft.set_state(State.objects.get(type='draft-stream-ietf',slug='writeupw'))
        draft.stream = StreamName.objects.get(slug='ietf')
        draft.save()
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
        draft = make_test_data()
        
        url = urlreverse('doc_edit_consensus', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "secretary", url)

        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        # post
        self.assertTrue(not draft.latest_event(ConsensusDocEvent, type="changed_consensus"))
        r = self.client.post(url, dict(consensus="Yes"))
        self.assertEqual(r.status_code, 302)

        self.assertEqual(draft.latest_event(ConsensusDocEvent, type="changed_consensus").consensus, True)

        # reset
        draft.intended_std_level_id = 'bcp'
        draft.save()
        r = self.client.post(url, dict(consensus="Unknown"))
        self.assertEqual(r.status_code, 403) # BCPs must have a consensus

        draft.intended_std_level_id = 'inf'
        draft.save()
        r = self.client.post(url, dict(consensus="Unknown"))
        self.assertEqual(r.status_code, 302)

        self.assertEqual(draft.latest_event(ConsensusDocEvent, type="changed_consensus").consensus, None)


class ResurrectTests(TestCase):
    def test_request_resurrect(self):
        draft = make_test_data()
        draft.set_state(State.objects.get(used=True, type="draft", slug="expired"))

        url = urlreverse('doc_request_resurrect', kwargs=dict(name=draft.name))
        
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
        draft = make_test_data()
        draft.set_state(State.objects.get(used=True, type="draft", slug="expired"))

        DocEvent.objects.create(doc=draft,
                             type="requested_resurrect",
                             by=Person.objects.get(name="Areað Irector"))

        url = urlreverse('doc_resurrect', kwargs=dict(name=draft.name))
        
        login_testing_unauthorized(self, "secretary", url)

        # normal get
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


class ExpireIDsTests(TestCase):
    def setUp(self):
        self.id_dir = os.path.abspath("tmp-id-dir")
        self.archive_dir = os.path.abspath("tmp-id-archive")
        if not os.path.exists(self.id_dir):
            os.mkdir(self.id_dir)
        if not os.path.exists(self.archive_dir):
            os.mkdir(self.archive_dir)
        os.mkdir(os.path.join(self.archive_dir, "unknown_ids"))
        os.mkdir(os.path.join(self.archive_dir, "deleted_tombstones"))
        os.mkdir(os.path.join(self.archive_dir, "expired_without_tombstone"))
        
        settings.INTERNET_DRAFT_PATH = self.id_dir
        settings.INTERNET_DRAFT_ARCHIVE_DIR = self.archive_dir

    def tearDown(self):
        shutil.rmtree(self.id_dir)
        shutil.rmtree(self.archive_dir)

    def write_draft_file(self, name, size):
        f = open(os.path.join(self.id_dir, name), 'w')
        f.write("a" * size)
        f.close()
        
    def test_in_draft_expire_freeze(self):
        from ietf.doc.expire import in_draft_expire_freeze

        Meeting.objects.create(number="123",
                               type=MeetingTypeName.objects.get(slug="ietf"),
                               date=datetime.date.today())
        second_cut_off = Meeting.get_second_cut_off()
        ietf_monday = Meeting.get_ietf_monday()

        self.assertTrue(not in_draft_expire_freeze(datetime.datetime.combine(second_cut_off - datetime.timedelta(days=7), datetime.time(0, 0, 0))))
        self.assertTrue(not in_draft_expire_freeze(datetime.datetime.combine(second_cut_off, datetime.time(0, 0, 0))))
        self.assertTrue(in_draft_expire_freeze(datetime.datetime.combine(second_cut_off + datetime.timedelta(days=7), datetime.time(0, 0, 0))))
        self.assertTrue(in_draft_expire_freeze(datetime.datetime.combine(ietf_monday - datetime.timedelta(days=1), datetime.time(0, 0, 0))))
        self.assertTrue(not in_draft_expire_freeze(datetime.datetime.combine(ietf_monday, datetime.time(0, 0, 0))))
        
    def test_warn_expirable_drafts(self):
        from ietf.doc.expire import get_soon_to_expire_drafts, send_expire_warning_for_draft

        draft = make_test_data()

        self.assertEqual(len(list(get_soon_to_expire_drafts(14))), 0)

        # hack into expirable state
        draft.unset_state("draft-iesg")
        draft.expires = datetime.datetime.now() + datetime.timedelta(days=10)
        draft.save()

        self.assertEqual(len(list(get_soon_to_expire_drafts(14))), 1)
        
        # test send warning
        mailbox_before = len(outbox)

        send_expire_warning_for_draft(draft)

        self.assertEqual(len(outbox), mailbox_before + 1)
        self.assertTrue('draft-ietf-mars-test@' in outbox[-1]['To']) # Gets the authors
        self.assertTrue('mars-chairs@ietf.org' in outbox[-1]['Cc'])
        self.assertTrue('aread@' in outbox[-1]['Cc'])
        
    def test_expire_drafts(self):
        from ietf.doc.expire import get_expired_drafts, send_expire_notice_for_draft, expire_draft

        draft = make_test_data()
        
        self.assertEqual(len(list(get_expired_drafts())), 0)
        
        # hack into expirable state
        draft.unset_state("draft-iesg")
        draft.expires = datetime.datetime.now()
        draft.save()

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

    def test_clean_up_draft_files(self):
        draft = make_test_data()
        
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
        draft.save()

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
        draft.save()

        e = DocEvent()
        e.doc = draft
        e.by = Person.objects.get(name="(System)")
        e.type = "expired_document"
        e.text = "Document has expired"
        e.time = draft.expires
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

        draft = make_test_data()
        draft.set_state(State.objects.get(used=True, type="draft-iesg", slug="lc"))

        secretary = Person.objects.get(name="Sec Retary")
        
        self.assertEqual(len(list(get_expired_last_calls())), 0)

        e = LastCallDocEvent()
        e.doc = draft
        e.by = secretary
        e.type = "sent_last_call"
        e.text = "Last call sent"
        e.expires = datetime.datetime.now() + datetime.timedelta(days=14)
        e.save()
        
        self.assertEqual(len(list(get_expired_last_calls())), 0)

        # test expired
        e = LastCallDocEvent()
        e.doc = draft
        e.by = secretary
        e.type = "sent_last_call"
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
    def test_doc_change_stream(self):
        url = urlreverse('doc_change_stream', kwargs=dict(name=self.docname))
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
        self.doc = Document.objects.get(name=self.docname)
        self.assertEqual(self.doc.stream_id,'ise')
        self.assertEqual(len(outbox), 1)
        self.assertTrue('Stream Change Notice' in outbox[0]['Subject'])
        self.assertTrue('rfc-ise@' in outbox[0]['To'])
        self.assertTrue('iesg@' in outbox[0]['To'])
        self.assertTrue('7gRMTjBM' in str(outbox[0]))
        self.assertTrue('7gRMTjBM' in self.doc.latest_event(DocEvent,type='added_comment').desc)

        # shift to an unknown stream (it must be possible to throw a document out of any stream)
        empty_outbox()
        r = self.client.post(url,dict(stream=""))
        self.assertEqual(r.status_code,302)
        self.doc = Document.objects.get(name=self.docname)
        self.assertEqual(self.doc.stream,None)
        self.assertTrue('rfc-ise@' in outbox[0]['To'])

    def test_doc_change_notify(self):
        url = urlreverse('doc_change_notify', kwargs=dict(name=self.docname))
        login_testing_unauthorized(self, "secretary", url)

        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form input[name=notify]')),1)

        # Provide a list
        r = self.client.post(url,dict(notify="TJ2APh2P@ietf.org",save_addresses="1"))
        self.assertEqual(r.status_code,302)
        self.doc = Document.objects.get(name=self.docname)
        self.assertEqual(self.doc.notify,'TJ2APh2P@ietf.org')
        
        # Ask the form to regenerate the list
        r = self.client.post(url,dict(regenerate_addresses="1"))
        self.assertEqual(r.status_code,200)
        self.doc = Document.objects.get(name=self.docname)
        # Regenerate does not save!
        self.assertEqual(self.doc.notify,'TJ2APh2P@ietf.org')
        q = PyQuery(r.content)
        self.assertEqual(None,q('form input[name=notify]')[0].value)

    def test_doc_change_intended_status(self):
        url = urlreverse('doc_change_intended_status', kwargs=dict(name=self.docname))
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
        self.doc = Document.objects.get(name=self.docname)
        self.assertEqual(self.doc.intended_std_level_id,'bcp')
        self.assertEqual(len(outbox),messages_before+1)
        self.assertTrue('Intended Status ' in outbox[-1]['Subject'])
        self.assertTrue('mars-chairs@' in outbox[-1]['To'])
        self.assertTrue('ZpyQFGmA' in str(outbox[-1]))

        self.assertTrue('ZpyQFGmA' in self.doc.latest_event(DocEvent,type='added_comment').desc)
       
    def test_doc_change_telechat_date(self):
        url = urlreverse('doc_change_telechat_date', kwargs=dict(name=self.docname))
        login_testing_unauthorized(self, "secretary", url)

        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('[type=submit]:contains("Save")')), 1)

        # set a date
        empty_outbox()
        self.assertFalse(self.doc.latest_event(TelechatDocEvent, "scheduled_for_telechat"))
        telechat_date = TelechatDate.objects.active().order_by('date')[0].date
        r = self.client.post(url,dict(telechat_date=telechat_date.isoformat()))
        self.assertEqual(r.status_code,302)
        self.doc = Document.objects.get(name=self.docname)
        self.assertEqual(self.doc.latest_event(TelechatDocEvent, "scheduled_for_telechat").telechat_date,telechat_date)
        self.assertEqual(len(outbox), 1)
        self.assertTrue('Telechat update notice' in outbox[0]['Subject'])
        self.assertTrue('iesg@' in outbox[0]['To'])
        self.assertTrue('iesg-secretary@' in outbox[0]['To'])

        # Take the doc back off any telechat
        r = self.client.post(url,dict(telechat_date=""))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.doc.latest_event(TelechatDocEvent, "scheduled_for_telechat").telechat_date,None)
        
    def test_doc_change_iesg_note(self):
        url = urlreverse('doc_change_iesg_note', kwargs=dict(name=self.docname))
        login_testing_unauthorized(self, "secretary", url)

        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('[type=submit]:contains("Save")')),1)

        # post
        r = self.client.post(url,dict(note='ZpyQFGmA\r\nZpyQFGmA'))
        self.assertEqual(r.status_code,302)
        self.doc = Document.objects.get(name=self.docname)
        self.assertEqual(self.doc.note,'ZpyQFGmA\nZpyQFGmA')
        self.assertTrue('ZpyQFGmA' in self.doc.latest_event(DocEvent,type='added_comment').desc)

    def test_doc_change_ad(self):
        url = urlreverse('doc_change_ad', kwargs=dict(name=self.docname))
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
        self.doc = Document.objects.get(name=self.docname)
        self.assertEqual(self.doc.ad,ad2)
        self.assertTrue(self.doc.latest_event(DocEvent,type="added_comment").desc.startswith('Shepherding AD changed'))

    def test_doc_change_shepherd(self):
        self.doc.shepherd = None
        self.doc.save()

        url = urlreverse('doc_edit_shepherd',kwargs=dict(name=self.docname))
        
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
        self.doc = Document.objects.get(name=self.docname)
        self.assertEqual(self.doc.shepherd, plain_email)
        comment_events = self.doc.docevent_set.filter(time=self.doc.time,type="added_comment")
        comments = '::'.join([x.desc for x in comment_events])
        self.assertTrue('Document shepherd changed to Plain Man' in comments)
        self.assertTrue('Notification list changed' in comments)

        # save the form without changing the email (nothing should be saved)
        r = self.client.post(url, dict(shepherd=plain_email.pk))
        self.assertEqual(r.status_code, 302)
        self.doc = Document.objects.get(name=self.docname)
        self.assertEqual(set(comment_events), set(self.doc.docevent_set.filter(time=self.doc.time,type="added_comment")))
        r = self.client.get(url)
        self.assertTrue(any(['no changes have been made' in m.message for m in r.context['messages']]))

        # Remove the shepherd
        r = self.client.post(url, dict(shepherd=''))
        self.assertEqual(r.status_code, 302)
        self.doc = Document.objects.get(name=self.docname)
        self.assertTrue(any(['Document shepherd changed to (None)' in x.desc for x in self.doc.docevent_set.filter(time=self.doc.time,type='added_comment')]))
        
        # test buggy change
        ad = Person.objects.get(name='Areað Irector')
        two_answers = "%s,%s" % (plain_email, ad.email_set.all()[0])
        r = self.client.post(url, dict(shepherd=two_answers))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form .has-error')) > 0)

    def test_doc_change_shepherd_email(self):
        self.doc.shepherd = None
        self.doc.save()

        url = urlreverse('doc_change_shepherd_email',kwargs=dict(name=self.docname))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)

        self.doc.shepherd = Email.objects.get(person__user__username="ad1")
        self.doc.save()

        login_testing_unauthorized(self, "plain", url)

        self.doc.shepherd = Email.objects.get(person__user__username="plain")
        self.doc.save()

        new_email = Email.objects.create(address="anotheremail@example.com", person=self.doc.shepherd.person)

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        # change the shepherd email
        r = self.client.post(url, dict(shepherd=new_email))
        self.assertEqual(r.status_code, 302)
        self.doc = Document.objects.get(name=self.docname)
        self.assertEqual(self.doc.shepherd, new_email)
        comment_event = self.doc.latest_event(DocEvent, type="added_comment")
        self.assertTrue(comment_event.desc.startswith('Document shepherd email changed'))

        # save the form without changing the email (nothing should be saved)
        r = self.client.post(url, dict(shepherd=new_email))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(comment_event, self.doc.latest_event(DocEvent, type="added_comment"))
       

    def test_doc_view_shepherd_writeup(self):
        url = urlreverse('doc_shepherd_writeup',kwargs=dict(name=self.docname))
  
        # get as a shepherd
        self.client.login(username="plain", password="plain+password")

        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('#content a:contains("Edit")')), 1)

        # Try again when no longer a shepherd.

        self.doc.shepherd = None
        self.doc.save()
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('#content a:contains("Edit")')), 0)

    def test_doc_change_shepherd_writeup(self):
        url = urlreverse('doc_edit_shepherd_writeup',kwargs=dict(name=self.docname))
  
        # get
        login_testing_unauthorized(self, "secretary", url)

        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form textarea[id=id_content]')),1)

        # direct edit
        r = self.client.post(url,dict(content='here is a new writeup',submit_response="1"))
        self.assertEqual(r.status_code,302)
        self.doc = Document.objects.get(name=self.docname)
        self.assertTrue(self.doc.latest_event(WriteupDocEvent,type="changed_protocol_writeup").text.startswith('here is a new writeup'))

        # file upload
        test_file = StringIO.StringIO("This is a different writeup.")
        test_file.name = "unnamed"
        r = self.client.post(url,dict(txt=test_file,submit_response="1"))
        self.assertEqual(r.status_code, 302)
        self.assertTrue(self.doc.latest_event(WriteupDocEvent,type="changed_protocol_writeup").text.startswith('This is a different writeup.'))

        # template reset
        r = self.client.post(url,dict(txt=test_file,reset_text="1"))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(q('textarea')[0].text.strip().startswith("As required by RFC 4858"))

    def setUp(self):
        make_test_data()
        self.docname='draft-ietf-mars-test'
        self.doc = Document.objects.get(name=self.docname)
        

class SubmitToIesgTests(TestCase):
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

        url = urlreverse('doc_to_iesg', kwargs=dict(name=self.docname))

        for username in [None,'plain','iana','iab chair']:
            verify_fail(username)

        for username in ['marschairman','secretary','ad']:
            verify_can_see(username)
        
    def test_cancel_submission(self):
        url = urlreverse('doc_to_iesg', kwargs=dict(name=self.docname))
        self.client.login(username="marschairman", password="marschairman+password")

	r = self.client.post(url, dict(cancel="1"))
        self.assertEqual(r.status_code, 302)

        doc = Document.objects.get(pk=self.doc.pk)
        self.assertTrue(doc.get_state('draft-iesg')==None)

    def test_confirm_submission(self):
        url = urlreverse('doc_to_iesg', kwargs=dict(name=self.docname))
        self.client.login(username="marschairman", password="marschairman+password")

        docevent_count_pre = self.doc.docevent_set.count()
        mailbox_before = len(outbox)

	r = self.client.post(url, dict(confirm="1"))
        self.assertEqual(r.status_code, 302)

        doc = Document.objects.get(pk=self.doc.pk)
        self.assertTrue(doc.get_state('draft-iesg').slug=='pub-req')
        self.assertTrue(doc.get_state('draft-stream-ietf').slug=='sub-pub')
        self.assertTrue(doc.ad!=None)
        self.assertTrue(doc.docevent_set.count() != docevent_count_pre)
        self.assertEqual(len(outbox), mailbox_before + 1)
        self.assertTrue("Publication has been requested" in outbox[-1]['Subject'])
        self.assertTrue("aread@" in outbox[-1]['To'])
        self.assertTrue("iesg-secretary@" in outbox[-1]['Cc'])

    def setUp(self):
        make_test_data()
        self.docname='draft-ietf-mars-test'
        self.doc = Document.objects.get(name=self.docname)
        self.doc.unset_state('draft-iesg') 


class RequestPublicationTests(TestCase):
    def test_request_publication(self):
        draft = make_test_data()
        draft.stream = StreamName.objects.get(slug="iab")
        draft.group = Group.objects.get(acronym="iab")
        draft.intended_std_level = IntendedStdLevelName.objects.get(slug="inf")
        draft.save()
        draft.set_state(State.objects.get(used=True, type="draft-stream-iab", slug="approved"))

        url = urlreverse('doc_request_publication', kwargs=dict(name=draft.name))
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

        r = self.client.post(url, dict(subject=subject, body=body, skiprfceditorpost="1"))
        self.assertEqual(r.status_code, 302)

        draft = Document.objects.get(name=draft.name)
        self.assertEqual(draft.get_state_slug("draft-stream-iab"), "rfc-edit")

        self.assertEqual(len(outbox), mailbox_before + 2)

        self.assertTrue("Document Action" in outbox[-2]['Subject'])
        self.assertTrue("rfc-editor@" in outbox[-2]['To'])

        self.assertTrue("Document Action" in outbox[-1]['Subject'])
        self.assertTrue("drafts-approval@icann.org" in outbox[-1]['To'])

        self.assertTrue("Document Action" in draft.message_set.order_by("-time")[0].subject)

class AdoptDraftTests(TestCase):
    def test_adopt_document(self):
        draft = make_test_data()
        draft.stream = None
        draft.group = Group.objects.get(type="individ")
        draft.save()
        draft.unset_state("draft-stream-ietf")

        url = urlreverse('doc_adopt_draft', kwargs=dict(name=draft.name))
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

class ChangeStreamStateTests(TestCase):
    def test_set_tags(self):
        draft = make_test_data()
        draft.tags = DocTagName.objects.filter(slug="w-expert")
        draft.group.unused_tags.add("w-refdoc")

        url = urlreverse('doc_change_stream_state', kwargs=dict(name=draft.name, state_type="draft-stream-ietf"))
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
        self.assertTrue("mars-chairs@ietf.org" in unicode(outbox[-1]))
        self.assertTrue("marsdelegate@ietf.org" in unicode(outbox[-1]))
        self.assertTrue("plain@example.com" in unicode(outbox[-1]))

    def test_set_initial_state(self):
        draft = make_test_data()
        draft.unset_state("draft-stream-%s"%draft.stream_id)

        url = urlreverse('doc_change_stream_state', kwargs=dict(name=draft.name, state_type="draft-stream-ietf"))
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
        self.assertTrue("mars-chairs@ietf.org" in unicode(outbox[0]))
        self.assertTrue("marsdelegate@ietf.org" in unicode(outbox[0]))

    def test_set_state(self):
        draft = make_test_data()

        url = urlreverse('doc_change_stream_state', kwargs=dict(name=draft.name, state_type="draft-stream-ietf"))
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
        self.assertTrue("mars-chairs@ietf.org" in unicode(outbox[0]))
        self.assertTrue("marsdelegate@ietf.org" in unicode(outbox[0]))

    def test_pubreq_validation(self):
        draft = make_test_data()

        url = urlreverse('doc_change_stream_state', kwargs=dict(name=draft.name, state_type="draft-stream-ietf"))
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

        make_test_data()

        mars_wg = Group.objects.get(acronym='mars')

        self.basea = Document.objects.create(
            name="draft-test-base-a",
            time=datetime.datetime.now(),
            type_id="draft",
            title="Base A",
            stream_id="ietf",
            expires=datetime.datetime.now() + datetime.timedelta(days=settings.INTERNET_DRAFT_DAYS_TO_EXPIRE),
            group=mars_wg,
        )
        self.basea.documentauthor_set.create(author=Email.objects.create(address="basea_author@example.com"),order=1)

        self.baseb = Document.objects.create(
            name="draft-test-base-b",
            time=datetime.datetime.now()-datetime.timedelta(days=365),
            type_id="draft",
            title="Base B",
            stream_id="ietf",
            expires=datetime.datetime.now() - datetime.timedelta(days = 365 - settings.INTERNET_DRAFT_DAYS_TO_EXPIRE),
            group=mars_wg,
        )
        self.baseb.documentauthor_set.create(author=Email.objects.create(address="baseb_author@example.com"),order=1)

        self.replacea = Document.objects.create(
            name="draft-test-replace-a",
            time=datetime.datetime.now(),
            type_id="draft",
            title="Replace Base A",
            stream_id="ietf",
            expires=datetime.datetime.now() + datetime.timedelta(days = settings.INTERNET_DRAFT_DAYS_TO_EXPIRE),
            group=mars_wg,
        )
        self.replacea.documentauthor_set.create(author=Email.objects.create(address="replacea_author@example.com"),order=1)
 
        self.replaceboth = Document.objects.create(
            name="draft-test-replace-both",
            time=datetime.datetime.now(),
            type_id="draft",
            title="Replace Base A and Base B",
            stream_id="ietf",
            expires=datetime.datetime.now() + datetime.timedelta(days = settings.INTERNET_DRAFT_DAYS_TO_EXPIRE),
            group=mars_wg,
        )
        self.replaceboth.documentauthor_set.create(author=Email.objects.create(address="replaceboth_author@example.com"),order=1)
 
        self.basea.set_state(State.objects.get(used=True, type="draft", slug="active"))
        self.baseb.set_state(State.objects.get(used=True, type="draft", slug="expired"))
        self.replacea.set_state(State.objects.get(used=True, type="draft", slug="active"))
        self.replaceboth.set_state(State.objects.get(used=True, type="draft", slug="active"))

        DocAlias.objects.create(document=self.basea,name=self.basea.name)
        DocAlias.objects.create(document=self.baseb,name=self.baseb.name)
        DocAlias.objects.create(document=self.replacea,name=self.replacea.name)
        DocAlias.objects.create(document=self.replaceboth,name=self.replaceboth.name)

    def test_change_replaces(self):

        url = urlreverse('doc_change_replaces', kwargs=dict(name=self.replacea.name))
        login_testing_unauthorized(self, "secretary", url)

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('[type=submit]:contains("Save")')), 1)
        
        # Post that says replacea replaces base a
        empty_outbox()
        RelatedDocument.objects.create(source=self.replacea, target=self.basea.docalias_set.first(),
                                       relationship=DocRelationshipName.objects.get(slug="possibly-replaces"))
        self.assertEqual(self.basea.get_state().slug,'active')
        r = self.client.post(url, dict(replaces=self.basea.name))
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
        url = urlreverse('doc_change_replaces', kwargs=dict(name=self.replaceboth.name))
        self.assertEqual(self.baseb.get_state().slug,'expired')
        r = self.client.post(url, dict(replaces=self.basea.name + "," + self.baseb.name))
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
        url = urlreverse('doc_change_replaces', kwargs=dict(name=self.replacea.name))
        r = self.client.post(url, dict(replaces=""))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Document.objects.get(name='draft-test-base-a').get_state().slug,'active')
        self.assertTrue('basea_author@' in outbox[-1]['To'])
        self.assertTrue('replacea_author@' in outbox[-1]['To'])


    def test_review_possibly_replaces(self):
        replaced = self.basea.docalias_set.first()
        RelatedDocument.objects.create(source=self.replacea, target=replaced,
                                       relationship=DocRelationshipName.objects.get(slug="possibly-replaces"))

        url = urlreverse('doc_review_possibly_replaces', kwargs=dict(name=self.replacea.name))
        login_testing_unauthorized(self, "secretary", url)

        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form[name=review-suggested-replaces]')), 1)

        r = self.client.post(url, dict(replaces=[replaced.pk]))
        self.assertEquals(r.status_code, 302)
        self.assertTrue(not self.replacea.related_that_doc("possibly-replaces"))
        self.assertEqual(len(self.replacea.related_that_doc("replaces")), 1)
        self.assertEquals(Document.objects.get(pk=self.basea.pk).get_state().slug, 'repl')
