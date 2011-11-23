# Copyright (C) 2009 Nokia Corporation and/or its subsidiary(-ies).
# All rights reserved. Contact: Pasi Eronen <pasi.eronen@nokia.com>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#
#  * Redistributions in binary form must reproduce the above
#    copyright notice, this list of conditions and the following
#    disclaimer in the documentation and/or other materials provided
#    with the distribution.
#
#  * Neither the name of the Nokia Corporation and/or its
#    subsidiary(-ies) nor the names of its contributors may be used
#    to endorse or promote products derived from this software
#    without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import unittest
import StringIO
import os, shutil
from datetime import date, timedelta

import django.test
from django.core.urlresolvers import reverse as urlreverse
from django.conf import settings

from pyquery import PyQuery

from ietf.idtracker.models import IDDates
from redesign.doc.models import *
from redesign.name.models import *
from redesign.group.models import *
from redesign.person.models import *
from ietf.iesg.models import TelechatDates
from ietf.utils.test_utils import SimpleUrlTestCase, RealDatabaseTest, login_testing_unauthorized
from ietf.utils.test_data import make_test_data
from ietf.utils.mail import outbox

class IdRfcUrlTestCase(SimpleUrlTestCase):
    def testUrls(self):
        #self.doTestUrls(__file__)
        self.doTestUrls(os.path.join(os.path.dirname(os.path.abspath(__file__)), "testurlREDESIGN.list"))


class ChangeStateTestCase(django.test.TestCase):
    fixtures = ['names']

    def test_change_state(self):
        draft = make_test_data()
        draft.set_state(State.objects.get(type="draft-iesg", slug="ad-eval"))

        url = urlreverse('doc_change_state', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "secretary", url)

        first_state = draft.get_state("draft-iesg")
        next_states = first_state.next_states

        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form select[name=state]')), 1)
        
        if next_states:
            self.assertTrue(len(q('.next-states form input[type=hidden]')) > 0)

            
        # faulty post
        r = self.client.post(url, dict(state=State.objects.get(type="draft", slug="active").pk))
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form ul.errorlist')) > 0)
        draft = Document.objects.get(name=draft.name)
        self.assertEquals(draft.get_state("draft-iesg"), first_state)

        
        # change state
        events_before = draft.docevent_set.count()
        mailbox_before = len(outbox)
        
        r = self.client.post(url, dict(state=State.objects.get(type="draft-iesg", slug="review-e").pk))
        self.assertEquals(r.status_code, 302)

        draft = Document.objects.get(name=draft.name)
        self.assertEquals(draft.get_state_slug("draft-iesg"), "review-e")
        self.assertEquals(draft.docevent_set.count(), events_before + 1)
        self.assertTrue("State changed" in draft.docevent_set.all()[0].desc)
        self.assertEquals(len(outbox), mailbox_before + 2)
        self.assertTrue("State Update Notice" in outbox[-2]['Subject'])
        self.assertTrue(draft.name in outbox[-1]['Subject'])

        
        # check that we got a previous state now
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('.prev-state form input[name="state"]')), 1)

        
    def test_request_last_call(self):
        draft = make_test_data()
        draft.set_state(State.objects.get(type="draft-iesg", slug="ad-eval"))

        self.client.login(remote_user="secretary")
        url = urlreverse('doc_change_state', kwargs=dict(name=draft.name))

        mailbox_before = len(outbox)
        
        self.assertTrue(not draft.latest_event(type="changed_ballot_writeup_text"))
        r = self.client.post(url, dict(state=State.objects.get(type="draft-iesg", slug="lc-req").pk))
        self.assertContains(r, "Your request to issue the Last Call")

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
        self.assertTrue(len(outbox) > mailbox_before)
        self.assertTrue("Last Call:" in outbox[-1]['Subject'])

        # comment
        self.assertTrue("Last call was requested" in draft.latest_event().desc)
        

class EditInfoTestCase(django.test.TestCase):
    fixtures = ['names']

    def test_edit_info(self):
        draft = make_test_data()
        url = urlreverse('doc_edit_info', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "secretary", url)

        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form select[name=intended_std_level]')), 1)
        self.assertEquals(len(q('form input[name=via_rfc_editor]')), 1)

        prev_ad = draft.ad
        # faulty post
        r = self.client.post(url, dict(ad="123456789"))
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form ul.errorlist')) > 0)
        draft = Document.objects.get(name=draft.name)
        self.assertEquals(draft.ad, prev_ad)

        # edit info
        events_before = draft.docevent_set.count()
        mailbox_before = len(outbox)

        new_ad = Person.objects.get(name="Ad No1")

        r = self.client.post(url,
                             dict(intended_std_level=str(draft.intended_std_level.pk),
                                  stream=draft.stream_id,
                                  via_rfc_editor="1",
                                  ad=str(new_ad.pk),
                                  notify="test@example.com",
                                  note="New note",
                                  telechat_date="",
                                  ))
        self.assertEquals(r.status_code, 302)

        draft = Document.objects.get(name=draft.name)
        self.assertTrue(draft.tags.filter(slug="via-rfc"))
        self.assertEquals(draft.ad, new_ad)
        self.assertEquals(draft.note, "New note")
        self.assertTrue(not draft.latest_event(TelechatDocEvent, type="telechat_date"))
        self.assertEquals(draft.docevent_set.count(), events_before + 3)
        self.assertEquals(len(outbox), mailbox_before + 1)
        self.assertTrue(draft.name in outbox[-1]['Subject'])

    def test_edit_telechat_date(self):
        draft = make_test_data()
        
        url = urlreverse('doc_edit_info', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "secretary", url)

        data = dict(intended_std_level=str(draft.intended_std_level_id),
                    stream=draft.stream_id,
                    via_rfc_editor="1",
                    ad=str(draft.ad_id),
                    notify="test@example.com",
                    note="",
                    )

        # add to telechat
        self.assertTrue(not draft.latest_event(TelechatDocEvent, "scheduled_for_telechat"))
        data["telechat_date"] = TelechatDates.objects.all()[0].date1.isoformat()
        r = self.client.post(url, data)
        self.assertEquals(r.status_code, 302)

        draft = Document.objects.get(name=draft.name)
        self.assertTrue(draft.latest_event(TelechatDocEvent, "scheduled_for_telechat"))
        self.assertEquals(draft.latest_event(TelechatDocEvent, "scheduled_for_telechat").telechat_date, TelechatDates.objects.all()[0].date1)

        # change telechat
        data["telechat_date"] = TelechatDates.objects.all()[0].date2.isoformat()
        r = self.client.post(url, data)
        self.assertEquals(r.status_code, 302)

        draft = Document.objects.get(name=draft.name)
        self.assertEquals(draft.latest_event(TelechatDocEvent, "scheduled_for_telechat").telechat_date, TelechatDates.objects.all()[0].date2)

        # remove from agenda
        data["telechat_date"] = ""
        r = self.client.post(url, data)
        self.assertEquals(r.status_code, 302)

        draft = Document.objects.get(name=draft.name)
        self.assertTrue(not draft.latest_event(TelechatDocEvent, "scheduled_for_telechat").telechat_date)

    def test_start_iesg_process_on_draft(self):
        draft = make_test_data()
        draft.ad = None
        draft.save()
        draft.unset_state("draft-iesg")
        draft.docevent_set.all().delete()
        
        url = urlreverse('doc_edit_info', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "secretary", url)

        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form select[name=intended_std_level]')), 1)
        self.assertEquals(len(q('form input[name=via_rfc_editor]')), 1)
        self.assertTrue('@' in q('form input[name=notify]')[0].get('value'))

        # add
        events_before = draft.docevent_set.count()
        mailbox_before = len(outbox)

        ad = Person.objects.get(name="Aread Irector")

        r = self.client.post(url,
                             dict(intended_std_level=str(draft.intended_std_level_id),
                                  stream=draft.stream_id,
                                  via_rfc_editor="1",
                                  ad=ad.pk,
                                  create_in_state=State.objects.get(type="draft-iesg", slug="watching").pk,
                                  notify="test@example.com",
                                  note="This is a note",
                                  telechat_date="",
                                  ))
        self.assertEquals(r.status_code, 302)

        draft = Document.objects.get(name=draft.name)
        self.assertTrue(draft.tags.filter(slug="via-rfc"))
        self.assertEquals(draft.get_state_slug("draft-iesg"), "watching")
        self.assertEquals(draft.ad, ad)
        self.assertEquals(draft.note, "This is a note")
        self.assertTrue(not draft.latest_event(TelechatDocEvent, type="scheduled_for_telechat"))
        self.assertEquals(draft.docevent_set.count(), events_before + 3)
        events = list(draft.docevent_set.order_by('time', 'id'))
        self.assertEquals(events[-3].type, "started_iesg_process")
        self.assertEquals(len(outbox), mailbox_before)


class ResurrectTestCase(django.test.TestCase):
    fixtures = ['names']

    def test_request_resurrect(self):
        draft = make_test_data()
        draft.set_state(State.objects.get(type="draft", slug="expired"))

        url = urlreverse('doc_request_resurrect', kwargs=dict(name=draft.name))
        
        login_testing_unauthorized(self, "ad", url)

        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form input[type=submit]')), 1)


        # request resurrect
        events_before = draft.docevent_set.count()
        mailbox_before = len(outbox)
        
        r = self.client.post(url, dict())
        self.assertEquals(r.status_code, 302)

        draft = Document.objects.get(name=draft.name)
        self.assertEquals(draft.docevent_set.count(), events_before + 1)
        e = draft.latest_event(type="requested_resurrect")
        self.assertTrue(e)
        self.assertEquals(e.by, Person.objects.get(name="Aread Irector"))
        self.assertTrue("Resurrection" in e.desc)
        self.assertEquals(len(outbox), mailbox_before + 1)
        self.assertTrue("Resurrection" in outbox[-1]['Subject'])

    def test_resurrect(self):
        draft = make_test_data()
        draft.set_state(State.objects.get(type="draft", slug="expired"))

        DocEvent.objects.create(doc=draft,
                             type="requested_resurrect",
                             by=Person.objects.get(name="Aread Irector"))

        url = urlreverse('doc_resurrect', kwargs=dict(name=draft.name))
        
        login_testing_unauthorized(self, "secretary", url)

        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form input[type=submit]')), 1)

        # request resurrect
        events_before = draft.docevent_set.count()
        mailbox_before = len(outbox)
        
        r = self.client.post(url, dict())
        self.assertEquals(r.status_code, 302)

        draft = Document.objects.get(name=draft.name)
        self.assertEquals(draft.docevent_set.count(), events_before + 1)
        self.assertEquals(draft.latest_event().type, "completed_resurrect")
        self.assertEquals(draft.get_state_slug(), "active")
        self.assertEquals(len(outbox), mailbox_before + 1)
        
class AddCommentTestCase(django.test.TestCase):
    fixtures = ['names']

    def test_add_comment(self):
        draft = make_test_data()
        url = urlreverse('doc_add_comment', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "secretary", url)

        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form textarea[name=comment]')), 1)

        # request resurrect
        events_before = draft.docevent_set.count()
        mailbox_before = len(outbox)
        
        r = self.client.post(url, dict(comment="This is a test."))
        self.assertEquals(r.status_code, 302)

        self.assertEquals(draft.docevent_set.count(), events_before + 1)
        self.assertEquals("This is a test.", draft.latest_event().desc)
        self.assertEquals("added_comment", draft.latest_event().type)
        self.assertEquals(len(outbox), mailbox_before + 1)
        self.assertTrue("updated" in outbox[-1]['Subject'])
        self.assertTrue(draft.name in outbox[-1]['Subject'])

class EditPositionTestCase(django.test.TestCase):
    fixtures = ['names']

    def test_edit_position(self):
        draft = make_test_data()
        url = urlreverse('doc_edit_position', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "ad", url)

        ad = Person.objects.get(name="Aread Irector")
        
        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form input[name=position]')) > 0)
        self.assertEquals(len(q('form textarea[name=comment]')), 1)

        # vote
        events_before = draft.docevent_set.count()
        
        r = self.client.post(url, dict(position="discuss",
                                       discuss="This is a discussion test.",
                                       comment="This is a test."))
        self.assertEquals(r.status_code, 302)

        pos = draft.latest_event(BallotPositionDocEvent, ad=ad)
        self.assertEquals(pos.pos.slug, "discuss")
        self.assertTrue("This is a discussion test." in pos.discuss)
        self.assertTrue(pos.discuss_time != None)
        self.assertTrue("This is a test." in pos.comment)
        self.assertTrue(pos.comment_time != None)
        self.assertTrue("New position" in pos.desc)
        self.assertEquals(draft.docevent_set.count(), events_before + 3)

        # recast vote
        events_before = draft.docevent_set.count()
        r = self.client.post(url, dict(position="noobj"))
        self.assertEquals(r.status_code, 302)

        pos = draft.latest_event(BallotPositionDocEvent, ad=ad)
        self.assertEquals(pos.pos.slug, "noobj")
        self.assertEquals(draft.docevent_set.count(), events_before + 1)
        self.assertTrue("Position for" in pos.desc)
        
        # clear vote
        events_before = draft.docevent_set.count()
        r = self.client.post(url, dict(position="norecord"))
        self.assertEquals(r.status_code, 302)

        pos = draft.latest_event(BallotPositionDocEvent, ad=ad)
        self.assertEquals(pos.pos.slug, "norecord")
        self.assertEquals(draft.docevent_set.count(), events_before + 1)
        self.assertTrue("Position for" in pos.desc)

        # change comment
        events_before = draft.docevent_set.count()
        r = self.client.post(url, dict(position="norecord", comment="New comment."))
        self.assertEquals(r.status_code, 302)

        pos = draft.latest_event(BallotPositionDocEvent, ad=ad)
        self.assertEquals(pos.pos.slug, "norecord")
        self.assertEquals(draft.docevent_set.count(), events_before + 2)
        self.assertTrue("Ballot comment text updated" in pos.desc)
        
    def test_edit_position_as_secretary(self):
        draft = make_test_data()
        url = urlreverse('doc_edit_position', kwargs=dict(name=draft.name))
        ad = Person.objects.get(name="Aread Irector")
        url += "?ad=%s" % ad.pk
        login_testing_unauthorized(self, "secretary", url)

        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form input[name=position]')) > 0)

        # vote on behalf of AD
        events_before = draft.docevent_set.count()
        r = self.client.post(url, dict(position="discuss", discuss="Test discuss text"))
        self.assertEquals(r.status_code, 302)

        pos = draft.latest_event(BallotPositionDocEvent, ad=ad)
        self.assertEquals(pos.pos.slug, "discuss")
        self.assertEquals(pos.discuss, "Test discuss text")
        self.assertTrue("New position" in pos.desc)
        self.assertTrue("by Sec" in pos.desc)
        
    def test_send_ballot_comment(self):
        draft = make_test_data()
        draft.notify = "somebody@example.com"
        draft.save()

        ad = Person.objects.get(name="Aread Irector")
        
        BallotPositionDocEvent.objects.create(doc=draft, type="changed_ballot_position",
                                      by=ad, ad=ad, pos=BallotPositionName.objects.get(slug="yes"),
                                      comment="Test!",
                                      comment_time=datetime.datetime.now())
        
        url = urlreverse('doc_send_ballot_comment', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "ad", url)

        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form input[name="cc"]')) > 0)

        # send
        mailbox_before = len(outbox)

        r = self.client.post(url, dict(cc="test@example.com", cc_state_change="1"))
        self.assertEquals(r.status_code, 302)

        self.assertEquals(len(outbox), mailbox_before + 1)
        m = outbox[-1]
        self.assertTrue("COMMENT" in m['Subject'])
        self.assertTrue(draft.name in m['Subject'])
        self.assertTrue("Test!" in str(m))
        
        
class DeferBallotTestCase(django.test.TestCase):
    fixtures = ['names']

    def test_defer_ballot(self):
        draft = make_test_data()
        draft.set_state(State.objects.get(type="draft-iesg", slug="iesg-eva"))

        url = urlreverse('doc_defer_ballot', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "ad", url)

        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)

        # defer
        mailbox_before = len(outbox)
        
        r = self.client.post(url, dict())
        self.assertEquals(r.status_code, 302)

        draft = Document.objects.get(name=draft.name)
        self.assertEquals(draft.get_state_slug("draft-iesg"), "defer")
        
        self.assertEquals(len(outbox), mailbox_before + 2)
        self.assertTrue("State Update" in outbox[-2]['Subject'])
        self.assertTrue("Deferred" in outbox[-1]['Subject'])
        self.assertTrue(draft.file_tag() in outbox[-1]['Subject'])

    def test_undefer_ballot(self):
        draft = make_test_data()
        draft.set_state(State.objects.get(type="draft-iesg", slug="defer"))

        url = urlreverse('doc_undefer_ballot', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "ad", url)

        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)

        # undefer
        r = self.client.post(url, dict())
        self.assertEquals(r.status_code, 302)

        draft = Document.objects.get(name=draft.name)
        self.assertEquals(draft.get_state_slug("draft-iesg"), "iesg-eva")

class BallotWriteupsTestCase(django.test.TestCase):
    fixtures = ['names']

    def test_edit_last_call_text(self):
        draft = make_test_data()
        url = urlreverse('doc_ballot_lastcall', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "secretary", url)

        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('textarea[name=last_call_text]')), 1)
        self.assertEquals(len(q('input[type=submit][value*="Save Last Call"]')), 1)
        # we're secretariat, so we got The Link 
        self.assertEquals(len(q('a:contains("Make Last Call")')), 1)
        
        # subject error
        r = self.client.post(url, dict(
                last_call_text="Subject: test\r\nhello\r\n\r\n",
                save_last_call_text="1"))
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('ul.errorlist')) > 0)

        # save
        r = self.client.post(url, dict(
                last_call_text="This is a simple test.",
                save_last_call_text="1"))
        self.assertEquals(r.status_code, 200)
        draft = Document.objects.get(name=draft.name)
        self.assertTrue("This is a simple test" in draft.latest_event(WriteupDocEvent, type="changed_last_call_text").text)

        # test regenerate
        r = self.client.post(url, dict(
                last_call_text="This is a simple test.",
                regenerate_last_call_text="1"))
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        draft = Document.objects.get(name=draft.name)
        self.assertTrue("Subject: Last Call" in draft.latest_event(WriteupDocEvent, type="changed_last_call_text").text)


    def test_request_last_call(self):
        draft = make_test_data()
        url = urlreverse('doc_ballot_lastcall', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "secretary", url)

        # give us an announcement to send
        r = self.client.post(url, dict(regenerate_last_call_text="1"))
        self.assertEquals(r.status_code, 200)
        
        mailbox_before = len(outbox)

        # send
        r = self.client.post(url, dict(
                last_call_text=draft.latest_event(WriteupDocEvent, type="changed_last_call_text").text,
                send_last_call_request="1"))
        draft = Document.objects.get(name=draft.name)
        self.assertEquals(draft.get_state_slug("draft-iesg"), "lc-req")
        self.assertEquals(len(outbox), mailbox_before + 3)
        self.assertTrue("Last Call" in outbox[-1]['Subject'])
        self.assertTrue(draft.name in outbox[-1]['Subject'])

    def test_edit_ballot_writeup(self):
        draft = make_test_data()
        url = urlreverse('doc_ballot_writeupnotes', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "secretary", url)

        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('textarea[name=ballot_writeup]')), 1)
        self.assertEquals(len(q('input[type=submit][value*="Save Ballot Writeup"]')), 1)

        # save
        r = self.client.post(url, dict(
                ballot_writeup="This is a simple test.",
                save_ballot_writeup="1"))
        self.assertEquals(r.status_code, 200)
        draft = Document.objects.get(name=draft.name)
        self.assertTrue("This is a simple test" in draft.latest_event(WriteupDocEvent, type="changed_ballot_writeup_text").text)

    def test_issue_ballot(self):
        draft = make_test_data()
        url = urlreverse('doc_ballot_writeupnotes', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "ad", url)

        def create_pos(num, vote, comment="", discuss=""):
            ad = Person.objects.get(name="Ad No%s" % num)
            e = BallotPositionDocEvent()
            e.doc = draft
            e.by = ad
            e.ad = ad
            e.pos = BallotPositionName.objects.get(slug=vote)
            e.type = "changed_ballot_position"
            e.comment = comment
            if e.comment:
                e.comment_time = datetime.datetime.now()
            e.discuss = discuss
            if e.discuss:
                e.discuss_time = datetime.datetime.now()
            e.save()

        # active
        create_pos(1, "yes", discuss="discuss1 " * 20)
        create_pos(2, "noobj", comment="comment2 " * 20)
        create_pos(3, "discuss", discuss="discuss3 " * 20, comment="comment3 " * 20)
        create_pos(4, "abstain")
        create_pos(5, "recuse")

        # inactive
        create_pos(9, "yes")

        # we need approval text to be able to submit
        e = WriteupDocEvent()
        e.doc = draft
        e.by = Person.objects.get(name="Aread Irector")
        e.type = "changed_ballot_approval_text"
        e.text = "The document has been approved."
        e.save()
        
        mailbox_before = len(outbox)
        
        r = self.client.post(url, dict(
                ballot_writeup="This is a test.",
                issue_ballot="1"))
        self.assertEquals(r.status_code, 200)
        draft = Document.objects.get(name=draft.name)

        self.assertTrue(draft.latest_event(type="sent_ballot_announcement"))
        self.assertEquals(len(outbox), mailbox_before + 2)
        issue_email = outbox[-2]
        self.assertTrue("Evaluation:" in issue_email['Subject'])
        self.assertTrue("comment1" not in str(issue_email))
        self.assertTrue("comment2" in str(issue_email))
        self.assertTrue("comment3" in str(issue_email))
        self.assertTrue("discuss3" in str(issue_email))
        self.assertTrue("This is a test" in str(issue_email))
        self.assertTrue("The document has been approved" in str(issue_email))

    def test_edit_approval_text(self):
        draft = make_test_data()
        url = urlreverse('doc_ballot_approvaltext', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "secretary", url)

        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('textarea[name=approval_text]')), 1)
        self.assertEquals(len(q('input[type=submit][value*="Save Approval"]')), 1)

        # save
        r = self.client.post(url, dict(
                approval_text="This is a simple test.",
                save_approval_text="1"))
        self.assertEquals(r.status_code, 200)
        draft = Document.objects.get(name=draft.name)
        self.assertTrue("This is a simple test" in draft.latest_event(WriteupDocEvent, type="changed_ballot_approval_text").text)

        # test regenerate
        r = self.client.post(url, dict(regenerate_approval_text="1"))
        self.assertEquals(r.status_code, 200)
        draft = Document.objects.get(name=draft.name)
        self.assertTrue("Subject: Protocol Action" in draft.latest_event(WriteupDocEvent, type="changed_ballot_approval_text").text)

        # test regenerate when it's a disapprove
        draft.set_state(State.objects.get(type="draft-iesg", slug="nopubadw"))

        r = self.client.post(url, dict(regenerate_approval_text="1"))
        self.assertEquals(r.status_code, 200)
        draft = Document.objects.get(name=draft.name)
        self.assertTrue("NOT be published" in draft.latest_event(WriteupDocEvent, type="changed_ballot_approval_text").text)
        
class ApproveBallotTestCase(django.test.TestCase):
    fixtures = ['names']

    def test_approve_ballot(self):
        draft = make_test_data()
        draft.set_state(State.objects.get(type="draft-iesg", slug="iesg-eva")) # make sure it's approvable

        url = urlreverse('doc_approve_ballot', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "secretary", url)

        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue("Send out the announcement" in q('.actions input[type=submit]')[0].get('value'))
        self.assertEquals(len(q('.announcement pre:contains("Subject: Protocol Action")')), 1)

        # approve
        mailbox_before = len(outbox)
        
        r = self.client.post(url, dict())
        self.assertEquals(r.status_code, 302)

        draft = Document.objects.get(name=draft.name)
        self.assertEquals(draft.get_state_slug("draft-iesg"), "ann")
        self.assertEquals(len(outbox), mailbox_before + 4)
        self.assertTrue("Protocol Action" in outbox[-2]['Subject'])
        # the IANA copy
        self.assertTrue("Protocol Action" in outbox[-1]['Subject'])

    def test_disapprove_ballot(self):
        draft = make_test_data()
        draft.set_state(State.objects.get(type="draft-iesg", slug="nopubadw"))

        url = urlreverse('doc_approve_ballot', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "secretary", url)

        # disapprove (the Martians aren't going to be happy)
        mailbox_before = len(outbox)

        r = self.client.post(url, dict())
        self.assertEquals(r.status_code, 302)

        draft = Document.objects.get(name=draft.name)
        self.assertEquals(draft.get_state_slug("draft-iesg"), "dead")
        self.assertEquals(len(outbox), mailbox_before + 3)
        self.assertTrue("NOT be published" in str(outbox[-1]))

class MakeLastCallTestCase(django.test.TestCase):
    fixtures = ['names']

    def test_make_last_call(self):
        draft = make_test_data()
        draft.set_state(State.objects.get(type="draft-iesg", slug="lc-req"))

        url = urlreverse('doc_make_last_call', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "secretary", url)

        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('input[name=last_call_sent_date]')), 1)

        # make last call
        mailbox_before = len(outbox)

        expire_date = q('input[name=last_call_expiration_date]')[0].get("value")
        
        r = self.client.post(url,
                             dict(last_call_sent_date=q('input[name=last_call_sent_date]')[0].get("value"),
                                  last_call_expiration_date=expire_date
                                  ))
        self.assertEquals(r.status_code, 302)

        draft = Document.objects.get(name=draft.name)
        self.assertEquals(draft.get_state_slug("draft-iesg"), "lc")
        self.assertEquals(draft.latest_event(LastCallDocEvent, "sent_last_call").expires.strftime("%Y-%m-%d"), expire_date)
        self.assertEquals(len(outbox), mailbox_before + 4)

        self.assertTrue("Last Call" in outbox[-4]['Subject'])
        # the IANA copy
        self.assertTrue("Last Call" in outbox[-3]['Subject'])

class ExpireIDsTestCase(django.test.TestCase):
    fixtures = ['names']

    def setUp(self):
        self.id_dir = os.path.abspath("tmp-id-dir")
        self.archive_dir = os.path.abspath("tmp-id-archive")
        os.mkdir(self.id_dir)
        os.mkdir(self.archive_dir)
        os.mkdir(os.path.join(self.archive_dir, "unknown_ids"))
        os.mkdir(os.path.join(self.archive_dir, "deleted_tombstones"))
        os.mkdir(os.path.join(self.archive_dir, "expired_without_tombstone"))
        
        settings.IDSUBMIT_REPOSITORY_PATH = self.id_dir
        settings.INTERNET_DRAFT_ARCHIVE_DIR = self.archive_dir

    def tearDown(self):
        shutil.rmtree(self.id_dir)
        shutil.rmtree(self.archive_dir)

    def write_id_file(self, name, size):
        f = open(os.path.join(self.id_dir, name), 'w')
        f.write("a" * size)
        f.close()
        
    def test_in_id_expire_freeze(self):
        from ietf.idrfc.expire import in_id_expire_freeze
        
        # dummy id dates
        IDDates.objects.create(id=IDDates.SECOND_CUT_OFF, date=datetime.date(2010, 7, 12), description="", f_name="")
        IDDates.objects.create(id=IDDates.IETF_MONDAY, date=datetime.date(2010, 7, 26), description="", f_name="")
    
        self.assertTrue(not in_id_expire_freeze(datetime.datetime(2010, 7, 11, 0, 0)))
        self.assertTrue(not in_id_expire_freeze(datetime.datetime(2010, 7, 12, 8, 0)))
        self.assertTrue(in_id_expire_freeze(datetime.datetime(2010, 7, 12, 10, 0)))
        self.assertTrue(in_id_expire_freeze(datetime.datetime(2010, 7, 25, 0, 0)))
        self.assertTrue(not in_id_expire_freeze(datetime.datetime(2010, 7, 26, 0, 0)))
        
    def test_warn_expirable_ids(self):
        from ietf.idrfc.expire import get_soon_to_expire_ids, send_expire_warning_for_id, INTERNET_DRAFT_DAYS_TO_EXPIRE

        draft = make_test_data()

        self.assertEquals(len(list(get_soon_to_expire_ids(14))), 0)

        # hack into expirable state
        draft.unset_state("draft-iesg")

        NewRevisionDocEvent.objects.create(
            type="new_revision",
            by=Person.objects.get(name="Aread Irector"),
            doc=draft,
            desc="New revision",
            time=datetime.datetime.now() - datetime.timedelta(days=INTERNET_DRAFT_DAYS_TO_EXPIRE - 7),
            rev="01"
        )

        self.assertEquals(len(list(get_soon_to_expire_ids(14))), 1)
        
        # test send warning
        mailbox_before = len(outbox)

        send_expire_warning_for_id(draft)

        self.assertEquals(len(outbox), mailbox_before + 1)
        self.assertTrue("aread@ietf.org" in str(outbox[-1])) # author
        self.assertTrue("wgchairman@ietf.org" in str(outbox[-1]))
        
    def test_expire_ids(self):
        from ietf.idrfc.expire import get_expired_ids, send_expire_notice_for_id, expire_id, INTERNET_DRAFT_DAYS_TO_EXPIRE

        draft = make_test_data()
        
        self.assertEquals(len(list(get_expired_ids())), 0)
        
        # hack into expirable state
        draft.unset_state("draft-iesg")

        NewRevisionDocEvent.objects.create(
            type="new_revision",
            by=Person.objects.get(name="Aread Irector"),
            doc=draft,
            desc="New revision",
            time=datetime.datetime.now() - datetime.timedelta(days=INTERNET_DRAFT_DAYS_TO_EXPIRE + 1),
            rev="01"
        )

        self.assertEquals(len(list(get_expired_ids())), 1)

        draft.set_state(State.objects.get(type="draft-iesg", slug="watching"))

        self.assertEquals(len(list(get_expired_ids())), 1)

        # test notice
        mailbox_before = len(outbox)

        send_expire_notice_for_id(draft)

        self.assertEquals(len(outbox), mailbox_before + 1)
        self.assertTrue("expired" in outbox[-1]["Subject"])

        # test expiry
        txt = "%s-%s.txt" % (draft.name, draft.rev)
        self.write_id_file(txt, 5000)

        revision_before = draft.rev

        expire_id(draft)

        draft = Document.objects.get(name=draft.name)
        self.assertEquals(draft.get_state_slug(), "expired")
        self.assertEquals(int(draft.rev), int(revision_before) + 1)
        self.assertEquals(draft.get_state_slug("draft-iesg"), "dead")
        self.assertTrue(draft.latest_event(type="expired_document"))
        self.assertTrue(not os.path.exists(os.path.join(self.id_dir, txt)))
        self.assertTrue(os.path.exists(os.path.join(self.archive_dir, txt)))
        new_txt = "%s-%s.txt" % (draft.name, draft.rev)
        self.assertTrue(os.path.exists(os.path.join(self.id_dir, new_txt)))

    def test_clean_up_id_files(self):
        draft = make_test_data()
        
        from ietf.idrfc.expire import clean_up_id_files, INTERNET_DRAFT_DAYS_TO_EXPIRE

        # put unknown file
        unknown = "draft-i-am-unknown-01.txt"
        self.write_id_file(unknown, 5000)

        clean_up_id_files()
        
        self.assertTrue(not os.path.exists(os.path.join(self.id_dir, unknown)))
        self.assertTrue(os.path.exists(os.path.join(self.archive_dir, "unknown_ids", unknown)))

        
        # put file with malformed name (no revision)
        malformed = draft.name + ".txt"
        self.write_id_file(malformed, 5000)

        clean_up_id_files()
        
        self.assertTrue(not os.path.exists(os.path.join(self.id_dir, malformed)))
        self.assertTrue(os.path.exists(os.path.join(self.archive_dir, "unknown_ids", malformed)))

        
        # RFC draft
        draft.set_state(State.objects.get(type="draft", slug="rfc"))
        draft.save()

        txt = "%s-%s.txt" % (draft.name, draft.rev)
        self.write_id_file(txt, 5000)
        pdf = "%s-%s.pdf" % (draft.name, draft.rev)
        self.write_id_file(pdf, 5000)

        clean_up_id_files()
        
        # txt files shouldn't be moved (for some reason)
        self.assertTrue(os.path.exists(os.path.join(self.id_dir, txt)))
        
        self.assertTrue(not os.path.exists(os.path.join(self.id_dir, pdf)))
        self.assertTrue(os.path.exists(os.path.join(self.archive_dir, "unknown_ids", pdf)))


        # expire draft
        draft.set_state(State.objects.get(type="draft", slug="expired"))
        draft.save()

        e = DocEvent()
        e.doc = draft
        e.by = Person.objects.get(name="(System)")
        e.type = "expired_document"
        e.text = "Document has expired"
        e.time = datetime.date.today() - datetime.timedelta(days=INTERNET_DRAFT_DAYS_TO_EXPIRE + 1)
        e.save()

        # expired without tombstone
        txt = "%s-%s.txt" % (draft.name, draft.rev)
        self.write_id_file(txt, 5000)

        clean_up_id_files()
        
        self.assertTrue(not os.path.exists(os.path.join(self.id_dir, txt)))
        self.assertTrue(os.path.exists(os.path.join(self.archive_dir, "expired_without_tombstone", txt)))
        

        # expired with tombstone
        revision_before = draft.rev

        txt = "%s-%s.txt" % (draft.name, draft.rev)
        self.write_id_file(txt, 1000) # < 1500 means tombstone

        clean_up_id_files()
        
        self.assertTrue(not os.path.exists(os.path.join(self.id_dir, txt)))
        self.assertTrue(os.path.exists(os.path.join(self.archive_dir, "deleted_tombstones", txt)))

        draft = Document.objects.get(name=draft.name)
        self.assertEquals(int(draft.rev), int(revision_before) - 1)
        self.assertTrue(draft.tags.filter(slug="exp-tomb"))
        
class ExpireLastCallTestCase(django.test.TestCase):
    fixtures = ['names']

    def test_expire_last_call(self):
        from ietf.idrfc.lastcall import get_expired_last_calls, expire_last_call
        
        # check that non-expirable drafts aren't expired

        draft = make_test_data()
        draft.set_state(State.objects.get(type="draft-iesg", slug="lc"))

        secretary = Person.objects.get(name="Sec Retary")
        
        self.assertEquals(len(list(get_expired_last_calls())), 0)

        e = LastCallDocEvent()
        e.doc = draft
        e.by = secretary
        e.type = "sent_last_call"
        e.text = "Last call sent"
        e.expires = datetime.datetime.now() + datetime.timedelta(days=14)
        e.save()
        
        self.assertEquals(len(list(get_expired_last_calls())), 0)

        # test expired
        e = LastCallDocEvent()
        e.doc = draft
        e.by = secretary
        e.type = "sent_last_call"
        e.text = "Last call sent"
        e.expires = datetime.datetime.now()
        e.save()
        
        drafts = list(get_expired_last_calls())
        self.assertEquals(len(drafts), 1)

        # expire it
        mailbox_before = len(outbox)
        events_before = draft.docevent_set.count()
        
        expire_last_call(drafts[0])

        draft = Document.objects.get(name=draft.name)
        self.assertEquals(draft.get_state_slug("draft-iesg"), "writeupw")
        self.assertEquals(draft.docevent_set.count(), events_before + 1)
        self.assertEquals(len(outbox), mailbox_before + 1)
        self.assertTrue("Last Call Expired" in outbox[-1]["Subject"])
        

        
TEST_RFC_INDEX = '''<?xml version="1.0" encoding="UTF-8"?>
<rfc-index xmlns="http://www.rfc-editor.org/rfc-index" 
           xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
           xsi:schemaLocation="http://www.rfc-editor.org/rfc-index 
                               http://www.rfc-editor.org/rfc-index.xsd">
    <bcp-entry>
        <doc-id>BCP0110</doc-id>
        <is-also>
            <doc-id>RFC4170</doc-id>
        </is-also>
    </bcp-entry>
    <bcp-entry>
        <doc-id>BCP0111</doc-id>
        <is-also>
            <doc-id>RFC4181</doc-id>
            <doc-id>RFC4841</doc-id>
        </is-also>
    </bcp-entry>
    <fyi-entry>
        <doc-id>FYI0038</doc-id>
        <is-also>
            <doc-id>RFC3098</doc-id>
        </is-also>
    </fyi-entry>
    <rfc-entry>
        <doc-id>RFC1938</doc-id>
        <title>A One-Time Password System</title>
        <author>
            <name>N. Haller</name>
        </author>
        <author>
            <name>C. Metz</name>
        </author>
        <date>
            <month>May</month>
            <year>1996</year>
        </date>
        <format>
            <file-format>ASCII</file-format>
            <char-count>44844</char-count>
            <page-count>18</page-count>
        </format>
        <keywords>
            <kw>OTP</kw>
            <kw>authentication</kw>
            <kw>S/KEY</kw>
        </keywords>
        <abstract><p>This document describes a one-time password authentication system (OTP). [STANDARDS-TRACK]</p></abstract>
        <obsoleted-by>
            <doc-id>RFC2289</doc-id>
        </obsoleted-by>
        <current-status>PROPOSED STANDARD</current-status>
        <publication-status>PROPOSED STANDARD</publication-status>
        <stream>Legacy</stream>
    </rfc-entry>
    <rfc-entry>
        <doc-id>RFC2289</doc-id>
        <title>A One-Time Password System</title>
        <author>
            <name>N. Haller</name>
        </author>
        <author>
            <name>C. Metz</name>
        </author>
        <author>
            <name>P. Nesser</name>
        </author>
        <author>
            <name>M. Straw</name>
        </author>
        <date>
            <month>February</month>
            <year>1998</year>
        </date>
        <format>
            <file-format>ASCII</file-format>
            <char-count>56495</char-count>
            <page-count>25</page-count>
        </format>
        <keywords>
            <kw>ONE-PASS</kw>
            <kw>authentication</kw>
            <kw>OTP</kw>
            <kw>replay</kw>
            <kw>attach</kw>
        </keywords>
        <abstract><p>This document describes a one-time password authentication system (OTP).  The system provides authentication for system access (login) and other applications requiring authentication that is secure against passive attacks based on replaying captured reusable passwords. [STANDARDS- TRACK]</p></abstract>
        <obsoletes>
            <doc-id>RFC1938</doc-id>
        </obsoletes>
        <is-also>
            <doc-id>STD0061</doc-id>
        </is-also>
        <current-status>STANDARD</current-status>
        <publication-status>DRAFT STANDARD</publication-status>
        <stream>Legacy</stream>
    </rfc-entry>
    <rfc-entry>
        <doc-id>RFC3098</doc-id>
        <title>How to Advertise Responsibly Using E-Mail and Newsgroups or - how NOT to $$$$$  MAKE ENEMIES FAST!  $$$$$</title>
        <author>
            <name>T. Gavin</name>
        </author>
        <author>
            <name>D. Eastlake 3rd</name>
        </author>
        <author>
            <name>S. Hambridge</name>
        </author>
        <date>
            <month>April</month>
            <year>2001</year>
        </date>
        <format>
            <file-format>ASCII</file-format>
            <char-count>64687</char-count>
            <page-count>28</page-count>
        </format>
        <keywords>
            <kw>internet</kw>
            <kw>marketing</kw>
            <kw>users</kw>
            <kw>service</kw>
            <kw>providers</kw>
            <kw>isps</kw>
        </keywords>
        <abstract><p>This memo offers useful suggestions for responsible advertising techniques that can be used via the internet in an environment where the advertiser, recipients, and the Internet Community can coexist in a productive and mutually respectful fashion.  This memo provides information for the Internet community.</p></abstract>
        <draft>draft-ietf-run-adverts-02</draft>
        <is-also>
            <doc-id>FYI0038</doc-id>
        </is-also>
        <current-status>INFORMATIONAL</current-status>
        <publication-status>INFORMATIONAL</publication-status>
        <stream>Legacy</stream>
    </rfc-entry>
    <rfc-entry>
        <doc-id>RFC4170</doc-id>
        <title>Tunneling Multiplexed Compressed RTP (TCRTP)</title>
        <author>
            <name>B. Thompson</name>
        </author>
        <author>
            <name>T. Koren</name>
        </author>
        <author>
            <name>D. Wing</name>
        </author>
        <date>
            <month>November</month>
            <year>2005</year>
        </date>
        <format>
            <file-format>ASCII</file-format>
            <char-count>48990</char-count>
            <page-count>24</page-count>
        </format>
        <keywords>
            <kw>real-time transport protocol</kw>
        </keywords>
        <abstract><p>This document describes a method to improve the bandwidth utilization of RTP streams over network paths that carry multiple Real-time Transport Protocol (RTP) streams in parallel between two endpoints, as in voice trunking.  The method combines standard protocols that provide compression, multiplexing, and tunneling over a network path for the purpose of reducing the bandwidth used when multiple RTP streams are carried over that path.  This document specifies an Internet Best Current Practices for the Internet Community, and requests discussion and suggestions for improvements.</p></abstract>
        <draft>draft-ietf-avt-tcrtp-08</draft>
        <is-also>
            <doc-id>BCP0110</doc-id>
        </is-also>
        <current-status>BEST CURRENT PRACTICE</current-status>
        <publication-status>BEST CURRENT PRACTICE</publication-status>
        <stream>IETF</stream>
        <area>rai</area>
        <wg_acronym>avt</wg_acronym>
    </rfc-entry>
    <rfc-entry>
        <doc-id>RFC4181</doc-id>
        <title>Guidelines for Authors and Reviewers of MIB Documents</title>
        <author>
            <name>C. Heard</name>
            <title>Editor</title>
        </author>
        <date>
            <month>September</month>
            <year>2005</year>
        </date>
        <format>
            <file-format>ASCII</file-format>
            <char-count>102521</char-count>
            <page-count>42</page-count>
        </format>
        <keywords>
            <kw>standards-track specifications</kw>
            <kw>management information base</kw>
            <kw>review</kw>
        </keywords>
        <abstract><p>This memo provides guidelines for authors and reviewers of IETF standards-track specifications containing MIB modules.  Applicable portions may be used as a basis for reviews of other MIB documents.  This document specifies an Internet Best Current Practices for the Internet Community, and requests discussion and suggestions for improvements.</p></abstract>
        <draft>draft-ietf-ops-mib-review-guidelines-04</draft>
        <updated-by>
            <doc-id>RFC4841</doc-id>
        </updated-by>
        <is-also>
            <doc-id>BCP0111</doc-id>
        </is-also>
        <current-status>BEST CURRENT PRACTICE</current-status>
        <publication-status>BEST CURRENT PRACTICE</publication-status>
        <stream>IETF</stream>
        <area>rtg</area>
        <wg_acronym>ospf</wg_acronym>
        <errata-url>http://www.rfc-editor.org/errata_search.php?rfc=4181</errata-url>
    </rfc-entry>
    <rfc-entry>
        <doc-id>RFC4841</doc-id>
        <title>RFC 4181 Update to Recognize the IETF Trust</title>
        <author>
            <name>C. Heard</name>
            <title>Editor</title>
        </author>
        <date>
            <month>March</month>
            <year>2007</year>
        </date>
        <format>
            <file-format>ASCII</file-format>
            <char-count>4414</char-count>
            <page-count>3</page-count>
        </format>
        <keywords>
            <kw>management information base</kw>
            <kw> standards-track specifications</kw>
            <kw>mib review</kw>
        </keywords>
        <abstract><p>This document updates RFC 4181, "Guidelines for Authors and Reviewers of MIB Documents", to recognize the creation of the IETF Trust.  This document specifies an Internet Best Current Practices for the Internet Community, and requests discussion and suggestions for improvements.</p></abstract>
        <draft>draft-heard-rfc4181-update-00</draft>
        <updates>
            <doc-id>RFC4181</doc-id>
        </updates>
        <is-also>
            <doc-id>BCP0111</doc-id>
        </is-also>
        <current-status>BEST CURRENT PRACTICE</current-status>
        <publication-status>BEST CURRENT PRACTICE</publication-status>
        <stream>IETF</stream>
        <wg_acronym>NON WORKING GROUP</wg_acronym>
    </rfc-entry>
    <std-entry>
        <doc-id>STD0061</doc-id>
        <title>A One-Time Password System</title>
        <is-also>
            <doc-id>RFC2289</doc-id>
        </is-also>
    </std-entry>
</rfc-index>
'''

TEST_QUEUE = '''<rfc-editor-queue xmlns="http://www.rfc-editor.org/rfc-editor-queue">
<section name="IETF STREAM: WORKING GROUP STANDARDS TRACK">
<entry xml:id="draft-ietf-sipping-app-interaction-framework">
<draft>draft-ietf-sipping-app-interaction-framework-05.txt</draft>
<date-received>2005-10-17</date-received>
<state>EDIT</state>
<normRef>
<ref-name>draft-ietf-sip-gruu</ref-name>
<ref-state>IN-QUEUE</ref-state>
</normRef>
<authors>J. Rosenberg</authors>
<title>
A Framework for Application Interaction in the Session Initiation Protocol (SIP)
</title>
<bytes>94672</bytes>
<source>Session Initiation Proposal Investigation</source>
</entry>
</section>
<section name="IETF STREAM: NON-WORKING GROUP STANDARDS TRACK">
<entry xml:id="draft-ietf-sip-gruu">
<draft>draft-ietf-sip-gruu-15.txt</draft>
<date-received>2007-10-15</date-received>
<state>MISSREF</state>
<normRef>
<ref-name>draft-ietf-sip-outbound</ref-name>
<ref-state>NOT-RECEIVED</ref-state>
</normRef>
<authors>J. Rosenberg</authors>
<title>
Obtaining and Using Globally Routable User Agent (UA) URIs (GRUU) in the Session Initiation Protocol (SIP)
</title>
<bytes>95501</bytes>
<source>Session Initiation Protocol</source>
</entry>
</section>
<section name="IETF STREAM: WORKING GROUP INFORMATIONAL/EXPERIMENTAL/BCP">
</section>
<section name="IETF STREAM: NON-WORKING GROUP INFORMATIONAL/EXPERIMENTAL/BCP">
<entry xml:id="draft-thomson-beep-async">
<draft>draft-thomson-beep-async-02.txt</draft>
<date-received>2009-05-12</date-received>
<state>EDIT</state>
<state>IANA</state>
<authors>M. Thomson</authors>
<title>
Asynchronous Channels for the Blocks Extensible Exchange Protocol (BEEP)
</title>
<bytes>17237</bytes>
<source>IETF - NON WORKING GROUP</source>
</entry>
</section>
<section name="IAB STREAM">
</section>
<section name="IRTF STREAM">
</section>
<section name="INDEPENDENT SUBMISSIONS">
</section>
</rfc-editor-queue>
'''

class MirrorScriptTestCases(unittest.TestCase,RealDatabaseTest):

    def setUp(self):
        self.setUpRealDatabase()
    def tearDown(self):
        self.tearDownRealDatabase()

    def testRfcIndex(self):
        print "     Testing rfc-index.xml parsing"
        from ietf.idrfc.mirror_rfc_index import parse
        data = parse(StringIO.StringIO(TEST_RFC_INDEX))
        self.assertEquals(len(data), 6)
        print "OK"

    def testRfcEditorQueue(self):
        print "     Testing queue2.xml parsing"
        from ietf.idrfc.mirror_rfc_editor_queue import parse_all
        (drafts,refs) = parse_all(StringIO.StringIO(TEST_QUEUE))
        self.assertEquals(len(drafts), 3)
        self.assertEquals(len(refs), 3)
        print "OK"

