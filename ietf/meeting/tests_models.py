# Copyright The IETF Trust 2021, All Rights Reserved
# -*- coding: utf-8 -*-
"""Tests of models in the Meeting application"""
import datetime

from mock import patch

from ietf.meeting.factories import MeetingFactory, SessionFactory
from ietf.stats.factories import MeetingRegistrationFactory
from ietf.utils.test_utils import TestCase


class MeetingTests(TestCase):
    def test_get_attendance_pre110(self):
        """Pre-110 meetings do not calculate attendance"""
        meeting = MeetingFactory(type_id='ietf', number='109')
        MeetingRegistrationFactory.create_batch(3, meeting=meeting, reg_type='')
        MeetingRegistrationFactory.create_batch(4, meeting=meeting, reg_type='remote')
        MeetingRegistrationFactory.create_batch(5, meeting=meeting, reg_type='in_person')
        self.assertIsNone(meeting.get_attendance())

    def test_get_attendance(self):
        """Post-110 meetings do calculate attendance"""
        meeting = MeetingFactory(type_id='ietf', number='110')

        # start with attendees that should be ignored
        MeetingRegistrationFactory.create_batch(3, meeting=meeting, reg_type='')
        MeetingRegistrationFactory(meeting=meeting, reg_type='', attended=False)
        attendance = meeting.get_attendance()
        self.assertIsNotNone(attendance)
        self.assertEqual(attendance.online, 0)
        self.assertEqual(attendance.onsite, 0)

        # add online attendees with at least one who registered but did not attend
        MeetingRegistrationFactory.create_batch(4, meeting=meeting, reg_type='remote')
        MeetingRegistrationFactory(meeting=meeting, reg_type='remote', attended=False)
        attendance = meeting.get_attendance()
        self.assertIsNotNone(attendance)
        self.assertEqual(attendance.online, 4)
        self.assertEqual(attendance.onsite, 0)

        # and the same for onsite attendees
        MeetingRegistrationFactory.create_batch(5, meeting=meeting, reg_type='in_person')
        MeetingRegistrationFactory(meeting=meeting, reg_type='in_person', attended=False)
        attendance = meeting.get_attendance()
        self.assertIsNotNone(attendance)
        self.assertEqual(attendance.online, 4)
        self.assertEqual(attendance.onsite, 5)

        # and once more after removing all the online attendees
        meeting.meetingregistration_set.filter(reg_type='remote').delete()
        attendance = meeting.get_attendance()
        self.assertIsNotNone(attendance)
        self.assertEqual(attendance.online, 0)
        self.assertEqual(attendance.onsite, 5)

    def test_vtimezone(self):
        # normal time zone that should have a zoneinfo file
        meeting = MeetingFactory(type_id='ietf', time_zone='America/Los_Angeles')
        vtz = meeting.vtimezone()
        self.assertIsNotNone(vtz)
        self.assertGreater(len(vtz), 0)
        # time zone that does not have a zoneinfo file should return None
        meeting = MeetingFactory(type_id='ietf', time_zone='Fake/Time_Zone')
        meeting.save()
        vtz = meeting.vtimezone()
        self.assertIsNone(vtz)
        # ioerror trying to read zoneinfo should return None
        meeting = MeetingFactory(type_id='ietf', time_zone='America/Los_Angeles')
        with patch('ietf.meeting.models.io.open', side_effect=IOError):
            vtz = meeting.vtimezone()
        self.assertIsNone(vtz)


class SessionTests(TestCase):
    def test_chat_archive_url_with_jabber(self):
        # datatracker 8.8.0 rolled out on 2022-07-15. Before that, chat logs were jabber logs hosted at www.ietf.org.
        session_with_jabber = SessionFactory(group__acronym='fakeacronym', meeting__date=datetime.date(2022,7,14))
        self.assertEqual(session_with_jabber.chat_archive_url(), 'https://www.ietf.org/jabber/logs/fakeacronym?C=M;O=D')
