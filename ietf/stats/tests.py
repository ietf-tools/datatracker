# Copyright The IETF Trust 2016-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import calendar
import json
import datetime
import re

import factory
from pyquery import PyQuery

import debug    # pyflakes:ignore

from django.urls import reverse as urlreverse
from django.utils import timezone

from ietf.utils.test_utils import login_testing_unauthorized, TestCase
import ietf.stats.views

from ietf.group.factories import RoleFactory
from ietf.person.factories import PersonFactory
from ietf.doc.factories import WgDraftFactory, WgRfcFactory, DocumentAuthorFactory, DocumentFactory, DocEventFactory, NewRevisionDocEventFactory
from ietf.group.factories import GroupFactory
from ietf.review.factories import ReviewRequestFactory, ReviewerSettingsFactory, ReviewAssignmentFactory
from ietf.meeting.tests_models import MeetingFactory, RegistrationFactory
from ietf.stats.factories import AffiliationIgnoredEndingFactory, AffiliationMainNameFactory
from ietf.utils.timezone import date_today
class StatisticsTests(TestCase):
    def test_stats_index(self):
        # Create a meeting as the index page needs to know the current meeting
        MeetingFactory(type_id='ietf', number='124', date=timezone.now())
        url = urlreverse(ietf.stats.views.stats_index)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

    def test_document_stats(self):
        timeNow = timezone.now()
        yearNow = timeNow.year
        time1960 = datetime.datetime(1960, 7, 26, 12, 13, 14, tzinfo=datetime.timezone.utc)
        year1960 = time1960.year

        # Let's create some WGs
        group1 = GroupFactory(type_id="wg")
        group2 = GroupFactory(type_id="wg")

        # Let's create some RFC and drafts with publication dates
        rfcPsGroup1 = WgRfcFactory(std_level_id='ps', group=group1)
        DocEventFactory(type='published_rfc', doc=rfcPsGroup1, time=time1960)
        rfcExpGroup1 = WgRfcFactory(std_level_id='exp', group=group1)
        DocEventFactory(type='published_rfc', doc=rfcExpGroup1, time=time1960)
        rfcInfGroup2 = WgRfcFactory(std_level_id='inf', group=group2)
        DocEventFactory(type='published_rfc', doc=rfcInfGroup2, time=timeNow)
        rfcBcpIAB1 = WgRfcFactory(std_level_id='bcp', stream_id='iab')
        DocEventFactory(type='published_rfc', doc=rfcBcpIAB1, time=time1960)
        rfcBcpIAB2 = WgRfcFactory(std_level_id='bcp', stream_id='iab')
        DocEventFactory(type='published_rfc', doc=rfcBcpIAB2, time=time1960)
        wgDraftPsGroup1 = WgDraftFactory(name='draft-ietf-' + group1.acronym + '-random-thing', intended_std_level_id='ps', group=group1)
        NewRevisionDocEventFactory(doc=wgDraftPsGroup1, time=time1960)
        wgDraftPsGroup2 = WgDraftFactory(name='draft-ietf-' + group2.acronym + '-random-thing', intended_std_level_id='inf', group=group2)
        NewRevisionDocEventFactory(doc=wgDraftPsGroup2, time=timeNow)
        draftExp = DocumentFactory(type_id='draft', intended_std_level_id='exp')
        NewRevisionDocEventFactory(doc=draftExp, time=timeNow)

        # Let's create some authors, first get some test strings for affiliations and countries
        affiliation = factory.Faker('company').evaluate(None, None, {'locale': None})
        # Sometimes the factory adds "LLC" or some other suffix, causing problem in the tests
        # below as another ", LLC" is added. Let's only take the first word of the affiliation
        # up to a space or ","
        if re.sub(r',?\s*\S+\s*$', '', affiliation) != '':
            affiliation = re.sub(r',?\s*\S+\s*$', '', affiliation)
        country = factory.Faker('country').evaluate(None, None, {'locale': None})

        # Create the various aliases ancilliary content
        AffiliationIgnoredEndingFactory(ending='llc\\.?')
        AffiliationIgnoredEndingFactory(ending='ag\\.?')
        AffiliationIgnoredEndingFactory(ending='inc\\.?')
        AffiliationIgnoredEndingFactory(ending='corp\\.?')
        AffiliationMainNameFactory(main_name='Cisco')

        DocumentAuthorFactory(document=rfcPsGroup1, affiliation=affiliation, country=country)
        DocumentAuthorFactory(document=rfcExpGroup1, affiliation=affiliation + ', LLC', country=country)
        DocumentAuthorFactory(document=rfcExpGroup1, affiliation=factory.Faker('company'), country=factory.Faker('country'))
        DocumentAuthorFactory(document=wgDraftPsGroup1, affiliation=affiliation + ' AG', country=country)
        DocumentAuthorFactory(document=rfcInfGroup2, affiliation='CiScO InC.', country=country)
        DocumentAuthorFactory(document=wgDraftPsGroup2, affiliation='CISCO corp.', country='belgique')
        DocumentAuthorFactory(document=wgDraftPsGroup2, affiliation=affiliation, country=country)
        DocumentAuthorFactory(document=rfcBcpIAB1, affiliation='CiScO PTY LTD', country='UnItEd StAtEs')
        DocumentAuthorFactory(document=rfcBcpIAB2, affiliation=affiliation, country='usa')
        DocumentAuthorFactory(document=draftExp, affiliation=affiliation + ',inc', country='U.S.A.')

        # Test#1 the documents specific statistics: for RFC about the level
        r = self.client.get(urlreverse(ietf.stats.views.documents_timeline, kwargs={"doc_type": "rfc", "stats_type": "level"}))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Specific lines can be removed")
        self.assertContains(r, "Rfc Documents by Level")
        # Extract the JSON embedded in the response
        pq = PyQuery(r.content)
        chart_data = json.loads(pq.find("script#chart_data").text())
        self.assertTrue(chart_data["labels"] == [year1960, yearNow])
        self.assertTrue(
            any(
                ds["label"] == "inf" and ds["data"] == [0, 1]
                for ds in chart_data["datasets"]
            )
        )
        self.assertTrue(
            any(
                ds["label"] == "bcp" and ds["data"] == [2, 0]
                for ds in chart_data["datasets"]
            )
        )

        # Test#2 the documents specific statistics: for RFC about the WG
        r = self.client.get(urlreverse(ietf.stats.views.documents_timeline, kwargs={"doc_type": "rfc", "stats_type": "wg"}))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Rfc Documents by Wg")
        # Extract the JSON embedded in the response
        pq = PyQuery(r.content)
        chart_data = json.loads(pq.find("script#chart_data").text())
        self.assertTrue(chart_data["labels"] == [year1960, yearNow])
        self.assertTrue(
            any(
                ds["label"] == group1.name and ds["data"] == [2, 0]
                for ds in chart_data["datasets"]
            )
        )

        # Test#3 the documents specific statistics: for drafts about the streams
        r = self.client.get(urlreverse(ietf.stats.views.documents_timeline, kwargs={"doc_type": "draft", "stats_type": "stream"}))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Draft Documents by Stream")
        # Extract the JSON embedded in the response
        pq = PyQuery(r.content)
        chart_data = json.loads(pq.find("script#chart_data").text())
        self.assertTrue(chart_data["labels"] == [yearNow])
        self.assertTrue(
            any(
                ds["label"] == "IETF" and ds["data"] == [2]
                for ds in chart_data["datasets"]
            )
        )
        self.assertTrue(
            any(
                ds["label"] == "Unspecified" and ds["data"] == [1]
                for ds in chart_data["datasets"]
            )
        )

        # Test#4 the authors specific statistics: for all docs about the countries
        r = self.client.get(urlreverse(ietf.stats.views.authors_timeline, kwargs={"doc_type": "all", "stats_type": "country"}))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "All Authors by Country")
        # Extract the JSON embedded in the response
        pq = PyQuery(r.content)
        chart_data = json.loads(pq.find("script#chart_data").text())
        self.assertTrue(chart_data["labels"] == [year1960, yearNow])
        self.assertTrue(
            any(
                ds["label"] == "United States of America" and ds["data"] == [2, 1]
                for ds in chart_data["datasets"]
            )
        )
        self.assertTrue(
            any(
                ds["label"] == "Belgium" and ds["data"] == [0, 1]
                for ds in chart_data["datasets"]
            )
        )

        # Test#5 the authors specific statistics: for all all rfcs about the affiliation
        r = self.client.get(urlreverse(ietf.stats.views.authors_timeline, kwargs={"doc_type": "rfc", "stats_type": "affiliation"}))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Rfc Authors by Affiliation")
        # Extract the JSON embedded in the response
        pq = PyQuery(r.content)
        chart_data = json.loads(pq.find("script#chart_data").text())
        self.assertTrue(chart_data["labels"] == [year1960, yearNow])
        self.assertTrue(
            any(
                ds["label"].casefold() == affiliation.casefold() and ds["data"] == [3, 0]
                for ds in chart_data["datasets"]
            )
        )
        self.assertTrue(
            any(
                ds["label"] == "Cisco" and ds["data"] == [1, 1]
                for ds in chart_data["datasets"]
            )
        )
        self.assertTrue(
            any(
                ds["label"] == "Other" and ds["data"] == [0, 0]
                for ds in chart_data["datasets"]
            )
        )

        # Test#6 the authors specific statistics: for all WG drafts about the country
        r = self.client.get(urlreverse(ietf.stats.views.authors_timeline, kwargs={"doc_type": "wg-draft", "stats_type": "country"}))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Wg-Draft Authors by Country")
        # Extract the JSON embedded in the response
        pq = PyQuery(r.content)
        chart_data = json.loads(pq.find("script#chart_data").text())
        self.assertTrue(chart_data["labels"] == [yearNow])
        # Test failing on line 209
        print("L207, chart_data=", chart_data)
        self.assertTrue(
            any(
                ds["label"].casefold() == country.casefold() and ds["data"] == [2]
                for ds in chart_data["datasets"]
            )
        )
        self.assertTrue(
            any(
                ds["label"] == "Belgium" and ds["data"] == [1]
                for ds in chart_data["datasets"]
            )
        )

        # Test#7 the authors specific statistics global
        r = self.client.get(urlreverse(ietf.stats.views.authors_total, kwargs={"doc_type": "draft", "stats_type": "country"}))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Draft Authors by Country")
        # Extract the JSON embedded in the response
        pq = PyQuery(r.content)
        chart_data = json.loads(pq.find("script#chart_data").text())
        self.assertTrue('Belgium' in chart_data["labels"])
        self.assertTrue('United States of America' in chart_data["labels"])
        self.assertTrue(country in chart_data["labels"])
        USA_index = chart_data["labels"].index('United States of America')
        # Let's check whether USA has indeed 1 
        self.assertTrue(chart_data["datasets"][0]["data"][USA_index] == 1)

        # Test#8 the documents specific statistics global
        r = self.client.get(urlreverse(ietf.stats.views.documents_total, kwargs={"doc_type": "draft", "stats_type": "wg"}))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Draft Documents by Wg")
        # Extract the JSON embedded in the response
        pq = PyQuery(r.content)
        chart_data = json.loads(pq.find("script#chart_data").text())
        self.assertTrue(group1.name in chart_data["labels"])
        individual_index = chart_data["labels"].index('Individual submissions')
        # Let's check whether USA has indeed 1 
        self.assertTrue(chart_data["datasets"][0]["data"][individual_index] == 1)

    def test_meeting_stats(self):
        meeting124 = MeetingFactory(type_id='ietf', number='124', date=timezone.now())
        meeting125 = MeetingFactory(type_id='ietf', number='125', date=timezone.now() + datetime.timedelta(days=120))
        RegistrationFactory.create_batch(15, meeting=meeting124, with_ticket={'attendance_type_id': 'onsite'}, attended=True)
        RegistrationFactory(meeting=meeting124, with_ticket={'attendance_type_id': 'onsite'}, attended=False)
        RegistrationFactory.create_batch(14, meeting=meeting124, with_ticket={'attendance_type_id': 'remote'}, attended=True)
        RegistrationFactory(meeting=meeting124, with_ticket={'attendance_type_id': 'remote'}, attended=False)
        RegistrationFactory.create_batch(15, meeting=meeting125, affiliation='Test LLC', with_ticket={'attendance_type_id': 'remote'}, attended=False)
        RegistrationFactory.create_batch(25, meeting=meeting125, affiliation='Example, Ltd', with_ticket={'attendance_type_id': 'onsite'}, attended=False)

        # Create the various aliases ancilliary content
        AffiliationIgnoredEndingFactory(ending='llc\\.?')
        AffiliationIgnoredEndingFactory(ending='ltd\\.?')

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
