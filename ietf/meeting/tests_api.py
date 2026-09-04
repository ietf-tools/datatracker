# Copyright The IETF Trust 2026, All Rights Reserved
import datetime
import json
from pathlib import Path
from unittest.mock import PropertyMock, patch

from django.test import override_settings
from django.urls import reverse as urlreverse

from ietf.doc.models import Document
from ietf.doc.utils import get_unicode_document_content
from ietf.meeting.factories import (
    AttendedFactory,
    MeetingFactory,
    RegistrationFactory,
    SessionFactory,
)
from ietf.meeting.models import Attended, Registration, Session
from ietf.person.factories import EmailFactory, PersonFactory, PersonUUIDFactory
from ietf.person.models import Person
from ietf.utils.test_utils import TestCase


@override_settings(
    APP_API_TOKENS={"ietf.api.meeting.registration.attended": "valid-token"}
)
class MeetingsAttendedByEmailTests(TestCase):
    VIEWNAME = "ietf.api.meeting.registration.attended"

    def setUp(self):
        super().setUp()
        self.person = PersonFactory()

    def attended_for(self, email=None):
        """Retrieve the "attended" list for an email address"""
        url = urlreverse(
            self.VIEWNAME, kwargs={"email": email or self.person.email_address()}
        )
        r = self.client.get(url, headers={"X-Api-Key": "valid-token"})
        self.assertEqual(r.status_code, 200)
        return r.json()["attended"]

    @staticmethod
    def ietf_meeting(number):
        return MeetingFactory(type_id="ietf", number=number, populate_schedule=False)

    def test_endpoint_is_plumbed(self):
        url = urlreverse(self.VIEWNAME, kwargs={"email": self.person.email_address()})
        # bad/missing API keys
        r = self.client.get(url)
        self.assertEqual(r.status_code, 403, "should require api key")
        r = self.client.get(url, headers={"X-Api-Key": "invalid-token"})
        self.assertEqual(r.status_code, 403, "should require valid api key")

        # valid request
        r = self.client.get(url, headers={"X-Api-Key": "valid-token"})
        self.assertEqual(r.status_code, 200, "should accept valid api key")
        self.assertEqual(r.json(), {"attended": []})

        # nonexistent person
        self.person.email_set.update(person=None)  # detach email
        self.person.delete()
        r = self.client.get(url, headers={"X-Api-Key": "valid-token"})
        self.assertEqual(r.status_code, 404, "404 for no such Person")

    def test_lists_registrations_with_attendance_evidence(self):
        """Registrations for IETF 110+ that were attended are listed

        Attendance is indicated by the attended flag, the checkedin flag, or an Attended
        record. These records only had their modern form starting at IETF 110.
        """
        attended = self.ietf_meeting("118")
        RegistrationFactory(meeting=attended, person=self.person, attended=True)
        checkedin = self.ietf_meeting("119")
        RegistrationFactory(meeting=checkedin, person=self.person, checkedin=True)
        session_attended = self.ietf_meeting("120")
        RegistrationFactory(meeting=session_attended, person=self.person)
        AttendedFactory(
            session__meeting=session_attended,
            session__add_to_schedule=False,  # these meetings have no timeslots
            person=self.person,
        )

        # another person's registrations for the same meetings must not appear
        other_person = PersonFactory()
        for meeting in [attended, checkedin, session_attended]:
            RegistrationFactory(meeting=meeting, person=other_person, attended=True)

        self.assertCountEqual(
            [entry["meeting"] for entry in self.attended_for()], ["118", "119", "120"]
        )

    def test_excludes_registrations_without_attendance_evidence(self):
        """Only attended IETF meetings from 110 onwards are reported"""
        RegistrationFactory(meeting=self.ietf_meeting("118"), person=self.person)
        RegistrationFactory(
            meeting=self.ietf_meeting("109"), person=self.person, attended=True
        )
        RegistrationFactory(
            meeting=MeetingFactory(type_id="interim", populate_schedule=False),
            person=self.person,
            attended=True,
        )

        self.assertEqual(self.attended_for(), [])

    def test_reports_attendance_and_ticket_type(self):
        """Ticket details are taken from the Registration's plenary_* properties"""
        RegistrationFactory(
            meeting=self.ietf_meeting("118"), person=self.person, attended=True
        )

        with (
            patch.object(
                Registration, "plenary_attendance_type", new_callable=PropertyMock
            ) as attendance_type,
            patch.object(
                Registration, "plenary_ticket_type", new_callable=PropertyMock
            ) as ticket_type,
        ):
            attendance_type.return_value = "onsite"
            ticket_type.return_value = "week_pass"
            self.assertEqual(
                self.attended_for(),
                [
                    {
                        "meeting": "118",
                        "attendance_type": "onsite",
                        "ticket_type": "week_pass",
                    }
                ],
            )

            # absent ticket details are reported as null
            attendance_type.return_value = None
            ticket_type.return_value = None
            self.assertEqual(
                self.attended_for(),
                [{"meeting": "118", "attendance_type": None, "ticket_type": None}],
            )

    def test_finds_person_by_any_email_address(self):
        """Any of the Person's email addresses identifies them"""
        RegistrationFactory(
            meeting=self.ietf_meeting("118"), person=self.person, attended=True
        )
        secondary_email = EmailFactory(person=self.person)

        by_secondary = self.attended_for(email=secondary_email.address)
        self.assertEqual([entry["meeting"] for entry in by_secondary], ["118"])
        self.assertEqual(by_secondary, self.attended_for())

    def test_excludes_non_plenary_registrations(self):
        """Registrations without an onsite or remote plenary ticket are not reported"""
        RegistrationFactory(
            meeting=self.ietf_meeting("118"),
            person=self.person,
            attended=True,
            with_ticket={"attendance_type_id": "onsite", "ticket_type_id": "week_pass"},
        )
        RegistrationFactory(
            meeting=self.ietf_meeting("119"),
            person=self.person,
            attended=True,
            with_ticket={
                "attendance_type_id": "hackathon_remote",
                "ticket_type_id": "unknown",
            },
        )

        attended = self.attended_for()
        self.assertEqual([entry["meeting"] for entry in attended], ["118"])
        self.assertEqual({entry["attendance_type"] for entry in attended}, {"onsite"})


TOKEN = "valid-token"

SESSION_DATA_TOKENS = {
    f"ietf.api.meeting.session.{name}": TOKEN
    for name in [
        "video_url",
        "recording_name",
        "bluesheet",
        "attendees",
        "chatlog",
        "polls",
    ]
}


@override_settings(APP_API_TOKENS=SESSION_DATA_TOKENS)
class SessionDataApiTests(TestCase):
    settings_temp_path_overrides = TestCase.settings_temp_path_overrides + [
        "AGENDA_PATH"
    ]

    def setUp(self):
        super().setUp()
        self.meeting = MeetingFactory(type_id="ietf")
        self.session = SessionFactory(group__type_id="wg", meeting=self.meeting)
        self.system = Person.objects.get(name="(System)")

    def url(self, name, session=None):
        return urlreverse(
            f"ietf.api.meeting.session.{name}",
            kwargs={"session_id": (session or self.session).pk},
        )

    def post(self, name, payload, token=TOKEN, session=None):
        return self.client.post(
            self.url(name, session=session),
            data=json.dumps(payload),
            content_type="application/json",
            headers={"X-Api-Key": token},
        )

    def unscheduled_session(self, meeting=None):
        return SessionFactory(
            group__type_id="wg",
            meeting=meeting or self.meeting,
            add_to_schedule=False,
        )

    def materials(self, type_id, doc):
        path = Path(self.meeting.get_materials_path()) / type_id / doc.uploaded_filename
        return get_unicode_document_content(doc.name, path)

    # --- plumbing, shared by every endpoint in this group ---

    def test_endpoints_are_plumbed(self):
        payloads = {
            "video_url": {"url": "https://example.com/v"},
            "recording_name": {"name": "a-name"},
            "bluesheet": {"bluesheet": []},
            "attendees": {"attendees": []},
            "chatlog": {"chatlog": []},
            "polls": {"polls": []},
        }
        for name, payload in payloads.items():
            with self.subTest(endpoint=name):
                r = self.client.post(
                    self.url(name),
                    data=json.dumps(payload),
                    content_type="application/json",
                )
                self.assertEqual(r.status_code, 403, "should require api key")

                r = self.post(name, payload, token="invalid-token")
                self.assertEqual(r.status_code, 403, "should require valid api key")

                r = self.post(name, payload)
                self.assertEqual(r.status_code, 200, r.content)
                self.assertEqual(r.json(), {"session_id": self.session.pk})

                self.assertEqual(
                    self.client.get(
                        self.url(name), headers={"X-Api-Key": TOKEN}
                    ).status_code,
                    405,
                    "should not accept GET",
                )

    def test_unknown_session_is_404(self):
        missing = Session.objects.order_by("-pk").first().pk + 1
        r = self.client.post(
            urlreverse(
                "ietf.api.meeting.session.recording_name",
                kwargs={"session_id": missing},
            ),
            data=json.dumps({"name": "a-name"}),
            content_type="application/json",
            headers={"X-Api-Key": TOKEN},
        )
        self.assertEqual(r.status_code, 404)

    def test_malformed_payload_is_400(self):
        for name, payload in [
            ("recording_name", {}),
            ("video_url", {"url": "not a url"}),
            ("attendees", {"attendees": [{"person_uuid": "not-a-uuid"}]}),
            ("chatlog", {"chatlog": "not a list"}),
            ("polls", {"polls": [1, 2, 3]}),
        ]:
            with self.subTest(endpoint=name):
                self.assertEqual(self.post(name, payload).status_code, 400)

    # --- recording name ---

    def test_sets_recording_name(self):
        self.post("recording_name", {"name": "the-recording"})
        self.session.refresh_from_db()
        self.assertEqual(self.session.meetecho_recording_name, "the-recording")

    def test_rejects_recording_name_the_column_cannot_hold(self):
        r = self.post("recording_name", {"name": "x" * 65})
        self.assertEqual(r.status_code, 400)
        self.session.refresh_from_db()
        self.assertEqual(self.session.meetecho_recording_name, "")

    # --- video url ---

    def test_creates_video_recording(self):
        self.post("video_url", {"url": "https://example.com/first"})
        recordings = [
            d for d in self.session.recordings() if "video" in d.title.lower()
        ]
        self.assertEqual(len(recordings), 1)
        self.assertEqual(recordings[0].external_url, "https://example.com/first")
        self.assertEqual(
            recordings[0].docevent_set.first().by,
            self.system,
            "events are attributed to the (System) person",
        )

    def test_updates_existing_video_recording(self):
        self.post("video_url", {"url": "https://example.com/first"})
        self.post("video_url", {"url": "https://example.com/second"})
        recordings = [
            d for d in self.session.recordings() if "video" in d.title.lower()
        ]
        self.assertEqual(len(recordings), 1, "no second recording document")
        self.assertEqual(recordings[0].external_url, "https://example.com/second")
        self.assertTrue(
            recordings[0]
            .docevent_set.filter(type="added_comment", by=self.system)
            .exists()
        )

    def test_rejects_video_url_the_column_cannot_hold(self):
        """An over-long URL is refused before any document or event is written"""
        r = self.post("video_url", {"url": "https://example.com/" + "a" * 250})
        self.assertEqual(r.status_code, 400)
        self.assertFalse(self.session.recordings())

    def test_rejects_video_url_update_the_column_cannot_hold(self):
        """The update path refuses it too, leaving the recording and its history alone"""
        self.post("video_url", {"url": "https://example.com/first"})
        doc = self.session.recordings()[0]
        events_before = doc.docevent_set.count()

        r = self.post("video_url", {"url": "https://example.com/" + "a" * 250})
        self.assertEqual(r.status_code, 400)
        doc.refresh_from_db()
        self.assertEqual(doc.external_url, "https://example.com/first")
        self.assertEqual(doc.docevent_set.count(), events_before)

    def test_video_url_without_official_timeslot_is_400(self):
        r = self.post(
            "video_url",
            {"url": "https://example.com/v"},
            session=self.unscheduled_session(),
        )
        self.assertEqual(r.status_code, 400)

    # --- bluesheet ---

    def test_uploads_bluesheet(self):
        r = self.post(
            "bluesheet",
            {
                "bluesheet": [
                    {"name": "Some Body", "affiliation": "Some Organization"},
                    {"name": "Another Body", "affiliation": ""},
                ]
            },
        )
        self.assertEqual(r.status_code, 200, r.content)
        doc = self.session.presentations.get(document__type_id="bluesheets").document
        self.assertEqual(doc.rev, "00")
        content = self.materials("bluesheets", doc)
        self.assertIn("Some Body", content)
        self.assertIn("Some Organization", content)
        self.assertIn("Another Body", content)
        self.assertEqual(doc.docevent_set.first().by, self.system)

    def test_bluesheet_upload_bumps_revision(self):
        self.post("bluesheet", {"bluesheet": [{"name": "Some Body"}]})
        self.post("bluesheet", {"bluesheet": [{"name": "Another Body"}]})
        doc = self.session.presentations.get(document__type_id="bluesheets").document
        self.assertEqual(doc.rev, "01")
        self.assertIn("Another Body", self.materials("bluesheets", doc))

    def test_bluesheet_without_official_timeslot_is_400(self):
        r = self.post(
            "bluesheet",
            {"bluesheet": [{"name": "Some Body"}]},
            session=self.unscheduled_session(),
        )
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Document.objects.filter(type_id="bluesheets").exists())

    # --- chatlog and polls ---

    def test_uploads_chatlog(self):
        chatlog = [
            {
                "author": "Some Body",
                "text": "<p>a remark</p>",
                "time": "2022-07-28T19:26:16Z",
            }
        ]
        r = self.post("chatlog", {"chatlog": chatlog})
        self.assertEqual(r.status_code, 200, r.content)
        doc = self.session.presentations.get(document__type_id="chatlog").document
        self.assertEqual(json.loads(self.materials("chatlog", doc)), chatlog)
        self.assertEqual(doc.docevent_set.first().by, self.system)

    def test_uploads_polls(self):
        polls = [
            {
                "start_time": "2022-07-28T19:19:54Z",
                "end_time": "2022-07-28T19:20:23Z",
                "text": "Are you willing to review the documents?",
                "raise_hand": 57,
                "do_not_raise_hand": 11,
            }
        ]
        r = self.post("polls", {"polls": polls})
        self.assertEqual(r.status_code, 200, r.content)
        doc = self.session.presentations.get(document__type_id="polls").document
        self.assertEqual(json.loads(self.materials("polls", doc)), polls)

    def test_chatlog_upload_bumps_revision(self):
        self.post("chatlog", {"chatlog": [{"author": "A", "text": "one"}]})
        self.post("chatlog", {"chatlog": [{"author": "A", "text": "two"}]})
        doc = self.session.presentations.get(document__type_id="chatlog").document
        self.assertEqual(doc.rev, "01")
        self.assertEqual(
            json.loads(self.materials("chatlog", doc)),
            [{"author": "A", "text": "two"}],
        )

    def test_chatlog_without_official_timeslot_is_400(self):
        r = self.post(
            "chatlog",
            {"chatlog": []},
            session=self.unscheduled_session(),
        )
        self.assertEqual(r.status_code, 400)

    # --- attendees ---

    def attend(self, entries, session=None):
        return self.post("attendees", {"attendees": entries}, session=session)

    @staticmethod
    def attendee(person_uuid, join_time="2024-02-21T18:00:00Z"):
        return {"person_uuid": str(person_uuid), "join_time": join_time}

    def test_records_attendees_by_uuid(self):
        people = PersonFactory.create_batch(2)
        r = self.attend(
            [
                self.attendee(people[0].primary_uuid, "2024-02-21T18:00:00Z"),
                self.attendee(people[1].primary_uuid, "2024-02-21T18:00:01Z"),
            ]
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.assertCountEqual(
            self.session.attended_set.values_list("person", flat=True),
            [p.pk for p in people],
        )
        self.assertEqual(
            self.session.attended_set.get(person=people[0]).time,
            datetime.datetime(2024, 2, 21, 18, 0, 0, tzinfo=datetime.UTC),
        )

    def test_records_attendee_by_superseded_uuid(self):
        person = PersonFactory()
        prior = PersonUUIDFactory(person=person, primary=False)
        r = self.attend([self.attendee(prior.uuid)])
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(self.session.attended_set.filter(person=person).exists())

    def test_unknown_attendee_uuid_records_nothing(self):
        """An unresolvable UUID rejects the whole request"""
        person = PersonFactory()
        unknown = "6f9a1c30-6c7e-4f0a-9a3f-2f1d0b8a4e11"
        r = self.attend(
            [
                self.attendee(person.primary_uuid),
                self.attendee(unknown, "2024-02-21T18:00:01Z"),
            ]
        )
        self.assertEqual(r.status_code, 400)
        errors = r.json()["errors"]
        self.assertEqual([e["attr"] for e in errors], ["person_uuid"])
        self.assertEqual([e["detail"] for e in errors], [unknown])
        self.assertFalse(self.session.attended_set.exists())

    def test_reports_each_unknown_uuid_once(self):
        unknown = "6f9a1c30-6c7e-4f0a-9a3f-2f1d0b8a4e11"
        r = self.attend(
            [
                self.attendee(unknown),
                self.attendee(unknown, "2024-02-21T18:00:01Z"),
            ]
        )
        self.assertEqual(r.status_code, 400)
        self.assertEqual([e["detail"] for e in r.json()["errors"]], [unknown])

    def test_rejects_join_time_without_an_offset(self):
        """A naive join_time is refused rather than read in the server's timezone"""
        person = PersonFactory()
        r = self.attend([self.attendee(person.primary_uuid, "2024-02-21T18:00:00")])
        self.assertEqual(r.status_code, 400)
        self.assertEqual(
            [e["attr"] for e in r.json()["errors"]], ["attendees.0.join_time"]
        )
        self.assertFalse(self.session.attended_set.exists())

    def test_repeated_attendee_push_keeps_first_join_time(self):
        person = PersonFactory()
        for join_time in ["2024-02-21T18:00:00Z", "2024-02-21T19:00:00Z"]:
            r = self.attend([self.attendee(person.primary_uuid, join_time)])
            self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(Attended.objects.filter(session=self.session).count(), 1)
        self.assertEqual(
            self.session.attended_set.get(person=person).time,
            datetime.datetime(2024, 2, 21, 18, 0, 0, tzinfo=datetime.UTC),
        )

    def test_interim_attendees_generate_bluesheet(self):
        interim = MeetingFactory(type_id="interim")
        session = SessionFactory(group__type_id="wg", meeting=interim)
        person = PersonFactory()
        r = self.attend([self.attendee(person.primary_uuid)], session=session)
        self.assertEqual(r.status_code, 200, r.content)
        doc = session.presentations.get(document__type_id="bluesheets").document
        self.assertEqual(doc.docevent_set.first().by, self.system)
        self.assertIn(
            person.plain_name(),
            get_unicode_document_content(
                doc.name,
                Path(interim.get_materials_path()) / "bluesheets" / doc.uploaded_filename,
            ),
        )

    def test_failed_bluesheet_leaves_no_attendees(self):
        """The Attended rows and the interim bluesheet succeed or fail together"""
        session = self.unscheduled_session(MeetingFactory(type_id="interim"))
        person = PersonFactory()
        r = self.attend([self.attendee(person.primary_uuid)], session=session)
        self.assertEqual(r.status_code, 400)
        self.assertFalse(session.attended_set.exists())

    def test_ietf_attendees_do_not_generate_bluesheet(self):
        person = PersonFactory()
        self.attend([self.attendee(person.primary_uuid)])
        self.assertFalse(
            Document.objects.filter(type_id="bluesheets").exists(),
            "bluesheets for an IETF meeting are generated at finalization",
        )
