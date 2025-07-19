# Copyright The IETF Trust 2016-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import calendar
import json

from pyquery import PyQuery

import debug    # pyflakes:ignore

from django.urls import reverse as urlreverse

from ietf.utils.test_utils import login_testing_unauthorized, TestCase
import ietf.stats.views


from ietf.group.factories import RoleFactory
from ietf.person.factories import PersonFactory
from ietf.review.factories import ReviewRequestFactory, ReviewerSettingsFactory, ReviewAssignmentFactory
from ietf.utils.timezone import date_today


class StatisticsTests(TestCase):
    def test_stats_index(self):
        url = urlreverse(ietf.stats.views.stats_index)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

    def test_document_stats(self):
        r = self.client.get(urlreverse("ietf.stats.views.document_stats"))
        self.assertRedirects(r, urlreverse("ietf.stats.views.stats_index"))


    def test_meeting_stats(self):
        r = self.client.get(urlreverse("ietf.stats.views.meeting_stats"))
        self.assertRedirects(r, urlreverse("ietf.stats.views.stats_index"))

                
    def test_known_country_list(self):
        # check redirect
        url = urlreverse(ietf.stats.views.known_countries_list)

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "United States")

    def test_review_stats(self):
        reviewer = PersonFactory()
        review_req = ReviewRequestFactory(state_id='assigned')
        ReviewAssignmentFactory(review_request=review_req, state_id='assigned', reviewer=reviewer.email_set.first())
        RoleFactory(group=review_req.team,name_id='reviewer',person=reviewer)
        ReviewerSettingsFactory(team=review_req.team, person=reviewer)
        PersonFactory(user__username='plain')

        # check redirect
        url = urlreverse(ietf.stats.views.review_stats)

        login_testing_unauthorized(self, "secretary", url)

        completion_url = urlreverse(ietf.stats.views.review_stats, kwargs={ "stats_type": "completion" })

        r = self.client.get(url)
        self.assertEqual(r.status_code, 302)
        self.assertTrue(completion_url in r["Location"])

        self.client.logout()
        self.client.login(username="plain", password="plain+password")
        r = self.client.get(completion_url)
        self.assertEqual(r.status_code, 403)

        # check tabular
        self.client.login(username="secretary", password="secretary+password")
        for stats_type in ["completion", "results", "states"]:
            url = urlreverse(ietf.stats.views.review_stats, kwargs={ "stats_type": stats_type })
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            if stats_type != "results":
                self.assertTrue(q('.review-stats td:contains("1")'))

        # check stacked chart
        expected_date = date_today().replace(day=1)
        expected_js_timestamp = calendar.timegm(expected_date.timetuple()) * 1000
        url = urlreverse(ietf.stats.views.review_stats, kwargs={ "stats_type": "time" })
        url += "?team={}".format(review_req.team.acronym)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(json.loads(r.context['data']), [
            {"label": "in time", "color": "#3d22b3", "data": [[expected_js_timestamp, 0]]},
            {"label": "late", "color": "#b42222", "data": [[expected_js_timestamp, 0]]}
        ])
        q = PyQuery(r.content)
        self.assertTrue(q('#stats-time-graph'))

        # check non-stacked chart
        url = urlreverse(ietf.stats.views.review_stats, kwargs={ "stats_type": "time" })
        url += "?team={}".format(review_req.team.acronym)
        url += "&completion=not_completed"
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(json.loads(r.context['data']), [{"color": "#3d22b3", "data": [[expected_js_timestamp, 0]]}])
        q = PyQuery(r.content)
        self.assertTrue(q('#stats-time-graph'))

        # check reviewer level
        url = urlreverse(ietf.stats.views.review_stats, kwargs={ "stats_type": "completion", "acronym": review_req.team.acronym })
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(q('.review-stats td:contains("1")'))
