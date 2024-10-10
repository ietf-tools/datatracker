# Copyright The IETF Trust 2021, All Rights Reserved
# -*- coding: utf-8 -*-
import datetime
import requests
import requests_mock

from unittest.mock import call, patch
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

from django.conf import settings
from django.test import override_settings
from django.utils import timezone

from ietf.doc.factories import DocumentFactory
from ietf.meeting.factories import SessionFactory, SessionPresentationFactory
from ietf.utils.tests import TestCase
from .meetecho import Conference, ConferenceManager, MeetechoAPI, MeetechoAPIError, SlidesManager

API_BASE = 'https://meetecho-api.example.com'
CLIENT_ID = 'datatracker'
CLIENT_SECRET = 'very secret'
API_CONFIG={
    'api_base': API_BASE,
    'client_id': CLIENT_ID,
    'client_secret': CLIENT_SECRET,
    'slides_notify_time': -1,  # always send notification
}


@override_settings(MEETECHO_API_CONFIG=API_CONFIG)
class APITests(TestCase):
    retrieve_token_url = urljoin(API_BASE, 'auth/ietfservice/tokens')
    schedule_meeting_url = urljoin(API_BASE, 'meeting/interim/createRoom')
    fetch_meetings_url = urljoin(API_BASE, 'meeting/interim/fetchRooms')
    delete_meetings_url = urljoin(API_BASE, 'meeting/interim/deleteRoom')
    slide_deck_url = urljoin(API_BASE, "materials")

    def setUp(self):
        super().setUp()
        self.requests_mock = requests_mock.Mocker()
        self.requests_mock.start()

    def tearDown(self):
        self.requests_mock.stop()
        super().tearDown()

    def test_retrieve_wg_tokens(self):
        data_to_fetch = {
            'tokens': {
                'acro': 'wg-token-value-for-acro',
                'beta': 'different-token',
                'gamma': 'this-is-not-the-same',
            }
        }
        self.requests_mock.post(self.retrieve_token_url, status_code=200, json=data_to_fetch)

        api = MeetechoAPI(API_BASE, CLIENT_ID, CLIENT_SECRET)
        api_response = api.retrieve_wg_tokens(['acro', 'beta', 'gamma'])
        self.assertTrue(self.requests_mock.called)
        request = self.requests_mock.last_request
        self.assertEqual(
            request.headers['Content-Type'],
            'application/json',
            'Incorrect request content-type',
        )
        self.assertEqual(
            request.json(),
            {
                'client': CLIENT_ID,
                'secret': CLIENT_SECRET,
                'wgs': ['acro', 'beta', 'gamma'],
            }
        )
        self.assertEqual(api_response, data_to_fetch)

    def test_schedule_meeting(self):
        self.requests_mock.post(
            self.schedule_meeting_url,
            status_code=200,
            json={
                'rooms': {
                    '3d55bce0-535e-4ba8-bb8e-734911cf3c32': {
                        'room': {
                            'id': 18,  # should match room_id in api.schedule_meeting() below
                            'start_time': '2021-09-14 10:00:00',
                            'duration': 130,
                            'description': 'interim-2021-wgname-01',
                        },
                        'url': 'https://meetings.conf.meetecho.com/interim/?short=3d55bce0-535e-4ba8-bb8e-734911cf3c32',
                        'deletion_token': 'session-deletion-token',
                    },
                }
            },
        )

        api = MeetechoAPI(API_BASE, CLIENT_ID, CLIENT_SECRET)
        api_response = api.schedule_meeting(
            wg_token='my-token',
            room_id=18,
            start_time=datetime.datetime(2021, 9, 14, 10, 0, 0, tzinfo=datetime.timezone.utc),
            duration=datetime.timedelta(minutes=130),
            description='interim-2021-wgname-01',
            extrainfo='message for staff',
        )

        self.assertTrue(self.requests_mock.called)
        request = self.requests_mock.last_request
        self.assertIn('Authorization', request.headers)
        self.assertEqual(
            request.headers['Content-Type'],
            'application/json',
            'Incorrect request content-type',
        )
        self.assertEqual(request.headers['Authorization'], 'bearer my-token',
                         'Incorrect request authorization header')
        self.assertEqual(
            request.json(),
            {
                'room_id': 18,
                'duration': 130,
                'start_time': '2021-09-14 10:00:00',
                'extrainfo': 'message for staff',
                'description': 'interim-2021-wgname-01',
            },
            'Incorrect request content'
        )
        # same time in different time zones
        for start_time in [
            datetime.datetime(2021, 9, 14, 10, 0, 0, tzinfo=datetime.timezone.utc),
            datetime.datetime(2021, 9, 14, 7, 0, 0, tzinfo=ZoneInfo('America/Halifax')),
            datetime.datetime(2021, 9, 14, 13, 0, 0, tzinfo=ZoneInfo('Europe/Kiev')),
            datetime.datetime(2021, 9, 14, 5, 0, 0, tzinfo=ZoneInfo('Pacific/Easter')),
            datetime.datetime(2021, 9, 14, 11, 0, 0, tzinfo=ZoneInfo('Africa/Porto-Novo')),
        ]:
            self.assertEqual(
                api_response,
                {
                    'rooms': {
                        '3d55bce0-535e-4ba8-bb8e-734911cf3c32': {
                            'room': {
                                'id': 18,
                                'start_time': start_time,
                                'duration': datetime.timedelta(minutes=130),
                                'description': 'interim-2021-wgname-01',
                            },
                            'url': 'https://meetings.conf.meetecho.com/interim/?short=3d55bce0-535e-4ba8-bb8e-734911cf3c32',
                            'deletion_token': 'session-deletion-token',
                        },
                    }
                },
                f'Incorrect time conversion for {start_time.tzinfo}',
            )

    def test_fetch_meetings(self):
        self.maxDiff = 2048
        self.requests_mock.get(
            self.fetch_meetings_url,
            status_code=200,
            json={
                'rooms': {
                    '3d55bce0-535e-4ba8-bb8e-734911cf3c32': {
                        'room': {
                            'id': 18,
                            'start_time': '2021-09-14 10:00:00',
                            'duration': 130,
                            'description': 'interim-2021-wgname-01',
                        },
                        'url': 'https://meetings.conf.meetecho.com/interim/?short=3d55bce0-535e-4ba8-bb8e-734911cf3c32',
                        'deletion_token': 'session-deletion-token-01',
                    },
                    'e68e96d4-d38f-475b-9073-ecab46ca96a5': {
                        'room': {
                            'id': 23,
                            'start_time': '2021-09-15 14:30:00',
                            'duration': 30,
                            'description': 'interim-2021-wgname-02',
                        },
                        'url': 'https://meetings.conf.meetecho.com/interim/?short=e68e96d4-d38f-475b-9073-ecab46ca96a5',
                        'deletion_token': 'session-deletion-token-02',
                    },
                }
            },
        )

        api = MeetechoAPI(API_BASE, CLIENT_ID, CLIENT_SECRET)
        api_response = api.fetch_meetings(wg_token='my-token')

        self.assertTrue(self.requests_mock.called)
        request = self.requests_mock.last_request
        self.assertIn('Authorization', request.headers)
        self.assertEqual(request.headers['Authorization'], 'bearer my-token',
                         'Incorrect request authorization header')
        self.assertEqual(
            api_response,
            {
                'rooms': {
                    '3d55bce0-535e-4ba8-bb8e-734911cf3c32': {
                        'room': {
                            'id': 18,
                            'start_time': datetime.datetime(2021, 9, 14, 10, 0, 0, tzinfo=datetime.timezone.utc),
                            'duration': datetime.timedelta(minutes=130),
                            'description': 'interim-2021-wgname-01',
                        },
                        'url': 'https://meetings.conf.meetecho.com/interim/?short=3d55bce0-535e-4ba8-bb8e-734911cf3c32',
                        'deletion_token': 'session-deletion-token-01',
                    },
                    'e68e96d4-d38f-475b-9073-ecab46ca96a5': {
                        'room': {
                            'id': 23,
                            'start_time': datetime.datetime(2021, 9, 15, 14, 30, 0, tzinfo=datetime.timezone.utc),
                            'duration': datetime.timedelta(minutes=30),
                            'description': 'interim-2021-wgname-02',
                        },
                        'url': 'https://meetings.conf.meetecho.com/interim/?short=e68e96d4-d38f-475b-9073-ecab46ca96a5',
                        'deletion_token': 'session-deletion-token-02',
                    },
                }
            },
        )

    def test_delete_meeting(self):
        data_to_fetch = {}
        self.requests_mock.post(self.delete_meetings_url, status_code=200, json=data_to_fetch)

        api = MeetechoAPI(API_BASE, CLIENT_ID, CLIENT_SECRET)
        api_response = api.delete_meeting(deletion_token='delete-this-meeting-please')

        self.assertTrue(self.requests_mock.called)
        request = self.requests_mock.last_request
        self.assertIn('Authorization', request.headers)
        self.assertEqual(request.headers['Authorization'], 'bearer delete-this-meeting-please',
                         'Incorrect request authorization header')
        self.assertIsNone(request.body, 'Delete meeting request has no body')
        self.assertCountEqual(api_response, data_to_fetch)

    def test_add_slide_deck(self):
        self.requests_mock.post(self.slide_deck_url, status_code=202)
        
        api = MeetechoAPI(API_BASE, CLIENT_ID, CLIENT_SECRET)
        api_response = api.add_slide_deck(
            wg_token="my-token",
            session="1234",
            deck={
                "title": "A Slide Deck",
                "id": 17,
                "url": "https://example.com/decks/17",
                "rev": "00",
                "order": 0,
            }
        )
        self.assertIsNone(api_response)  # no return value from this call

        self.assertTrue(self.requests_mock.called)
        request = self.requests_mock.last_request
        self.assertIn("Authorization", request.headers)
        self.assertEqual(
            request.headers["Content-Type"],
            "application/json",
            "Incorrect request content-type",
        )
        self.assertEqual(request.headers["Authorization"], "bearer my-token",
                         "Incorrect request authorization header")
        self.assertEqual(
            request.json(),
            {
                "session": "1234",
                "title": "A Slide Deck",
                "id": 17,
                "url": "https://example.com/decks/17",
                "rev": "00",
                "order": 0,
            },
            "Incorrect request content"
        )

    def test_delete_slide_deck(self):
        self.requests_mock.delete(self.slide_deck_url, status_code=202)

        api = MeetechoAPI(API_BASE, CLIENT_ID, CLIENT_SECRET)
        api_response = api.delete_slide_deck(
            wg_token="my-token",
            session="1234",
            id=17,
        )
        self.assertIsNone(api_response)  # no return value from this call

        self.assertTrue(self.requests_mock.called)
        request = self.requests_mock.last_request
        self.assertIn("Authorization", request.headers)
        self.assertEqual(
            request.headers["Content-Type"],
            "application/json",
            "Incorrect request content-type",
        )
        self.assertEqual(request.headers["Authorization"], "bearer my-token",
                         "Incorrect request authorization header")
        self.assertEqual(
            request.json(),
            {
                "session": "1234",
                "id": 17,
            },
            "Incorrect request content"
        )

    def test_update_slide_decks(self):
        self.requests_mock.put(self.slide_deck_url, status_code=202)

        api = MeetechoAPI(API_BASE, CLIENT_ID, CLIENT_SECRET)
        api_response = api.update_slide_decks(
            wg_token="my-token",
            session="1234",
            decks=[
                {
                    "title": "A Slide Deck",
                    "id": 17,
                    "url": "https://example.com/decks/17",
                    "rev": "00",
                    "order": 0,
                },
                {
                    "title": "Another Slide Deck",
                    "id": 23,
                    "url": "https://example.com/decks/23",
                    "rev": "03",
                    "order": 1,
                }
            ]
        )
        self.assertIsNone(api_response)  # no return value from this call

        self.assertTrue(self.requests_mock.called)
        request = self.requests_mock.last_request
        self.assertIn("Authorization", request.headers)
        self.assertEqual(
            request.headers["Content-Type"],
            "application/json",
            "Incorrect request content-type",
        )
        self.assertEqual(request.headers["Authorization"], "bearer my-token",
                         "Incorrect request authorization header")
        self.assertEqual(
            request.json(),
            {
                "session": "1234",
                "decks": [
                    {
                        "title": "A Slide Deck",
                        "id": 17,
                        "url": "https://example.com/decks/17",
                        "rev": "00",
                        "order": 0,
                    },
                    {
                        "title": "Another Slide Deck",
                        "id": 23,
                        "url": "https://example.com/decks/23",
                        "rev": "03",
                        "order": 1,
                    },
                ],
            },
            "Incorrect request content"
        )

    def test_request_helper_failed_requests(self):
        self.requests_mock.register_uri(requests_mock.ANY, urljoin(API_BASE, 'unauthorized/url/endpoint'), status_code=401)
        self.requests_mock.register_uri(requests_mock.ANY, urljoin(API_BASE, 'forbidden/url/endpoint'), status_code=403)
        self.requests_mock.register_uri(requests_mock.ANY, urljoin(API_BASE, 'notfound/url/endpoint'), status_code=404)
        api = MeetechoAPI(API_BASE, CLIENT_ID, CLIENT_SECRET)
        for method in ['POST', 'GET']:
            for code, endpoint in ((401, 'unauthorized/url/endpoint'), (403, 'forbidden/url/endpoint'), (404, 'notfound/url/endpoint')):
                with self.assertRaises(Exception) as context:
                    api._request(method, endpoint)
                self.assertIsInstance(context.exception, MeetechoAPIError)
                self.assertIn(str(code), str(context.exception))

    def test_request_helper_exception(self):
        self.requests_mock.register_uri(requests_mock.ANY, urljoin(API_BASE, 'exception/url/endpoint'), exc=requests.exceptions.RequestException)
        api = MeetechoAPI(API_BASE, CLIENT_ID, CLIENT_SECRET)
        for method in ['POST', 'GET']:
            with self.assertRaises(Exception) as context:
                api._request(method, 'exception/url/endpoint')
            self.assertIsInstance(context.exception, MeetechoAPIError)

    def test_time_serialization(self):
        """Time de/serialization should be consistent"""
        time = timezone.now().astimezone(datetime.timezone.utc).replace(microsecond=0)  # cut off to 0 microseconds
        api = MeetechoAPI(API_BASE, CLIENT_ID, CLIENT_SECRET)
        self.assertEqual(api._deserialize_time(api._serialize_time(time)), time)


@override_settings(MEETECHO_API_CONFIG=API_CONFIG)
class ConferenceManagerTests(TestCase):
    def test_conference_from_api_dict(self):
        confs = Conference.from_api_dict(
            None,
            {
                'session-1-uuid': {
                    'room': {
                        'id': 1,
                        'start_time': datetime.datetime(2022,2,4,1,2,3, tzinfo=datetime.timezone.utc),
                        'duration': datetime.timedelta(minutes=45),
                        'description': 'some-description',
                    },
                    'url': 'https://example.com/some/url',
                    'deletion_token': 'delete-me',
                },
                'session-2-uuid': {
                    'room': {
                        'id': 2,
                        'start_time': datetime.datetime(2022,2,5,4,5,6, tzinfo=datetime.timezone.utc),
                        'duration': datetime.timedelta(minutes=90),
                        'description': 'another-description',
                    },
                    'url': 'https://example.com/another/url',
                    'deletion_token': 'delete-me-too',
                },
            }
        )
        self.assertCountEqual(
            confs,
            [
                Conference(
                    manager=None,
                    id=1,
                    public_id='session-1-uuid',
                    description='some-description',
                    start_time=datetime.datetime(2022, 2, 4, 1, 2, 3, tzinfo=datetime.timezone.utc),
                    duration=datetime.timedelta(minutes=45),
                    url='https://example.com/some/url',
                    deletion_token='delete-me',
                ),
                Conference(
                    manager=None,
                    id=2,
                    public_id='session-2-uuid',
                    description='another-description',
                    start_time=datetime.datetime(2022, 2, 5, 4, 5, 6, tzinfo=datetime.timezone.utc),
                    duration=datetime.timedelta(minutes=90),
                    url='https://example.com/another/url',
                    deletion_token='delete-me-too',
                ),
            ]
        )

    @patch.object(ConferenceManager, 'wg_token', return_value='atoken')
    @patch('ietf.utils.meetecho.MeetechoAPI.fetch_meetings')
    def test_fetch(self, mock_fetch, _):
        mock_fetch.return_value = {
            'rooms': {
                'session-1-uuid': {
                    'room': {
                        'id': 1,
                        'start_time': datetime.datetime(2022,2,4,1,2,3, tzinfo=datetime.timezone.utc),
                        'duration': datetime.timedelta(minutes=45),
                        'description': 'some-description',
                    },
                    'url': 'https://example.com/some/url',
                    'deletion_token': 'delete-me',
                },
            }
        }

        cm = ConferenceManager(settings.MEETECHO_API_CONFIG)
        fetched = cm.fetch('acronym')
        self.assertEqual(
            fetched,
            [Conference(
                manager=cm,
                id=1,
                public_id='session-1-uuid',
                description='some-description',
                start_time=datetime.datetime(2022,2,4,1,2,3, tzinfo=datetime.timezone.utc),
                duration=datetime.timedelta(minutes=45),
                url='https://example.com/some/url',
                deletion_token='delete-me',
            )],
        )
        self.assertEqual(mock_fetch.call_args[0], ('atoken',))

    @patch.object(ConferenceManager, 'wg_token', return_value='atoken')
    @patch('ietf.utils.meetecho.MeetechoAPI.schedule_meeting')
    def test_create(self, mock_schedule, _):
        mock_schedule.return_value = {
            'rooms': {
                'session-1-uuid': {
                    'room': {
                        'id': 1,  # value should match session_id param to cm.create() below 
                        'start_time': datetime.datetime(2022,2,4,1,2,3, tzinfo=datetime.timezone.utc),
                        'duration': datetime.timedelta(minutes=45),
                        'description': 'some-description',
                    },
                    'url': 'https://example.com/some/url',
                    'deletion_token': 'delete-me',
                },
            },
        }
        cm = ConferenceManager(settings.MEETECHO_API_CONFIG)
        result = cm.create('group', '1', 'desc', 'starttime', 'dur', 'extra')
        self.assertEqual(
            result,
            [Conference(
                manager=cm,
                id=1,
                public_id='session-1-uuid',
                description='some-description',
                start_time=datetime.datetime(2022,2,4,1,2,3, tzinfo=datetime.timezone.utc),
                duration=datetime.timedelta(minutes=45),
                url='https://example.com/some/url',
                deletion_token='delete-me',
            )]
        )
        args, kwargs = mock_schedule.call_args
        self.assertEqual(
            kwargs,
            {
                'wg_token': 'atoken',
                'room_id': 1,
                'description': 'desc',
                'start_time': 'starttime',
                'duration': 'dur',
                'extrainfo': 'extra',
            })

    @patch('ietf.utils.meetecho.MeetechoAPI.delete_meeting')
    def test_delete_conference(self, mock_delete):
        cm = ConferenceManager(settings.MEETECHO_API_CONFIG)
        cm.delete_conference(Conference(None, None, None, None, None, None, None, 'delete-this'))
        args, kwargs = mock_delete.call_args
        self.assertEqual(args, ('delete-this',))

    @patch('ietf.utils.meetecho.MeetechoAPI.delete_meeting')
    def test_delete_by_url(self, mock_delete):
        cm = ConferenceManager(settings.MEETECHO_API_CONFIG)
        cm.delete_conference(Conference(None, None, None, None, None, None, 'the-url', 'delete-this'))
        args, kwargs = mock_delete.call_args
        self.assertEqual(args, ('delete-this',))


@patch.object(SlidesManager, 'wg_token', return_value='atoken')
@override_settings(MEETECHO_API_CONFIG=API_CONFIG)
class SlidesManagerTests(TestCase):
    @patch("ietf.utils.meetecho.MeetechoAPI.add_slide_deck")
    def test_add(self, mock_add, mock_wg_token):
        sm = SlidesManager(settings.MEETECHO_API_CONFIG)
        session = SessionFactory()
        slides_doc = DocumentFactory(type_id="slides")
        sm.add(session, slides_doc, 13)
        self.assertTrue(mock_wg_token.called)
        self.assertTrue(mock_add.called)
        self.assertEqual(
            mock_add.call_args,
            call(
                wg_token="atoken",
                session=str(session.pk),
                deck={
                    "id": slides_doc.pk,
                    "title": slides_doc.title,
                    "url": slides_doc.get_href(session.meeting),
                    "rev": slides_doc.rev,
                    "order": 13,
                },
            ),
        )

    @patch("ietf.utils.meetecho.MeetechoAPI.update_slide_decks")
    @patch("ietf.utils.meetecho.MeetechoAPI.delete_slide_deck")
    def test_delete(self, mock_delete, mock_update, mock_wg_token):
        sm = SlidesManager(settings.MEETECHO_API_CONFIG)
        # Test scenario: we had a session with two slide decks and we already deleted the SessionPresentation
        # for one and are now updating Meetecho
        slides = SessionPresentationFactory(document__type_id="slides", order=1)  # still attached to the session
        session = slides.session
        slides_doc = slides.document
        removed_slides_doc = DocumentFactory(type_id="slides")
        
        with self.assertRaises(MeetechoAPIError):
            sm.delete(session, slides_doc)  # can't remove slides still attached to the session
        self.assertFalse(any([mock_wg_token.called, mock_delete.called, mock_update.called]))

        sm.delete(session, removed_slides_doc)
        self.assertTrue(mock_wg_token.called)
        self.assertTrue(mock_delete.called)
        self.assertEqual(
            mock_delete.call_args,
            call(wg_token="atoken", session=str(session.pk), id=removed_slides_doc.pk),
        )
        self.assertTrue(mock_update.called)
        self.assertEqual(
            mock_update.call_args,
            call(
                wg_token="atoken",
                session=str(session.pk),
                decks=[
                    {
                        "id": slides_doc.pk,
                        "title": slides_doc.title,
                        "url": slides_doc.get_href(session.meeting),
                        "rev": slides_doc.rev,
                        "order": 1,
                    },
                ]
            )
        )
        mock_delete.reset_mock()
        mock_update.reset_mock()
        
        # Delete the other session and check that we don't make the update call
        slides.delete()
        sm.delete(session, slides_doc)
        self.assertTrue(mock_delete.called)
        self.assertFalse(mock_update.called)

    @patch("ietf.utils.meetecho.MeetechoAPI.delete_slide_deck")
    @patch("ietf.utils.meetecho.MeetechoAPI.add_slide_deck")
    def test_revise(self, mock_add, mock_delete, mock_wg_token):
        sm = SlidesManager(settings.MEETECHO_API_CONFIG)
        slides = SessionPresentationFactory(document__type_id="slides", order=23)
        slides_doc = slides.document
        sm.revise(slides.session, slides.document)
        self.assertTrue(mock_wg_token.called)
        self.assertTrue(mock_delete.called)
        self.assertEqual(
            mock_delete.call_args,
            call(wg_token="atoken", session=str(slides.session.pk), id=slides_doc.pk),
        )
        self.assertTrue(mock_add.called)
        self.assertEqual(
            mock_add.call_args,
            call(
                wg_token="atoken",
                session=str(slides.session.pk),
                deck={
                    "id": slides_doc.pk,
                    "title": slides_doc.title,
                    "url": slides_doc.get_href(slides.session.meeting),
                    "rev": slides_doc.rev,
                    "order": 23,
                },
            ),
        )


    @patch("ietf.utils.meetecho.MeetechoAPI.update_slide_decks")
    def test_send_update(self, mock_send_update, mock_wg_token):
        sm = SlidesManager(settings.MEETECHO_API_CONFIG)
        slides = SessionPresentationFactory(document__type_id="slides")
        SessionPresentationFactory(session=slides.session, document__type_id="agenda")
        sm.send_update(slides.session)
        self.assertTrue(mock_wg_token.called)
        self.assertTrue(mock_send_update.called)
        self.assertEqual(
            mock_send_update.call_args,
            call(
                wg_token="atoken",
                session=str(slides.session_id),
                decks=[
                    {
                        "id": slides.document_id,
                        "title": slides.document.title,
                        "url": slides.document.get_href(slides.session.meeting),
                        "rev": slides.document.rev,
                        "order": 0,
                    }
                ]
            )
        )
