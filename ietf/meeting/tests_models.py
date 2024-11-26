# Copyright The IETF Trust 2021-2024, All Rights Reserved
# -*- coding: utf-8 -*-
"""Tests of models in the Meeting application"""
import datetime

from mock import patch

from django.conf import settings
from django.test import override_settings

import ietf.meeting.models
from ietf.group.factories import GroupFactory, GroupHistoryFactory
from ietf.meeting.factories import MeetingFactory, SessionFactory, AttendedFactory, SessionPresentationFactory
from ietf.meeting.models import Session
from ietf.stats.factories import MeetingRegistrationFactory
from ietf.utils.test_utils import TestCase
from ietf.utils.timezone import date_today, datetime_today


class MeetingTests(TestCase):
    def test_get_attendance_pre110(self):
        """Pre-110 meetings do not calculate attendance"""
        meeting = MeetingFactory(type_id='ietf', number='109')
        MeetingRegistrationFactory.create_batch(3, meeting=meeting, reg_type='')
        MeetingRegistrationFactory.create_batch(4, meeting=meeting, reg_type='remote')
        MeetingRegistrationFactory.create_batch(5, meeting=meeting, reg_type='in_person')
        self.assertIsNone(meeting.get_attendance())

    def test_get_attendance_110(self):
        """Look at attendance as captured at 110"""
        meeting = MeetingFactory(type_id='ietf', number='110')

        # start with attendees that should be ignored
        MeetingRegistrationFactory.create_batch(3, meeting=meeting, reg_type='', attended=True)
        MeetingRegistrationFactory(meeting=meeting, reg_type='', attended=False)
        attendance = meeting.get_attendance()
        self.assertIsNotNone(attendance)
        self.assertEqual(attendance.remote, 0)
        self.assertEqual(attendance.onsite, 0)

        # add online attendees with at least one who registered but did not attend
        MeetingRegistrationFactory.create_batch(4, meeting=meeting, reg_type='remote', attended=True)
        MeetingRegistrationFactory(meeting=meeting, reg_type='remote', attended=False)
        attendance = meeting.get_attendance()
        self.assertIsNotNone(attendance)
        self.assertEqual(attendance.remote, 4)
        self.assertEqual(attendance.onsite, 0)

        # and the same for onsite attendees
        MeetingRegistrationFactory.create_batch(5, meeting=meeting, reg_type='onsite', attended=True)
        MeetingRegistrationFactory(meeting=meeting, reg_type='in_person', attended=False)
        attendance = meeting.get_attendance()
        self.assertIsNotNone(attendance)
        self.assertEqual(attendance.remote, 4)
        self.assertEqual(attendance.onsite, 5)

        # and once more after removing all the online attendees
        meeting.meetingregistration_set.filter(reg_type='remote').delete()
        attendance = meeting.get_attendance()
        self.assertIsNotNone(attendance)
        self.assertEqual(attendance.remote, 0)
        self.assertEqual(attendance.onsite, 5)

    def test_get_attendance_113(self):
        """Simulate IETF 113 attendance gathering data"""
        meeting = MeetingFactory(type_id='ietf', number='113')
        MeetingRegistrationFactory(meeting=meeting, reg_type='onsite', attended=True, checkedin=False)
        MeetingRegistrationFactory(meeting=meeting, reg_type='onsite', attended=False, checkedin=True)
        p1 = MeetingRegistrationFactory(meeting=meeting, reg_type='onsite', attended=False, checkedin=False).person
        AttendedFactory(session__meeting=meeting, person=p1)
        p2 = MeetingRegistrationFactory(meeting=meeting, reg_type='remote', attended=False, checkedin=False).person
        AttendedFactory(session__meeting=meeting, person=p2)
        attendance = meeting.get_attendance()
        self.assertEqual(attendance.onsite, 3)
        self.assertEqual(attendance.remote, 1)

    def test_get_attendance_keeps_meetings_distinct(self):
        """No cross-talk between attendance for different meetings"""
        # numbers are arbitrary here
        first_mtg = MeetingFactory(type_id='ietf', number='114')
        second_mtg = MeetingFactory(type_id='ietf', number='115')

        # Create a person who attended a remote session for first_mtg and onsite for second_mtg without
        # checking in for either.
        p = MeetingRegistrationFactory(meeting=second_mtg, reg_type='onsite', attended=False, checkedin=False).person
        AttendedFactory(session__meeting=first_mtg, person=p)
        MeetingRegistrationFactory(meeting=first_mtg, person=p, reg_type='remote', attended=False, checkedin=False)
        AttendedFactory(session__meeting=second_mtg, person=p)

        att = first_mtg.get_attendance()
        self.assertEqual(att.onsite, 0)
        self.assertEqual(att.remote, 1)

        att = second_mtg.get_attendance()
        self.assertEqual(att.onsite, 1)
        self.assertEqual(att.remote, 0)

    def test_vtimezone(self):
        # normal time zone that should have a zoneinfo file
        meeting = MeetingFactory(type_id='ietf', time_zone='America/Los_Angeles', populate_schedule=False)
        vtz = meeting.vtimezone()
        self.assertIsNotNone(vtz)
        self.assertGreater(len(vtz), 0)
        # time zone that does not have a zoneinfo file should return None
        meeting = MeetingFactory(type_id='ietf', time_zone='Fake/Time_Zone', populate_schedule=False)
        vtz = meeting.vtimezone()
        self.assertIsNone(vtz)
        # ioerror trying to read zoneinfo should return None
        meeting = MeetingFactory(type_id='ietf', time_zone='America/Los_Angeles', populate_schedule=False)
        with patch('ietf.meeting.models.io.open', side_effect=IOError):
            vtz = meeting.vtimezone()
        self.assertIsNone(vtz)

    def test_group_at_the_time(self):
        m = MeetingFactory(type_id='ietf', date=date_today() - datetime.timedelta(days=10))
        cached_groups = GroupFactory.create_batch(2)
        m.cached_groups_at_the_time = {g.pk: g for g in cached_groups}  # fake the cache
        uncached_group_hist = GroupHistoryFactory(time=datetime_today() - datetime.timedelta(days=30))
        self.assertEqual(m.group_at_the_time(uncached_group_hist.group), uncached_group_hist)
        self.assertIn(uncached_group_hist.group.pk, m.cached_groups_at_the_time)


class SessionTests(TestCase):
    def test_chat_archive_url(self):
        session = SessionFactory(
            meeting__date=datetime.date.today(),
            meeting__number=120,  # needs to use proceedings_format_version > 1
        )
        with override_settings():
            if hasattr(settings, 'CHAT_ARCHIVE_URL_PATTERN'):
                del settings.CHAT_ARCHIVE_URL_PATTERN
            self.assertEqual(session.chat_archive_url(), session.chat_room_url())
            settings.CHAT_ARCHIVE_URL_PATTERN = 'http://chat.example.com'
            self.assertEqual(session.chat_archive_url(), 'http://chat.example.com')
            chatlog = SessionPresentationFactory(session=session, document__type_id='chatlog').document
            self.assertEqual(session.chat_archive_url(), chatlog.get_href())

        # datatracker 8.8.0 rolled out on 2022-07-15. Before that, chat logs were jabber logs hosted at www.ietf.org.
        session_with_jabber = SessionFactory(group__acronym='fakeacronym', meeting__date=datetime.date(2022,7,14))
        self.assertEqual(session_with_jabber.chat_archive_url(), 'https://www.ietf.org/jabber/logs/fakeacronym?C=M;O=D')
        chatlog = SessionPresentationFactory(session=session_with_jabber, document__type_id='chatlog').document
        self.assertEqual(session_with_jabber.chat_archive_url(), chatlog.get_href())

    def test_chat_room_name(self):
        session = SessionFactory(group__acronym='xyzzy')
        self.assertEqual(session.chat_room_name(), 'xyzzy')
        session.type_id = 'plenary'
        self.assertEqual(session.chat_room_name(), 'plenary')
        session.chat_room = 'fnord'
        self.assertEqual(session.chat_room_name(), 'fnord')

    def test_alpha_str(self):
        self.assertEqual(Session._alpha_str(0), "a")
        self.assertEqual(Session._alpha_str(1), "b")
        self.assertEqual(Session._alpha_str(25), "z")
        self.assertEqual(Session._alpha_str(26), "aa")
        self.assertEqual(Session._alpha_str(27 * 26 - 1), "zz")
        self.assertEqual(Session._alpha_str(27 * 26), "aaa")

    @patch.object(ietf.meeting.models.Session, "_session_recording_url_label", return_value="LABEL")
    def test_session_recording_url(self, mock):
        for session_type in ["ietf", "interim"]:
            session = SessionFactory(meeting__type_id=session_type)
            with override_settings():
                if hasattr(settings, "MEETECHO_SESSION_RECORDING_URL"):
                    del settings.MEETECHO_SESSION_RECORDING_URL
                self.assertIsNone(session.session_recording_url())
    
                settings.MEETECHO_SESSION_RECORDING_URL = "http://player.example.com"
                self.assertEqual(session.session_recording_url(), "http://player.example.com")
    
                settings.MEETECHO_SESSION_RECORDING_URL = "http://player.example.com?{session_label}"
                self.assertEqual(session.session_recording_url(), "http://player.example.com?LABEL")

                session.meetecho_recording_name="actualname"
                session.save()
                self.assertEqual(session.session_recording_url(), "http://player.example.com?actualname")

    def test_session_recording_url_label_ietf(self):
        session = SessionFactory(
            meeting__type_id='ietf',
            meeting__date=date_today(),
            meeting__number="123",
            group__acronym="acro",
        )
        session_time = session.official_timeslotassignment().timeslot.time
        self.assertEqual(
            f"IETF123-ACRO-{session_time:%Y%m%d-%H%M}",  # n.b., time in label is UTC
            session._session_recording_url_label())

    def test_session_recording_url_label_interim(self):
        session = SessionFactory(
            meeting__type_id='interim',
            meeting__date=date_today(),
            group__acronym="acro",
        )
        session_time = session.official_timeslotassignment().timeslot.time
        self.assertEqual(
            f"IETF-ACRO-{session_time:%Y%m%d-%H%M}",  # n.b., time in label is UTC
            session._session_recording_url_label())
