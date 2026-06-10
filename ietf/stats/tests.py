# Copyright The IETF Trust 2016-2026, All Rights Reserved

import calendar
import csv
import datetime
import io
import json

from django.http import Http404
from pyquery import PyQuery

import debug    # pyflakes:ignore

from django.test import RequestFactory
from django.urls import reverse as urlreverse
from django.utils import timezone

from ietf.meeting.models import Meeting
from ietf.utils.test_utils import login_testing_unauthorized, TestCase
import ietf.stats.views


from ietf.doc.factories import NewRevisionDocEventFactory
from ietf.group.factories import GroupFactory, RoleFactory
from ietf.person.factories import EmailFactory, PersonFactory
from ietf.review.factories import ReviewRequestFactory, ReviewerSettingsFactory, ReviewAssignmentFactory
from ietf.meeting.tests_models import MeetingFactory, RegistrationFactory
from ietf.submit.factories import SubmissionFactory
from ietf.utils.timezone import date_today


class StatisticsTests(TestCase):
    def test_stats_index(self):
        # Create a meeting as the index page needs to know the current meeting
        MeetingFactory(type_id='ietf', number='124', date=timezone.now())
        url = urlreverse(ietf.stats.views.stats_index)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

    def test_document_stats(self):
        # Create a meeting as the index page needs to know the current meeting
        MeetingFactory(type_id='ietf', number='124', date=timezone.now())
        r = self.client.get(urlreverse(ietf.stats.views.document_stats))
        self.assertRedirects(r, urlreverse(ietf.stats.views.stats_index))

    def test_meeting_stats(self):
        meeting124 = MeetingFactory(type_id='ietf', number='124', date=timezone.now())
        meeting125 = MeetingFactory(type_id='ietf', number='125', date=timezone.now() + datetime.timedelta(days=120))
        RegistrationFactory.create_batch(15, meeting=meeting124, with_ticket={'attendance_type_id': 'onsite'}, attended=True)
        RegistrationFactory(meeting=meeting124, with_ticket={'attendance_type_id': 'onsite'}, attended=False)
        RegistrationFactory.create_batch(14, meeting=meeting124, with_ticket={'attendance_type_id': 'remote'}, attended=True)
        RegistrationFactory(meeting=meeting124, with_ticket={'attendance_type_id': 'remote'}, attended=False)
        RegistrationFactory.create_batch(15, meeting=meeting125, affiliation='Test LLC', with_ticket={'attendance_type_id': 'remote'}, attended=False)
        RegistrationFactory.create_batch(25, meeting=meeting125, affiliation='Example, Ltd', with_ticket={'attendance_type_id': 'onsite'}, attended=False)
        # Test the meeting specific statitistics per affiliation and per country
        r = self.client.get(urlreverse(ietf.stats.views.meeting_stats, kwargs={"meeting_number": "124", "stats_type": "affiliation"}))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Total Registrations by Affiliation (31 in total)")
        self.assertContains(r, "In Person Registrations by Affiliation (16 in total)")
        self.assertContains(r, "/stats/meeting/124/affiliation")
        self.assertContains(r, "/stats/meeting/125/affiliation")
        r = self.client.get(urlreverse(ietf.stats.views.meeting_stats, kwargs={"meeting_number": "124", "stats_type": "country"}))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Total Registrations by Country (31 in total)")
        self.assertContains(r, "In Person Registrations by Country (16 in total)")
        self.assertContains(r, "/stats/meeting/124/country")
        self.assertContains(r, "/stats/meeting/125/country")
        # Test the meetings timeline per country
        r = self.client.get(urlreverse(ietf.stats.views.meetings_timeline, kwargs={"stats_type": "country"}))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "/stats/meeting/124/country")
        self.assertContains(r, "/stats/meeting/125/country")
        self.assertContains(r, "This page provides a timeline of meeting registrations by country")
        # Test the meetings timeline per affiliation
        r = self.client.get(urlreverse(ietf.stats.views.meetings_timeline, kwargs={"stats_type": "affiliation"}))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "/stats/meeting/124/affiliation")
        self.assertContains(r, "/stats/meeting/125/affiliation")
        self.assertContains(r, "This page provides a timeline of meeting registrations by affiliation")
        # Extract the JSON embedded in the response
        pq = PyQuery(r.content)
        in_person_data = json.loads(pq.find("script#in-person-chart-data").text())
        self.assertTrue(
            any(
                ds["label"] == "Example" and ds["data"] == [0, 25]
                for ds in in_person_data["datasets"]
            )
        )
        # Test the global meetings timeline
        r = self.client.get(urlreverse(ietf.stats.views.meetings_timeline, kwargs={"stats_type": "total"}))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "/stats/meeting/124/country")
        self.assertContains(r, "/stats/meeting/125/country")
        self.assertContains(r, "This page provides a timeline of meeting registrations.")

    def test_meeting_stats_for_bad_meeting(self):
        self.assertFalse(Meeting.objects.filter(number=676767).exists())
        for stats_type in ["affiliation", "country"]:
            r = self.client.get(
                urlreverse(
                    "ietf.stats.views.meeting_stats",
                    kwargs={"meeting_number": 676767, "stats_type": stats_type},
                )
            )
            self.assertEqual(r.status_code, 404)

            # We don't have a URL for an interim, but make sure the view will 404 if
            # somehow a non-interim gets selected...
            interim_num = MeetingFactory(type_id="interim").number
            request_factory = RequestFactory()
            with self.assertRaises(Http404):
                ietf.stats.views.meeting_stats(
                    request_factory.get(f"/stats/meeting/{interim_num}/{stats_type}"),
                    meeting_number=interim_num,
                    stats_type=stats_type,
                )

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


class AnnualReportInputsTests(TestCase):
    def setUp(self):
        super().setUp()
        llc_staff = GroupFactory(acronym="llc-staff", type_id="team")
        self.member = PersonFactory()
        RoleFactory(group=llc_staff, name_id="member", person=self.member)
        self.non_member = PersonFactory()

    def _member_login(self):
        self.client.login(
            username=self.member.user.username,
            password=f"{self.member.user.username}+password",
        )

    def test_access_unauthenticated(self):
        url = urlreverse(ietf.stats.views.annual_report_inputs, kwargs={"year": "2024"})
        r = self.client.get(url)
        self.assertEqual(r.status_code, 302)
        self.assertIn("/accounts/login", r["Location"])

    def test_access_non_member_forbidden(self):
        url = urlreverse(ietf.stats.views.annual_report_inputs, kwargs={"year": "2024"})
        self.client.login(
            username=self.non_member.user.username,
            password=f"{self.non_member.user.username}+password",
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 403)

    def test_access_member_allowed(self):
        self._member_login()
        url = urlreverse(ietf.stats.views.annual_report_inputs, kwargs={"year": "2024"})
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

    def test_default_year(self):
        self._member_login()
        url = urlreverse(ietf.stats.views.annual_report_inputs)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["year"], datetime.date.today().year - 1)

    def test_year_param_redirects_to_year_url(self):
        self._member_login()
        url = urlreverse(ietf.stats.views.annual_report_inputs)
        r = self.client.get(url, {"year": "2022"})
        self.assertRedirects(
            r,
            urlreverse(ietf.stats.views.annual_report_inputs, kwargs={"year": "2022"}),
        )

    def test_summary_counts(self):
        self._member_login()
        year = 2021
        # author1 has a matching Person record; author2 does not
        EmailFactory(address="author1@example.com")
        sub = SubmissionFactory(
            state_id="posted",
            submission_date=datetime.date(year, 6, 1),
            submitter_email="submitter@example.com",
        )
        sub.authors = [
            {"name": "Author One", "email": "author1@example.com", "affiliation": "", "country": "", "errors": []},
            {"name": "Author Two", "email": "author2@example.com", "affiliation": "", "country": "", "errors": []},
        ]
        sub.save()
        NewRevisionDocEventFactory(
            time=datetime.datetime(year, 6, 1, tzinfo=datetime.timezone.utc),
            doc__type_id="draft",
        )
        NewRevisionDocEventFactory(
            time=datetime.datetime(year, 6, 1, tzinfo=datetime.timezone.utc),
            doc__type_id="draft",
        )
        # Same draft, second revision — should count once
        extra = NewRevisionDocEventFactory(
            time=datetime.datetime(year, 9, 1, tzinfo=datetime.timezone.utc),
            doc__type_id="draft",
        )
        NewRevisionDocEventFactory(
            time=datetime.datetime(year, 9, 15, tzinfo=datetime.timezone.utc),
            doc=extra.doc,
        )

        url = urlreverse(ietf.stats.views.annual_report_inputs, kwargs={"year": str(year)})
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["year"], year)
        self.assertEqual(r.context["author_count"], 2)
        self.assertEqual(r.context["author_person_count"], 1)
        self.assertEqual(r.context["author_noperson_count"], 1)
        self.assertEqual(r.context["submitter_count"], 1)
        self.assertEqual(r.context["submitter_person_count"], 0)
        self.assertEqual(r.context["submitter_noperson_count"], 1)
        self.assertEqual(r.context["draft_count"], 3)

    def test_download_authors_csv(self):
        self._member_login()
        year = 2020
        sub = SubmissionFactory(
            state_id="posted",
            submission_date=datetime.date(year, 4, 1),
        )
        sub.authors = [
            {"name": "Author", "email": "csvauthor@example.com", "affiliation": "", "country": "", "errors": []},
        ]
        sub.save()

        url = urlreverse(ietf.stats.views.annual_report_inputs, kwargs={"year": str(year)})
        r = self.client.get(url, {"download": "authors"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "text/csv")
        self.assertIn(f"authors-{year}.csv", r["Content-Disposition"])
        rows = list(csv.reader(io.StringIO(r.content.decode())))
        self.assertEqual(len(rows), 1)
        self.assertIn("csvauthor@example.com", rows[0])

    def test_download_submitters_csv(self):
        self._member_login()
        year = 2020
        SubmissionFactory(
            state_id="posted",
            submission_date=datetime.date(year, 4, 1),
            submitter_email="csvsubmitter@example.com",
        )

        url = urlreverse(ietf.stats.views.annual_report_inputs, kwargs={"year": str(year)})
        r = self.client.get(url, {"download": "submitters"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "text/csv")
        self.assertIn(f"submitters-{year}.csv", r["Content-Disposition"])
        rows = list(csv.reader(io.StringIO(r.content.decode())))
        self.assertEqual(len(rows), 1)
        self.assertIn("csvsubmitter@example.com", rows[0])
