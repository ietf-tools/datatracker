import unittest
import StringIO
import os, shutil
from datetime import date, timedelta, time

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
from ietf.utils.test_utils import login_testing_unauthorized
from ietf.utils.test_data import make_test_data
from ietf.utils.mail import outbox
from ietf.utils import TestCase

class EditPositionTestCase(TestCase):
    # See ietf.utils.test_utils.TestCase for the use of perma_fixtures vs. fixtures
    perma_fixtures = ['names']

    def test_edit_position(self):
        draft = make_test_data()
        url = urlreverse('ietf.doc.views_ballot.edit_position', kwargs=dict(name=draft.name,
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
        url = urlreverse('ietf.doc.views_ballot.edit_position', kwargs=dict(name=draft.name,
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
        url = urlreverse('ietf.doc.views_ballot.edit_position', kwargs=dict(name=draft.name,
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

        
class DeferBallotTestCase(TestCase):
    # See ietf.utils.test_utils.TestCase for the use of perma_fixtures vs. fixtures
    perma_fixtures = ['names']

    def test_defer_ballot(self):
        draft = make_test_data()
        draft.set_state(State.objects.get(used=True, type="draft-iesg", slug="iesg-eva"))

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
        draft.set_state(State.objects.get(used=True, type="draft-iesg", slug="defer"))

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

class BallotWriteupsTestCase(TestCase):
    # See ietf.utils.test_utils.TestCase for the use of perma_fixtures vs. fixtures
    perma_fixtures = ['names']

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
        draft.set_state(State.objects.get(used=True, type="draft-iana-review", slug="not-ok"))
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
        draft.set_state(State.objects.get(used=True, type="draft-iesg", slug="nopubadw"))

        r = self.client.post(url, dict(regenerate_approval_text="1"))
        self.assertEquals(r.status_code, 200)
        draft = Document.objects.get(name=draft.name)
        self.assertTrue("NOT be published" in draft.latest_event(WriteupDocEvent, type="changed_ballot_approval_text").text)

        # test regenerate when it's a conflict review
        draft.group = Group.objects.get(type="individ")
        draft.stream_id = "irtf"
        draft.save()
        draft.set_state(State.objects.get(used=True, type="draft-iesg", slug="iesg-eva"))

        r = self.client.post(url, dict(regenerate_approval_text="1"))
        self.assertEquals(r.status_code, 200)
        draft = Document.objects.get(name=draft.name)
        self.assertTrue("Subject: Results of IETF-conflict review" in draft.latest_event(WriteupDocEvent, type="changed_ballot_approval_text").text)
        
class ApproveBallotTestCase(TestCase):
    # See ietf.utils.test_utils.TestCase for the use of perma_fixtures vs. fixtures
    perma_fixtures = ['names']

    def test_approve_ballot(self):
        draft = make_test_data()
        draft.set_state(State.objects.get(used=True, type="draft-iesg", slug="iesg-eva")) # make sure it's approvable

        url = urlreverse('doc_approve_ballot', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "secretary", url)

        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue("send out the announcement" in q('.actions input[type=submit]')[0].get('value').lower())
        self.assertEquals(len(q('.announcement pre:contains("Subject: Protocol Action")')), 1)

        # approve
        mailbox_before = len(outbox)

        r = self.client.post(url, dict(skiprfceditorpost="1"))
        self.assertEquals(r.status_code, 302)

        draft = Document.objects.get(name=draft.name)
        self.assertEquals(draft.get_state_slug("draft-iesg"), "ann")
        self.assertEquals(len(outbox), mailbox_before + 4)
        self.assertTrue("Protocol Action" in outbox[-2]['Subject'])
        # the IANA copy
        self.assertTrue("Protocol Action" in outbox[-1]['Subject'])
        self.assertTrue(not outbox[-1]['CC'])
        self.assertTrue("Protocol Action" in draft.message_set.order_by("-time")[0].subject)

    def test_disapprove_ballot(self):
        draft = make_test_data()
        draft.set_state(State.objects.get(used=True, type="draft-iesg", slug="nopubadw"))

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

class MakeLastCallTestCase(TestCase):
    # See ietf.utils.test_utils.TestCase for the use of perma_fixtures vs. fixtures
    perma_fixtures = ['names']

    def test_make_last_call(self):
        draft = make_test_data()
        draft.set_state(State.objects.get(used=True, type="draft-iesg", slug="lc-req"))

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

