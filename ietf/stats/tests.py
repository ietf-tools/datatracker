# Copyright The IETF Trust 2016-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import calendar
import datetime
import json

from mock import patch
from pyquery import PyQuery
from requests import Response

import debug    # pyflakes:ignore

from django.urls import reverse as urlreverse

from ietf.utils.test_utils import login_testing_unauthorized, TestCase
import ietf.stats.views


from ietf.group.factories import RoleFactory
from ietf.meeting.factories import MeetingFactory
from ietf.person.factories import PersonFactory
from ietf.review.factories import ReviewRequestFactory, ReviewerSettingsFactory, ReviewAssignmentFactory
from ietf.stats.models import MeetingRegistration
from ietf.stats.tasks import fetch_meeting_attendance_task
from ietf.stats.utils import get_meeting_registration_data, FetchStats, fetch_attendance_from_meetings
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

    @patch('requests.get')
    def test_get_meeting_registration_data(self, mock_get):
        '''Test function to get reg data.  Confirm leading/trailing spaces stripped'''
        person = PersonFactory()
        data = {
            'LastName': person.last_name() + ' ',
            'FirstName': person.first_name(),
            'Company': 'ABC',
            'Country': 'US',
            'Email': person.email().address,
            'RegType': 'onsite',
            'TicketType': 'week_pass',
            'CheckedIn': 'True',
        }
        data2 = data.copy()
        data2['RegType'] = 'hackathon'
        response_a = Response()
        response_a.status_code = 200
        response_a._content = json.dumps([data, data2]).encode('utf8')
        # second response one less record, it's been deleted
        response_b = Response()
        response_b.status_code = 200
        response_b._content = json.dumps([data]).encode('utf8')
        # mock_get.return_value = response
        mock_get.side_effect = [response_a, response_b]
        meeting = MeetingFactory(type_id='ietf', date=datetime.date(2016, 7, 14), number="96")
        get_meeting_registration_data(meeting)
        query = MeetingRegistration.objects.filter(
            first_name=person.first_name(),
            last_name=person.last_name(),
            country_code='US')
        self.assertEqual(query.count(), 2)
        self.assertEqual(query.filter(reg_type='onsite').count(), 1)
        self.assertEqual(query.filter(reg_type='hackathon').count(), 1)
        onsite = query.get(reg_type='onsite')
        self.assertEqual(onsite.ticket_type, 'week_pass')
        self.assertEqual(onsite.checkedin, True)
        # call a second time to test delete
        get_meeting_registration_data(meeting)
        query = MeetingRegistration.objects.filter(meeting=meeting, email=person.email())
        self.assertEqual(query.count(), 1)
        self.assertEqual(query.filter(reg_type='onsite').count(), 1)
        self.assertEqual(query.filter(reg_type='hackathon').count(), 0)

    @patch('requests.get')
    def test_get_meeting_registration_data_duplicates(self, mock_get):
        '''Test that get_meeting_registration_data does not create duplicate
           MeetingRegistration records
        '''
        person = PersonFactory()
        data = {
            'LastName': person.last_name() + ' ',
            'FirstName': person.first_name(),
            'Company': 'ABC',
            'Country': 'US',
            'Email': person.email().address,
            'RegType': 'onsite',
            'TicketType': 'week_pass',
            'CheckedIn': 'True',
        }
        data2 = data.copy()
        data2['RegType'] = 'hackathon'
        response = Response()
        response.status_code = 200
        response._content = json.dumps([data, data2, data]).encode('utf8')
        mock_get.return_value = response
        meeting = MeetingFactory(type_id='ietf', date=datetime.date(2016, 7, 14), number="96")
        self.assertEqual(MeetingRegistration.objects.count(), 0)
        get_meeting_registration_data(meeting)
        query = MeetingRegistration.objects.all()
        self.assertEqual(query.count(), 2)

    @patch("ietf.stats.utils.get_meeting_registration_data")
    def test_fetch_attendance_from_meetings(self, mock_get_mtg_reg_data):
        mock_meetings = [object(), object(), object()]
        mock_get_mtg_reg_data.side_effect = (
            (1, 2, 3),
            (4, 5, 6),
            (7, 8, 9),
        )
        stats = fetch_attendance_from_meetings(mock_meetings)
        self.assertEqual(
            [mock_get_mtg_reg_data.call_args_list[n][0][0] for n in range(3)],
            mock_meetings,
        )
        self.assertEqual(
            stats,
            [
                FetchStats(1, 2, 3),
                FetchStats(4, 5, 6),
                FetchStats(7, 8, 9),
            ]
        )


class TaskTests(TestCase):
    @patch("ietf.stats.tasks.fetch_attendance_from_meetings")
    def test_fetch_meeting_attendance_task(self, mock_fetch_attendance):
        today = date_today()
        meetings = [
            MeetingFactory(type_id="ietf", date=today - datetime.timedelta(days=1)),
            MeetingFactory(type_id="ietf", date=today - datetime.timedelta(days=2)),
            MeetingFactory(type_id="ietf", date=today - datetime.timedelta(days=3)),
        ]
        mock_fetch_attendance.return_value = [FetchStats(1,2,3), FetchStats(1,2,3)]

        fetch_meeting_attendance_task()
        self.assertEqual(mock_fetch_attendance.call_count, 1)
        self.assertCountEqual(mock_fetch_attendance.call_args[0][0], meetings[0:2])

        # test handling of RuntimeError
        mock_fetch_attendance.reset_mock()
        mock_fetch_attendance.side_effect = RuntimeError
        fetch_meeting_attendance_task()
        self.assertTrue(mock_fetch_attendance.called)
        # Good enough that we got here without raising an exception
