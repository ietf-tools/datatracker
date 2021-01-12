# Copyright The IETF Trust 2016-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime, os, shutil
import io
import tarfile, tempfile, mailbox
import email.mime.multipart, email.mime.text, email.utils

from mock import patch
from requests import Response


from django.apps import apps
from django.urls import reverse as urlreverse
from django.conf import settings

from pyquery import PyQuery

import debug                            # pyflakes:ignore

import ietf.review.mailarch

from ietf.doc.factories import ( NewRevisionDocEventFactory, IndividualDraftFactory, WgDraftFactory,
                            WgRfcFactory, ReviewFactory, DocumentFactory)
from ietf.doc.models import ( Document, DocumentAuthor, RelatedDocument, DocEvent, ReviewRequestDocEvent,
                            ReviewAssignmentDocEvent, )
from ietf.group.factories import RoleFactory, ReviewTeamFactory
from ietf.group.models import Group
from ietf.message.models import Message
from ietf.name.models import ReviewResultName, ReviewRequestStateName, ReviewAssignmentStateName, ReviewTypeName
from ietf.person.factories import PersonFactory
from ietf.person.models import Email, Person
from ietf.review.factories import ReviewRequestFactory, ReviewAssignmentFactory
from ietf.review.models import ReviewRequest, ReviewerSettings, ReviewWish, NextReviewerInTeam
from ietf.review.policies import get_reviewer_queue_policy
from ietf.utils.mail import outbox, empty_outbox, parseaddr, on_behalf_of, get_payload_text
from ietf.utils.test_utils import login_testing_unauthorized, reload_db_objects
from ietf.utils.test_utils import TestCase
from ietf.utils.text import strip_prefix, xslugify

class ReviewTests(TestCase):
    def setUp(self):
        self.review_dir = self.tempdir('review')
        self.old_document_path_pattern = settings.DOCUMENT_PATH_PATTERN
        settings.DOCUMENT_PATH_PATTERN = self.review_dir + "/{doc.type_id}/"

        self.review_subdir = os.path.join(self.review_dir, "review")
        if not os.path.exists(self.review_subdir):
            os.mkdir(self.review_subdir)
        
    def tearDown(self):
        shutil.rmtree(self.review_dir)
        settings.DOCUMENT_PATH_PATTERN = self.old_document_path_pattern

    def test_request_review(self):
        doc = WgDraftFactory(group__acronym='mars',rev='01')
        NewRevisionDocEventFactory(doc=doc,rev='01')
        RoleFactory(name_id='chair',person__user__username='marschairman',group=doc.group)
        review_team = ReviewTeamFactory(acronym="reviewteam", name="Review Team", type_id="review", list_email="reviewteam@ietf.org", parent=Group.objects.get(acronym="farfut"))
        review_team3 = ReviewTeamFactory(acronym="reviewteam3", name="Review Team3", type_id="review", list_email="reviewteam3@ietf.org", parent=Group.objects.get(acronym="farfut"))
        rev_role = RoleFactory(group=review_team,person__user__username='reviewer',person__user__email='reviewer@example.com',name_id='reviewer')
        RoleFactory(group=review_team3,person=rev_role.person,name_id='reviewer')
        RoleFactory(group=review_team,person__user__username='reviewsecretary',person__user__email='reviewsecretary@example.com',name_id='secr')
        RoleFactory(group=review_team3,person__user__username='reviewsecretary3',person__user__email='reviewsecretary3@example.com',name_id='secr')

        req = ReviewRequestFactory(doc=doc,team=review_team,type_id='early',state_id='assigned',requested_by=rev_role.person,deadline=datetime.datetime.now()+datetime.timedelta(days=20))
        ReviewAssignmentFactory(review_request = req, reviewer = rev_role.person.email_set.first(), state_id='accepted')

        url = urlreverse('ietf.doc.views_review.request_review', kwargs={ "name": doc.name })
        login_testing_unauthorized(self, "ad", url)

        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        deadline = datetime.date.today() + datetime.timedelta(days=10)

        empty_outbox()

        # post request
        r = self.client.post(url, {
            "type": "early",
            "team": [review_team.pk,review_team3.pk],
            "deadline": deadline.isoformat(),
            "requested_rev": "01",
            "requested_by": Person.objects.get(user__username="ad").pk,
            "comment": "gZT2iiYqYLKiQHvsgWCcVLdH"
        })
        self.assertEqual(r.status_code, 302)

        qs = ReviewRequest.objects.filter(doc=doc, state="requested")
        self.assertEqual(qs.count(),2)
        self.assertEqual(set(qs.values_list('team__acronym',flat=True)),set(['reviewteam','reviewteam3']))
        for req in qs:
            self.assertEqual(req.deadline, deadline)
            self.assertEqual(req.requested_rev, "01")
            self.assertEqual(doc.latest_event().type, "requested_review")
            self.assertEqual(req.comment, "gZT2iiYqYLKiQHvsgWCcVLdH")

        self.assertEqual(len(outbox),2)
        self.assertTrue('reviewteam Early' in outbox[0]['Subject'])
        self.assertTrue('reviewsecretary@' in outbox[0]['To'])
        self.assertTrue('reviewteam3 Early' in outbox[1]['Subject'])
        if not 'reviewsecretary3@' in outbox[1]['To']:
            print(outbox[1].as_string())
        self.assertTrue('reviewsecretary3@' in outbox[1]['To'])

        # set the reviewteamsetting for the secretary email alias, then do the post again
        m = apps.get_model('review', 'ReviewTeamSettings')
        for row in m.objects.all():
            if row.group.upcase_acronym == review_team3.upcase_acronym:
               row.secr_mail_alias = 'reviewsecretary3-alias@example.com'
               row.save(update_fields=['secr_mail_alias'])

        r = self.client.post(url, {
            "type": "early",
            "team": [review_team.pk,review_team3.pk],
            "deadline": deadline.isoformat(),
            "requested_rev": "01",
            "requested_by": Person.objects.get(user__username="ad").pk,
            "comment": "gZT2iiYqYLKiQHvsgWCcVLdH"
        })
        self.assertEqual(r.status_code, 302)

        self.assertEqual(len(outbox),4)
        self.assertTrue('reviewsecretary@' in outbox[2]['To'])
        self.assertTrue('reviewsecretary3-alias@' in outbox[3]['To'])

    def test_request_review_of_rfc(self):
        doc = WgRfcFactory()

        url = urlreverse('ietf.doc.views_review.request_review', kwargs={ "name": doc.name })
        login_testing_unauthorized(self, "ad", url)

        # get should fail
        r = self.client.get(url)
        self.assertEqual(r.status_code, 403)

    def test_doc_page(self):

        doc = WgDraftFactory(group__acronym='mars',rev='01')
        review_team = ReviewTeamFactory(acronym="reviewteam", name="Review Team", type_id="review", list_email="reviewteam@ietf.org", parent=Group.objects.get(acronym="farfut"))
        rev_role = RoleFactory(group=review_team,person__user__username='reviewer',person__user__email='reviewer@example.com',name_id='reviewer')
        review_req = ReviewRequestFactory(doc=doc,team=review_team,type_id='early',state_id='assigned',requested_by=rev_role.person,deadline=datetime.datetime.now()+datetime.timedelta(days=20))
        ReviewAssignmentFactory(review_request=review_req, reviewer=rev_role.person.email_set.first(), state_id='accepted')

        # move the review request to a doubly-replaced document to
        # check we can fish it out
        old_doc = WgDraftFactory(name="draft-foo-mars-test")
        older_doc = WgDraftFactory(name="draft-older")
        RelatedDocument.objects.create(source=old_doc, target=older_doc.docalias.first(), relationship_id='replaces')
        RelatedDocument.objects.create(source=doc, target=old_doc.docalias.first(), relationship_id='replaces')
        review_req.doc = older_doc
        review_req.save()

        url = urlreverse('ietf.doc.views_doc.document_main', kwargs={ "name": doc.name })
        r = self.client.get(url)
        self.assertContains(r, "{} Review".format(review_req.type.name))

    def test_review_request(self):
        author = PersonFactory()
        doc = WgDraftFactory(group__acronym='mars',rev='01', authors=[author])
        review_team = ReviewTeamFactory(acronym="reviewteam", name="Review Team", type_id="review", list_email="reviewteam@ietf.org", parent=Group.objects.get(acronym="farfut"))
        rev_role = RoleFactory(group=review_team,person__user__username='reviewer',person__user__email='reviewer@example.com',name_id='reviewer')
        review_req = ReviewRequestFactory(doc=doc,team=review_team,type_id='early',state_id='assigned',requested_by=rev_role.person,deadline=datetime.datetime.now()+datetime.timedelta(days=20))
        ReviewAssignmentFactory(review_request = review_req, reviewer = rev_role.person.email_set.first(), state_id='accepted')

        url = urlreverse('ietf.doc.views_review.review_request', kwargs={ "name": doc.name, "request_id": review_req.pk })

        r = self.client.get(url)
        self.assertContains(r, review_req.team.acronym)
        self.assertContains(r, review_req.team.name)
        self.assertContains(r, str(author))

        url = urlreverse('ietf.doc.views_review.review_request_forced_login', kwargs={ "name": doc.name, "request_id": review_req.pk })
        r = self.client.get(url)
        self.assertEqual(r.status_code, 302)
        self.client.login(username='reviewer', password="reviewer+password")
        r = self.client.get(url,follow=True)
        self.assertEqual(r.status_code, 200)


    def test_close_request(self):
        doc = WgDraftFactory(group__acronym='mars',rev='01')
        review_team = ReviewTeamFactory(acronym="reviewteam", name="Review Team", type_id="review", list_email="reviewteam@ietf.org", parent=Group.objects.get(acronym="farfut"))
        rev_role = RoleFactory(group=review_team,person__user__username='reviewer',person__user__email='reviewer@example.com',name_id='reviewer')
        RoleFactory(group=review_team,person__user__username='reviewsecretary',person__user__email='reviewsecretary@example.com',name_id='secr')
        RoleFactory(group=review_team,person__user__username='reviewsecretary2',person__user__email='reviewsecretary2@example.com',name_id='secr')
        review_req = ReviewRequestFactory(doc=doc,team=review_team,type_id='early',state_id='assigned',requested_by=rev_role.person,deadline=datetime.datetime.now()+datetime.timedelta(days=20))
        ReviewAssignmentFactory(review_request=review_req, state_id='accepted', reviewer=rev_role.person.email_set.first())

        close_url = urlreverse('ietf.doc.views_review.close_request', kwargs={ "name": doc.name, "request_id": review_req.pk })

        # follow link
        req_url = urlreverse('ietf.doc.views_review.review_request', kwargs={ "name": doc.name, "request_id": review_req.pk })
        self.client.login(username="reviewsecretary", password="reviewsecretary+password")
        r = self.client.get(req_url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, close_url)
        self.client.logout()

        # get close page
        login_testing_unauthorized(self, "reviewsecretary", close_url)
        r = self.client.get(close_url)
        self.assertEqual(r.status_code, 200)

        # close
        empty_outbox()
        r = self.client.post(close_url, {"close_reason": "withdrawn",
                                         "close_comment": "review_request_close_comment"})
        self.assertEqual(r.status_code, 302)

        review_req = reload_db_objects(review_req)
        self.assertEqual(review_req.state_id, "withdrawn")

        e = doc.latest_event(ReviewRequestDocEvent)
        self.assertEqual(e.type, "closed_review_request")
        self.assertIn("closed", e.desc.lower())
        self.assertIn("review_request_close_comment", e.desc.lower())

        e = doc.latest_event(ReviewAssignmentDocEvent)
        self.assertEqual(e.type, "closed_review_assignment")
        self.assertIn("closed", e.desc.lower())
        self.assertNotIn("review_request_close_comment", e.desc.lower())

        self.assertEqual(len(outbox), 1)
        self.assertIn('<reviewer@example.com>', outbox[0]["To"])
        self.assertNotIn("<reviewsecretary@example.com>", outbox[0]["To"])
        self.assertIn("reviewsecretary2@example.com", outbox[0]["CC"])
        mail_content = get_payload_text(outbox[0])
        self.assertIn("closed", mail_content)
        self.assertIn("review_request_close_comment", mail_content)

    def test_assign_reviewer(self):
        doc = WgDraftFactory(pages=2)
        review_team = ReviewTeamFactory(acronym="reviewteam", name="Review Team", type_id="review", list_email="reviewteam@ietf.org", parent=Group.objects.get(acronym="farfut"))
        rev_role = RoleFactory(group=review_team,person__user__username='reviewer',person__user__email='reviewer@example.com',person__name='Some Reviewer',name_id='reviewer')
        RoleFactory(group=review_team,person__user__username='marschairman',person__name='WG Cháir Man',name_id='reviewer')
        secretary = RoleFactory(group=review_team,person__user__username='reviewsecretary',person__user__email='reviewsecretary@example.com',name_id='secr')
        ReviewerSettings.objects.create(team=review_team, person=rev_role.person, min_interval=14, skip_next=0)
        queue_policy = get_reviewer_queue_policy(review_team)

        # review to assign to
        review_req = ReviewRequestFactory(team=review_team,doc=doc,state_id='requested')

        # set up some reviewer-suitability factors
        reviewer_email = Email.objects.get(person__user__username="reviewer")
        DocumentAuthor.objects.create(person=reviewer_email.person, email=reviewer_email, document=doc)
        doc.rev = "10"
        doc.save_with_history([DocEvent.objects.create(doc=doc, rev=doc.rev, type="changed_document", by=Person.objects.get(user__username="secretary"), desc="Test")])

        # previous review
        req = ReviewRequestFactory(
            time=datetime.datetime.now() - datetime.timedelta(days=100),
            requested_by=Person.objects.get(name="(System)"),
            doc=doc,
            type_id='early',
            team=review_req.team,
            state_id='assigned',
            requested_rev="01",
            deadline=datetime.date.today() - datetime.timedelta(days=80),
        )
        ReviewAssignmentFactory(
            review_request = req,
            state_id='completed',
            result_id='serious-issues',
            reviewer=reviewer_email,
            reviewed_rev="01",
            review = ReviewFactory(),
            assigned_on=req.time,
            completed_on=req.time + datetime.timedelta(days=10),
        )

        reviewer_settings = ReviewerSettings.objects.get(person__email=reviewer_email, team=review_req.team)
        reviewer_settings.filter_re = doc.name
        reviewer_settings.skip_next = 1
        reviewer_settings.save()

        # Need one more person in review team one so we can test incrementing skip_count without immediately decrementing it
        another_reviewer = PersonFactory.create(name = "Extra TestReviewer") # needs to be lexically greater than the existing one
        another_reviewer.role_set.create(name_id='reviewer', email=another_reviewer.email(), group=review_req.team)

        ReviewWish.objects.create(person=reviewer_email.person, team=review_req.team, doc=doc)

        NextReviewerInTeam.objects.filter(team=review_req.team).delete()
        NextReviewerInTeam.objects.create(
            team=review_req.team,
            next_reviewer=Person.objects.exclude(pk=reviewer_email.person_id).first(),
        )

        assign_url = urlreverse('ietf.doc.views_review.assign_reviewer', kwargs={ "name": doc.name, "request_id": review_req.pk })


        # follow link
        req_url = urlreverse('ietf.doc.views_review.review_request', kwargs={ "name": doc.name, "request_id": review_req.pk })
        self.client.login(username="reviewsecretary", password="reviewsecretary+password")
        r = self.client.get(req_url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, assign_url)
        self.client.logout()

        # get assign page
        login_testing_unauthorized(self, "reviewsecretary", assign_url)
        r = self.client.get(assign_url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        reviewer_label = q("option[value=\"{}\"]".format(reviewer_email.address)).text().lower()
        self.assertIn("reviewed document before", reviewer_label)
        self.assertIn("wishes to review", reviewer_label)
        self.assertIn("is author", reviewer_label)
        self.assertIn("regexp matches", reviewer_label)
        self.assertIn("skip next 1", reviewer_label)
        self.assertIn("#1", reviewer_label)
        self.assertIn("1 fully completed", reviewer_label)

        # assign
        empty_outbox()
        rotation_list = queue_policy.default_reviewer_rotation_list()
        reviewer = Email.objects.filter(role__name="reviewer", role__group=review_req.team, person=rotation_list[0]).first()
        r = self.client.post(assign_url, { "action": "assign", "reviewer": reviewer.pk })
        self.assertEqual(r.status_code, 302)

        review_req = reload_db_objects(review_req)
        self.assertEqual(review_req.state_id, "assigned")
        self.assertEqual(review_req.reviewassignment_set.count(),1)
        assignment = review_req.reviewassignment_set.first()
        self.assertEqual(assignment.reviewer, reviewer)
        self.assertEqual(assignment.state_id, "assigned")

        self.assertEqual(len(outbox), 1)
        self.assertEqual('"Some Reviewer" <reviewer@example.com>', outbox[0]["To"])
        message = get_payload_text(outbox[0])
        self.assertIn("Pages: {}".format(doc.pages), message )
        self.assertIn("{} has assigned {}".format(secretary.person.ascii, reviewer.person.ascii), message)
        self.assertIn("This team has completed other reviews", message)
        self.assertIn("{} -01 Serious Issues".format(reviewer_email.person.ascii), message)

    def test_previously_reviewed_replaced_doc(self):
        review_team = ReviewTeamFactory(acronym="reviewteam", name="Review Team", type_id="review", list_email="reviewteam@ietf.org", parent=Group.objects.get(acronym="farfut"))
        rev_role = RoleFactory(group=review_team,person__user__username='reviewer',person__user__email='reviewer@example.com',person__name='Some Reviewer',name_id='reviewer')
        RoleFactory(group=review_team,person__user__username='reviewsecretary',person__user__email='reviewsecretary@example.com',name_id='secr')

        ind_doc = IndividualDraftFactory()
        old_wg_doc = WgDraftFactory(relations=[('replaces',ind_doc)])
        middle_wg_doc = WgDraftFactory(relations=[('replaces',old_wg_doc)])
        new_wg_doc = WgDraftFactory(relations=[('replaces',middle_wg_doc)])

        ReviewAssignmentFactory(review_request__team=review_team, review_request__doc=old_wg_doc, reviewer=rev_role.email, state_id='completed')

        review_req=ReviewRequestFactory(team=review_team, doc=new_wg_doc)

        assign_url = urlreverse('ietf.doc.views_review.assign_reviewer', kwargs={ "name": new_wg_doc.name, "request_id": review_req.pk })

        login_testing_unauthorized(self, "reviewsecretary", assign_url)
        r = self.client.get(assign_url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        reviewer_label = q("option[value=\"{}\"]".format(rev_role.email.address)).text().lower()
        self.assertIn("reviewed document before", reviewer_label)

    def test_accept_reviewer_assignment(self):

        doc = WgDraftFactory(group__acronym='mars',rev='01')
        review_team = ReviewTeamFactory(acronym="reviewteam", name="Review Team", type_id="review", list_email="reviewteam@ietf.org", parent=Group.objects.get(acronym="farfut"))
        rev_role = RoleFactory(group=review_team,person__user__username='reviewer',person__user__email='reviewer@example.com',name_id='reviewer')
        review_req = ReviewRequestFactory(doc=doc,team=review_team,type_id='early',state_id='assigned',requested_by=rev_role.person,deadline=datetime.datetime.now()+datetime.timedelta(days=20))
        assignment = ReviewAssignmentFactory(review_request=review_req, state_id='assigned', reviewer=rev_role.person.email_set.first())

        url = urlreverse('ietf.doc.views_review.review_request', kwargs={ "name": doc.name, "request_id": review_req.pk })
        username = assignment.reviewer.person.user.username
        self.client.login(username=username, password=username + "+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(q("[name=action][value=accept]"))

        # accept
        r = self.client.post(url, { "action": "accept" })
        self.assertEqual(r.status_code, 302)

        assignment = reload_db_objects(assignment)
        self.assertEqual(assignment.state_id, "accepted")

    def test_reject_reviewer_assignment(self):
        doc = WgDraftFactory(group__acronym='mars',rev='01')
        review_team = ReviewTeamFactory(acronym="reviewteam", name="Review Team", type_id="review", list_email="reviewteam@ietf.org", parent=Group.objects.get(acronym="farfut"))
        rev_role = RoleFactory(group=review_team,person__user__username='reviewer',person__user__email='reviewer@example.com',name_id='reviewer')
        RoleFactory(group=review_team,person__user__username='reviewsecretary',person__user__email='reviewsecretary@example.com',name_id='secr')
        review_req = ReviewRequestFactory(doc=doc,team=review_team,type_id='early',state_id='assigned',requested_by=rev_role.person,deadline=datetime.datetime.now()+datetime.timedelta(days=20))
        assignment = ReviewAssignmentFactory(review_request = review_req, reviewer=rev_role.person.email_set.first(), state_id='accepted')

        reject_url = urlreverse('ietf.doc.views_review.reject_reviewer_assignment', kwargs={ "name": doc.name, "assignment_id": assignment.pk })


        # follow link
        req_url = urlreverse('ietf.doc.views_review.review_request', kwargs={ "name": doc.name, "request_id": assignment.review_request.pk })
        self.client.login(username="reviewsecretary", password="reviewsecretary+password")
        r = self.client.get(req_url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, reject_url)
        self.client.logout()

        # get reject page
        login_testing_unauthorized(self, "reviewsecretary", reject_url)
        r = self.client.get(reject_url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, assignment.reviewer.person.plain_name())
        self.assertNotContains(r, 'can not be rejected')
        self.assertContains(r, '<button type="submit"')

        # reject
        empty_outbox()
        r = self.client.post(reject_url, { "action": "reject", "message_to_secretary": "Test message" })
        self.assertEqual(r.status_code, 302)

        assignment = reload_db_objects(assignment)
        self.assertEqual(assignment.state_id, "rejected")
        self.assertNotEqual(assignment.completed_on,None)
        e = doc.latest_event()
        self.assertEqual(e.type, "closed_review_assignment")
        self.assertTrue("rejected" in e.desc)
        self.assertEqual(len(outbox), 1)
        self.assertIn(assignment.reviewer.address, outbox[0]["To"])
        self.assertNotIn("<reviewsecretary@example.com>", outbox[0]["To"])
        self.assertTrue("Test message" in get_payload_text(outbox[0]))

        # try again, but now with an expired review request, which should not be allowed (#2277)
        assignment.state_id = 'assigned'
        assignment.save()
        review_req.deadline = datetime.date(2019, 1, 1)
        review_req.save()
        
        r = self.client.get(reject_url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, str(assignment.reviewer.person))
        self.assertContains(r, 'can not be rejected')
        self.assertNotContains(r, '<button type="submit"')

        # even though the form is not visible, try posting to the URL, which should not work
        empty_outbox()
        r = self.client.post(reject_url, { "action": "reject", "message_to_secretary": "Test message" })
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'can not be rejected')

        assignment = reload_db_objects(assignment)
        self.assertEqual(assignment.state_id, "assigned")
        self.assertEqual(len(outbox), 0)

    def make_test_mbox_tarball(self, review_req):
        mbox_path = os.path.join(self.review_dir, "testmbox.tar.gz")
        with tarfile.open(mbox_path, "w:gz") as tar:
            with tempfile.NamedTemporaryFile(dir=self.review_dir, suffix=".mbox") as tmp:
                mbox = mailbox.mbox(tmp.name)

                # plain text
                msg = email.mime.text.MIMEText("Hello,\n\nI have reviewed the document and did not find any problems.\n\nJohn Doe")
                msg["From"] = "John Doe <johndoe@example.com>"
                msg["To"] = review_req.team.list_email
                msg["Subject"] = "Review of {}-01".format(review_req.doc.name)
                msg["Message-ID"] = email.utils.make_msgid()
                msg["Archived-At"] = "<https://www.example.com/testmessage>"
                msg["Date"] = email.utils.formatdate()

                mbox.add(msg)

                # plain text + HTML
                msg = email.mime.multipart.MIMEMultipart('alternative')
                msg["From"] = "John Doe II <johndoe2@example.com>"
                msg["To"] = review_req.team.list_email
                msg["Subject"] = "Review of {}".format(review_req.doc.name)
                msg["Message-ID"] = email.utils.make_msgid()
                msg["Archived-At"] = "<https://www.example.com/testmessage2>"

                msg.attach(email.mime.text.MIMEText("Hi!,\r\nLooks OK!\r\n-John", "plain"))
                msg.attach(email.mime.text.MIMEText("<html><body><p>Hi!,</p><p>Looks OK!</p><p>-John</p></body></html>", "html"))
                mbox.add(msg)

                tmp.flush()

                tar.add(os.path.relpath(tmp.name))

        return mbox_path

    def test_search_mail_archive(self):
        doc = WgDraftFactory(group__acronym='mars',rev='01')
        review_team = ReviewTeamFactory(acronym="reviewteam", name="Review Team", type_id="review", list_email="reviewteam@ietf.org", parent=Group.objects.get(acronym="farfut"))
        rev_role = RoleFactory(group=review_team,person__user__username='reviewer',person__user__email='reviewer@example.com',name_id='reviewer')
        RoleFactory(group=review_team,person__user__username='reviewsecretary',person__user__email='reviewsecretary@example.com',name_id='secr')
        review_req = ReviewRequestFactory(doc=doc,team=review_team,type_id='early',state_id='assigned',requested_by=rev_role.person,deadline=datetime.datetime.now()+datetime.timedelta(days=20))
        assignment = ReviewAssignmentFactory(review_request=review_req, reviewer=rev_role.person.email_set.first(), state_id='accepted')

        # test URL construction
        query_urls = ietf.review.mailarch.construct_query_urls(doc, review_team)
        self.assertTrue(review_req.doc.name in query_urls["query_data_url"])

        # test parsing
        mbox_path = self.make_test_mbox_tarball(review_req)

        try:
            # mock URL generator and point it to local file - for this
            # to work, the module (and not the function) must be
            # imported in the view
            real_fn = ietf.review.mailarch.construct_query_urls
            ietf.review.mailarch.construct_query_urls = lambda doc, team, query=None: { "query_data_url": "file://" + os.path.abspath(mbox_path) }
            url = urlreverse('ietf.doc.views_review.search_mail_archive', kwargs={ "name": doc.name, "assignment_id": assignment.pk })
            url2 = urlreverse('ietf.doc.views_review.search_mail_archive', kwargs={ "name": doc.name, "acronym": review_team.acronym })
            login_testing_unauthorized(self, "reviewsecretary", url)

            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            messages = r.json()["messages"]
            self.assertEqual(len(messages), 2)

            r = self.client.get(url2)
            self.assertEqual(r.status_code, 200)
            messages = r.json()["messages"]
            self.assertEqual(len(messages), 2)

            today = datetime.date.today()

            self.assertEqual(messages[0]["url"], "https://www.example.com/testmessage")
            self.assertTrue("John Doe" in messages[0]["content"])
            self.assertEqual(messages[0]["subject"], "Review of {}-01".format(review_req.doc.name))
            self.assertEqual(messages[0]["revision_guess"], "01")
            self.assertEqual(messages[0]["splitfrom"], ["John Doe", "johndoe@example.com"])
            self.assertEqual(messages[0]["utcdate"][0], today.isoformat())

            self.assertEqual(messages[1]["url"], "https://www.example.com/testmessage2")
            self.assertTrue("Looks OK" in messages[1]["content"])
            self.assertTrue("<html>" not in messages[1]["content"])
            self.assertEqual(messages[1]["subject"], "Review of {}".format(review_req.doc.name))
            self.assertFalse('revision_guess' in messages[1])
            self.assertEqual(messages[1]["splitfrom"], ["John Doe II", "johndoe2@example.com"])
            self.assertEqual(messages[1]["utcdate"][0], "")


            # Test failure to return mailarch results
            no_result_path = os.path.join(self.review_dir, "mailarch_no_result.html")
            with io.open(no_result_path, "w") as f:
                f.write('Content-Type: text/html\n\n<html><body><div class="xtr"><div class="xtd no-results">No results found</div></div>')
            ietf.review.mailarch.construct_query_urls = lambda doc, team, query=None: { "query_data_url": "file://" + os.path.abspath(no_result_path) }

            url = urlreverse('ietf.doc.views_review.search_mail_archive', kwargs={ "name": doc.name, "assignment_id": assignment.pk })

            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            result = r.json()
            self.assertNotIn('messages', result)
            self.assertIn('No results found', result['error'])

        finally:
            ietf.review.mailarch.construct_query_urls = real_fn

    def test_submit_unsolicited_review_choose_team(self):
        doc = WgDraftFactory(group__acronym='mars', rev='01')
        review_team = ReviewTeamFactory(acronym="reviewteam", name="Review Team", type_id="review", list_email="reviewteam@ietf.org", parent=Group.objects.get(acronym="farfut"))
        secretary = RoleFactory(group=review_team,person__user__username='reviewsecretary',person__user__email='reviewsecretary@example.com', name_id='secr')
        
        url = urlreverse('ietf.doc.views_review.submit_unsolicited_review_choose_team',
                         kwargs={'name': doc.name})
        redirect_url = urlreverse("ietf.doc.views_review.complete_review",
                                  kwargs={'name': doc.name, 'acronym': review_team.acronym})
        login_testing_unauthorized(self, secretary.person.user.username, url)

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, review_team.name)

        r = self.client.post(url, data={'team': review_team.pk})
        self.assertRedirects(r, redirect_url)

        r = self.client.post(url, data={'team': review_team.pk + 5})
        self.assertEqual(r.status_code, 200)

    def setup_complete_review_test(self):
        doc = WgDraftFactory(group__acronym='mars',rev='01')
        NewRevisionDocEventFactory(doc=doc,rev='01')
        review_team = ReviewTeamFactory(acronym="reviewteam", name="Review Team", type_id="review", list_email="reviewteam@ietf.org", parent=Group.objects.get(acronym="farfut"))
        rev_role = RoleFactory(group=review_team,person__user__username='reviewer',person__user__email='reviewer@example.com',name_id='reviewer')
        RoleFactory(group=review_team,person__user__username='reviewsecretary',person__user__email='reviewsecretary@example.com',name_id='secr')
        review_req = ReviewRequestFactory(doc=doc,team=review_team,type_id='early',state_id='assigned',requested_by=rev_role.person,deadline=datetime.datetime.now()+datetime.timedelta(days=20))
        assignment = ReviewAssignmentFactory(review_request=review_req, state_id='accepted', reviewer=rev_role.person.email_set.first())
        for r in ReviewResultName.objects.filter(slug__in=("issues", "ready")):
            review_req.team.reviewteamsettings.review_results.add(r)

        url = urlreverse('ietf.doc.views_review.complete_review', kwargs={ "name": doc.name, "assignment_id": review_req.pk })

        return assignment, url

    def test_complete_review_upload_content(self):
        assignment, url = self.setup_complete_review_test()

        login_testing_unauthorized(self, assignment.reviewer.person.user.username, url)

        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, assignment.review_request.team.list_email)
        for author in assignment.review_request.doc.authors():
            self.assertContains(r, author.formatted_email())

        # faulty post
        r = self.client.post(url, data={
            "result": "ready",
            "state": "completed",
            "reviewed_rev": "abc",
            "review_submission": "upload",
            "review_content": "",
            "review_url": "",
            "review_file": "",
        })
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(q("[name=reviewed_rev]").closest(".form-group").filter(".has-error"))
        self.assertTrue(q("[name=review_file]").closest(".form-group").filter(".has-error"))

        # complete by uploading file
        empty_outbox()

        test_file = io.StringIO("This is a review\nwith two lines")
        test_file.name = "unnamed"

        r = self.client.post(url, data={
            "result": ReviewResultName.objects.get(reviewteamsettings_review_results_set__group=assignment.review_request.team, slug="ready").pk,
            "state": ReviewAssignmentStateName.objects.get(slug="completed").pk,
            "reviewed_rev": assignment.review_request.doc.rev,
            "review_submission": "upload",
            "review_content": "",
            "review_url": "",
            "review_file": test_file,
        })
        self.assertEqual(r.status_code, 302)

        assignment = reload_db_objects(assignment)
        self.assertEqual(assignment.state_id, "completed")
        self.assertEqual(assignment.result_id, "ready")
        self.assertEqual(assignment.reviewed_rev, assignment.review_request.doc.rev)
        self.assertTrue(assignment.review_request.team.acronym.lower() in assignment.review.name)
        self.assertTrue(assignment.review_request.doc.rev in assignment.review.name)

        with io.open(os.path.join(self.review_subdir, assignment.review.name + ".txt")) as f:
            self.assertEqual(f.read(), "This is a review\nwith two lines")

        self.assertEqual(len(outbox), 1)
        self.assertIn(assignment.review_request.team.list_email, outbox[0]["To"])
        self.assertIn(assignment.reviewer.role_set.filter(group=assignment.review_request.team,name='reviewer').first().person.plain_name(), parseaddr(outbox[0]["From"])[0] )
        self.assertIn("This is a review", get_payload_text(outbox[0]))

        self.assertIn(settings.MAILING_LIST_ARCHIVE_URL, assignment.review.external_url)

        # Check that the review has the reviewer as author
        self.assertEqual(assignment.reviewer, assignment.review.documentauthor_set.first().email)

        # Check that we have a copy of the outgoing message
        msgid = outbox[0]["Message-ID"]
        message = Message.objects.get(msgid=msgid)
        self.assertEqual(parseaddr(outbox[0]["To"]), parseaddr(message.to))
        self.assertEqual(parseaddr(outbox[0]["From"]), parseaddr(on_behalf_of(message.frm)))
        self.assertEqual(parseaddr(outbox[0]["Reply-To"]), parseaddr(message.frm))
        self.assertEqual(get_payload_text(outbox[0]), message.body)

        # check the review document page
        url = urlreverse('ietf.doc.views_doc.document_main', kwargs={ "name": assignment.review.name })
        r = self.client.get(url)
        self.assertContains(r, "{} Review".format(assignment.review_request.type.name))
        self.assertContains(r, "This is a review")


    def test_complete_review_enter_content(self):
        assignment, url = self.setup_complete_review_test()

        login_testing_unauthorized(self, assignment.reviewer.person.user.username, url)

        empty_outbox()

        r = self.client.post(url, data={
            "result": ReviewResultName.objects.get(reviewteamsettings_review_results_set__group=assignment.review_request.team, slug="ready").pk,
            "state": ReviewAssignmentStateName.objects.get(slug="completed").pk,
            "reviewed_rev": assignment.review_request.doc.rev,
            "review_submission": "enter",
            "review_content": "This is a review\nwith two lines",
            "review_url": "",
            "review_file": "",
            # Custom completion should be ignored - review posted by assignee is always set to now
            "completion_date": "2012-12-24",
            "completion_time": "12:13:14",
        })
        self.assertEqual(r.status_code, 302)

        assignment = reload_db_objects(assignment)
        self.assertEqual(assignment.state_id, "completed")
        # Completed time should be close to now, but will not be exactly, so check within 10s margin
        completed_time_diff = datetime.datetime.now() - assignment.completed_on
        self.assertLess(completed_time_diff, datetime.timedelta(seconds=10))

        with io.open(os.path.join(self.review_subdir, assignment.review.name + ".txt")) as f:
            self.assertEqual(f.read(), "This is a review\nwith two lines")

        self.assertEqual(len(outbox), 1)
        self.assertIn(assignment.review_request.team.list_email, outbox[0]["To"])
        self.assertIn("This is a review", get_payload_text(outbox[0]))

        self.assertIn(settings.MAILING_LIST_ARCHIVE_URL, assignment.review.external_url)

    def test_complete_review_enter_content_by_secretary(self):
        assignment, url = self.setup_complete_review_test()
        login_testing_unauthorized(self, 'reviewsecretary', url)

        empty_outbox()

        r = self.client.post(url, data={
            "result": ReviewResultName.objects.get(reviewteamsettings_review_results_set__group=assignment.review_request.team, slug="ready").pk,
            "state": ReviewAssignmentStateName.objects.get(slug="completed").pk,
            "reviewed_rev": assignment.review_request.doc.rev,
            "review_submission": "enter",
            "review_content": "This is a review\nwith two lines",
            "review_url": "",
            "review_file": "",
            "completion_date": "2012-12-24",
            "completion_time": "12:13:14",
        })
        self.assertEqual(r.status_code, 302)

        # The secretary is allowed to set a custom completion date (#2590)
        assignment = reload_db_objects(assignment)
        self.assertEqual(assignment.state_id, "completed")
        self.assertEqual(assignment.completed_on, datetime.datetime(2012, 12, 24, 12, 13, 14))

        # There should be two events:
        # - the event logging when the change when it was entered, i.e. very close to now.
        # - the completion of the review, set to the provided date/time
        events = ReviewAssignmentDocEvent.objects.filter(doc=assignment.review_request.doc).order_by('-time')
        event0_time_diff = datetime.datetime.now() - events[0].time
        self.assertLess(event0_time_diff, datetime.timedelta(seconds=10))
        self.assertEqual(events[1].time, datetime.datetime(2012, 12, 24, 12, 13, 14))
        
        with io.open(os.path.join(self.review_subdir, assignment.review.name + ".txt")) as f:
            self.assertEqual(f.read(), "This is a review\nwith two lines")

        self.assertEqual(len(outbox), 1)
        self.assertIn(assignment.review_request.team.list_email, outbox[0]["To"])
        self.assertIn("This is a review", get_payload_text(outbox[0]))

        self.assertIn(settings.MAILING_LIST_ARCHIVE_URL, assignment.review.external_url)

    def test_complete_notify_ad_because_team_settings(self):
        assignment, url = self.setup_complete_review_test()
        assignment.review_request.team.reviewteamsettings.notify_ad_when.add(ReviewResultName.objects.get(slug='issues'))
        # TODO - it's a little surprising that the factories so far didn't give this doc an ad
        assignment.review_request.doc.ad = PersonFactory()
        assignment.review_request.doc.save_with_history([DocEvent.objects.create(doc=assignment.review_request.doc, rev=assignment.review_request.doc.rev, by=assignment.reviewer.person, type='changed_document',desc='added an AD')])
        login_testing_unauthorized(self, assignment.reviewer.person.user.username, url)

        empty_outbox()

        r = self.client.post(url, data={
            "result": ReviewResultName.objects.get(reviewteamsettings_review_results_set__group=assignment.review_request.team, slug="issues").pk,
            "state": ReviewRequestStateName.objects.get(slug="completed").pk,
            "reviewed_rev": assignment.review_request.doc.rev,
            "review_submission": "enter",
            "review_content": "This is a review\nwith two lines",
            "review_url": "",
            "review_file": "",
        })
        self.assertEqual(r.status_code, 302)

        self.assertEqual(len(outbox), 2)
        self.assertIn('Has Issues', outbox[-1]['Subject'])
        self.assertIn('settings indicated', get_payload_text(outbox[-1]))

    def test_complete_notify_ad_because_checkbox(self):
        assignment, url = self.setup_complete_review_test()
        assignment.review_request.doc.ad = PersonFactory()
        assignment.review_request.doc.save_with_history([DocEvent.objects.create(doc=assignment.review_request.doc, rev=assignment.review_request.doc.rev, by=assignment.reviewer.person, type='changed_document',desc='added an AD')])
        login_testing_unauthorized(self, assignment.reviewer.person.user.username, url)

        empty_outbox()

        r = self.client.post(url, data={
            "result": ReviewResultName.objects.get(reviewteamsettings_review_results_set__group=assignment.review_request.team, slug="issues").pk,
            "state": ReviewAssignmentStateName.objects.get(slug="completed").pk,
            "reviewed_rev": assignment.review_request.doc.rev,
            "review_submission": "enter",
            "review_content": "This is a review\nwith two lines",
            "review_url": "",
            "review_file": "",
            "email_ad": "1",
        })
        self.assertEqual(r.status_code, 302)

        self.assertEqual(len(outbox), 2)
        self.assertIn('Has Issues', outbox[-1]['Subject']) 
        self.assertIn('reviewer indicated', get_payload_text(outbox[-1]))

    @patch('requests.get')
    def test_complete_review_link_to_mailing_list(self, mock):
        # Mock up the url response for the request.get() call to retrieve the mailing list url
        response = Response()
        response.status_code = 200
        response._content = b"This is a review\nwith two lines"
        mock.return_value = response

        # Run the test
        assignment, url = self.setup_complete_review_test()

        login_testing_unauthorized(self, assignment.reviewer.person.user.username, url)

        empty_outbox()

        r = self.client.post(url, data={
            "result": ReviewResultName.objects.get(reviewteamsettings_review_results_set__group=assignment.review_request.team, slug="ready").pk,
            "state": ReviewAssignmentStateName.objects.get(slug="completed").pk,
            "reviewed_rev": assignment.review_request.doc.rev,
            "review_submission": "link",
            "review_content": response.content.decode(),
            "review_url": "http://example.com/testreview/",
            "review_file": "",
        })
        self.assertEqual(r.status_code, 302)

        assignment = reload_db_objects(assignment)
        self.assertEqual(assignment.state_id, "completed")

        with io.open(os.path.join(self.review_subdir, assignment.review.name + ".txt")) as f:
            self.assertEqual(f.read(), "This is a review\nwith two lines")

        self.assertEqual(len(outbox), 0)
        self.assertTrue("http://example.com" in assignment.review.external_url)

    @patch('requests.get')
    def test_complete_unsolicited_review_link_to_mailing_list_by_secretary(self, mock):
        # Mock up the url response for the request.get() call to retrieve the mailing list url
        response = Response()
        response.status_code = 200
        response._content = b"This is a review\nwith two lines"
        mock.return_value = response

        # Run the test
        doc = WgDraftFactory(group__acronym='mars', rev='01')
        NewRevisionDocEventFactory(doc=doc, rev='01')
        review_team = ReviewTeamFactory(acronym="reviewteam", name="Review Team", type_id="review", list_email="reviewteam@ietf.org", parent=Group.objects.get(acronym="farfut"))
        rev_role = RoleFactory(group=review_team, person__user__username='reviewer', person__user__email='reviewer@example.com', name_id='reviewer')
        secretary_role = RoleFactory(group=review_team, person__user__username='reviewsecretary', person__user__email='reviewsecretary@example.com', name_id='secr')

        url = urlreverse('ietf.doc.views_review.complete_review',
                         kwargs={"name": doc.name, "acronym": review_team.acronym})

        login_testing_unauthorized(self, secretary_role.person.user.username, url)

        empty_outbox()
        
        r = self.client.post(url, data={
            "result": ReviewResultName.objects.get(slug="ready").pk,
            "state": ReviewAssignmentStateName.objects.get(slug="completed").pk,
            "reviewed_rev": '01',
            "review_submission": "link",
            "review_content": response.content.decode(),
            "review_url": "http://example.com/testreview/",
            "review_file": "",
            "review_type": ReviewTypeName.objects.get(slug="early").pk,
            "reviewer": rev_role.person.pk,
            "completion_date": "2012-12-24",
            "completion_time": "12:13:14",
        })
        self.assertEqual(r.status_code, 302)

        review_req = doc.reviewrequest_set.get()
        assignment = review_req.reviewassignment_set.get()
        self.assertEqual(review_req.type_id, "early")
        self.assertEqual(review_req.requested_by, secretary_role.person)
        self.assertEqual(assignment.reviewer, rev_role.person.role_email('reviewer'))
        self.assertEqual(assignment.state_id, "completed")

        with io.open(os.path.join(self.review_subdir, assignment.review.name + ".txt")) as f:
            self.assertEqual(f.read(), "This is a review\nwith two lines")

        self.assertEqual(len(outbox), 0)
        self.assertTrue("http://example.com" in assignment.review.external_url)

    def test_double_submit_review(self):
        assignment, url = self.setup_complete_review_test()

        login_testing_unauthorized(self, assignment.reviewer.person.user.username, url)

        name_components = [
            "review",
            strip_prefix(assignment.review_request.doc.name, "draft-"),
            assignment.review_request.doc.rev,
            assignment.review_request.team.acronym, 
            assignment.review_request.type.slug,
            xslugify(assignment.reviewer.person.ascii_parts()[3]),
            datetime.date.today().isoformat(),
        ]
        review_name = "-".join(c for c in name_components if c).lower()
        Document.objects.create(name=review_name,type_id='review',group=assignment.review_request.team)

        r = self.client.post(url, data={
            "result": ReviewResultName.objects.get(reviewteamsettings_review_results_set__group=assignment.review_request.team, slug="ready").pk,
            "state": ReviewAssignmentStateName.objects.get(slug="completed").pk,
            "reviewed_rev": assignment.review_request.doc.rev,
            "review_submission": "enter",
            "review_content": "This is a review\nwith two lines",
            "review_url": "",
            "review_file": "",
            # Custom completion should be ignored - review posted by assignee is always set to now
            "completion_date": "2012-12-24",
            "completion_time": "12:13:14",
        })
        self.assertEqual(r.status_code, 302)
        r2 = self.client.get(r.url)
        self.assertEqual(len(r2.context['messages']),1)
        self.assertIn('Attempt to save review failed', list(r2.context['messages'])[0].message)

    def test_partially_complete_review(self):
        assignment, url = self.setup_complete_review_test()

        login_testing_unauthorized(self, assignment.reviewer.person.user.username, url)

        # partially complete
        empty_outbox()

        r = self.client.post(url, data={
            "result": ReviewResultName.objects.get(reviewteamsettings_review_results_set__group=assignment.review_request.team, slug="ready").pk,
            "state": ReviewAssignmentStateName.objects.get(slug="part-completed").pk,
            "reviewed_rev": assignment.review_request.doc.rev,
            "review_submission": "enter",
            "review_content": "This is a review with a somewhat long line spanning over 80 characters to test word wrapping\nand another line",
        })
        self.assertEqual(r.status_code, 302)

        assignment = reload_db_objects(assignment)
        self.assertEqual(assignment.state_id, "part-completed")
        self.assertTrue(assignment.review_request.doc.rev in assignment.review.name)

        self.assertEqual(len(outbox), 2)
        self.assertIn("<reviewsecretary@example.com>", outbox[0]["To"])
        self.assertNotIn(assignment.reviewer.address, outbox[0]["To"])
        self.assertTrue("partially" in outbox[0]["Subject"].lower())

        self.assertTrue(assignment.review_request.team.list_email in outbox[1]["To"])
        self.assertTrue("partial review" in outbox[1]["Subject"].lower())
        body = get_payload_text(outbox[1])
        self.assertTrue("This is a review" in body)
        # This review has a line longer than 80, but less than 100; it should
        # not be wrapped.

        self.assertTrue(not any( len(line) > 100 for line in body.splitlines() ))
        self.assertTrue(any( len(line) > 80 for line in body.splitlines() ))


    def test_revise_review_enter_content(self):
        assignment, url = self.setup_complete_review_test()
        assignment.state = ReviewAssignmentStateName.objects.get(slug="no-response")
        assignment.save()

        login_testing_unauthorized(self, assignment.reviewer.person.user.username, url)

        empty_outbox()

        r = self.client.post(url, data={
            "result": ReviewResultName.objects.get(reviewteamsettings_review_results_set__group=assignment.review_request.team, slug="ready").pk,
            "state": ReviewAssignmentStateName.objects.get(slug="completed").pk,
            "reviewed_rev": assignment.review_request.doc.rev,
            "review_submission": "enter",
            "review_content": "This is a review\nwith two lines",
            "review_url": "",
            "review_file": "",
            "completion_date": "2012-12-24",
            "completion_time": "12:13:14",
        })
        self.assertEqual(r.status_code, 302)

        assignment = reload_db_objects(assignment)
        self.assertEqual(assignment.state_id, "completed")
        # The revision event time should be the date the revision was submitted, i.e. not backdated
        event1 = assignment.review_request.doc.latest_event(ReviewAssignmentDocEvent)
        event_time_diff = datetime.datetime.now() - event1.time
        self.assertLess(event_time_diff, datetime.timedelta(seconds=10))
        self.assertTrue('revised' in event1.desc.lower())

        with io.open(os.path.join(self.review_subdir, assignment.review.name + ".txt")) as f:
            self.assertEqual(f.read(), "This is a review\nwith two lines")

        self.assertEqual(len(outbox), 0)

        # revise again
        empty_outbox()
        r = self.client.post(url, data={
            "result": ReviewResultName.objects.get(reviewteamsettings_review_results_set__group=assignment.review_request.team, slug="ready").pk,
            "state": ReviewAssignmentStateName.objects.get(slug="part-completed").pk,
            "reviewed_rev": assignment.review_request.doc.rev,
            "review_submission": "enter",
            "review_content": "This is a revised review",
            "review_url": "",
            "review_file": "",
            "completion_date": "2013-12-24",
            "completion_time": "11:11:11",
        })
        self.assertEqual(r.status_code, 302)

        assignment = reload_db_objects(assignment)
        self.assertEqual(assignment.review.rev, "01")
        event2 = assignment.review_request.doc.latest_event(ReviewAssignmentDocEvent)
        event_time_diff = datetime.datetime.now() - event2.time
        self.assertLess(event_time_diff, datetime.timedelta(seconds=10))
        # Ensure that a new event was created for the new revision (#2590)
        self.assertNotEqual(event1.id, event2.id)

        self.assertEqual(len(outbox), 0)
        
    def test_edit_comment(self):
        doc = WgDraftFactory(group__acronym='mars',rev='01')
        review_team = ReviewTeamFactory(acronym="reviewteam", name="Review Team", type_id="review", list_email="reviewteam@ietf.org", parent=Group.objects.get(acronym="farfut"))
        rev_role = RoleFactory(group=review_team,person__user__username='reviewer',person__user__email='reviewer@example.com',name_id='reviewer')
        RoleFactory(group=review_team,person__user__username='reviewsecretary',person__user__email='reviewsecretary@example.com',name_id='secr')
        review_req = ReviewRequestFactory(doc=doc,team=review_team,type_id='early',state_id='assigned',requested_by=rev_role.person,deadline=datetime.datetime.now()+datetime.timedelta(days=20))
        ReviewAssignmentFactory(review_request = review_req, reviewer = rev_role.person.email_set.first(), state_id='accepted')

        url = urlreverse('ietf.doc.views_review.edit_comment', kwargs={ "name": doc.name, "request_id": review_req.pk })

        login_testing_unauthorized(self, "ad", url)

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        r = self.client.post(url, data={
            "comment": "iHsnReEHXEmNPXcixsvAF9Aa",
        })
        self.assertEqual(r.status_code, 302)
        review_req = reload_db_objects(review_req)
        self.assertEqual(review_req.comment,'iHsnReEHXEmNPXcixsvAF9Aa')

    def test_edit_deadline(self):
        doc = WgDraftFactory(group__acronym='mars',rev='01')
        review_team = ReviewTeamFactory(acronym="reviewteam", name="Review Team", type_id="review", list_email="reviewteam@ietf.org", parent=Group.objects.get(acronym="farfut"))
        rev_role = RoleFactory(group=review_team,person__user__username='reviewer',person__user__email='reviewer@example.com',name_id='reviewer')
        RoleFactory(group=review_team,person__user__username='reviewsecretary',person__user__email='reviewsecretary@example.com',name_id='secr')
        review_req = ReviewRequestFactory(doc=doc,team=review_team,type_id='early',state_id='accepted',requested_by=rev_role.person,deadline=datetime.datetime.now()+datetime.timedelta(days=20))
        ReviewAssignmentFactory(review_request = review_req, reviewer = rev_role.person.email_set.first(), state_id='accepted')

        url = urlreverse('ietf.doc.views_review.edit_deadline', kwargs={ "name": doc.name, "request_id": review_req.pk })

        login_testing_unauthorized(self, "ad", url)

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        empty_outbox()
        old_deadline = review_req.deadline.date()
        new_deadline = old_deadline + datetime.timedelta(days=1)
        r = self.client.post(url, data={
            "deadline": new_deadline.isoformat(),
        })
        self.assertEqual(r.status_code, 302)
        review_req = reload_db_objects(review_req)
        self.assertEqual(review_req.deadline,new_deadline)
        self.assertEqual(len(outbox), 1)
        self.assertIn('reviewsecretary@example.com', outbox[0]["Cc"])
        self.assertIn('<reviewer@example.com>', outbox[0]["To"])
        self.assertIn('Deadline changed', outbox[0]['Subject'])

    def test_mark_no_response(self):
        assignment = ReviewAssignmentFactory()
        secr = RoleFactory(group=assignment.review_request.team,person__user__username='reviewsecretary',person__user__email='reviewsecretary@example.com',name_id='secr').person
        url = urlreverse('ietf.doc.views_review.mark_reviewer_assignment_no_response', kwargs={"name": assignment.review_request.doc.name, "assignment_id": assignment.pk})

        login_testing_unauthorized(self, secr.user.username, url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        empty_outbox()
        r=self.client.post(url, data={"action":"noresponse"})
        self.assertEqual(r.status_code, 302)

        assignment = reload_db_objects(assignment)
        self.assertEqual(assignment.state_id, 'no-response')

        self.assertEqual(len(outbox), 1)
        self.assertIn(assignment.reviewer.address,  outbox[0]["To"])
        self.assertNotIn('<reviewsecretary@example.com>', outbox[0]["To"])
        self.assertIn('Reviewer assignment marked no-response', outbox[0]['Subject'])

    def test_withdraw_assignment(self):
        assignment = ReviewAssignmentFactory()
        secr = RoleFactory(group=assignment.review_request.team,person__user__username='reviewsecretary',person__user__email='reviewsecretary@example.com',name_id='secr').person
        url = urlreverse('ietf.doc.views_review.withdraw_reviewer_assignment', kwargs={"name": assignment.review_request.doc.name, "assignment_id": assignment.pk})

        login_testing_unauthorized(self, secr.user.username, url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        r=self.client.post(url, data={"action":"withdraw"})
        self.assertEqual(r.status_code, 302)

        assignment = reload_db_objects(assignment)
        self.assertEqual(assignment.state_id, 'withdrawn')

    def test_review_wish_add(self):
        doc = DocumentFactory()
        team = ReviewTeamFactory()
        reviewer = RoleFactory(group=team, name_id='reviewer').person
        url = urlreverse('ietf.doc.views_review.review_wish_add', kwargs={'name': doc.name})
        
        login_testing_unauthorized(self, reviewer.user.username, url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        
        # As this reviewer is only on a single team, posting without data should work
        r = self.client.post(url + '?next=/redirect-url')
        self.assertRedirects(r, '/redirect-url', fetch_redirect_response=False)
        self.assertTrue(ReviewWish.objects.get(person=reviewer, doc=doc, team=team))

        # Try again with a reviewer on multiple teams, requiring team selection.
        # This also uses an invalid redirect URL that should be ignored.
        ReviewWish.objects.all().delete()
        team2 = ReviewTeamFactory()
        RoleFactory(group=team2, person=reviewer, name_id='reviewer')

        r = self.client.post(url + '?next=http://example.com/')
        self.assertEqual(r.status_code, 200)  # Missing team parameter
        
        r = self.client.post(url + '?next=http://example.com/', data={'team': team2.pk})
        self.assertRedirects(r, doc.get_absolute_url(), fetch_redirect_response=False)
        self.assertTrue(ReviewWish.objects.get(person=reviewer, doc=doc, team=team2))

    def test_review_wishes_remove(self):
        doc = DocumentFactory()
        team = ReviewTeamFactory()
        reviewer = RoleFactory(group=team, name_id='reviewer').person
        ReviewWish.objects.create(person=reviewer, doc=doc, team=team)
        url = urlreverse('ietf.doc.views_review.review_wishes_remove', kwargs={'name': doc.name})

        login_testing_unauthorized(self, reviewer.user.username, url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        r = self.client.post(url + '?next=/redirect-url')
        self.assertRedirects(r, '/redirect-url', fetch_redirect_response=False)
        self.assertFalse(ReviewWish.objects.all())

        # Try again with an invalid redirect URL that should be ignored.
        ReviewWish.objects.create(person=reviewer, doc=doc, team=team)
        r = self.client.post(url + '?next=http://example.com')
        self.assertRedirects(r, doc.get_absolute_url(), fetch_redirect_response=False)
        self.assertFalse(ReviewWish.objects.all())
