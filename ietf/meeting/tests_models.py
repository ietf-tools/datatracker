# Copyright The IETF Trust 2021-2024, All Rights Reserved
# -*- coding: utf-8 -*-
"""Tests of models in the Meeting application"""

import datetime

from unittest.mock import patch

from django.conf import settings
from django.test import override_settings

import ietf.meeting.models
from ietf.group.factories import GroupFactory, GroupHistoryFactory
from ietf.meeting.factories import (
    MeetingFactory,
    SessionFactory,
    AttendedFactory,
    SessionPresentationFactory,
)
from ietf.meeting.factories import RegistrationFactory
from ietf.meeting.models import Session
from ietf.utils.test_utils import TestCase
from ietf.utils.timezone import date_today, datetime_today


class MeetingTests(TestCase):
    def test_get_attendees_pre110(self):
        """Pre-110 meetings return None"""
        meeting = MeetingFactory(type_id="ietf", number="109")
        RegistrationFactory.create_batch(
            3, meeting=meeting, with_ticket={"attendance_type_id": "unknown"}
        )
        RegistrationFactory.create_batch(
            4, meeting=meeting, with_ticket={"attendance_type_id": "remote"}
        )
        RegistrationFactory.create_batch(
            5, meeting=meeting, with_ticket={"attendance_type_id": "onsite"}
        )
        self.assertIsNone(meeting.get_attendees())

    def test_get_attendees_110(self):
        """Registration-based attendance (attended flag) used at IETF 110"""
        meeting = MeetingFactory(type_id="ietf", number="110")

        # Unknown-ticket attendees are excluded regardless of attended flag
        RegistrationFactory.create_batch(
            3,
            meeting=meeting,
            with_ticket={"attendance_type_id": "unknown"},
            attended=True,
        )
        RegistrationFactory(
            meeting=meeting,
            with_ticket={"attendance_type_id": "unknown"},
            attended=False,
        )
        onsite, remote = meeting.get_attendees()
        self.assertEqual(len(onsite), 0)
        self.assertEqual(len(remote), 0)

        # Remote attendees: only those with attended=True are included
        remote_regs = RegistrationFactory.create_batch(
            4,
            meeting=meeting,
            with_ticket={"attendance_type_id": "remote"},
            attended=True,
        )
        RegistrationFactory(
            meeting=meeting,
            with_ticket={"attendance_type_id": "remote"},
            attended=False,
        )
        onsite, remote = meeting.get_attendees()
        self.assertEqual({p.pk for p in onsite}, set())
        self.assertEqual({p.pk for p in remote}, {r.person.pk for r in remote_regs})

        # Onsite attendees: only those with attended=True are included
        onsite_regs = RegistrationFactory.create_batch(
            5,
            meeting=meeting,
            with_ticket={"attendance_type_id": "onsite"},
            attended=True,
        )
        RegistrationFactory(
            meeting=meeting,
            with_ticket={"attendance_type_id": "onsite"},
            attended=False,
        )
        onsite, remote = meeting.get_attendees()
        self.assertEqual({p.pk for p in onsite}, {r.person.pk for r in onsite_regs})
        self.assertEqual({p.pk for p in remote}, {r.person.pk for r in remote_regs})

        # Deleting remote registrations empties the remote set
        meeting.registration_set.remote().delete()
        onsite, remote = meeting.get_attendees()
        self.assertEqual({p.pk for p in onsite}, {r.person.pk for r in onsite_regs})
        self.assertEqual(len(remote), 0)

    def test_get_attendees_113(self):
        """Simulate IETF 113: mix of attended flag, checkedin flag, and Attended records"""
        meeting = MeetingFactory(type_id="ietf", number="113")
        p_attended = RegistrationFactory(
            meeting=meeting,
            with_ticket={"attendance_type_id": "onsite"},
            attended=True,
            checkedin=False,
        ).person
        p_checkedin = RegistrationFactory(
            meeting=meeting,
            with_ticket={"attendance_type_id": "onsite"},
            attended=False,
            checkedin=True,
        ).person
        p_onsite_session = RegistrationFactory(
            meeting=meeting,
            with_ticket={"attendance_type_id": "onsite"},
            attended=False,
            checkedin=False,
        ).person
        AttendedFactory(session__meeting=meeting, person=p_onsite_session)
        p_remote_session = RegistrationFactory(
            meeting=meeting,
            with_ticket={"attendance_type_id": "remote"},
            attended=False,
            checkedin=False,
        ).person
        AttendedFactory(session__meeting=meeting, person=p_remote_session)
        onsite, remote = meeting.get_attendees()
        self.assertEqual(
            {p.pk for p in onsite}, {p_attended.pk, p_checkedin.pk, p_onsite_session.pk}
        )
        self.assertEqual({p.pk for p in remote}, {p_remote_session.pk})

    def test_get_attendees_keeps_meetings_distinct(self):
        """No cross-talk between attendance for different meetings"""
        first_mtg = MeetingFactory(type_id="ietf", number="114")
        second_mtg = MeetingFactory(type_id="ietf", number="115")

        # Person with remote ticket at first_mtg and onsite ticket at second_mtg, attended both via Attended records
        p = RegistrationFactory(
            meeting=second_mtg,
            with_ticket={"attendance_type_id": "onsite"},
            attended=False,
            checkedin=False,
        ).person
        RegistrationFactory(
            meeting=first_mtg,
            person=p,
            with_ticket={"attendance_type_id": "remote"},
            attended=False,
            checkedin=False,
        )
        AttendedFactory(session__meeting=first_mtg, person=p)
        AttendedFactory(session__meeting=second_mtg, person=p)

        first_onsite, first_remote = first_mtg.get_attendees()
        self.assertEqual({q.pk for q in first_onsite}, set())
        self.assertEqual({q.pk for q in first_remote}, {p.pk})

        second_onsite, second_remote = second_mtg.get_attendees()
        self.assertEqual({q.pk for q in second_onsite}, {p.pk})
        self.assertEqual({q.pk for q in second_remote}, set())

    def test_get_attendance(self):
        """get_attendance delegates to get_attendees and returns counts as a NamedTuple"""
        meeting = MeetingFactory(type_id="ietf", number="120")
        onsite_regs = RegistrationFactory.create_batch(
            3,
            meeting=meeting,
            with_ticket={"attendance_type_id": "onsite"},
            attended=True,
        )
        remote_regs = RegistrationFactory.create_batch(
            2,
            meeting=meeting,
            with_ticket={"attendance_type_id": "remote"},
            attended=True,
        )
        att = meeting.get_attendance()
        self.assertIsNotNone(att)
        self.assertEqual(att.onsite, len(onsite_regs))
        self.assertEqual(att.remote, len(remote_regs))

        old_meeting = MeetingFactory(type_id="ietf", number="109")
        self.assertIsNone(old_meeting.get_attendance())

    def test_vtimezone(self):
        # normal time zone that should have a zoneinfo file
        meeting = MeetingFactory(
            type_id="ietf", time_zone="America/Los_Angeles", populate_schedule=False
        )
        vtz = meeting.vtimezone()
        self.assertIsNotNone(vtz)
        self.assertGreater(len(vtz), 0)
        # time zone that does not have a zoneinfo file should return None
        meeting = MeetingFactory(
            type_id="ietf", time_zone="Fake/Time_Zone", populate_schedule=False
        )
        vtz = meeting.vtimezone()
        self.assertIsNone(vtz)
        # ioerror trying to read zoneinfo should return None
        meeting = MeetingFactory(
            type_id="ietf", time_zone="America/Los_Angeles", populate_schedule=False
        )
        with patch("ietf.meeting.models.io.open", side_effect=IOError):
            vtz = meeting.vtimezone()
        self.assertIsNone(vtz)

    def test_group_at_the_time(self):
        m = MeetingFactory(
            type_id="ietf", date=date_today() - datetime.timedelta(days=10)
        )
        cached_groups = GroupFactory.create_batch(2)
        m.cached_groups_at_the_time = {g.pk: g for g in cached_groups}  # fake the cache
        uncached_group_hist = GroupHistoryFactory(
            time=datetime_today() - datetime.timedelta(days=30)
        )
        self.assertEqual(
            m.group_at_the_time(uncached_group_hist.group), uncached_group_hist
        )
        self.assertIn(uncached_group_hist.group.pk, m.cached_groups_at_the_time)


class SessionTests(TestCase):
    def test_chat_archive_url(self):
        session = SessionFactory(
            meeting__date=datetime.date.today(),
            meeting__number=120,  # needs to use proceedings_format_version > 1
        )
        with override_settings():
            if hasattr(settings, "CHAT_ARCHIVE_URL_PATTERN"):
                del settings.CHAT_ARCHIVE_URL_PATTERN
            self.assertEqual(session.chat_archive_url(), session.chat_room_url())
            settings.CHAT_ARCHIVE_URL_PATTERN = "http://chat.example.com"
            self.assertEqual(session.chat_archive_url(), "http://chat.example.com")
            chatlog = SessionPresentationFactory(
                session=session, document__type_id="chatlog"
            ).document
            self.assertEqual(session.chat_archive_url(), chatlog.get_href())

        # datatracker 8.8.0 rolled out on 2022-07-15. Before that, chat logs were jabber logs hosted at www.ietf.org.
        session_with_jabber = SessionFactory(
            group__acronym="fakeacronym", meeting__date=datetime.date(2022, 7, 14)
        )
        self.assertEqual(
            session_with_jabber.chat_archive_url(),
            "https://www.ietf.org/jabber/logs/fakeacronym?C=M;O=D",
        )
        chatlog = SessionPresentationFactory(
            session=session_with_jabber, document__type_id="chatlog"
        ).document
        self.assertEqual(session_with_jabber.chat_archive_url(), chatlog.get_href())

    def test_chat_room_name(self):
        session = SessionFactory(group__acronym="xyzzy")
        self.assertEqual(session.chat_room_name(), "xyzzy") 
        session.type_id = "plenary"
        self.assertEqual(session.chat_room_name(), "plenary")
        session.chat_room = "fnord"
        self.assertEqual(session.chat_room_name(), "fnord")

    def test_alpha_str(self):
        self.assertEqual(Session._alpha_str(0), "a")
        self.assertEqual(Session._alpha_str(1), "b")
        self.assertEqual(Session._alpha_str(25), "z")
        self.assertEqual(Session._alpha_str(26), "aa")
        self.assertEqual(Session._alpha_str(27 * 26 - 1), "zz")
        self.assertEqual(Session._alpha_str(27 * 26), "aaa")

    @patch.object(
        ietf.meeting.models.Session,
        "_session_recording_url_label",
        return_value="LABEL",
    )
    def test_session_recording_url(self, mock):
        for session_type in ["ietf", "interim"]:
            session = SessionFactory(meeting__type_id=session_type)
            with override_settings():
                if hasattr(settings, "MEETECHO_SESSION_RECORDING_URL"):
                    del settings.MEETECHO_SESSION_RECORDING_URL
                self.assertIsNone(session.session_recording_url())

                settings.MEETECHO_SESSION_RECORDING_URL = "http://player.example.com"
                self.assertEqual(
                    session.session_recording_url(), "http://player.example.com"
                )

                settings.MEETECHO_SESSION_RECORDING_URL = (
                    "http://player.example.com?{session_label}"
                )
                self.assertEqual(
                    session.session_recording_url(), "http://player.example.com?LABEL"
                )

                session.meetecho_recording_name = "actualname"
                session.save()
                self.assertEqual(
                    session.session_recording_url(),
                    "http://player.example.com?actualname",
                )

    def test_session_recording_url_label_ietf(self):
        session = SessionFactory(
            meeting__type_id="ietf",
            meeting__date=date_today(),
            meeting__number="123",
            group__acronym="acro",
        )
        session_time = session.official_timeslotassignment().timeslot.time
        self.assertEqual(
            f"IETF123-ACRO-{session_time:%Y%m%d-%H%M}",  # n.b., time in label is UTC
            session._session_recording_url_label(),
        )

    def test_session_recording_url_label_interim(self):
        session = SessionFactory(
            meeting__type_id="interim",
            meeting__date=date_today(),
            group__acronym="acro",
        )
        session_time = session.official_timeslotassignment().timeslot.time
        self.assertEqual(
            f"IETF-ACRO-{session_time:%Y%m%d-%H%M}",  # n.b., time in label is UTC
            session._session_recording_url_label(),
        )
