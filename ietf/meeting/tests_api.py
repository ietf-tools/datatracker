# Copyright The IETF Trust 2026, All Rights Reserved
from unittest.mock import PropertyMock, patch

from django.test import override_settings
from django.urls import reverse as urlreverse

from ietf.meeting.factories import (
    AttendedFactory,
    MeetingFactory,
    RegistrationFactory,
)
from ietf.meeting.models import Registration
from ietf.person.factories import EmailFactory, PersonFactory
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
