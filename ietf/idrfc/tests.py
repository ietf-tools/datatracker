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
from datetime import date, timedelta

import django.test
from django.core.urlresolvers import reverse as urlreverse

from pyquery import PyQuery

from ietf.idrfc.models import *
from ietf.idtracker.models import *
from ietf.utils.test_utils import SimpleUrlTestCase, RealDatabaseTest, login_testing_unauthorized
from ietf.utils.test_runner import mail_outbox

class IdRfcUrlTestCase(SimpleUrlTestCase):
    def testUrls(self):
        self.doTestUrls(__file__)

class ChangeStateTestCase(django.test.TestCase):
    fixtures = ['base', 'draft']

    def test_change_state(self):
        draft = InternetDraft.objects.get(filename="draft-ietf-mipshop-pfmipv6")
        url = urlreverse('doc_change_state', kwargs=dict(name=draft.filename))
        login_testing_unauthorized(self, "klm", url)

        state = draft.idinternal.cur_state
        substate = draft.idinternal.cur_sub_state
        next_states = IDNextState.objects.filter(cur_state=draft.idinternal.cur_state)

        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form select[name=state]')), 1)
        self.assertEquals(len(q('form select[name=substate]')), 1)

        if next_states:
            self.assertTrue(len(q('.next-states form input[type=hidden]')) > 0)

            
        # faulty post
        r = self.client.post(url,
                             dict(state="123456789", substate="987654531"))
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form ul.errorlist')) > 0)
        draft = InternetDraft.objects.get(filename="draft-ietf-mipshop-pfmipv6")
        self.assertEquals(draft.idinternal.cur_state, state)

        
        # change state
        comments_before = draft.idinternal.comments().count()
        mailbox_before = len(mail_outbox)
        
        r = self.client.post(url,
                             dict(state="12", substate=""))
        self.assertEquals(r.status_code, 302)

        draft = InternetDraft.objects.get(filename="draft-ietf-mipshop-pfmipv6")
        self.assertEquals(draft.idinternal.prev_state, state)
        self.assertEquals(draft.idinternal.prev_sub_state, substate)
        self.assertEquals(draft.idinternal.cur_state.document_state_id, 12)
        self.assertEquals(draft.idinternal.cur_sub_state, None)
        self.assertEquals(draft.idinternal.comments().count(), comments_before + 1)
        self.assertTrue("State changed" in draft.idinternal.comments()[0].comment_text)
        self.assertEquals(len(mail_outbox), mailbox_before + 2)
        self.assertTrue("State Update Notice" in mail_outbox[-2]['Subject'])
        self.assertTrue(draft.filename in mail_outbox[-1]['Subject'])

        
    def test_make_last_call(self):
        draft = InternetDraft.objects.get(filename="draft-ietf-mipshop-pfmipv6")

        self.client.login(remote_user="klm")
        url = urlreverse('doc_change_state', kwargs=dict(name=draft.filename))

        mailbox_before = len(mail_outbox)
        
        self.assertRaises(BallotInfo.DoesNotExist, lambda: draft.idinternal.ballot)
        r = self.client.post(url,
                             dict(state="15", substate=""))
        self.assertContains(r, "Your request to issue the Last Call")

        # last call text
        self.assertTrue("The IESG has received" in draft.idinternal.ballot.last_call_text)
        self.assertTrue(draft.title in draft.idinternal.ballot.last_call_text)
        self.assertTrue(draft.idinternal.get_absolute_url() in draft.idinternal.ballot.last_call_text)

        # approval text
        self.assertTrue("The IESG has approved" in draft.idinternal.ballot.approval_text)
        self.assertTrue(draft.title in draft.idinternal.ballot.approval_text)
        self.assertTrue(draft.idinternal.get_absolute_url() in draft.idinternal.ballot.approval_text)

        # ballot writeup
        self.assertTrue("Technical Summary" in draft.idinternal.ballot.ballot_writeup)

        # mail notice
        self.assertTrue(len(mail_outbox) > mailbox_before)
        self.assertTrue("Last Call:" in mail_outbox[-1]['Subject'])

        # comment
        self.assertTrue("Last Call was requested" in draft.idinternal.comments()[0].comment_text)

class EditInfoTestCase(django.test.TestCase):
    fixtures = ['base', 'draft']

    def test_edit_info(self):
        draft = InternetDraft.objects.get(filename="draft-ietf-mipshop-pfmipv6")
        url = urlreverse('doc_edit_info', kwargs=dict(name=draft.filename))
        login_testing_unauthorized(self, "klm", url)

        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form select[name=intended_status]')), 1)
        self.assertEquals(len(q('form input[name=via_rfc_editor]')), 1)

        prev_job_owner = draft.idinternal.job_owner
        # faulty post
        r = self.client.post(url, dict(job_owner="123456789"))
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form ul.errorlist')) > 0)
        draft = InternetDraft.objects.get(filename="draft-ietf-mipshop-pfmipv6")
        self.assertEquals(draft.idinternal.job_owner, prev_job_owner)

        # edit info
        comments_before = draft.idinternal.comments().count()
        mailbox_before = len(mail_outbox)
        draft.group = Acronym.objects.get(acronym_id=Acronym.INDIVIDUAL_SUBMITTER)
        draft.save()
        new_job_owner = IESGLogin.objects.exclude(id__in=[IESGLogin.objects.get(login_name="klm").id, draft.idinternal.job_owner_id])[0]
        new_area = Area.active_areas()[0]

        r = self.client.post(url,
                             dict(intended_status=str(draft.intended_status_id),
                                  status_date=str(date.today() + timedelta(2)),
                                  area_acronym=str(new_area.area_acronym_id),
                                  via_rfc_editor="1",
                                  job_owner=new_job_owner.id,
                                  state_change_notice_to="test@example.com",
                                  note="",
                                  telechat_date="",
                                  ))
        self.assertEquals(r.status_code, 302)

        draft = InternetDraft.objects.get(filename="draft-ietf-mipshop-pfmipv6")
        self.assertEquals(draft.idinternal.area_acronym, new_area)
        self.assertTrue(draft.idinternal.via_rfc_editor)
        self.assertEquals(draft.idinternal.job_owner, new_job_owner)
        self.assertEquals(draft.idinternal.note, "")
        self.assertTrue(not draft.idinternal.agenda)
        self.assertEquals(draft.idinternal.comments().count(), comments_before + 3)
        self.assertEquals(len(mail_outbox), mailbox_before + 1)
        self.assertTrue(draft.filename in mail_outbox[-1]['Subject'])

    def test_add_draft(self):
        draft = InternetDraft.objects.get(filename="draft-ah-rfc2141bis-urn")
        url = urlreverse('doc_edit_info', kwargs=dict(name=draft.filename))
        login_testing_unauthorized(self, "klm", url)

        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form select[name=intended_status]')), 1)
        self.assertEquals(len(q('form input[name=via_rfc_editor]')), 1)
        self.assertTrue('@' in q('form input[name=state_change_notice_to]')[0].get('value'))

        # add
        mailbox_before = len(mail_outbox)

        job_owner = IESGLogin.objects.filter(user_level=1)[0]
        area = Area.active_areas()[0]

        r = self.client.post(url,
                             dict(intended_status=str(draft.intended_status_id),
                                  status_date=str(date.today() + timedelta(2)),
                                  area_acronym=str(area.area_acronym_id),
                                  via_rfc_editor="1",
                                  job_owner=job_owner.id,
                                  state_change_notice_to="test@example.com",
                                  note="This is a note",
                                  telechat_date="",
                                  ))
        self.assertEquals(r.status_code, 302)

        draft = InternetDraft.objects.get(filename="draft-ah-rfc2141bis-urn")
        self.assertEquals(draft.idinternal.area_acronym, area)
        self.assertTrue(draft.idinternal.via_rfc_editor)
        self.assertEquals(draft.idinternal.job_owner, job_owner)
        self.assertEquals(draft.idinternal.note, "This is a note")
        self.assertTrue(not draft.idinternal.agenda)
        self.assertEquals(draft.idinternal.comments().count(), 3)
        self.assertTrue("Draft added" in draft.idinternal.comments()[0].comment_text)
        self.assertEquals(len(mail_outbox), mailbox_before)


class ResurrectTestCase(django.test.TestCase):
    fixtures = ['base', 'draft']

    def test_request_resurrect(self):
        draft = InternetDraft.objects.get(filename="draft-ietf-mip6-cn-ipsec")
        self.assertEquals(draft.status.status, "Expired")
        self.assertTrue(not draft.idinternal.resurrect_requested_by)
        
        url = urlreverse('doc_request_resurrect', kwargs=dict(name=draft.filename))
        login_as = "rhousley"
        
        login_testing_unauthorized(self, login_as, url)

        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form input[type=submit]')), 1)


        # request resurrect
        comments_before = draft.idinternal.comments().count()
        mailbox_before = len(mail_outbox)
        
        r = self.client.post(url, dict())
        self.assertEquals(r.status_code, 302)

        draft = InternetDraft.objects.get(filename="draft-ietf-mip6-cn-ipsec")
        self.assertEquals(draft.idinternal.resurrect_requested_by, IESGLogin.objects.get(login_name=login_as))
        self.assertEquals(draft.idinternal.comments().count(), comments_before + 1)
        self.assertTrue("Resurrection" in draft.idinternal.comments()[0].comment_text)
        self.assertEquals(len(mail_outbox), mailbox_before + 1)
        self.assertTrue("Resurrection" in mail_outbox[-1]['Subject'])

    def test_resurrect(self):
        draft = InternetDraft.objects.get(filename="draft-ietf-mip6-cn-ipsec")
        self.assertEquals(draft.status.status, "Expired")
        draft.idinternal.resurrect_requested_by = IESGLogin.objects.get(login_name="rhousley")
        draft.idinternal.save()
        
        url = urlreverse('doc_resurrect', kwargs=dict(name=draft.filename))
        
        login_testing_unauthorized(self, "klm", url)

        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form input[type=submit]')), 1)

        # request resurrect
        comments_before = draft.idinternal.comments().count()
        mailbox_before = len(mail_outbox)
        
        r = self.client.post(url, dict())
        self.assertEquals(r.status_code, 302)

        draft = InternetDraft.objects.get(filename="draft-ietf-mip6-cn-ipsec")
        self.assertEquals(draft.idinternal.resurrect_requested_by, None)
        self.assertEquals(draft.idinternal.comments().count(), comments_before + 1)
        self.assertTrue("completed" in draft.idinternal.comments()[0].comment_text)
        self.assertEquals(draft.status.status, "Active")
        self.assertEquals(len(mail_outbox), mailbox_before + 1)
        
class AddCommentTestCase(django.test.TestCase):
    fixtures = ['base', 'draft']

    def test_add_comment(self):
        draft = InternetDraft.objects.get(filename="draft-ietf-mipshop-pfmipv6")
        url = urlreverse('doc_add_comment', kwargs=dict(name=draft.filename))
        login_testing_unauthorized(self, "klm", url)

        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form textarea[name=comment]')), 1)

        # request resurrect
        comments_before = draft.idinternal.comments().count()
        mailbox_before = len(mail_outbox)
        
        r = self.client.post(url, dict(comment="This is a test."))
        self.assertEquals(r.status_code, 302)

        self.assertEquals(draft.idinternal.comments().count(), comments_before + 1)
        self.assertTrue("This is a test." in draft.idinternal.comments()[0].comment_text)
        self.assertEquals(len(mail_outbox), mailbox_before + 1)
        self.assertTrue("updated" in mail_outbox[-1]['Subject'])
        self.assertTrue(draft.filename in mail_outbox[-1]['Subject'])

class EditPositionTestCase(django.test.TestCase):
    fixtures = ['base', 'draft', 'ballot']

    def test_edit_position(self):
        draft = InternetDraft.objects.get(filename="draft-ietf-mipshop-pfmipv6")
        url = urlreverse('doc_edit_position', kwargs=dict(name=draft.filename))
        login_testing_unauthorized(self, "rhousley", url)

        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form input[name=position]')) > 0)
        self.assertEquals(len(q('form textarea[name=comment_text]')), 1)

        # vote
        comments_before = draft.idinternal.comments().count()
        self.assertTrue(not Position.objects.filter(ballot=draft.idinternal.ballot, ad__login_name="rhousley"))
        
        r = self.client.post(url, dict(position="discuss",
                                       discuss_text="This is a discussion test.",
                                       comment_text="This is a test."))
        self.assertEquals(r.status_code, 302)

        pos = Position.objects.get(ballot=draft.idinternal.ballot, ad__login_name="rhousley")
        self.assertTrue("This is a discussion test." in IESGDiscuss.objects.get(ballot=draft.idinternal.ballot, ad__login_name="rhousley").text)
        self.assertTrue("This is a test." in IESGComment.objects.get(ballot=draft.idinternal.ballot, ad__login_name="rhousley").text)
        self.assertTrue(pos.discuss)
        self.assertTrue(not (pos.yes or pos.noobj or pos.abstain or pos.recuse))
        
        self.assertEquals(draft.idinternal.comments().count(), comments_before + 3)
        self.assertTrue("New position" in draft.idinternal.comments()[2].comment_text)

        # recast vote
        comments_before = draft.idinternal.comments().count()
        r = self.client.post(url, dict(position="noobj"))
        self.assertEquals(r.status_code, 302)

        pos = Position.objects.filter(ballot=draft.idinternal.ballot, ad__login_name="rhousley")[0]
        self.assertTrue(pos.noobj)
        self.assertTrue(not (pos.yes or pos.abstain or pos.recuse))
        self.assertTrue(pos.discuss == -1)
        self.assertEquals(draft.idinternal.comments().count(), comments_before + 1)
        self.assertTrue("Position" in draft.idinternal.comments()[0].comment_text)

    def test_edit_position_as_secretary(self):
        draft = InternetDraft.objects.get(filename="draft-ietf-mipshop-pfmipv6")
        url = urlreverse('doc_edit_position', kwargs=dict(name=draft.filename))
        url += "?ad=rhousley"
        login_testing_unauthorized(self, "klm", url)

        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form input[name=position]')) > 0)

        # vote for rhousley
        comments_before = draft.idinternal.comments().count()
        self.assertTrue(not Position.objects.filter(ballot=draft.idinternal.ballot, ad__login_name="rhousley"))
        
        r = self.client.post(url, dict(position="discuss"))
        self.assertEquals(r.status_code, 302)

        pos = Position.objects.get(ballot=draft.idinternal.ballot, ad__login_name="rhousley")
        self.assertTrue(pos.discuss)
        self.assertTrue(not (pos.yes or pos.noobj or pos.abstain or pos.recuse))

        
    def test_send_ballot_comment(self):
        draft = InternetDraft.objects.get(filename="draft-ietf-mipshop-pfmipv6")
        url = urlreverse('doc_send_ballot_comment', kwargs=dict(name=draft.filename))
        login_as = "rhousley"
        login_testing_unauthorized(self, login_as, url)

        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form input[name="cc"]')) > 0)

        # send
        mailbox_before = len(mail_outbox)
        IESGComment.objects.create(ballot=draft.idinternal.ballot,
                                   ad=IESGLogin.objects.get(login_name=login_as),
                                   text="Test!", date=date.today(),
                                   revision=draft.revision_display(), active=1)
        
        r = self.client.post(url, dict(cc="test@example.com", cc_state_change="1"))
        self.assertEquals(r.status_code, 302)

        self.assertEquals(len(mail_outbox), mailbox_before + 1)
        self.assertTrue("COMMENT" in mail_outbox[-1]['Subject'])
        
        
class DeferBallotTestCase(django.test.TestCase):
    fixtures = ['base', 'draft', 'ballot']

    def test_defer_ballot(self):
        draft = InternetDraft.objects.get(filename="draft-ietf-mipshop-pfmipv6")
        url = urlreverse('doc_defer_ballot', kwargs=dict(name=draft.filename))
        login_testing_unauthorized(self, "rhousley", url)

        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)

        # defer
        self.assertTrue(not draft.idinternal.ballot.defer)
        mailbox_before = len(mail_outbox)
        
        r = self.client.post(url, dict())
        self.assertEquals(r.status_code, 302)

        draft = InternetDraft.objects.get(filename="draft-ietf-mipshop-pfmipv6")
        self.assertTrue(draft.idinternal.ballot.defer)
        self.assertTrue(draft.idinternal.cur_state_id == IDState.IESG_EVALUATION_DEFER)
        
        self.assertEquals(len(mail_outbox), mailbox_before + 2)
        self.assertTrue("Deferred" in mail_outbox[-2]['Subject'])
        self.assertTrue(draft.file_tag() in mail_outbox[-2]['Subject'])

    def test_undefer_ballot(self):
        draft = InternetDraft.objects.get(filename="draft-ietf-mipshop-pfmipv6")
        url = urlreverse('doc_undefer_ballot', kwargs=dict(name=draft.filename))
        login_testing_unauthorized(self, "rhousley", url)

        draft.idinternal.ballot.defer = True
        draft.idinternal.ballot.save()
        
        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)

        # undefer
        self.assertTrue(draft.idinternal.ballot.defer)
        
        r = self.client.post(url, dict())
        self.assertEquals(r.status_code, 302)

        draft = InternetDraft.objects.get(filename="draft-ietf-mipshop-pfmipv6")
        self.assertTrue(not draft.idinternal.ballot.defer)
        self.assertEquals(draft.idinternal.cur_state_id, IDState.IESG_EVALUATION)

class BallotWriteupsTestCase(django.test.TestCase):
    fixtures = ['base', 'draft', 'ballot']

    def test_edit_last_call_text(self):
        draft = InternetDraft.objects.get(filename="draft-ietf-mipshop-pfmipv6")
        url = urlreverse('doc_ballot_writeups', kwargs=dict(name=draft.filename))
        login_testing_unauthorized(self, "klm", url)

        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('textarea[name=last_call_text]')), 1)
        self.assertEquals(len(q('input[type=submit][value*="Save Last Call"]')), 1)

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
        draft = InternetDraft.objects.get(filename="draft-ietf-mipshop-pfmipv6")
        self.assertTrue("This is a simple test" in draft.idinternal.ballot.last_call_text)

        # test regenerate
        r = self.client.post(url, dict(
                last_call_text="This is a simple test.",
                regenerate_last_call_text="1"))
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        draft = InternetDraft.objects.get(filename="draft-ietf-mipshop-pfmipv6")
        self.assertTrue("Subject: Last Call" in draft.idinternal.ballot.last_call_text)

    def test_request_last_call(self):
        draft = InternetDraft.objects.get(filename="draft-ietf-mipshop-pfmipv6")
        url = urlreverse('doc_ballot_writeups', kwargs=dict(name=draft.filename))
        login_testing_unauthorized(self, "klm", url)

        mailbox_before = len(mail_outbox)
        
        r = self.client.post(url, dict(
                last_call_text=draft.idinternal.ballot.last_call_text,
                send_last_call_request="1"))
        draft = InternetDraft.objects.get(filename="draft-ietf-mipshop-pfmipv6")
        self.assertEquals(draft.idinternal.cur_state_id, IDState.LAST_CALL_REQUESTED)

        self.assertEquals(len(mail_outbox), mailbox_before + 3)

        self.assertTrue("Last Call" in mail_outbox[-1]['Subject'])

    def test_edit_ballot_writeup(self):
        draft = InternetDraft.objects.get(filename="draft-ietf-mipshop-pfmipv6")
        url = urlreverse('doc_ballot_writeups', kwargs=dict(name=draft.filename))
        login_testing_unauthorized(self, "klm", url)

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
        draft = InternetDraft.objects.get(filename="draft-ietf-mipshop-pfmipv6")
        self.assertTrue("This is a simple test" in draft.idinternal.ballot.ballot_writeup)

    def test_issue_ballot(self):
        draft = InternetDraft.objects.get(filename="draft-ietf-mipshop-pfmipv6")
        url = urlreverse('doc_ballot_writeups', kwargs=dict(name=draft.filename))
        login_testing_unauthorized(self, "rhousley", url)

        draft.idinternal.ballot.ballot_issued = False
        draft.idinternal.ballot.save()
        active = IESGLogin.objects.filter(user_level=1)
        Position.objects.create(ad=active[0], yes=1, noobj=0, discuss=0, abstain=0, recuse=0, ballot=draft.idinternal.ballot)
        Position.objects.create(ad=active[1], yes=0, noobj=1, discuss=0, abstain=0, recuse=0, ballot=draft.idinternal.ballot)
        Position.objects.create(ad=active[2], yes=0, noobj=1, discuss=-1, abstain=0, recuse=0, ballot=draft.idinternal.ballot)
        Position.objects.create(ad=active[3], yes=0, noobj=0, discuss=1, abstain=0, recuse=0, ballot=draft.idinternal.ballot)        
        Position.objects.create(ad=active[4], yes=0, noobj=0, discuss=0, abstain=1, recuse=0, ballot=draft.idinternal.ballot)
        Position.objects.create(ad=active[5], yes=0, noobj=0, discuss=0, abstain=0, recuse=1, ballot=draft.idinternal.ballot)
        inactive = IESGLogin.objects.filter(user_level=2)
        Position.objects.create(ad=inactive[0], yes=1, noobj=0, discuss=0, abstain=0, recuse=0, ballot=draft.idinternal.ballot)
        IESGDiscuss.objects.create(ad=active[1], active=True, date=datetime.date.today(), text="test " * 20, ballot=draft.idinternal.ballot)
        IESGComment.objects.create(ad=active[2], active=True, date=datetime.date.today(), text="test " * 20, ballot=draft.idinternal.ballot)        
        IESGDiscuss.objects.create(ad=active[3], active=True, date=datetime.date.today(), text="test " * 20, ballot=draft.idinternal.ballot)
        IESGComment.objects.create(ad=active[3], active=True, date=datetime.date.today(), text="test " * 20, ballot=draft.idinternal.ballot)

        mailbox_before = len(mail_outbox)
        
        r = self.client.post(url, dict(
                ballot_writeup=draft.idinternal.ballot.ballot_writeup,
                approval_text=draft.idinternal.ballot.approval_text,
                issue_ballot="1"))
        self.assertEquals(r.status_code, 200)
        draft = InternetDraft.objects.get(filename="draft-ietf-mipshop-pfmipv6")

        self.assertTrue(draft.idinternal.ballot.ballot_issued)
        self.assertEquals(len(mail_outbox), mailbox_before + 2)
        self.assertTrue("Evaluation:" in mail_outbox[-2]['Subject'])


    def test_edit_approval_text(self):
        draft = InternetDraft.objects.get(filename="draft-ietf-mipshop-pfmipv6")
        url = urlreverse('doc_ballot_writeups', kwargs=dict(name=draft.filename))
        login_testing_unauthorized(self, "klm", url)

        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('textarea[name=approval_text]')), 1)
        self.assertEquals(len(q('input[type=submit][value*="Save Approval"]')), 1)

        # subject error
        r = self.client.post(url, dict(
                last_call_text="Subject: test\r\nhello\r\n\r\n",
                save_last_call_text="1"))
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('ul.errorlist')) > 0)

        # save
        r = self.client.post(url, dict(
                approval_text="This is a simple test.",
                save_approval_text="1"))
        self.assertEquals(r.status_code, 200)
        draft = InternetDraft.objects.get(filename="draft-ietf-mipshop-pfmipv6")
        self.assertTrue("This is a simple test" in draft.idinternal.ballot.approval_text)

        # test regenerate
        r = self.client.post(url, dict(
                approval_text="This is a simple test.",
                regenerate_approval_text="1"))
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        draft = InternetDraft.objects.get(filename="draft-ietf-mipshop-pfmipv6")
        self.assertTrue("Subject: Protocol Action" in draft.idinternal.ballot.approval_text)
        
class ApproveBallotTestCase(django.test.TestCase):
    fixtures = ['base', 'draft', 'ballot']

    def test_approve_ballot(self):
        draft = InternetDraft.objects.get(filename="draft-ietf-mipshop-pfmipv6")
        url = urlreverse('doc_approve_ballot', kwargs=dict(name=draft.filename))
        login_testing_unauthorized(self, "klm", url)

        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue("Send out the announcement" in q('input[type=submit]')[0].get('value'))
        self.assertEquals(len(q('pre')), 1)

        # approve
        mailbox_before = len(mail_outbox)
        
        r = self.client.post(url, dict())
        self.assertEquals(r.status_code, 302)

        draft = InternetDraft.objects.get(filename="draft-ietf-mipshop-pfmipv6")
        self.assertEquals(draft.idinternal.cur_state_id, IDState.APPROVED_ANNOUNCEMENT_SENT)
        
        self.assertEquals(len(mail_outbox), mailbox_before + 4)

        self.assertTrue("Protocol Action" in mail_outbox[-2]['Subject'])
        # the IANA copy
        self.assertTrue("Protocol Action" in mail_outbox[-1]['Subject'])

class MakeLastCallTestCase(django.test.TestCase):
    fixtures = ['base', 'draft', 'ballot']

    def test_make_last_call(self):
        draft = InternetDraft.objects.get(filename="draft-ietf-mipshop-pfmipv6")
        url = urlreverse('doc_make_last_call', kwargs=dict(name=draft.filename))
        login_testing_unauthorized(self, "klm", url)

        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('input[name=last_call_sent_date]')), 1)

        # make last call
        mailbox_before = len(mail_outbox)
        
        r = self.client.post(url,
                             dict(last_call_sent_date=q('input[name=last_call_sent_date]')[0].get("value"),
                                  last_call_expiration_date=q('input[name=last_call_expiration_date]')[0].get("value")
                                  ))
        self.assertEquals(r.status_code, 302)

        draft = InternetDraft.objects.get(filename="draft-ietf-mipshop-pfmipv6")
        self.assertEquals(draft.idinternal.cur_state_id, IDState.IN_LAST_CALL)
        
        self.assertEquals(len(mail_outbox), mailbox_before + 4)

        self.assertTrue("Last Call" in mail_outbox[-4]['Subject'])
        # the IANA copy
        self.assertTrue("Last Call" in mail_outbox[-3]['Subject'])

        
        
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

