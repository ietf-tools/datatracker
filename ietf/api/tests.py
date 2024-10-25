# Copyright The IETF Trust 2015-2024, All Rights Reserved
# -*- coding: utf-8 -*-
import base64
import datetime
import json
import html
import mock
import os
import sys

from importlib import import_module
from pathlib import Path
from random import randrange

from django.apps import apps
from django.conf import settings
from django.http import HttpResponseForbidden
from django.test import Client, RequestFactory
from django.test.utils import override_settings
from django.urls import reverse as urlreverse
from django.utils import timezone

from tastypie.test import ResourceTestCaseMixin

import debug                            # pyflakes:ignore

import ietf
from ietf.doc.utils import get_unicode_document_content
from ietf.doc.models import RelatedDocument, State
from ietf.doc.factories import IndividualDraftFactory, WgDraftFactory, WgRfcFactory
from ietf.group.factories import RoleFactory
from ietf.meeting.factories import MeetingFactory, SessionFactory
from ietf.meeting.models import Session
from ietf.nomcom.models import Volunteer
from ietf.nomcom.factories import NomComFactory, nomcom_kwargs_for_year
from ietf.person.factories import PersonFactory, random_faker, EmailFactory, PersonalApiKeyFactory
from ietf.person.models import Email, User
from ietf.stats.models import MeetingRegistration
from ietf.utils.mail import empty_outbox, outbox, get_payload_text
from ietf.utils.models import DumpInfo
from ietf.utils.test_utils import TestCase, login_testing_unauthorized, reload_db_objects

from .ietf_utils import is_valid_token, requires_api_token
from .views import EmailIngestionError

OMITTED_APPS = (
    'ietf.secr.meetings',
    'ietf.secr.proceedings',
    'ietf.ipr',
    'ietf.status',
)

class CustomApiTests(TestCase):
    settings_temp_path_overrides = TestCase.settings_temp_path_overrides + ['AGENDA_PATH']

    def test_api_help_page(self):
        url = urlreverse('ietf.api.views.api_help')
        r = self.client.get(url)
        self.assertContains(r, 'The datatracker API', status_code=200)

    def test_api_openid_issuer(self):
        url = urlreverse('ietf.api.urls.oidc_issuer')
        r = self.client.get(url)
        self.assertContains(r, 'OpenID Connect Issuer', status_code=200)

    def test_deprecated_api_set_session_video_url(self):
        url = urlreverse('ietf.meeting.views.api_set_session_video_url')
        recmanrole = RoleFactory(group__type_id='ietf', name_id='recman')
        recman = recmanrole.person
        meeting = MeetingFactory(type_id='ietf')
        session = SessionFactory(group__type_id='wg', meeting=meeting)
        group = session.group
        apikey = PersonalApiKeyFactory(endpoint=url, person=recman)
        video = 'https://foo.example.com/bar/beer/'

        # error cases
        r = self.client.post(url, {})
        self.assertContains(r, "Missing apikey parameter", status_code=400)

        badrole  = RoleFactory(group__type_id='ietf', name_id='ad')
        badapikey = PersonalApiKeyFactory(endpoint=url, person=badrole.person)
        badrole.person.user.last_login = timezone.now()
        badrole.person.user.save()
        r = self.client.post(url, {'apikey': badapikey.hash()} )
        self.assertContains(r, "Restricted to role: Recording Manager", status_code=403)

        r = self.client.post(url, {'apikey': apikey.hash()} )
        self.assertContains(r, "Too long since last regular login", status_code=400)
        recman.user.last_login = timezone.now()
        recman.user.save()

        r = self.client.get(url, {'apikey': apikey.hash()} )
        self.assertContains(r, "Method not allowed", status_code=405)

        r = self.client.post(url, {'apikey': apikey.hash(), 'group': group.acronym} )
        self.assertContains(r, "Missing meeting parameter", status_code=400)


        r = self.client.post(url, {'apikey': apikey.hash(), 'meeting': meeting.number, } )
        self.assertContains(r, "Missing group parameter", status_code=400)

        r = self.client.post(url, {'apikey': apikey.hash(), 'meeting': meeting.number, 'group': group.acronym} )
        self.assertContains(r, "Missing item parameter", status_code=400)

        r = self.client.post(url, {'apikey': apikey.hash(), 'meeting': meeting.number, 'group': group.acronym, 'item': '1'} )
        self.assertContains(r, "Missing url parameter", status_code=400)

        r = self.client.post(url, {'apikey': apikey.hash(), 'meeting': '1', 'group': group.acronym,
                                    'item': '1', 'url': video, })
        self.assertContains(r, "No sessions found for meeting", status_code=400)

        r = self.client.post(url, {'apikey': apikey.hash(), 'meeting': meeting.number, 'group': 'bogous',
                                    'item': '1', 'url': video, })
        self.assertContains(r, "No sessions found in meeting '%s' for group 'bogous'"%meeting.number, status_code=400)

        r = self.client.post(url, {'apikey': apikey.hash(), 'meeting': meeting.number, 'group': group.acronym,
                                    'item': '1', 'url': "foobar", })
        self.assertContains(r, "Invalid url value: 'foobar'", status_code=400)

        r = self.client.post(url, {'apikey': apikey.hash(), 'meeting': meeting.number, 'group': group.acronym,
                                    'item': '5', 'url': video, })
        self.assertContains(r, "No item '5' found in list of sessions for group", status_code=400)

        r = self.client.post(url, {'apikey': apikey.hash(), 'meeting': meeting.number, 'group': group.acronym,
                                    'item': 'foo', 'url': video, })
        self.assertContains(r, "Expected a numeric value for 'item', found 'foo'", status_code=400)

        r = self.client.post(url, {'apikey': apikey.hash(), 'meeting': meeting.number, 'group': group.acronym,
                                    'item': '1', 'url': video+'/rum', })
        self.assertContains(r, "Done", status_code=200)

        r = self.client.post(url, {'apikey': apikey.hash(), 'meeting': meeting.number, 'group': group.acronym,
                                    'item': '1', 'url': video+'/rum', })
        self.assertContains(r, "URL is the same", status_code=400)

        r = self.client.post(url, {'apikey': apikey.hash(), 'meeting': meeting.number, 'group': group.acronym,
                                    'item': '1', 'url': video, })
        self.assertContains(r, "Done", status_code=200)

        recordings = session.recordings()
        self.assertEqual(len(recordings), 1)
        doc = recordings[0]
        self.assertEqual(doc.external_url, video)
        event = doc.latest_event()
        self.assertEqual(event.by, recman)

    def test_api_set_session_video_url(self):
        url = urlreverse("ietf.meeting.views.api_set_session_video_url")
        recmanrole = RoleFactory(group__type_id="ietf", name_id="recman")
        recman = recmanrole.person
        meeting = MeetingFactory(type_id="ietf")
        session = SessionFactory(group__type_id="wg", meeting=meeting)
        apikey = PersonalApiKeyFactory(endpoint=url, person=recman)
        video = "https://foo.example.com/bar/beer/"

        # error cases
        r = self.client.post(url, {})
        self.assertContains(r, "Missing apikey parameter", status_code=400)

        badrole = RoleFactory(group__type_id="ietf", name_id="ad")
        badapikey = PersonalApiKeyFactory(endpoint=url, person=badrole.person)
        badrole.person.user.last_login = timezone.now()
        badrole.person.user.save()
        r = self.client.post(url, {"apikey": badapikey.hash()})
        self.assertContains(r, "Restricted to role: Recording Manager", status_code=403)

        r = self.client.post(url, {"apikey": apikey.hash()})
        self.assertContains(r, "Too long since last regular login", status_code=400)
        recman.user.last_login = timezone.now()
        recman.user.save()

        r = self.client.get(url, {"apikey": apikey.hash()})
        self.assertContains(r, "Method not allowed", status_code=405)

        r = self.client.post(url, {"apikey": apikey.hash()})
        self.assertContains(r, "Missing session_id parameter", status_code=400)

        r = self.client.post(url, {"apikey": apikey.hash(), "session_id": session.pk})
        self.assertContains(r, "Missing url parameter", status_code=400)

        bad_pk = int(Session.objects.order_by("-pk").first().pk) + 1
        r = self.client.post(
            url,
            {
                "apikey": apikey.hash(),
                "session_id": bad_pk,
                "url": video,
            },
        )
        self.assertContains(r, "Session not found", status_code=400)

        r = self.client.post(
            url,
            {
                "apikey": apikey.hash(),
                "session_id": "foo",
                "url": video,
            },
        )
        self.assertContains(r, "Invalid session_id", status_code=400)

        r = self.client.post(
            url,
            {
                "apikey": apikey.hash(),
                "session_id": session.pk,
                "url": "foobar",
            },
        )
        self.assertContains(r, "Invalid url value: 'foobar'", status_code=400)

        r = self.client.post(
            url, {"apikey": apikey.hash(), "session_id": session.pk, "url": video}
        )
        self.assertContains(r, "Done", status_code=200)

        recordings = session.recordings()
        self.assertEqual(len(recordings), 1)
        doc = recordings[0]
        self.assertEqual(doc.external_url, video)
        event = doc.latest_event()
        self.assertEqual(event.by, recman)

    def test_api_set_meetecho_recording_name(self):
        url = urlreverse("ietf.meeting.views.api_set_meetecho_recording_name")
        recmanrole = RoleFactory(group__type_id="ietf", name_id="recman")
        recman = recmanrole.person
        meeting = MeetingFactory(type_id="ietf")
        session = SessionFactory(group__type_id="wg", meeting=meeting)
        apikey = PersonalApiKeyFactory(endpoint=url, person=recman)
        name = "testname"

        # error cases
        r = self.client.post(url, {})
        self.assertContains(r, "Missing apikey parameter", status_code=400)

        badrole = RoleFactory(group__type_id="ietf", name_id="ad")
        badapikey = PersonalApiKeyFactory(endpoint=url, person=badrole.person)
        badrole.person.user.last_login = timezone.now()
        badrole.person.user.save()
        r = self.client.post(url, {"apikey": badapikey.hash()})
        self.assertContains(r, "Restricted to role: Recording Manager", status_code=403)

        r = self.client.post(url, {"apikey": apikey.hash()})
        self.assertContains(r, "Too long since last regular login", status_code=400)
        recman.user.last_login = timezone.now()
        recman.user.save()

        r = self.client.get(url, {"apikey": apikey.hash()})
        self.assertContains(r, "Method not allowed", status_code=405)

        r = self.client.post(url, {"apikey": apikey.hash()})
        self.assertContains(r, "Missing session_id parameter", status_code=400)

        r = self.client.post(url, {"apikey": apikey.hash(), "session_id": session.pk})
        self.assertContains(r, "Missing name parameter", status_code=400)

        bad_pk = int(Session.objects.order_by("-pk").first().pk) + 1
        r = self.client.post(
            url,
            {
                "apikey": apikey.hash(),
                "session_id": bad_pk,
                "name": name,
            },
        )
        self.assertContains(r, "Session not found", status_code=400)

        r = self.client.post(
            url,
            {
                "apikey": apikey.hash(),
                "session_id": "foo",
                "name": name,
            },
        )
        self.assertContains(r, "Invalid session_id", status_code=400)

        r = self.client.post(
            url, {"apikey": apikey.hash(), "session_id": session.pk, "name": name}
        )
        self.assertContains(r, "Done", status_code=200)

        session.refresh_from_db()
        self.assertEqual(session.meetecho_recording_name, name)


    def test_api_add_session_attendees_deprecated(self):
        # Deprecated test - should be removed when we stop accepting a simple list of user PKs in
        # the add_session_attendees() view
        url = urlreverse('ietf.meeting.views.api_add_session_attendees')
        otherperson = PersonFactory()
        recmanrole = RoleFactory(group__type_id='ietf', name_id='recman')
        recman = recmanrole.person
        meeting = MeetingFactory(type_id='ietf')
        session = SessionFactory(group__type_id='wg', meeting=meeting)  
        apikey = PersonalApiKeyFactory(endpoint=url, person=recman)

        badrole  = RoleFactory(group__type_id='ietf', name_id='ad')
        badapikey = PersonalApiKeyFactory(endpoint=url, person=badrole.person)
        badrole.person.user.last_login = timezone.now()
        badrole.person.user.save()

        # Improper credentials, or method
        r = self.client.post(url, {})
        self.assertContains(r, "Missing apikey parameter", status_code=400)

        r = self.client.post(url, {'apikey': badapikey.hash()} )
        self.assertContains(r, "Restricted to role: Recording Manager", status_code=403)

        r = self.client.post(url, {'apikey': apikey.hash()} )
        self.assertContains(r, "Too long since last regular login", status_code=400)

        recman.user.last_login = timezone.now()-datetime.timedelta(days=365)
        recman.user.save()        
        r = self.client.post(url, {'apikey': apikey.hash()} )
        self.assertContains(r, "Too long since last regular login", status_code=400)

        recman.user.last_login = timezone.now()
        recman.user.save()
        r = self.client.get(url, {'apikey': apikey.hash()} )
        self.assertContains(r, "Method not allowed", status_code=405)

        recman.user.last_login = timezone.now()
        recman.user.save()

        # Malformed requests
        r = self.client.post(url, {'apikey': apikey.hash()} )
        self.assertContains(r, "Missing attended parameter", status_code=400)

        for baddict in (
            '{}',
            '{"bogons;drop table":"bogons;drop table"}',
            '{"session_id":"Not an integer;drop table"}',
            f'{{"session_id":{session.pk},"attendees":"not a list;drop table"}}',
            f'{{"session_id":{session.pk},"attendees":"not a list;drop table"}}',
            f'{{"session_id":{session.pk},"attendees":[1,2,"not an int;drop table",4]}}',
        ):
            r = self.client.post(url, {'apikey': apikey.hash(), 'attended': baddict})
            self.assertContains(r, "Malformed post", status_code=400)

        bad_session_id = Session.objects.order_by('-pk').first().pk + 1
        r = self.client.post(url, {'apikey': apikey.hash(), 'attended': f'{{"session_id":{bad_session_id},"attendees":[]}}'})
        self.assertContains(r, "Invalid session", status_code=400)
        bad_user_id = User.objects.order_by('-pk').first().pk + 1
        r = self.client.post(url, {'apikey': apikey.hash(), 'attended': f'{{"session_id":{session.pk},"attendees":[{bad_user_id}]}}'})
        self.assertContains(r, "Invalid attendee", status_code=400)

        # Reasonable request
        r = self.client.post(url, {'apikey':apikey.hash(), 'attended': f'{{"session_id":{session.pk},"attendees":[{recman.user.pk}, {otherperson.user.pk}]}}'})

        self.assertEqual(session.attended_set.count(),2)
        self.assertTrue(session.attended_set.filter(person=recman).exists())
        self.assertTrue(session.attended_set.filter(person=otherperson).exists())

    def test_api_add_session_attendees(self):
        url = urlreverse("ietf.meeting.views.api_add_session_attendees")
        otherperson = PersonFactory()
        recmanrole = RoleFactory(group__type_id="ietf", name_id="recman")
        recman = recmanrole.person
        meeting = MeetingFactory(type_id="ietf")
        session = SessionFactory(group__type_id="wg", meeting=meeting)
        apikey = PersonalApiKeyFactory(endpoint=url, person=recman)

        badrole = RoleFactory(group__type_id="ietf", name_id="ad")
        badapikey = PersonalApiKeyFactory(endpoint=url, person=badrole.person)
        badrole.person.user.last_login = timezone.now()
        badrole.person.user.save()

        # Improper credentials, or method
        r = self.client.post(url, {})
        self.assertContains(r, "Missing apikey parameter", status_code=400)

        r = self.client.post(url, {"apikey": badapikey.hash()})
        self.assertContains(r, "Restricted to role: Recording Manager", status_code=403)

        r = self.client.post(url, {"apikey": apikey.hash()})
        self.assertContains(r, "Too long since last regular login", status_code=400)

        recman.user.last_login = timezone.now() - datetime.timedelta(days=365)
        recman.user.save()
        r = self.client.post(url, {"apikey": apikey.hash()})
        self.assertContains(r, "Too long since last regular login", status_code=400)

        recman.user.last_login = timezone.now()
        recman.user.save()
        r = self.client.get(url, {"apikey": apikey.hash()})
        self.assertContains(r, "Method not allowed", status_code=405)

        recman.user.last_login = timezone.now()
        recman.user.save()

        # Malformed requests
        r = self.client.post(url, {"apikey": apikey.hash()})
        self.assertContains(r, "Missing attended parameter", status_code=400)

        for baddict in (
            "{}",
            '{"bogons;drop table":"bogons;drop table"}',
            '{"session_id":"Not an integer;drop table"}',
            f'{{"session_id":{session.pk},"attendees":"not a list;drop table"}}',
            f'{{"session_id":{session.pk},"attendees":"not a list;drop table"}}',
            f'{{"session_id":{session.pk},"attendees":[1,2,"not an int;drop table",4]}}',
            f'{{"session_id":{session.pk},"attendees":["user_id":{recman.user.pk}]}}',  # no join_time
            f'{{"session_id":{session.pk},"attendees":["user_id":{recman.user.pk},"join_time;drop table":"2024-01-01T00:00:00Z]}}',
            f'{{"session_id":{session.pk},"attendees":["user_id":{recman.user.pk},"join_time":"not a time;drop table"]}}',
            # next has no time zone indicator
            f'{{"session_id":{session.pk},"attendees":["user_id":{recman.user.pk},"join_time":"2024-01-01T00:00:00"]}}',
            f'{{"session_id":{session.pk},"attendees":["user_id":"not an int; drop table","join_time":"2024-01-01T00:00:00Z"]}}',
            # Uncomment the next one when the _deprecated version of this test is retired
            # f'{{"session_id":{session.pk},"attendees":[{recman.user.pk}, {otherperson.user.pk}]}}',
        ):
            r = self.client.post(url, {"apikey": apikey.hash(), "attended": baddict})
            self.assertContains(r, "Malformed post", status_code=400)

        bad_session_id = Session.objects.order_by("-pk").first().pk + 1
        r = self.client.post(
            url,
            {
                "apikey": apikey.hash(),
                "attended": f'{{"session_id":{bad_session_id},"attendees":[]}}',
            },
        )
        self.assertContains(r, "Invalid session", status_code=400)
        bad_user_id = User.objects.order_by("-pk").first().pk + 1
        r = self.client.post(
            url,
            {
                "apikey": apikey.hash(),
                "attended": f'{{"session_id":{session.pk},"attendees":[{{"user_id":{bad_user_id}, "join_time":"2024-01-01T00:00:00Z"}}]}}',
            },
        )
        self.assertContains(r, "Invalid attendee", status_code=400)

        # Reasonable request
        r = self.client.post(
            url,
            {
                "apikey": apikey.hash(),
                "attended": json.dumps(
                    {
                        "session_id": session.pk,
                        "attendees": [
                            {
                                "user_id": recman.user.pk,
                                "join_time": "2023-09-03T12:34:56Z",
                            },
                            {
                                "user_id": otherperson.user.pk,
                                "join_time": "2023-09-03T03:00:19Z",
                            },
                        ],
                    }
                ),
            },
        )

        self.assertEqual(session.attended_set.count(), 2)
        self.assertTrue(session.attended_set.filter(person=recman).exists())
        self.assertEqual(
            session.attended_set.get(person=recman).time,
            datetime.datetime(2023, 9, 3, 12, 34, 56, tzinfo=datetime.timezone.utc),
        )
        self.assertTrue(session.attended_set.filter(person=otherperson).exists())
        self.assertEqual(
            session.attended_set.get(person=otherperson).time,
            datetime.datetime(2023, 9, 3, 3, 0, 19, tzinfo=datetime.timezone.utc),
        )

    def test_api_upload_polls_and_chatlog(self):
        recmanrole = RoleFactory(group__type_id='ietf', name_id='recman')
        recmanrole.person.user.last_login = timezone.now()
        recmanrole.person.user.save()

        badrole  = RoleFactory(group__type_id='ietf', name_id='ad')
        badrole.person.user.last_login = timezone.now()
        badrole.person.user.save()

        meeting = MeetingFactory(type_id='ietf')
        session = SessionFactory(group__type_id='wg', meeting=meeting)

        for type_id, content in (
            (
                "chatlog",
                """[
                    {
                        "author": "Raymond Lutz",
                        "text": "<p>Yes I like that comment just made</p>",
                        "time": "2022-07-28T19:26:16Z"
                    },
                    {
                        "author": "Carsten Bormann",
                        "text": "<p>But software is not a thing.</p>",
                        "time": "2022-07-28T19:26:45Z"
                    }
                ]"""
            ),
            (
                "polls",
                """[
                    {
                        "start_time": "2022-07-28T19:19:54Z",
                        "end_time": "2022-07-28T19:20:23Z",
                        "text": "Are you willing to review the documents?",
                        "raise_hand": 57,
                        "do_not_raise_hand": 11
                    },
                    {
                        "start_time": "2022-07-28T19:20:56Z",
                        "end_time": "2022-07-28T19:21:30Z",
                        "text": "Would you be willing to edit or coauthor a document?",
                        "raise_hand": 31,
                        "do_not_raise_hand": 31
                    }
                ]"""
            ),
        ):
            url = urlreverse(f"ietf.meeting.views.api_upload_{type_id}")
            apikey = PersonalApiKeyFactory(endpoint=url, person=recmanrole.person)
            badapikey = PersonalApiKeyFactory(endpoint=url, person=badrole.person)

            r = self.client.post(url, {})
            self.assertContains(r, "Missing apikey parameter", status_code=400)

            r = self.client.post(url, {'apikey': badapikey.hash()} )
            self.assertContains(r, "Restricted to role: Recording Manager", status_code=403)

            r = self.client.get(url, {'apikey': apikey.hash()} )
            self.assertContains(r, "Method not allowed", status_code=405)

            r = self.client.post(url, {'apikey': apikey.hash()} )
            self.assertContains(r, "Missing apidata parameter", status_code=400)

            for baddict in (
                '{}',
                '{"bogons;drop table":"bogons;drop table"}',
                '{"session_id":"Not an integer;drop table"}',
                f'{{"session_id":{session.pk},"{type_id}":"not a list;drop table"}}',
                f'{{"session_id":{session.pk},"{type_id}":"not a list;drop table"}}',
                f'{{"session_id":{session.pk},"{type_id}":[{{}}, {{}}, "not an int;drop table", {{}}]}}',
            ):
                r = self.client.post(url, {'apikey': apikey.hash(), 'apidata': baddict})
                self.assertContains(r, "Malformed post", status_code=400)

            bad_session_id = Session.objects.order_by('-pk').first().pk + 1
            r = self.client.post(url, {'apikey': apikey.hash(), 'apidata': f'{{"session_id":{bad_session_id},"{type_id}":[]}}'})
            self.assertContains(r, "Invalid session", status_code=400)

            # Valid POST
            r = self.client.post(url,{'apikey':apikey.hash(),'apidata': f'{{"session_id":{session.pk}, "{type_id}":{content}}}'})
            self.assertEqual(r.status_code, 200)

            newdoc = session.presentations.get(document__type_id=type_id).document
            newdoccontent = get_unicode_document_content(newdoc.name, Path(session.meeting.get_materials_path()) / type_id / newdoc.uploaded_filename)
            self.assertEqual(json.loads(content), json.loads(newdoccontent))

    def test_deprecated_api_upload_bluesheet(self):
        url = urlreverse('ietf.meeting.views.api_upload_bluesheet')
        recmanrole = RoleFactory(group__type_id='ietf', name_id='recman')
        recman = recmanrole.person
        meeting = MeetingFactory(type_id='ietf')
        session = SessionFactory(group__type_id='wg', meeting=meeting)
        group = session.group
        apikey = PersonalApiKeyFactory(endpoint=url, person=recman)

        people = [
            {"name": "Andrea Andreotti", "affiliation": "Azienda"},
            {"name": "Bosse Bernadotte", "affiliation": "Bolag"},
            {"name": "Charles Charlemagne", "affiliation": "Compagnie"},
        ]
        for i in range(3):
            faker = random_faker()
            people.append(dict(name=faker.name(), affiliation=faker.company()))
        bluesheet = json.dumps(people)

        # error cases
        r = self.client.post(url, {})
        self.assertContains(r, "Missing apikey parameter", status_code=400)

        badrole = RoleFactory(group__type_id='ietf', name_id='ad')
        badapikey = PersonalApiKeyFactory(endpoint=url, person=badrole.person)
        badrole.person.user.last_login = timezone.now()
        badrole.person.user.save()
        r = self.client.post(url, {'apikey': badapikey.hash()})
        self.assertContains(r, "Restricted to roles: Recording Manager, Secretariat", status_code=403)

        r = self.client.post(url, {'apikey': apikey.hash()})
        self.assertContains(r, "Too long since last regular login", status_code=400)
        recman.user.last_login = timezone.now()
        recman.user.save()

        r = self.client.get(url, {'apikey': apikey.hash()})
        self.assertContains(r, "Method not allowed", status_code=405)

        r = self.client.post(url, {'apikey': apikey.hash(), 'group': group.acronym})
        self.assertContains(r, "Missing meeting parameter", status_code=400)

        r = self.client.post(url, {'apikey': apikey.hash(), 'meeting': meeting.number, })
        self.assertContains(r, "Missing group parameter", status_code=400)

        r = self.client.post(url, {'apikey': apikey.hash(), 'meeting': meeting.number, 'group': group.acronym})
        self.assertContains(r, "Missing item parameter", status_code=400)

        r = self.client.post(url,
                             {'apikey': apikey.hash(), 'meeting': meeting.number, 'group': group.acronym, 'item': '1'})
        self.assertContains(r, "Missing bluesheet parameter", status_code=400)

        r = self.client.post(url, {'apikey': apikey.hash(), 'meeting': '1', 'group': group.acronym,
                                   'item': '1', 'bluesheet': bluesheet, })
        self.assertContains(r, "No sessions found for meeting", status_code=400)

        r = self.client.post(url, {'apikey': apikey.hash(), 'meeting': meeting.number, 'group': 'bogous',
                                   'item': '1', 'bluesheet': bluesheet, })
        self.assertContains(r, "No sessions found in meeting '%s' for group 'bogous'" % meeting.number, status_code=400)

        r = self.client.post(url, {'apikey': apikey.hash(), 'meeting': meeting.number, 'group': group.acronym,
                                   'item': '1', 'bluesheet': "foobar", })
        self.assertContains(r, "Invalid json value: 'foobar'", status_code=400)

        r = self.client.post(url, {'apikey': apikey.hash(), 'meeting': meeting.number, 'group': group.acronym,
                                   'item': '5', 'bluesheet': bluesheet, })
        self.assertContains(r, "No item '5' found in list of sessions for group", status_code=400)

        r = self.client.post(url, {'apikey': apikey.hash(), 'meeting': meeting.number, 'group': group.acronym,
                                   'item': 'foo', 'bluesheet': bluesheet, })
        self.assertContains(r, "Expected a numeric value for 'item', found 'foo'", status_code=400)

        r = self.client.post(url, {'apikey': apikey.hash(), 'meeting': meeting.number, 'group': group.acronym,
                                   'item': '1', 'bluesheet': bluesheet, })
        self.assertContains(r, "Done", status_code=200)

        # Submit again, with slightly different content, as an updated version
        people[1]['affiliation'] = 'Bolaget AB'
        bluesheet = json.dumps(people)
        r = self.client.post(url, {'apikey': apikey.hash(), 'meeting': meeting.number, 'group': group.acronym,
                                   'item': '1', 'bluesheet': bluesheet, })
        self.assertContains(r, "Done", status_code=200)

        bluesheet = session.presentations.filter(document__type__slug='bluesheets').first().document
        # We've submitted an update; check that the rev is right
        self.assertEqual(bluesheet.rev, '01')
        # Check the content
        with open(bluesheet.get_file_name()) as file:
            text = file.read()
            for p in people:
                self.assertIn(p['name'], html.unescape(text))
                self.assertIn(p['affiliation'], html.unescape(text))

    def test_api_upload_bluesheet(self):
        url = urlreverse("ietf.meeting.views.api_upload_bluesheet")
        recmanrole = RoleFactory(group__type_id="ietf", name_id="recman")
        recman = recmanrole.person
        meeting = MeetingFactory(type_id="ietf")
        session = SessionFactory(group__type_id="wg", meeting=meeting)
        group = session.group
        apikey = PersonalApiKeyFactory(endpoint=url, person=recman)

        people = [
            {"name": "Andrea Andreotti", "affiliation": "Azienda"},
            {"name": "Bosse Bernadotte", "affiliation": "Bolag"},
            {"name": "Charles Charlemagne", "affiliation": "Compagnie"},
        ]
        for i in range(3):
            faker = random_faker()
            people.append(dict(name=faker.name(), affiliation=faker.company()))
        bluesheet = json.dumps(people)

        # error cases
        r = self.client.post(url, {})
        self.assertContains(r, "Missing apikey parameter", status_code=400)

        badrole = RoleFactory(group__type_id="ietf", name_id="ad")
        badapikey = PersonalApiKeyFactory(endpoint=url, person=badrole.person)
        badrole.person.user.last_login = timezone.now()
        badrole.person.user.save()
        r = self.client.post(url, {"apikey": badapikey.hash()})
        self.assertContains(
            r, "Restricted to roles: Recording Manager, Secretariat", status_code=403
        )

        r = self.client.post(url, {"apikey": apikey.hash()})
        self.assertContains(r, "Too long since last regular login", status_code=400)
        recman.user.last_login = timezone.now()
        recman.user.save()

        r = self.client.get(url, {"apikey": apikey.hash()})
        self.assertContains(r, "Method not allowed", status_code=405)

        r = self.client.post(url, {"apikey": apikey.hash()})
        self.assertContains(r, "Missing session_id parameter", status_code=400)

        r = self.client.post(url, {"apikey": apikey.hash(), "session_id": session.pk})
        self.assertContains(r, "Missing bluesheet parameter", status_code=400)

        r = self.client.post(
            url,
            {
                "apikey": apikey.hash(),
                "meeting": meeting.number,
                "group": group.acronym,
                "item": "1",
                "bluesheet": "foobar",
            },
        )
        self.assertContains(r, "Invalid json value: 'foobar'", status_code=400)

        bad_session_pk = int(Session.objects.order_by("-pk").first().pk) + 1
        r = self.client.post(
            url,
            {
                "apikey": apikey.hash(),
                "session_id": bad_session_pk,
                "bluesheet": bluesheet,
            },
        )
        self.assertContains(r, "Session not found", status_code=400)

        r = self.client.post(
            url,
            {
                "apikey": apikey.hash(),
                "session_id": "foo",
                "bluesheet": bluesheet,
            },
        )
        self.assertContains(r, "Invalid session_id", status_code=400)

        r = self.client.post(
            url,
            {
                "apikey": apikey.hash(),
                "session_id": session.pk,
                "bluesheet": bluesheet,
            },
        )
        self.assertContains(r, "Done", status_code=200)

        # Submit again, with slightly different content, as an updated version
        people[1]["affiliation"] = "Bolaget AB"
        bluesheet = json.dumps(people)
        r = self.client.post(
            url,
            {
                "apikey": apikey.hash(),
                "meeting": meeting.number,
                "group": group.acronym,
                "item": "1",
                "bluesheet": bluesheet,
            },
        )
        self.assertContains(r, "Done", status_code=200)

        bluesheet = (
            session.presentations.filter(document__type__slug="bluesheets")
            .first()
            .document
        )
        # We've submitted an update; check that the rev is right
        self.assertEqual(bluesheet.rev, "01")
        # Check the content
        with open(bluesheet.get_file_name()) as file:
            text = file.read()
            for p in people:
                self.assertIn(p["name"], html.unescape(text))
                self.assertIn(p["affiliation"], html.unescape(text))

    def test_person_export(self):
        person = PersonFactory()
        url = urlreverse('ietf.api.views.PersonalInformationExportView')
        login_testing_unauthorized(self, person.user.username, url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        jsondata = r.json()
        data = jsondata['person.person'][str(person.id)]
        self.assertEqual(data['name'], person.name)
        self.assertEqual(data['ascii'], person.ascii)
        self.assertEqual(data['user']['email'], person.user.email)

    def test_api_v2_person_export_view(self):
        url = urlreverse('ietf.api.views.ApiV2PersonExportView')
        robot = PersonFactory(user__is_staff=True)
        RoleFactory(name_id='robot', person=robot, email=robot.email(), group__acronym='secretariat')
        apikey = PersonalApiKeyFactory(endpoint=url, person=robot)

        # error cases
        r = self.client.post(url, {})
        self.assertContains(r, "Missing apikey parameter", status_code=400)

        badrole = RoleFactory(group__type_id='ietf', name_id='ad')
        badapikey = PersonalApiKeyFactory(endpoint=url, person=badrole.person)
        badrole.person.user.last_login = timezone.now()
        badrole.person.user.save()
        r = self.client.post(url, {'apikey': badapikey.hash()})
        self.assertContains(r, "Restricted to role: Robot", status_code=403)

        r = self.client.post(url, {'apikey': apikey.hash()})
        self.assertContains(r, "No filters provided", status_code=400)

        # working case
        r = self.client.post(url, {'apikey': apikey.hash(), 'email': robot.email().address, '_expand': 'user'})
        self.assertEqual(r.status_code, 200)
        jsondata = r.json()
        data = jsondata['person.person'][str(robot.id)]
        self.assertEqual(data['name'], robot.name)
        self.assertEqual(data['ascii'], robot.ascii)
        self.assertEqual(data['user']['email'], robot.user.email)

    def test_api_new_meeting_registration(self):
        meeting = MeetingFactory(type_id='ietf')
        reg = {
            'apikey': 'invalid',
            'affiliation': "Alguma Corporação",
            'country_code': 'PT',
            'email': 'foo@example.pt',
            'first_name': 'Foo',
            'last_name': 'Bar',
            'meeting': meeting.number,
            'reg_type': 'hackathon',
            'ticket_type': '',
            'checkedin': 'False',
            'is_nomcom_volunteer': 'False',
        }
        url = urlreverse('ietf.api.views.api_new_meeting_registration')
        r = self.client.post(url, reg)
        self.assertContains(r, 'Invalid apikey', status_code=403)
        oidcp = PersonFactory(user__is_staff=True)
        # Make sure 'oidcp' has an acceptable role
        RoleFactory(name_id='robot', person=oidcp, email=oidcp.email(), group__acronym='secretariat')
        key = PersonalApiKeyFactory(person=oidcp, endpoint=url)
        reg['apikey'] = key.hash()
        #
        # Test valid POST
        # FIXME: sometimes, there seems to be something in the outbox?
        old_len = len(outbox)
        r = self.client.post(url, reg)
        self.assertContains(r, "Accepted, New registration, Email sent", status_code=202)
        #
        # Check outgoing mail
        self.assertEqual(len(outbox), old_len + 1)
        body = get_payload_text(outbox[-1])
        self.assertIn(reg['email'], outbox[-1]['To'] )
        self.assertIn(reg['email'], body)
        self.assertIn('account creation request', body)
        #
        # Check record
        obj = MeetingRegistration.objects.get(email=reg['email'], meeting__number=reg['meeting'])
        for key in ['affiliation', 'country_code', 'first_name', 'last_name', 'person', 'reg_type', 'ticket_type', 'checkedin']:
            self.assertEqual(getattr(obj, key), False if key=='checkedin' else reg.get(key) , "Bad data for field '%s'" % key)
        #
        # Test with existing user
        person = PersonFactory()
        reg['email'] = person.email().address
        reg['first_name'] = person.first_name()
        reg['last_name'] = person.last_name()
        #
        r = self.client.post(url, reg)
        self.assertContains(r, "Accepted, New registration", status_code=202)
        #
        # There should be no new outgoing mail
        self.assertEqual(len(outbox), old_len + 1)
        #
        # Test multiple reg types
        reg['reg_type'] = 'remote'
        reg['ticket_type'] = 'full_week_pass'
        r = self.client.post(url, reg)
        self.assertContains(r, "Accepted, New registration", status_code=202)
        objs = MeetingRegistration.objects.filter(email=reg['email'], meeting__number=reg['meeting'])
        self.assertEqual(len(objs), 2)
        self.assertEqual(objs.filter(reg_type='hackathon').count(), 1)
        self.assertEqual(objs.filter(reg_type='remote', ticket_type='full_week_pass').count(), 1)
        self.assertEqual(len(outbox), old_len + 1)
        #
        # Test incomplete POST
        drop_fields = ['affiliation', 'first_name', 'reg_type']
        for field in drop_fields:
            del reg[field]
        r = self.client.post(url, reg)        
        self.assertContains(r, 'Missing parameters:', status_code=400)
        err, fields = r.content.decode().split(':', 1)
        missing_fields = [f.strip() for f in fields.split(',')]
        self.assertEqual(set(missing_fields), set(drop_fields))

    def test_api_new_meeting_registration_nomcom_volunteer(self):
        '''Test that Volunteer is created if is_nomcom_volunteer=True
           is submitted to API
        '''
        meeting = MeetingFactory(type_id='ietf')
        reg = {
            'apikey': 'invalid',
            'affiliation': "Alguma Corporação",
            'country_code': 'PT',
            'meeting': meeting.number,
            'reg_type': 'onsite',
            'ticket_type': '',
            'checkedin': 'False',
            'is_nomcom_volunteer': 'False',
        }
        person = PersonFactory()
        reg['email'] = person.email().address
        reg['first_name'] = person.first_name()
        reg['last_name'] = person.last_name()
        now = datetime.datetime.now()
        if now.month > 10:
            year = now.year + 1
        else:
            year = now.year
        # create appropriate group and nomcom objects
        nomcom = NomComFactory.create(is_accepting_volunteers=True, **nomcom_kwargs_for_year(year))
        url = urlreverse('ietf.api.views.api_new_meeting_registration')
        oidcp = PersonFactory(user__is_staff=True)
        # Make sure 'oidcp' has an acceptable role
        RoleFactory(name_id='robot', person=oidcp, email=oidcp.email(), group__acronym='secretariat')
        key = PersonalApiKeyFactory(person=oidcp, endpoint=url)
        reg['apikey'] = key.hash()

        # first test is_nomcom_volunteer False
        r = self.client.post(url, reg)
        self.assertContains(r, "Accepted, New registration", status_code=202)
        # assert no Volunteers exists
        self.assertEqual(Volunteer.objects.count(), 0)

        # test is_nomcom_volunteer True
        reg['is_nomcom_volunteer'] = 'True'
        r = self.client.post(url, reg)
        self.assertContains(r, "Accepted, Updated registration", status_code=202)
        # assert Volunteer exists
        self.assertEqual(Volunteer.objects.count(), 1)
        volunteer = Volunteer.objects.last()
        self.assertEqual(volunteer.person, person)
        self.assertEqual(volunteer.nomcom, nomcom)
        self.assertEqual(volunteer.origin, 'registration')

    def test_api_version(self):
        DumpInfo.objects.create(date=timezone.datetime(2022,8,31,7,10,1,tzinfo=datetime.timezone.utc), host='testapi.example.com',tz='UTC')
        url = urlreverse('ietf.api.views.version')
        r = self.client.get(url)
        data = r.json()
        self.assertEqual(data['version'], ietf.__version__+ietf.__patch__)
        self.assertEqual(data['dumptime'], "2022-08-31 07:10:01 +0000")
        DumpInfo.objects.update(tz='PST8PDT')
        r = self.client.get(url)
        data = r.json()        
        self.assertEqual(data['dumptime'], "2022-08-31 07:10:01 -0700")


    def test_api_appauth(self):
        for app in ["authortools", "bibxml"]:
            url = urlreverse('ietf.api.views.app_auth', kwargs={"app": app})
            person = PersonFactory()
            apikey = PersonalApiKeyFactory(endpoint=url, person=person)
    
            self.client.login(username=person.user.username,password=f'{person.user.username}+password')
            self.client.logout()
    
            # error cases
            # missing apikey
            r = self.client.post(url, {})
            self.assertContains(r, 'Missing apikey parameter', status_code=400)
    
            # invalid apikey
            r = self.client.post(url, {'apikey': 'foobar'})
            self.assertContains(r, 'Invalid apikey', status_code=403)
    
            # working case
            r = self.client.post(url, {'apikey': apikey.hash()})
            self.assertEqual(r.status_code, 200)
            jsondata = r.json()
            self.assertEqual(jsondata['success'], True)
            self.client.logout()

    def test_api_get_session_matherials_no_agenda_meeting_url(self):
        meeting = MeetingFactory(type_id='ietf')
        session = SessionFactory(meeting=meeting)
        url = urlreverse('ietf.meeting.views.api_get_session_materials', kwargs={'session_id': session.pk})
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
    
    @override_settings(APP_API_TOKENS={"ietf.api.views.draft_aliases": ["valid-token"]})
    @mock.patch("ietf.api.views.DraftAliasGenerator")
    def test_draft_aliases(self, mock):
        mock.return_value = (("alias1", ("a1", "a2")), ("alias2", ("a3", "a4")))
        url = urlreverse("ietf.api.views.draft_aliases")
        r = self.client.get(url, headers={"X-Api-Key": "valid-token"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["Content-type"], "application/json")
        self.assertEqual(
            json.loads(r.content),
            {
                "aliases": [
                    {"alias": "alias1", "domains": ["ietf"], "addresses": ["a1", "a2"]},
                    {"alias": "alias2", "domains": ["ietf"], "addresses": ["a3", "a4"]},
                ]}
        )
        # some invalid cases
        self.assertEqual(
            self.client.get(url, headers={}).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(url, headers={"X-Api-Key": "something-else"}).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(url, headers={"X-Api-Key": "something-else"}).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(url, headers={"X-Api-Key": "valid-token"}).status_code,
            405,
        )

    @override_settings(APP_API_TOKENS={"ietf.api.views.group_aliases": ["valid-token"]})
    @mock.patch("ietf.api.views.GroupAliasGenerator")
    def test_group_aliases(self, mock):
        mock.return_value = (("alias1", ("ietf",), ("a1", "a2")), ("alias2", ("ietf", "iab"), ("a3", "a4")))
        url = urlreverse("ietf.api.views.group_aliases")
        r = self.client.get(url, headers={"X-Api-Key": "valid-token"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["Content-type"], "application/json")
        self.assertEqual(
            json.loads(r.content),
            {
                "aliases": [
                    {"alias": "alias1", "domains": ["ietf"], "addresses": ["a1", "a2"]},
                    {"alias": "alias2", "domains": ["ietf", "iab"], "addresses": ["a3", "a4"]},
                ]}
        )
        # some invalid cases
        self.assertEqual(
            self.client.get(url, headers={}).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(url, headers={"X-Api-Key": "something-else"}).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(url, headers={"X-Api-Key": "something-else"}).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(url, headers={"X-Api-Key": "valid-token"}).status_code,
            405,
        )

    @override_settings(APP_API_TOKENS={"ietf.api.views.active_email_list": ["valid-token"]})
    def test_active_email_list(self):
        EmailFactory(active=True)  # make sure there's at least one active email...
        EmailFactory(active=False)  # ... and at least one non-active emai
        url = urlreverse("ietf.api.views.active_email_list")
        r = self.client.post(url, headers={})
        self.assertEqual(r.status_code, 403)
        r = self.client.get(url, headers={})
        self.assertEqual(r.status_code, 403)
        r = self.client.get(url, headers={"X-Api-Key": "not-the-valid-token"})
        self.assertEqual(r.status_code, 403)
        r = self.client.post(url, headers={"X-Api-Key": "not-the-valid-token"})
        self.assertEqual(r.status_code, 403)
        r = self.client.post(url, headers={"X-Api-Key": "valid-token"})
        self.assertEqual(r.status_code, 405)
        r = self.client.get(url, headers={"X-Api-Key": "valid-token"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["Content-Type"], "application/json")
        result = json.loads(r.content)
        self.assertCountEqual(result.keys(), ["addresses"])
        self.assertCountEqual(result["addresses"], Email.objects.filter(active=True).values_list("address", flat=True))

    @override_settings(APP_API_TOKENS={"ietf.api.views.role_holder_addresses": ["valid-token"]})
    def test_role_holder_addresses(self):
        url = urlreverse("ietf.api.views.role_holder_addresses")
        r = self.client.get(url, headers={})
        self.assertEqual(r.status_code, 403, "No api token, no access")
        r = self.client.get(url, headers={"X-Api-Key": "not-valid-token"})
        self.assertEqual(r.status_code, 403, "Bad api token, no access")
        r = self.client.post(url, headers={"X-Api-Key": "valid-token"})
        self.assertEqual(r.status_code, 405, "Bad method, no access")

        emails = EmailFactory.create_batch(5)
        email_queryset = Email.objects.filter(pk__in=[e.pk for e in emails])
        with mock.patch("ietf.api.views.role_holder_emails", return_value=email_queryset):
            r = self.client.get(url, headers={"X-Api-Key": "valid-token"})
        self.assertEqual(r.status_code, 200, "Good api token and method, access")
        content_dict = json.loads(r.content)
        self.assertCountEqual(content_dict.keys(), ["addresses"])
        self.assertEqual(
            content_dict["addresses"],
            sorted(e.address for e in emails),
        )

    @override_settings(
        APP_API_TOKENS={"ietf.api.views.ingest_email": "valid-token", "ietf.api.views.ingest_email_test": "test-token"}
    )
    @mock.patch("ietf.api.views.iana_ingest_review_email")
    @mock.patch("ietf.api.views.ipr_ingest_response_email")
    @mock.patch("ietf.api.views.nomcom_ingest_feedback_email")
    def test_ingest_email(
        self, mock_nomcom_ingest, mock_ipr_ingest, mock_iana_ingest
    ):
        mocks = {mock_nomcom_ingest, mock_ipr_ingest, mock_iana_ingest}
        empty_outbox()        
        url = urlreverse("ietf.api.views.ingest_email")
        test_mode_url = urlreverse("ietf.api.views.ingest_email_test")

        # test various bad calls
        r = self.client.get(url)
        self.assertEqual(r.status_code, 403)
        self.assertFalse(any(m.called for m in mocks))
        r = self.client.get(test_mode_url)
        self.assertEqual(r.status_code, 403)
        self.assertFalse(any(m.called for m in mocks))

        r = self.client.post(url)
        self.assertEqual(r.status_code, 403)
        self.assertFalse(any(m.called for m in mocks))
        r = self.client.post(test_mode_url)
        self.assertEqual(r.status_code, 403)
        self.assertFalse(any(m.called for m in mocks))

        r = self.client.get(url, headers={"X-Api-Key": "valid-token"})
        self.assertEqual(r.status_code, 405)
        self.assertFalse(any(m.called for m in mocks))
        r = self.client.get(test_mode_url, headers={"X-Api-Key": "test-token"})
        self.assertEqual(r.status_code, 405)
        self.assertFalse(any(m.called for m in mocks))

        r = self.client.post(url, headers={"X-Api-Key": "valid-token"})
        self.assertEqual(r.status_code, 415)
        self.assertFalse(any(m.called for m in mocks))
        r = self.client.post(test_mode_url, headers={"X-Api-Key": "test-token"})
        self.assertEqual(r.status_code, 415)
        self.assertFalse(any(m.called for m in mocks))

        r = self.client.post(
            url, content_type="application/json", headers={"X-Api-Key": "valid-token"}
        )
        self.assertEqual(r.status_code, 400)
        self.assertFalse(any(m.called for m in mocks))
        r = self.client.post(
            test_mode_url, content_type="application/json", headers={"X-Api-Key": "test-token"}
        )
        self.assertEqual(r.status_code, 400)
        self.assertFalse(any(m.called for m in mocks))

        r = self.client.post(
            url,
            "this is not JSON!",
            content_type="application/json",
            headers={"X-Api-Key": "valid-token"},
        )
        self.assertEqual(r.status_code, 400)
        self.assertFalse(any(m.called for m in mocks))
        r = self.client.post(
            test_mode_url,
            "this is not JSON!",
            content_type="application/json",
            headers={"X-Api-Key": "test-token"},
        )
        self.assertEqual(r.status_code, 400)
        self.assertFalse(any(m.called for m in mocks))

        r = self.client.post(
            url,
            {"json": "yes", "valid_schema": False},
            content_type="application/json",
            headers={"X-Api-Key": "valid-token"},
        )
        self.assertEqual(r.status_code, 400)
        self.assertFalse(any(m.called for m in mocks))
        r = self.client.post(
            test_mode_url,
            {"json": "yes", "valid_schema": False},
            content_type="application/json",
            headers={"X-Api-Key": "test-token"},
        )
        self.assertEqual(r.status_code, 400)
        self.assertFalse(any(m.called for m in mocks))

        # bad destination
        message_b64 = base64.b64encode(b"This is a message").decode()
        r = self.client.post(
            url,
            {"dest": "not-a-destination", "message": message_b64},
            content_type="application/json",
            headers={"X-Api-Key": "valid-token"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["Content-Type"], "application/json")
        self.assertEqual(json.loads(r.content), {"result": "bad_dest"})
        self.assertFalse(any(m.called for m in mocks))
        r = self.client.post(
            test_mode_url,
            {"dest": "not-a-destination", "message": message_b64},
            content_type="application/json",
            headers={"X-Api-Key": "test-token"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["Content-Type"], "application/json")
        self.assertEqual(json.loads(r.content), {"result": "bad_dest"})
        self.assertFalse(any(m.called for m in mocks))

        # test that valid requests call handlers appropriately
        r = self.client.post(
            url,
            {"dest": "iana-review", "message": message_b64},
            content_type="application/json",
            headers={"X-Api-Key": "valid-token"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["Content-Type"], "application/json")
        self.assertEqual(json.loads(r.content), {"result": "ok"})
        self.assertTrue(mock_iana_ingest.called)
        self.assertEqual(mock_iana_ingest.call_args, mock.call(b"This is a message"))
        self.assertFalse(any(m.called for m in (mocks - {mock_iana_ingest})))
        mock_iana_ingest.reset_mock()
        
        # the test mode endpoint should _not_ call the handler
        r = self.client.post(
            test_mode_url,
            {"dest": "iana-review", "message": message_b64},
            content_type="application/json",
            headers={"X-Api-Key": "test-token"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["Content-Type"], "application/json")
        self.assertEqual(json.loads(r.content), {"result": "ok"})
        self.assertFalse(any(m.called for m in mocks))
        mock_iana_ingest.reset_mock()
        
        r = self.client.post(
            url,
            {"dest": "ipr-response", "message": message_b64},
            content_type="application/json",
            headers={"X-Api-Key": "valid-token"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["Content-Type"], "application/json")
        self.assertEqual(json.loads(r.content), {"result": "ok"})
        self.assertTrue(mock_ipr_ingest.called)
        self.assertEqual(mock_ipr_ingest.call_args, mock.call(b"This is a message"))
        self.assertFalse(any(m.called for m in (mocks - {mock_ipr_ingest})))
        mock_ipr_ingest.reset_mock()

        # the test mode endpoint should _not_ call the handler
        r = self.client.post(
            test_mode_url,
            {"dest": "ipr-response", "message": message_b64},
            content_type="application/json",
            headers={"X-Api-Key": "test-token"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["Content-Type"], "application/json")
        self.assertEqual(json.loads(r.content), {"result": "ok"})
        self.assertFalse(any(m.called for m in mocks))
        mock_ipr_ingest.reset_mock()

        # bad nomcom-feedback dest
        for bad_nomcom_dest in [
            "nomcom-feedback",  # no suffix
            "nomcom-feedback-",  # no year
            "nomcom-feedback-squid",  # not a year,
            "nomcom-feedback-2024-2025",  # also not a year
        ]:
            r = self.client.post(
                url,
                {"dest": bad_nomcom_dest, "message": message_b64},
                content_type="application/json",
                headers={"X-Api-Key": "valid-token"},
            )
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.headers["Content-Type"], "application/json")
            self.assertEqual(json.loads(r.content), {"result": "bad_dest"})
            self.assertFalse(any(m.called for m in mocks))
            r = self.client.post(
                test_mode_url,
                {"dest": bad_nomcom_dest, "message": message_b64},
                content_type="application/json",
                headers={"X-Api-Key": "test-token"},
            )
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.headers["Content-Type"], "application/json")
            self.assertEqual(json.loads(r.content), {"result": "bad_dest"})
            self.assertFalse(any(m.called for m in mocks))

        # good nomcom-feedback dest
        random_year = randrange(100000)
        r = self.client.post(
            url,
            {"dest": f"nomcom-feedback-{random_year}", "message": message_b64},
            content_type="application/json",
            headers={"X-Api-Key": "valid-token"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["Content-Type"], "application/json")
        self.assertEqual(json.loads(r.content), {"result": "ok"})
        self.assertTrue(mock_nomcom_ingest.called)
        self.assertEqual(mock_nomcom_ingest.call_args, mock.call(b"This is a message", random_year))
        self.assertFalse(any(m.called for m in (mocks - {mock_nomcom_ingest})))
        mock_nomcom_ingest.reset_mock()

        # the test mode endpoint should _not_ call the handler
        r = self.client.post(
            test_mode_url,
            {"dest": f"nomcom-feedback-{random_year}", "message": message_b64},
            content_type="application/json",
            headers={"X-Api-Key": "test-token"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["Content-Type"], "application/json")
        self.assertEqual(json.loads(r.content), {"result": "ok"})
        self.assertFalse(any(m.called for m in mocks))
        mock_nomcom_ingest.reset_mock()

        # test that exceptions lead to email being sent - assumes that iana-review handling is representative
        mock_iana_ingest.side_effect = EmailIngestionError("Error: don't send email")
        r = self.client.post(
            url,
            {"dest": "iana-review", "message": message_b64},
            content_type="application/json",
            headers={"X-Api-Key": "valid-token"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["Content-Type"], "application/json")
        self.assertEqual(json.loads(r.content), {"result": "bad_msg"})
        self.assertTrue(mock_iana_ingest.called)
        self.assertEqual(mock_iana_ingest.call_args, mock.call(b"This is a message"))
        self.assertFalse(any(m.called for m in (mocks - {mock_iana_ingest})))
        self.assertEqual(len(outbox), 0)  # implicitly tests that _none_ of the earlier tests sent email
        mock_iana_ingest.reset_mock()

        # test default recipients and attached original message
        mock_iana_ingest.side_effect = EmailIngestionError(
            "Error: do send email",
            email_body="This is my email\n",
            email_original_message=b"This is the original message"
        )
        with override_settings(ADMINS=[("Some Admin", "admin@example.com")]):
            r = self.client.post(
                url,
                {"dest": "iana-review", "message": message_b64},
                content_type="application/json",
                headers={"X-Api-Key": "valid-token"},
            )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["Content-Type"], "application/json")
        self.assertEqual(json.loads(r.content), {"result": "bad_msg"})
        self.assertTrue(mock_iana_ingest.called)
        self.assertEqual(mock_iana_ingest.call_args, mock.call(b"This is a message"))
        self.assertFalse(any(m.called for m in (mocks - {mock_iana_ingest})))
        self.assertEqual(len(outbox), 1)
        self.assertIn("admin@example.com", outbox[0]["To"])
        self.assertEqual("Error: do send email", outbox[0]["Subject"])
        self.assertEqual("This is my email\n", get_payload_text(outbox[0].get_body()))
        attachments = list(a for a in outbox[0].iter_attachments())
        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0].get_filename(), "original-message")
        self.assertEqual(attachments[0].get_content_type(), "application/octet-stream")
        self.assertEqual(attachments[0].get_content(), b"This is the original message")
        mock_iana_ingest.reset_mock()
        empty_outbox()

        # test overridden recipients and no attached original message
        mock_iana_ingest.side_effect = EmailIngestionError(
            "Error: do send email",
            email_body="This is my email\n",
            email_recipients=("thatguy@example.com")
        )
        with override_settings(ADMINS=[("Some Admin", "admin@example.com")]):
            r = self.client.post(
                url,
                {"dest": "iana-review", "message": message_b64},
                content_type="application/json",
                headers={"X-Api-Key": "valid-token"},
            )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["Content-Type"], "application/json")
        self.assertEqual(json.loads(r.content), {"result": "bad_msg"})
        self.assertTrue(mock_iana_ingest.called)
        self.assertEqual(mock_iana_ingest.call_args, mock.call(b"This is a message"))
        self.assertFalse(any(m.called for m in (mocks - {mock_iana_ingest})))
        self.assertEqual(len(outbox), 1)
        self.assertNotIn("admin@example.com", outbox[0]["To"])
        self.assertIn("thatguy@example.com", outbox[0]["To"])
        self.assertEqual("Error: do send email", outbox[0]["Subject"])
        self.assertEqual("This is my email\n", get_payload_text(outbox[0]))
        mock_iana_ingest.reset_mock()
        empty_outbox()

        # test attached traceback
        mock_iana_ingest.side_effect = EmailIngestionError(
            "Error: do send email",
            email_body="This is my email\n",
            email_attach_traceback=True,
        )
        with override_settings(ADMINS=[("Some Admin", "admin@example.com")]):
            r = self.client.post(
                url,
                {"dest": "iana-review", "message": message_b64},
                content_type="application/json",
                headers={"X-Api-Key": "valid-token"},
            )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["Content-Type"], "application/json")
        self.assertEqual(json.loads(r.content), {"result": "bad_msg"})
        self.assertTrue(mock_iana_ingest.called)
        self.assertEqual(mock_iana_ingest.call_args, mock.call(b"This is a message"))
        self.assertFalse(any(m.called for m in (mocks - {mock_iana_ingest})))
        self.assertEqual(len(outbox), 1)
        self.assertIn("admin@example.com", outbox[0]["To"])
        self.assertEqual("Error: do send email", outbox[0]["Subject"])
        self.assertEqual("This is my email\n", get_payload_text(outbox[0].get_body()))
        attachments = list(a for a in outbox[0].iter_attachments())
        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0].get_filename(), "traceback.txt")
        self.assertEqual(attachments[0].get_content_type(), "text/plain")
        self.assertIn("ietf.api.views.EmailIngestionError: Error: do send email", attachments[0].get_content())
        mock_iana_ingest.reset_mock()
        empty_outbox()


class DirectAuthApiTests(TestCase):

    def setUp(self):
        super().setUp()
        self.valid_token = "nSZJDerbau6WZwbEAYuQ"
        self.invalid_token = self.valid_token
        while self.invalid_token == self.valid_token:
            self.invalid_token = User.objects.make_random_password(20)
        self.url = urlreverse("ietf.api.views.directauth")
        self.valid_person = PersonFactory()
        self.valid_password = self.valid_person.user.username+"+password"
        self.invalid_password = self.valid_password
        while self.invalid_password == self.valid_password:
            self.invalid_password = User.objects.make_random_password(20)

        self.valid_body_with_good_password = self.post_dict(authtoken=self.valid_token, username=self.valid_person.user.username, password=self.valid_password)
        self.valid_body_with_bad_password = self.post_dict(authtoken=self.valid_token, username=self.valid_person.user.username, password=self.invalid_password)
        self.valid_body_with_unknown_user = self.post_dict(authtoken=self.valid_token, username="notauser@nowhere.nada", password=self.valid_password)

    def post_dict(self, authtoken, username, password):
        data = dict()
        if authtoken is not None:
            data["authtoken"] = authtoken
        if username is not None:
            data["username"] = username
        if password is not None:
            data["password"] = password
        return dict(data = json.dumps(data))

    def response_data(self, response):
        try:
            data = json.loads(response.content)
        except json.decoder.JSONDecodeError:
            data = None
        self.assertIsNotNone(data)
        return data

    def test_bad_methods(self):
        for method in (self.client.get, self.client.put, self.client.head, self.client.delete, self.client.patch):
            r = method(self.url)
            self.assertEqual(r.status_code, 405)

    def test_bad_post(self):
        for bad in [
            self.post_dict(authtoken=None, username=self.valid_person.user.username, password=self.valid_password),
            self.post_dict(authtoken=self.valid_token, username=None, password=self.valid_password),
            self.post_dict(authtoken=self.valid_token, username=self.valid_person.user.username, password=None),
            self.post_dict(authtoken=None, username=None, password=self.valid_password),
            self.post_dict(authtoken=self.valid_token, username=None, password=None),
            self.post_dict(authtoken=None, username=self.valid_person.user.username, password=None),
            self.post_dict(authtoken=None, username=None, password=None),
        ]:
            r = self.client.post(self.url, bad)
            self.assertEqual(r.status_code, 200)
            data = self.response_data(r)
            self.assertEqual(data["result"], "failure")
            self.assertEqual(data["reason"], "invalid post")
        
        bad = dict(authtoken=self.valid_token, username=self.valid_person.user.username, password=self.valid_password)
        r = self.client.post(self.url, bad)
        self.assertEqual(r.status_code, 200)
        data = self.response_data(r)
        self.assertEqual(data["result"], "failure")
        self.assertEqual(data["reason"], "invalid post")       

    def test_notokenstore(self):
        self.assertFalse(hasattr(settings, "APP_API_TOKENS"))
        r = self.client.post(self.url,self.valid_body_with_good_password)
        self.assertEqual(r.status_code, 200)
        data = self.response_data(r)
        self.assertEqual(data["result"], "failure")
        self.assertEqual(data["reason"], "invalid authtoken")

    @override_settings(APP_API_TOKENS={"ietf.api.views.directauth":"nSZJDerbau6WZwbEAYuQ"})
    def test_bad_username(self):
        r = self.client.post(self.url, self.valid_body_with_unknown_user)
        self.assertEqual(r.status_code, 200)
        data = self.response_data(r)
        self.assertEqual(data["result"], "failure")
        self.assertEqual(data["reason"], "authentication failed")

    @override_settings(APP_API_TOKENS={"ietf.api.views.directauth":"nSZJDerbau6WZwbEAYuQ"})
    def test_bad_password(self):
        r = self.client.post(self.url, self.valid_body_with_bad_password)
        self.assertEqual(r.status_code, 200)
        data = self.response_data(r)
        self.assertEqual(data["result"], "failure")
        self.assertEqual(data["reason"], "authentication failed")

    @override_settings(APP_API_TOKENS={"ietf.api.views.directauth":"nSZJDerbau6WZwbEAYuQ"})
    def test_good_password(self):
        r = self.client.post(self.url, self.valid_body_with_good_password)
        self.assertEqual(r.status_code, 200)
        data = self.response_data(r)
        self.assertEqual(data["result"], "success")

class TastypieApiTestCase(ResourceTestCaseMixin, TestCase):
    def __init__(self, *args, **kwargs):
        self.apps = {}
        for app_name in settings.INSTALLED_APPS:
            if app_name.startswith('ietf') and not app_name in OMITTED_APPS:
                app = import_module(app_name)
                name = app_name.split('.',1)[-1]
                models_path = os.path.join(os.path.dirname(app.__file__), "models.py")
                if os.path.exists(models_path):
                    self.apps[name] = app_name
        super(TastypieApiTestCase, self).__init__(*args, **kwargs)

    def test_api_top_level(self):
        client = Client(Accept='application/json')
        r = client.get("/api/v1/")
        self.assertValidJSONResponse(r)        
        resource_list = r.json()

        for name in self.apps:
            if not name in self.apps:
                sys.stderr.write("Expected a REST API resource for %s, but didn't find one\n" % name)

        for name in self.apps:
            self.assertIn(name, resource_list,
                        "Expected a REST API resource for %s, but didn't find one" % name)

    def test_all_model_resources_exist(self):
        client = Client(Accept='application/json')
        r = client.get("/api/v1")
        top = r.json()
        for name in self.apps:
            app_name = self.apps[name]
            app = import_module(app_name)
            self.assertEqual("/api/v1/%s/"%name, top[name]["list_endpoint"])
            r = client.get(top[name]["list_endpoint"])
            self.assertValidJSONResponse(r)
            app_resources = r.json()
            #
            model_list = apps.get_app_config(name).get_models()
            for model in model_list:
                if not model._meta.model_name in list(app_resources.keys()):
                    #print("There doesn't seem to be any resource for model %s.models.%s"%(app.__name__,model.__name__,))
                    self.assertIn(model._meta.model_name, list(app_resources.keys()),
                        "There doesn't seem to be any API resource for model %s.models.%s"%(app.__name__,model.__name__,))


class RfcdiffSupportTests(TestCase):

    def setUp(self):
        super().setUp()
        self.target_view = 'ietf.api.views.rfcdiff_latest_json'
        self._last_rfc_num = 8000

    def getJson(self, view_args):
        url = urlreverse(self.target_view, kwargs=view_args)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        return r.json()

    def next_rfc_number(self):
        self._last_rfc_num += 1
        return self._last_rfc_num

    def do_draft_test(self, name):
        draft = IndividualDraftFactory(name=name, rev='00', create_revisions=range(0,13))
        draft = reload_db_objects(draft)
        prev_draft_rev = f'{(int(draft.rev)-1):02d}'

        received = self.getJson(dict(name=draft.name))
        self.assertEqual(
            received,
            dict(
                name=draft.name,
                rev=draft.rev,
                content_url=draft.get_href(),
                previous=f'{draft.name}-{prev_draft_rev}',
                previous_url= draft.history_set.get(rev=prev_draft_rev).get_href(),
            ),
            'Incorrect JSON when draft revision not specified',
        )

        received = self.getJson(dict(name=draft.name, rev=draft.rev))
        self.assertEqual(
            received,
            dict(
                name=draft.name,
                rev=draft.rev,
                content_url=draft.get_href(),
                previous=f'{draft.name}-{prev_draft_rev}',
                previous_url= draft.history_set.get(rev=prev_draft_rev).get_href(),
            ),
            'Incorrect JSON when latest revision specified',
        )

        received = self.getJson(dict(name=draft.name, rev='10'))
        prev_draft_rev = '09'
        self.assertEqual(
            received,
            dict(
                name=draft.name,
                rev='10',
                content_url=draft.history_set.get(rev='10').get_href(),
                previous=f'{draft.name}-{prev_draft_rev}',
                previous_url= draft.history_set.get(rev=prev_draft_rev).get_href(),
            ),
            'Incorrect JSON when historical revision specified',
        )

        received = self.getJson(dict(name=draft.name, rev='00'))
        self.assertNotIn('previous', received, 'Rev 00 has no previous name when not replacing a draft')

        replaced = IndividualDraftFactory()
        RelatedDocument.objects.create(relationship_id='replaces',source=draft,target=replaced)
        received = self.getJson(dict(name=draft.name, rev='00'))
        self.assertEqual(received['previous'], f'{replaced.name}-{replaced.rev}',
                         'Rev 00 has a previous name when replacing a draft')

    def test_draft(self):
        # test with typical, straightforward names
        self.do_draft_test(name='draft-somebody-did-a-thing')
        # try with different potentially problematic names
        self.do_draft_test(name='draft-someone-did-something-01-02')
        self.do_draft_test(name='draft-someone-did-something-else-02')
        self.do_draft_test(name='draft-someone-did-something-02-weird-01')

    def do_draft_with_broken_history_test(self, name):
        draft = IndividualDraftFactory(name=name, rev='10')
        received = self.getJson(dict(name=draft.name,rev='09'))
        self.assertEqual(received['rev'],'09')
        self.assertEqual(received['previous'], f'{draft.name}-08')
        self.assertTrue('warning' in received)

    def test_draft_with_broken_history(self):
        # test with typical, straightforward names
        self.do_draft_with_broken_history_test(name='draft-somebody-did-something')
        # try with different potentially problematic names
        self.do_draft_with_broken_history_test(name='draft-someone-did-something-01-02')
        self.do_draft_with_broken_history_test(name='draft-someone-did-something-else-02')
        self.do_draft_with_broken_history_test(name='draft-someone-did-something-02-weird-03')

    def do_rfc_test(self, draft_name):
        draft = WgDraftFactory(name=draft_name, create_revisions=range(0,2))
        rfc = WgRfcFactory(group=draft.group, rfc_number=self.next_rfc_number())
        draft.relateddocument_set.create(relationship_id="became_rfc", target=rfc)
        draft.set_state(State.objects.get(type_id='draft',slug='rfc'))
        draft.set_state(State.objects.get(type_id='draft-iesg', slug='pub'))
        draft, rfc = reload_db_objects(draft, rfc)

        number = rfc.rfc_number
        received = self.getJson(dict(name=number))
        self.assertEqual(
            received,
            dict(
                content_url=rfc.get_href(),
                name=rfc.name,
                previous=f'{draft.name}-{draft.rev}',
                previous_url= draft.history_set.get(rev=draft.rev).get_href(),
            ),
            'Can look up an RFC by number',
        )

        num_received = received
        received = self.getJson(dict(name=rfc.name))
        self.assertEqual(num_received, received, 'RFC by canonical name gives same result as by number')

        received = self.getJson(dict(name=f'RfC {number}'))
        self.assertEqual(num_received, received, 'RFC with unusual spacing/caps gives same result as by number')

        received = self.getJson(dict(name=draft.name))
        self.assertEqual(num_received, received, 'RFC by draft name and no rev gives same result as by number')

        received = self.getJson(dict(name=draft.name, rev='01'))
        prev_draft_rev = '00'
        self.assertEqual(
            received,
            dict(
                content_url=draft.history_set.get(rev='01').get_href(),
                name=draft.name,
                rev='01',
                previous=f'{draft.name}-{prev_draft_rev}',
                previous_url= draft.history_set.get(rev=prev_draft_rev).get_href(),
            ),
            'RFC by draft name with rev should give draft name, not canonical name'
        )

    def test_rfc(self):
        # simple draft name
        self.do_rfc_test(draft_name='draft-test-ar-ef-see')
        # tricky draft names
        self.do_rfc_test(draft_name='draft-whatever-02')
        self.do_rfc_test(draft_name='draft-test-me-03-04')

    def test_rfc_with_tombstone(self):
        draft = WgDraftFactory(create_revisions=range(0,2))
        rfc = WgRfcFactory(rfc_number=3261,group=draft.group)# See views_doc.HAS_TOMBSTONE
        draft.relateddocument_set.create(relationship_id="became_rfc", target=rfc)
        draft.set_state(State.objects.get(type_id='draft',slug='rfc'))
        draft.set_state(State.objects.get(type_id='draft-iesg', slug='pub'))
        draft = reload_db_objects(draft)

        # Some old rfcs had tombstones that shouldn't be used for comparisons
        received = self.getJson(dict(name=rfc.name))
        self.assertTrue(received['previous'].endswith('00'))

    def do_rfc_with_broken_history_test(self, draft_name):
        draft = WgDraftFactory(rev='10', name=draft_name)
        rfc = WgRfcFactory(group=draft.group, rfc_number=self.next_rfc_number())
        draft.relateddocument_set.create(relationship_id="became_rfc", target=rfc)
        draft.set_state(State.objects.get(type_id='draft',slug='rfc'))
        draft.set_state(State.objects.get(type_id='draft-iesg', slug='pub'))
        draft = reload_db_objects(draft)

        received = self.getJson(dict(name=draft.name))
        self.assertEqual(
            received,
            dict(
                content_url=rfc.get_href(),
                name=rfc.name,
                previous=f'{draft.name}-10',
                previous_url= f'{settings.IETF_ID_ARCHIVE_URL}{draft.name}-10.txt',
            ),
            'RFC by draft name without rev should return canonical RFC name and no rev',
        )

        received = self.getJson(dict(name=draft.name, rev='10'))
        self.assertEqual(received['name'], draft.name, 'RFC by draft name with rev should return draft name')
        self.assertEqual(received['rev'], '10', 'Requested rev should be returned')
        self.assertEqual(received['previous'], f'{draft.name}-09', 'Previous rev is one less than requested')
        self.assertIn(f'{draft.name}-10', received['content_url'], 'Returned URL should include requested rev')
        self.assertNotIn('warning', received, 'No warning when we have the rev requested')

        received = self.getJson(dict(name=f'{draft.name}-09'))
        self.assertEqual(received['name'], draft.name, 'RFC by draft name with rev should return draft name')
        self.assertEqual(received['rev'], '09', 'Requested rev should be returned')
        self.assertEqual(received['previous'], f'{draft.name}-08', 'Previous rev is one less than requested')
        self.assertIn(f'{draft.name}-09', received['content_url'], 'Returned URL should include requested rev')
        self.assertEqual(
            received['warning'],
            'History for this version not found - these results are speculation',
            'Warning should be issued when requested rev is not found'
        )

    def test_rfc_with_broken_history(self):
        # simple draft name
        self.do_rfc_with_broken_history_test(draft_name='draft-some-draft')
        # tricky draft names
        self.do_rfc_with_broken_history_test(draft_name='draft-gizmo-01')
        self.do_rfc_with_broken_history_test(draft_name='draft-oh-boy-what-a-draft-02-03')

    def test_no_such_document(self):
        for name in ['rfc0000', 'draft-ftei-oof-rab-00']:
            url = urlreverse(self.target_view, kwargs={'name': name})
            r = self.client.get(url)
            self.assertEqual(r.status_code, 404)


class TokenTests(TestCase):
    @override_settings(APP_API_TOKENS={"known.endpoint": ["token in a list"], "oops": "token as a str"})
    def test_is_valid_token(self):
        # various invalid cases
        self.assertFalse(is_valid_token("unknown.endpoint", "token in a list"))
        self.assertFalse(is_valid_token("known.endpoint", "token"))
        self.assertFalse(is_valid_token("known.endpoint", "token as a str"))
        self.assertFalse(is_valid_token("oops", "token"))
        self.assertFalse(is_valid_token("oops", "token in a list"))
        # the only valid cases
        self.assertTrue(is_valid_token("known.endpoint", "token in a list"))
        self.assertTrue(is_valid_token("oops", "token as a str"))

    @mock.patch("ietf.api.ietf_utils.is_valid_token")
    def test_requires_api_token(self, mock_is_valid_token):
        called = False

        @requires_api_token
        def fn_to_wrap(request, *args, **kwargs):
            nonlocal called
            called = True
            return request, args, kwargs
        
        req_factory = RequestFactory()
        arg = object()
        kwarg = object()

        # No X-Api-Key header
        mock_is_valid_token.return_value = False
        val = fn_to_wrap(
            req_factory.get("/some/url", headers={}),
            arg,
            kwarg=kwarg,
        )
        self.assertTrue(isinstance(val, HttpResponseForbidden))
        self.assertFalse(mock_is_valid_token.called)
        self.assertFalse(called)

        # Bad X-Api-Key header (not resetting the mock, it was not used yet)
        val = fn_to_wrap(
            req_factory.get("/some/url", headers={"X-Api-Key": "some-value"}),
            arg, 
            kwarg=kwarg,
        )
        self.assertTrue(isinstance(val, HttpResponseForbidden))
        self.assertTrue(mock_is_valid_token.called)
        self.assertEqual(
            mock_is_valid_token.call_args[0], 
            (fn_to_wrap.__module__ + "." + fn_to_wrap.__qualname__, "some-value"),
        )
        self.assertFalse(called)

        # Valid header
        mock_is_valid_token.reset_mock()
        mock_is_valid_token.return_value = True
        request = req_factory.get("/some/url", headers={"X-Api-Key": "some-value"}) 
        # Bad X-Api-Key header (not resetting the mock, it was not used yet)
        val = fn_to_wrap(
            request,
            arg, 
            kwarg=kwarg,
        )
        self.assertEqual(val, (request, (arg,), {"kwarg": kwarg}))
        self.assertTrue(mock_is_valid_token.called)
        self.assertEqual(
            mock_is_valid_token.call_args[0], 
            (fn_to_wrap.__module__ + "." + fn_to_wrap.__qualname__, "some-value"),
        )
        self.assertTrue(called)

        # Test the endpoint setting
        @requires_api_token("endpoint")
        def another_fn_to_wrap(request):
            return "yep"
        
        val = another_fn_to_wrap(request)
        self.assertEqual(
            mock_is_valid_token.call_args[0], 
            ("endpoint", "some-value"),
        )
