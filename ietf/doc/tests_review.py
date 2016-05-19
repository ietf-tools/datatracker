# -*- coding: utf-8 -*-

import datetime
from pyquery import PyQuery

from django.core.urlresolvers import reverse as urlreverse

import debug                            # pyflakes:ignore

from ietf.review.models import ReviewRequest
from ietf.person.models import Person
from ietf.group.models import Group, Role
from ietf.name.models import ReviewResultName
from ietf.utils.test_utils import TestCase
from ietf.utils.test_data import make_test_data
from ietf.utils.test_utils import login_testing_unauthorized

def make_review_data():
    review_team = Group.objects.create(state_id="active", acronym="reviewteam", name="Review Team", type_id="team")
    review_team.reviewresultname_set.add(ReviewResultName.objects.filter(slug__in=["issues", "ready-issues", "ready", "not-ready"]))

    p = Person.objects.get(user__username="plain")
    Role.objects.create(name_id="reviewer", person=p, email=p.email_set.first(), group=review_team)

    return review_team

class ReviewTests(TestCase):
    def test_request_review(self):
        doc = make_test_data()
        review_team = make_review_data()

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

        req = ReviewRequest.objects.get(doc=doc)
        self.assertEqual(req.deadline.date(), deadline_date)
        self.assertEqual(req.deadline.time(), datetime.time(23, 59, 59))
        self.assertEqual(req.state_id, "requested")
        self.assertEqual(req.team, review_team)
        self.assertEqual(req.requested_rev, "01")
        self.assertEqual(doc.latest_event().type, "requested_review")

    def test_request_review_by_reviewer(self):
        doc = make_test_data()
        review_team = make_review_data()

        url = urlreverse('ietf.doc.views_review.request_review', kwargs={ "name": doc.name })
        login_testing_unauthorized(self, "plain", url)

        # post request
        deadline_date = datetime.date.today() + datetime.timedelta(days=10)

        r = self.client.post(url, {
            "type": "early",
            "team": review_team.pk,
            "deadline_date": deadline_date.isoformat(),
            "requested_rev": "01"
        })
        self.assertEqual(r.status_code, 302)

        req = ReviewRequest.objects.get(doc=doc)
        self.assertEqual(req.state_id, "requested")
        self.assertEqual(req.team, review_team)

    def test_doc_page(self):
        pass

