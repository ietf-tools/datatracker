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
from datetime import date, timedelta, time

import django.test
from django.core.urlresolvers import reverse as urlreverse
from django.conf import settings

from pyquery import PyQuery
import debug

from ietf.doc.models import *
from ietf.name.models import *
from ietf.group.models import *
from ietf.person.models import *
from ietf.meeting.models import Meeting, MeetingTypeName
from ietf.iesg.models import TelechatDate
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
        draft.tags.add("ad-f-up")
        
        r = self.client.post(url,
                             dict(state=State.objects.get(type="draft-iesg", slug="review-e").pk,
                                  substate="point",
                                  comment="Test comment"))
        self.assertEquals(r.status_code, 302)

        draft = Document.objects.get(name=draft.name)
        self.assertEquals(draft.get_state_slug("draft-iesg"), "review-e")
        self.assertTrue(not draft.tags.filter(slug="ad-f-up"))
        self.assertTrue(draft.tags.filter(slug="point"))
        self.assertEquals(draft.docevent_set.count(), events_before + 2)
        self.assertTrue("Test comment" in draft.docevent_set.all()[0].desc)
        self.assertTrue("State changed" in draft.docevent_set.all()[1].desc)
        self.assertEquals(len(outbox), mailbox_before + 2)
        self.assertTrue("State Update Notice" in outbox[-2]['Subject'])
        self.assertTrue(draft.name in outbox[-1]['Subject'])

        
        # check that we got a previous state now
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('.prev-state form input[name="state"]')), 1)

    def test_pull_from_rfc_queue(self):
        draft = make_test_data()
        draft.set_state(State.objects.get(type="draft-iesg", slug="rfcqueue"))

        url = urlreverse('doc_change_state', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "secretary", url)

        # change state
        mailbox_before = len(outbox)

        r = self.client.post(url,
                             dict(state=State.objects.get(type="draft-iesg", slug="review-e").pk,
                                  substate="",
                                  comment="Test comment"))
        self.assertEquals(r.status_code, 302)

        draft = Document.objects.get(name=draft.name)
        self.assertEquals(draft.get_state_slug("draft-iesg"), "review-e")
        self.assertEquals(len(outbox), mailbox_before + 2 + 1)
        self.assertTrue(draft.name in outbox[-1]['Subject'])
        self.assertTrue("changed state" in outbox[-1]['Subject'])
        self.assertTrue("is no longer" in str(outbox[-1]))
        self.assertTrue("Test comment" in str(outbox[-1]))

    def test_change_iana_state(self):
        draft = make_test_data()

        first_state = State.objects.get(type="draft-iana-review", slug="need-rev")
        next_state = State.objects.get(type="draft-iana-review", slug="ok-noact")
        draft.set_state(first_state)

        url = urlreverse('doc_change_iana_state', kwargs=dict(name=draft.name, state_type="iana-review"))
        login_testing_unauthorized(self, "iana", url)

        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form select[name=state]')), 1)
        
        # faulty post
        r = self.client.post(url, dict(state="foobarbaz"))
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form ul.errorlist')) > 0)
        draft = Document.objects.get(name=draft.name)
        self.assertEquals(draft.get_state("draft-iana-review"), first_state)

        # change state
        r = self.client.post(url, dict(state=next_state.pk))
        self.assertEquals(r.status_code, 302)

        draft = Document.objects.get(name=draft.name)
        self.assertEquals(draft.get_state("draft-iana-review"), next_state)

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
                                  ad=str(new_ad.pk),
                                  notify="test@example.com",
                                  note="New note",
                                  telechat_date="",
                                  ))
        self.assertEquals(r.status_code, 302)

        draft = Document.objects.get(name=draft.name)
        self.assertEquals(draft.ad, new_ad)
        self.assertEquals(draft.note, "New note")
        self.assertTrue(not draft.latest_event(TelechatDocEvent, type="scheduled_for_telechat"))
        self.assertEquals(draft.docevent_set.count(), events_before + 3)
        self.assertEquals(len(outbox), mailbox_before + 1)
        self.assertTrue(draft.name in outbox[-1]['Subject'])

    def test_edit_telechat_date(self):
        draft = make_test_data()
        
        url = urlreverse('doc_edit_info', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "secretary", url)

        data = dict(intended_std_level=str(draft.intended_std_level_id),
                    stream=draft.stream_id,
                    ad=str(draft.ad_id),
                    notify="test@example.com",
                    note="",
                    )

        # add to telechat
        self.assertTrue(not draft.latest_event(TelechatDocEvent, type="scheduled_for_telechat"))
        data["telechat_date"] = TelechatDate.objects.active()[0].date.isoformat()
        r = self.client.post(url, data)
        self.assertEquals(r.status_code, 302)

        draft = Document.objects.get(name=draft.name)
        self.assertTrue(draft.latest_event(TelechatDocEvent, type="scheduled_for_telechat"))
        self.assertEqual(draft.latest_event(TelechatDocEvent, type="scheduled_for_telechat").telechat_date, TelechatDate.objects.active()[0].date)

        # change telechat
        data["telechat_date"] = TelechatDate.objects.active()[1].date.isoformat()
        r = self.client.post(url, data)
        self.assertEquals(r.status_code, 302)

        draft = Document.objects.get(name=draft.name)
        self.assertEqual(draft.latest_event(TelechatDocEvent, type="scheduled_for_telechat").telechat_date, TelechatDate.objects.active()[1].date)

        # remove from agenda
        data["telechat_date"] = ""
        r = self.client.post(url, data)
        self.assertEquals(r.status_code, 302)

        draft = Document.objects.get(name=draft.name)
        self.assertTrue(not draft.latest_event(TelechatDocEvent, type="scheduled_for_telechat").telechat_date)

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
        doc_alias = DocAlias.objects.create(
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
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form select[name=intended_std_level]')), 1)
        self.assertTrue('@' in q('form input[name=notify]')[0].get('value'))

        # add
        events_before = draft.docevent_set.count()
        mailbox_before = len(outbox)

        ad = Person.objects.get(name="Aread Irector")

        r = self.client.post(url,
                             dict(intended_std_level=str(draft.intended_std_level_id),
                                  ad=ad.pk,
                                  create_in_state=State.objects.get(type="draft-iesg", slug="watching").pk,
                                  notify="test@example.com",
                                  note="This is a note",
                                  telechat_date="",
                                  ))
        self.assertEquals(r.status_code, 302)

        draft = Document.objects.get(name=draft.name)
        self.assertEquals(draft.get_state_slug("draft-iesg"), "watching")
        self.assertEquals(draft.ad, ad)
        self.assertEquals(draft.note, "This is a note")
        self.assertTrue(not draft.latest_event(TelechatDocEvent, type="scheduled_for_telechat"))
        self.assertEquals(draft.docevent_set.count(), events_before + 3)
        events = list(draft.docevent_set.order_by('time', 'id'))
        self.assertEquals(events[-3].type, "started_iesg_process")
        self.assertEquals(len(outbox), mailbox_before)

    def test_edit_consensus(self):
        draft = make_test_data()
        
        url = urlreverse('doc_edit_consensus', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "secretary", url)

        self.assertTrue(not draft.latest_event(ConsensusDocEvent, type="changed_consensus"))
        r = self.client.post(url, dict(consensus="Yes"))
        self.assertEquals(r.status_code, 302)

        self.assertEqual(draft.latest_event(ConsensusDocEvent, type="changed_consensus").consensus, True)


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

        # complete resurrect
        events_before = draft.docevent_set.count()
        mailbox_before = len(outbox)
        
        r = self.client.post(url, dict())
        self.assertEquals(r.status_code, 302)

        draft = Document.objects.get(name=draft.name)
        self.assertEquals(draft.docevent_set.count(), events_before + 1)
        self.assertEquals(draft.latest_event().type, "completed_resurrect")
        self.assertEquals(draft.get_state_slug(), "active")
        self.assertTrue(draft.expires >= datetime.datetime.now() + datetime.timedelta(days=settings.INTERNET_DRAFT_DAYS_TO_EXPIRE - 1))
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

        # Make sure we can also do it as IANA
        self.client.login(remote_user="iana")

        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form textarea[name=comment]')), 1)


class EditPositionTestCase(django.test.TestCase):
    fixtures = ['names']

    def test_edit_position(self):
        draft = make_test_data()
        url = urlreverse('ietf.idrfc.views_ballot.edit_position', kwargs=dict(name=draft.name,
                                                          ballot_id=draft.latest_event(BallotDocEvent, type="created_ballot").pk))
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
                                       discuss=" This is a discussion test. \n ",
                                       comment=" This is a test. \n "))
        self.assertEquals(r.status_code, 302)

        pos = draft.latest_event(BallotPositionDocEvent, ad=ad)
        self.assertEquals(pos.pos.slug, "discuss")
        self.assertTrue(" This is a discussion test." in pos.discuss)
        self.assertTrue(pos.discuss_time != None)
        self.assertTrue(" This is a test." in pos.comment)
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
        url = urlreverse('ietf.idrfc.views_ballot.edit_position', kwargs=dict(name=draft.name,
                                                          ballot_id=draft.latest_event(BallotDocEvent, type="created_ballot").pk))
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

    def test_cannot_edit_position_as_pre_ad(self):
        draft = make_test_data()
        url = urlreverse('ietf.idrfc.views_ballot.edit_position', kwargs=dict(name=draft.name,
                          ballot_id=draft.latest_event(BallotDocEvent, type="created_ballot").pk))
        
        # transform to pre-ad
        ad_role = Role.objects.filter(name="ad")[0]
        ad_role.name_id = "pre-ad"
        ad_role.save()

        # we can see
        login_testing_unauthorized(self, ad_role.person.user.username, url)

        # but not touch
        r = self.client.post(url, dict(position="discuss", discuss="Test discuss text"))
        self.assertEquals(r.status_code, 403)
        
    def test_send_ballot_comment(self):
        draft = make_test_data()
        draft.notify = "somebody@example.com"
        draft.save()

        ad = Person.objects.get(name="Aread Irector")

        ballot = draft.latest_event(BallotDocEvent, type="created_ballot")

        BallotPositionDocEvent.objects.create(
            doc=draft, type="changed_ballot_position",
            by=ad, ad=ad, ballot=ballot, pos=BallotPositionName.objects.get(slug="discuss"),
            discuss="This draft seems to be lacking a clearer title?",
            discuss_time=datetime.datetime.now(),
            comment="Test!",
            comment_time=datetime.datetime.now())
        
        url = urlreverse('doc_send_ballot_comment', kwargs=dict(name=draft.name,
                                                                ballot_id=ballot.pk))
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
        self.assertTrue("DISCUSS" in m['Subject'])
        self.assertTrue(draft.name in m['Subject'])
        self.assertTrue("clearer title" in str(m))
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

        # add a IANA review note
        draft.set_state(State.objects.get(type="draft-iana-review", slug="not-ok"))
        DocEvent.objects.create(type="iana_review",
                                doc=draft,
                                by=Person.objects.get(user__username="iana"),
                                desc="IANA does not approve of this document, it does not make sense.",
                                )

        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('textarea[name=ballot_writeup]')), 1)
        self.assertEquals(len(q('input[type=submit][value*="Save Ballot Writeup"]')), 1)
        self.assertTrue("IANA does not" in r.content)

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

        ballot = draft.latest_event(BallotDocEvent, type="created_ballot")

        def create_pos(num, vote, comment="", discuss=""):
            ad = Person.objects.get(name="Ad No%s" % num)
            e = BallotPositionDocEvent()
            e.doc = draft
            e.ballot = ballot
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
        self.assertTrue("The IESG has approved" in str(issue_email))

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

        # test regenerate when it's a conflict review
        draft.group = Group.objects.get(type="individ")
        draft.stream_id = "irtf"
        draft.save()
        draft.set_state(State.objects.get(type="draft-iesg", slug="iesg-eva"))

        r = self.client.post(url, dict(regenerate_approval_text="1"))
        self.assertEquals(r.status_code, 200)
        draft = Document.objects.get(name=draft.name)
        self.assertTrue("Subject: Results of IETF-conflict review" in draft.latest_event(WriteupDocEvent, type="changed_ballot_approval_text").text)
        
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
        self.assertTrue("Protocol Action" in draft.message_set.order_by("-time")[0].subject)

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
        self.assertTrue("Last Call" in draft.message_set.order_by("-time")[0].subject)

class RequestPublicationTestCase(django.test.TestCase):
    fixtures = ['names']

    def test_request_publication(self):
        draft = make_test_data()
        draft.stream = StreamName.objects.get(slug="iab")
        draft.group = Group.objects.get(acronym="iab")
        draft.intended_std_level = IntendedStdLevelName.objects.get(slug="inf")
        draft.save()
        draft.set_state(State.objects.get(type="draft-stream-iab", slug="approved"))

        url = urlreverse('doc_request_publication', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "iabchair", url)

        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        subject = q('input#id_subject')[0].get("value")
        self.assertTrue("Document Action" in subject)
        body = q('.request-publication #id_body').text()
        self.assertTrue("Informational" in body)
        self.assertTrue("IAB" in body)

        # approve
        mailbox_before = len(outbox)

        r = self.client.post(url, dict(subject=subject, body=body))
        self.assertEquals(r.status_code, 302)

        draft = Document.objects.get(name=draft.name)
        self.assertEquals(draft.get_state_slug("draft-stream-iab"), "rfc-edit")
        self.assertEquals(len(outbox), mailbox_before + 2)
        self.assertTrue("Document Action" in outbox[-2]['Subject'])
        self.assertTrue("Document Action" in draft.message_set.order_by("-time")[0].subject)
        # the IANA copy
        self.assertTrue("Document Action" in outbox[-1]['Subject'])

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
        
        settings.INTERNET_DRAFT_PATH = self.id_dir
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

        Meeting.objects.create(number="123",
                               type=MeetingTypeName.objects.get(slug="ietf"),
                               date=date.today())
        second_cut_off = Meeting.get_second_cut_off()
        ietf_monday = Meeting.get_ietf_monday()

        self.assertTrue(not in_id_expire_freeze(datetime.datetime.combine(second_cut_off - datetime.timedelta(days=7), time(0, 0, 0))))
        self.assertTrue(not in_id_expire_freeze(datetime.datetime.combine(second_cut_off, time(0, 0, 0))))
        self.assertTrue(in_id_expire_freeze(datetime.datetime.combine(second_cut_off + datetime.timedelta(days=7), time(0, 0, 0))))
        self.assertTrue(in_id_expire_freeze(datetime.datetime.combine(ietf_monday - datetime.timedelta(days=1), time(0, 0, 0))))
        self.assertTrue(not in_id_expire_freeze(datetime.datetime.combine(ietf_monday, time(0, 0, 0))))
        
    def test_warn_expirable_ids(self):
        from ietf.idrfc.expire import get_soon_to_expire_ids, send_expire_warning_for_id

        draft = make_test_data()

        self.assertEquals(len(list(get_soon_to_expire_ids(14))), 0)

        # hack into expirable state
        draft.unset_state("draft-iesg")
        draft.expires = datetime.datetime.now() + datetime.timedelta(days=10)
        draft.save()

        self.assertEquals(len(list(get_soon_to_expire_ids(14))), 1)
        
        # test send warning
        mailbox_before = len(outbox)

        send_expire_warning_for_id(draft)

        self.assertEquals(len(outbox), mailbox_before + 1)
        self.assertTrue("aread@ietf.org" in str(outbox[-1])) # author
        self.assertTrue("wgchairman@ietf.org" in str(outbox[-1]))
        
    def test_expire_ids(self):
        from ietf.idrfc.expire import get_expired_ids, send_expire_notice_for_id, expire_id

        draft = make_test_data()
        
        self.assertEquals(len(list(get_expired_ids())), 0)
        
        # hack into expirable state
        draft.unset_state("draft-iesg")
        draft.expires = datetime.datetime.now()
        draft.save()

        self.assertEquals(len(list(get_expired_ids())), 1)

        draft.set_state(State.objects.get(type="draft-iesg", slug="watching"))

        self.assertEquals(len(list(get_expired_ids())), 1)

        draft.set_state(State.objects.get(type="draft-iesg", slug="iesg-eva"))

        self.assertEquals(len(list(get_expired_ids())), 0)
        
        # test notice
        mailbox_before = len(outbox)

        send_expire_notice_for_id(draft)

        self.assertEquals(len(outbox), mailbox_before + 1)
        self.assertTrue("expired" in outbox[-1]["Subject"])

        # test expiry
        txt = "%s-%s.txt" % (draft.name, draft.rev)
        self.write_id_file(txt, 5000)

        expire_id(draft)

        draft = Document.objects.get(name=draft.name)
        self.assertEquals(draft.get_state_slug(), "expired")
        self.assertEquals(draft.get_state_slug("draft-iesg"), "dead")
        self.assertTrue(draft.latest_event(type="expired_document"))
        self.assertTrue(not os.path.exists(os.path.join(self.id_dir, txt)))
        self.assertTrue(os.path.exists(os.path.join(self.archive_dir, txt)))

    def test_clean_up_id_files(self):
        draft = make_test_data()
        
        from ietf.idrfc.expire import clean_up_id_files

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
        draft.expires = datetime.datetime.now() - datetime.timedelta(days=1)
        draft.save()

        e = DocEvent()
        e.doc = draft
        e.by = Person.objects.get(name="(System)")
        e.type = "expired_document"
        e.text = "Document has expired"
        e.time = draft.expires
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

class IndividualInfoFormsTestCase(django.test.TestCase):

    fixtures = ['names']

    def test_doc_change_stream(self):
        url = urlreverse('doc_change_stream', kwargs=dict(name=self.docname))
        login_testing_unauthorized(self, "secretary", url)

        # get
        r = self.client.get(url)
        self.assertEquals(r.status_code,200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form.change-stream')),1) 

        # shift to ISE stream
        messages_before = len(outbox)
        r = self.client.post(url,dict(stream="ise",comment="7gRMTjBM"))
        self.assertEquals(r.status_code,302)
        self.doc = Document.objects.get(name=self.docname)
        self.assertEquals(self.doc.stream_id,'ise')
        self.assertEquals(len(outbox),messages_before+1)
        self.assertTrue('Stream Change Notice' in outbox[-1]['Subject'])
        self.assertTrue('7gRMTjBM' in str(outbox[-1]))
        self.assertTrue('7gRMTjBM' in self.doc.latest_event(DocEvent,type='added_comment').desc)
        # Would be nice to test that the stream managers were in the To header...

        # shift to an unknown stream (it must be possible to throw a document out of any stream)
        r = self.client.post(url,dict(stream=""))
        self.assertEquals(r.status_code,302)
        self.doc = Document.objects.get(name=self.docname)
        self.assertEquals(self.doc.stream,None)

    def test_doc_change_notify(self):
        url = urlreverse('doc_change_notify', kwargs=dict(name=self.docname))
        login_testing_unauthorized(self, "secretary", url)

        # get
        r = self.client.get(url)
        self.assertEquals(r.status_code,200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form input[name=notify]')),1)

        # Provide a list
        r = self.client.post(url,dict(notify="TJ2APh2P@ietf.org",save_addresses="1"))
        self.assertEquals(r.status_code,302)
        self.doc = Document.objects.get(name=self.docname)
        self.assertEquals(self.doc.notify,'TJ2APh2P@ietf.org')
        
        # Ask the form to regenerate the list
        r = self.client.post(url,dict(regenerate_addresses="1"))
        self.assertEquals(r.status_code,200)
        self.doc = Document.objects.get(name=self.docname)
        # Regenerate does not save!
        self.assertEquals(self.doc.notify,'TJ2APh2P@ietf.org')
        q = PyQuery(r.content)
        self.assertTrue('TJ2Aph2P' not in q('form input[name=notify]')[0].value)

    def test_doc_change_intended_status(self):
        url = urlreverse('doc_change_intended_status', kwargs=dict(name=self.docname))
        login_testing_unauthorized(self, "secretary", url)

        # get
        r = self.client.get(url)
        self.assertEquals(r.status_code,200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form.change-intended-status')),1)

        # don't allow status level to be cleared
        r = self.client.post(url,dict(intended_std_level=""))
        self.assertEquals(r.status_code,200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form ul.errorlist')) > 0)
        
        # change intended status level
        messages_before = len(outbox)
        r = self.client.post(url,dict(intended_std_level="bcp",comment="ZpyQFGmA"))
        self.assertEquals(r.status_code,302)
        self.doc = Document.objects.get(name=self.docname)
        self.assertEquals(self.doc.intended_std_level_id,'bcp')
        self.assertEquals(len(outbox),messages_before+1)
        self.assertTrue('ZpyQFGmA' in str(outbox[-1]))
        self.assertTrue('ZpyQFGmA' in self.doc.latest_event(DocEvent,type='added_comment').desc)
       
    def test_doc_change_telechat_date(self):
        url = urlreverse('doc_change_telechat_date', kwargs=dict(name=self.docname))
        login_testing_unauthorized(self, "secretary", url)

        # get
        r = self.client.get(url)
        self.assertEquals(r.status_code,200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form.telechat-date')),1)

        # set a date
        self.assertFalse(self.doc.latest_event(TelechatDocEvent, "scheduled_for_telechat"))
        telechat_date = TelechatDate.objects.active().order_by('date')[0].date
        r = self.client.post(url,dict(telechat_date=telechat_date.isoformat()))
        self.assertEquals(r.status_code,302)
        self.doc = Document.objects.get(name=self.docname)
        self.assertEquals(self.doc.latest_event(TelechatDocEvent, "scheduled_for_telechat").telechat_date,telechat_date)

        # Take the doc back off any telechat
        r = self.client.post(url,dict(telechat_date=""))
        self.assertEquals(r.status_code, 302)
        self.assertEquals(self.doc.latest_event(TelechatDocEvent, "scheduled_for_telechat").telechat_date,None)
        
    def test_doc_change_iesg_note(self):
        url = urlreverse('doc_change_iesg_note', kwargs=dict(name=self.docname))
        login_testing_unauthorized(self, "secretary", url)

        # get
        r = self.client.get(url)
        self.assertEquals(r.status_code,200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form.edit-iesg-note')),1)

        # No validation code to test

        # post - testing that the munge code exists in note.clean...
        r = self.client.post(url,dict(note='ZpyQFGmA\nZpyQFGmA'))
        self.assertEquals(r.status_code,302)
        self.doc = Document.objects.get(name=self.docname)
        self.assertEquals(self.doc.note,'ZpyQFGmA<br>ZpyQFGmA')
        self.assertTrue('ZpyQFGmA' in self.doc.latest_event(DocEvent,type='added_comment').desc)

    def test_doc_change_ad(self):
        url = urlreverse('doc_change_ad', kwargs=dict(name=self.docname))
        login_testing_unauthorized(self, "secretary", url)

        # get
        r = self.client.get(url)
        self.assertEquals(r.status_code,200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form select[name=ad]')),1)
        
        # change ads
        ad2 = Person.objects.get(name='Ad No2')
        r = self.client.post(url,dict(ad=str(ad2.pk)))
        self.assertEquals(r.status_code,302)
        self.doc = Document.objects.get(name=self.docname)
        self.assertEquals(self.doc.ad,ad2)
        self.assertTrue(self.doc.latest_event(DocEvent,type="added_comment").desc.startswith('Shepherding AD changed'))

    def setUp(self):
        make_test_data()
        self.docname='draft-ietf-mars-test'
        self.doc = Document.objects.get(name=self.docname)
        
