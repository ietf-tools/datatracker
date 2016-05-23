# -*- coding: utf-8 -*-

import datetime

from django.core.urlresolvers import reverse as urlreverse

import debug                            # pyflakes:ignore

from ietf.review.models import ReviewRequest, Reviewer
from ietf.person.models import Person
from ietf.group.models import Group, Role
from ietf.name.models import ReviewResultName, ReviewRequestStateName
from ietf.utils.test_utils import TestCase
from ietf.utils.test_data import make_test_data
from ietf.utils.test_utils import login_testing_unauthorized, unicontent, reload_db_objects
from ietf.utils.mail import outbox, empty_outbox


def make_review_data(doc):
    team = Group.objects.create(state_id="active", acronym="reviewteam", name="Review Team", type_id="team")
    team.reviewresultname_set.add(ReviewResultName.objects.filter(slug__in=["issues", "ready-issues", "ready", "not-ready"]))

    p = Person.objects.get(user__username="plain")
    role = Role.objects.create(name_id="reviewer", person=p, email=p.email_set.first(), group=team)
    Reviewer.objects.create(team=team, person=p, frequency=14, skip_next=0)

    review_req = ReviewRequest.objects.create(
        doc=doc,
        team=team,
        type_id="early",
        deadline=datetime.datetime.now() + datetime.timedelta(days=20),
        state_id="ready",
        reviewer=role,
        reviewed_rev="01",
    )

    p = Person.objects.get(user__username="marschairman")
    role = Role.objects.create(name_id="reviewer", person=p, email=p.email_set.first(), group=team)

    return review_req

class ReviewTests(TestCase):
    def test_request_review(self):
        doc = make_test_data()
        review_req = make_review_data(doc)
        review_team = review_req.team

        url = urlreverse('ietf.doc.views_review.request_review', kwargs={ "name": doc.name })
        login_testing_unauthorized(self, "secretary", url)

        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        deadline_date = datetime.date.today() + datetime.timedelta(days=10)

        # post request
        r = self.client.post(url, {
            "type": "early",
            "team": review_team.pk,
            "deadline_date": deadline_date.isoformat(),
            "requested_rev": "01"
        })
        self.assertEqual(r.status_code, 302)

        req = ReviewRequest.objects.get(doc=doc, state="requested")
        self.assertEqual(req.deadline.date(), deadline_date)
        self.assertEqual(req.deadline.time(), datetime.time(23, 59, 59))
        self.assertEqual(req.team, review_team)
        self.assertEqual(req.requested_rev, "01")
        self.assertEqual(doc.latest_event().type, "requested_review")

    def test_doc_page(self):
        # FIXME: fill in
        pass

    def test_review_request(self):
        doc = make_test_data()
        review_req = make_review_data(doc)

        url = urlreverse('ietf.doc.views_review.review_request', kwargs={ "name": doc.name, "request_id": review_req.pk })

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(review_req.team.acronym.upper() in unicontent(r))

    def test_withdraw_request(self):
        doc = make_test_data()
        review_req = make_review_data(doc)
        review_req.state = ReviewRequestStateName.objects.get(slug="accepted")
        review_req.save()

        withdraw_url = urlreverse('ietf.doc.views_review.withdraw_request', kwargs={ "name": doc.name, "request_id": review_req.pk })


        # follow link
        req_url = urlreverse('ietf.doc.views_review.review_request', kwargs={ "name": doc.name, "request_id": review_req.pk })
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(req_url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(withdraw_url in unicontent(r))
        self.client.logout()

        # get withdraw page
        login_testing_unauthorized(self, "secretary", withdraw_url)
        r = self.client.get(withdraw_url)
        self.assertEqual(r.status_code, 200)

        # withdraw
        r = self.client.post(withdraw_url, { "action": "withdraw" })
        self.assertEqual(r.status_code, 302)

        review_req = reload_db_objects(review_req)
        self.assertEqual(review_req.state_id, "withdrawn")
        e = doc.latest_event()
        self.assertEqual(e.type, "changed_review_request")
        self.assertTrue("Withdrew" in e.desc)

    def test_assign_reviewer(self):
        doc = make_test_data()
        review_req = make_review_data(doc)
        review_req.state = ReviewRequestStateName.objects.get(slug="requested")
        review_req.reviewer = None
        review_req.save()

        assign_url = urlreverse('ietf.doc.views_review.assign_reviewer', kwargs={ "name": doc.name, "request_id": review_req.pk })


        # follow link
        req_url = urlreverse('ietf.doc.views_review.review_request', kwargs={ "name": doc.name, "request_id": review_req.pk })
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(req_url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(assign_url in unicontent(r))
        self.client.logout()

        # get assign page
        login_testing_unauthorized(self, "secretary", assign_url)
        r = self.client.get(assign_url)
        self.assertEqual(r.status_code, 200)

        # assign
        reviewer = Role.objects.filter(name="reviewer", group=review_req.team).first()
        r = self.client.post(assign_url, { "action": "assign", "reviewer": reviewer.pk })
        self.assertEqual(r.status_code, 302)

        review_req = reload_db_objects(review_req)
        self.assertEqual(review_req.state_id, "requested")
        self.assertEqual(review_req.reviewer, reviewer)

        # re-assign
        review_req.state = ReviewRequestStateName.objects.get(slug="accepted")
        review_req.save()
        reviewer = Role.objects.filter(name="reviewer", group=review_req.team).exclude(pk=reviewer.pk).first()
        r = self.client.post(assign_url, { "action": "assign", "reviewer": reviewer.pk })
        self.assertEqual(r.status_code, 302)

        review_req = reload_db_objects(review_req)
        self.assertEqual(review_req.state_id, "requested")
        self.assertEqual(review_req.reviewer, reviewer)

    def test_reject_reviewer_assignment(self):
        doc = make_test_data()
        review_req = make_review_data(doc)
        review_req.state = ReviewRequestStateName.objects.get(slug="accepted")
        review_req.save()

        reject_url = urlreverse('ietf.doc.views_review.reject_reviewer_assignment', kwargs={ "name": doc.name, "request_id": review_req.pk })


        # follow link
        req_url = urlreverse('ietf.doc.views_review.review_request', kwargs={ "name": doc.name, "request_id": review_req.pk })
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(req_url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(reject_url in unicontent(r))
        self.client.logout()

        # get reject page
        login_testing_unauthorized(self, "secretary", reject_url)
        r = self.client.get(reject_url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(unicode(review_req.reviewer.person) in unicontent(r))

        # reject
        empty_outbox()
        r = self.client.post(reject_url, { "action": "reject", "message_to_secretary": "Test message" })
        self.assertEqual(r.status_code, 302)

        review_req = reload_db_objects(review_req)
        self.assertEqual(review_req.state_id, "rejected")
        e = doc.latest_event()
        self.assertEqual(e.type, "changed_review_request")
        self.assertTrue("rejected" in e.desc)
        self.assertEqual(ReviewRequest.objects.filter(doc=review_req.doc, team=review_req.team, state="requested").count(), 1)
        self.assertEqual(len(outbox), 1)
        
