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
from django.contrib.auth.models import User

from ietf.utils.test_utils import login_testing_unauthorized, TestCase
import ietf.stats.views

from ietf.submit.models import Submission
from ietf.doc.factories import WgDraftFactory, WgRfcFactory
from ietf.doc.models import Document, DocAlias, State, RelatedDocument, NewRevisionDocEvent, DocumentAuthor
from ietf.group.factories import RoleFactory
from ietf.meeting.factories import MeetingFactory
from ietf.person.factories import PersonFactory
from ietf.person.models import Person, Email
from ietf.name.models import FormalLanguageName, DocRelationshipName, CountryName
from ietf.review.factories import ReviewRequestFactory, ReviewerSettingsFactory, ReviewAssignmentFactory
from ietf.stats.models import MeetingRegistration, CountryAlias
from ietf.stats.utils import get_meeting_registration_data


class StatisticsTests(TestCase):
    def test_stats_index(self):
        url = urlreverse(ietf.stats.views.stats_index)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

    def test_document_stats(self):
        WgRfcFactory()
        draft = WgDraftFactory()
        DocumentAuthor.objects.create(
            document=draft,
            person=Person.objects.get(email__address="aread@example.org"),
            email=Email.objects.get(address="aread@example.org"),
            country="Germany",
            affiliation="IETF",
            order=1
        )

        # create some data for the statistics
        Submission.objects.create(
            authors=[ { "name": "Some Body", "email": "somebody@example.com", "affiliation": "Some Inc.", "country": "US" }],
            pages=30,
            rev=draft.rev,
            words=4000,
            draft=draft,
            file_types=".txt",
            state_id="posted",
        )

        draft.formal_languages.add(FormalLanguageName.objects.get(slug="xml"))
        Document.objects.filter(pk=draft.pk).update(words=4000)
        # move it back so it shows up in the yearly summaries
        NewRevisionDocEvent.objects.filter(doc=draft, rev=draft.rev).update(
            time=datetime.datetime.now() - datetime.timedelta(days=500))

        referencing_draft = Document.objects.create(
            name="draft-ietf-mars-referencing",
            type_id="draft",
            title="Referencing",
            stream_id="ietf",
            abstract="Test",
            rev="00",
            pages=2,
            words=100
            )
        referencing_draft.set_state(State.objects.get(used=True, type="draft", slug="active"))
        DocAlias.objects.create(name=referencing_draft.name).docs.add(referencing_draft)
        RelatedDocument.objects.create(
            source=referencing_draft,
            target=draft.docalias.first(),
            relationship=DocRelationshipName.objects.get(slug="refinfo")
        )
        NewRevisionDocEvent.objects.create(
            type="new_revision",
            by=Person.objects.get(name="(System)"),
            doc=referencing_draft,
            desc="New revision available",
            rev=referencing_draft.rev,
            time=datetime.datetime.now() - datetime.timedelta(days=1000)
        )


        # check redirect
        url = urlreverse(ietf.stats.views.document_stats)

        authors_url = urlreverse(ietf.stats.views.document_stats, kwargs={ "stats_type": "authors" })

        r = self.client.get(url)
        self.assertEqual(r.status_code, 302)
        self.assertTrue(authors_url in r["Location"])

        # check various stats types
        for stats_type in ["authors", "pages", "words", "format", "formlang",
                           "author/documents", "author/affiliation", "author/country",
                           "author/continent", "author/citations", "author/hindex",
                           "yearly/affiliation", "yearly/country", "yearly/continent"]:
            for document_type in ["", "rfc", "draft"]:
                for time_choice in ["", "5y"]:
                    url = urlreverse(ietf.stats.views.document_stats, kwargs={ "stats_type": stats_type })
                    r = self.client.get(url, {
                        "type": document_type,
                        "time": time_choice,
                    })
                    self.assertEqual(r.status_code, 200)
                    q = PyQuery(r.content)
                    self.assertTrue(q('#chart'))
                    if not stats_type.startswith("yearly"):
                        self.assertTrue(q('table.stats-data'))

    def test_meeting_stats(self):
        # create some data for the statistics
        meeting = MeetingFactory(type_id='ietf', date=datetime.date.today(), number="96")
        MeetingRegistration.objects.create(first_name='John', last_name='Smith', country_code='US', email="john.smith@example.us", meeting=meeting, attended=True)
        CountryAlias.objects.get_or_create(alias="US", country=CountryName.objects.get(slug="US"))
        MeetingRegistration.objects.create(first_name='Jaume', last_name='Guillaume', country_code='FR', email="jaume.guillaume@example.fr", meeting=meeting, attended=True)
        CountryAlias.objects.get_or_create(alias="FR", country=CountryName.objects.get(slug="FR"))

        # check redirect
        url = urlreverse(ietf.stats.views.meeting_stats)

        authors_url = urlreverse(ietf.stats.views.meeting_stats, kwargs={ "stats_type": "overview" })

        r = self.client.get(url)
        self.assertEqual(r.status_code, 302)
        self.assertTrue(authors_url in r["Location"])

        # check various stats types
        for stats_type in ["overview", "country", "continent"]:
            url = urlreverse(ietf.stats.views.meeting_stats, kwargs={ "stats_type": stats_type })
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            self.assertTrue(q('#chart'))
            if stats_type == "overview":
                self.assertTrue(q('table.stats-data'))

        for stats_type in ["country", "continent"]:
            url = urlreverse(ietf.stats.views.meeting_stats, kwargs={ "stats_type": stats_type, "num": meeting.number })
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            self.assertTrue(q('#chart'))
            self.assertTrue(q('table.stats-data'))
                
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
        expected_date = datetime.date.today().replace(day=1)
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
        self.assertTrue(q('.stats-time-graph'))

        # check non-stacked chart
        url = urlreverse(ietf.stats.views.review_stats, kwargs={ "stats_type": "time" })
        url += "?team={}".format(review_req.team.acronym)
        url += "&completion=not_completed"
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(json.loads(r.context['data']), [{"color": "#3d22b3", "data": [[expected_js_timestamp, 0]]}])
        q = PyQuery(r.content)
        self.assertTrue(q('.stats-time-graph'))

        # check reviewer level
        url = urlreverse(ietf.stats.views.review_stats, kwargs={ "stats_type": "completion", "acronym": review_req.team.acronym })
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(q('.review-stats td:contains("1")'))

    @patch('requests.get')
    def test_get_meeting_registration_data(self, mock_get):
        '''Test function to get reg data.  Confirm leading/trailing spaces stripped'''
        response = Response()
        response.status_code = 200
        response._content = b'[{"LastName":"Smith ","FirstName":" John","Company":"ABC","Country":"US","Email":"john.doe@example.us"}]'
        mock_get.return_value = response
        meeting = MeetingFactory(type_id='ietf', date=datetime.date(2016,7,14), number="96")
        get_meeting_registration_data(meeting)
        query = MeetingRegistration.objects.filter(first_name='John',last_name='Smith',country_code='US')
        self.assertTrue(query.count(), 1)
        self.assertTrue(isinstance(query[0].person,Person))
        
    @patch('requests.get')
    def test_get_meeting_registration_data_user_exists(self, mock_get):
        response = Response()
        response.status_code = 200
        response._content = b'[{"LastName":"Smith","FirstName":"John","Company":"ABC","Country":"US","Email":"john.doe@example.us"}]'
        email = "john.doe@example.us"
        user = User.objects.create(username=email)
        user.save()
        
        mock_get.return_value = response
        meeting = MeetingFactory(type_id='ietf', date=datetime.date(2016,7,14), number="96")
        get_meeting_registration_data(meeting)
        query = MeetingRegistration.objects.filter(first_name='John',last_name='Smith',country_code='US')
        emails = Email.objects.filter(address=email)
        self.assertTrue(query.count(), 1)
        self.assertTrue(isinstance(query[0].person, Person))
        self.assertTrue(len(emails)>=1)                                
        self.assertEqual(query[0].person, emails[0].person)                        

        
