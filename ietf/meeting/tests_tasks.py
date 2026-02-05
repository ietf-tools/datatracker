# Copyright The IETF Trust 2025, All Rights Reserved

import datetime
from unittest.mock import patch, call
from ietf.utils.test_utils import TestCase
from ietf.utils.timezone import date_today
from .factories import MeetingFactory
from .tasks import (
    proceedings_content_refresh_task,
    agenda_data_refresh_task,
    agenda_data_refresh_all_task,
)
from .tasks import fetch_meeting_attendance_task


class TaskTests(TestCase):
    @patch("ietf.meeting.tasks.generate_agenda_data")
    def test_agenda_data_refresh_task(self, mock_generate):
        agenda_data_refresh_task()
        self.assertTrue(mock_generate.called)
        self.assertEqual(mock_generate.call_args, call(None, force_refresh=True))
        
        mock_generate.reset_mock()
        mock_generate.side_effect = RuntimeError
        try:
            agenda_data_refresh_task()
        except Exception as err:
            self.fail(
                f"agenda_data_refresh_task should not raise exceptions (got {repr(err)})"
            )

    @patch("ietf.meeting.tasks.agenda_data_refresh_task")
    @patch("ietf.meeting.tasks.chain")
    def test_agenda_data_refresh_all_task(self, mock_chain, mock_agenda_data_refresh):
        # Patch the agenda_data_refresh_task task with a mock whose `.map` attribute
        # converts its argument, which is expected to be an iterator,  to a list
        # and returns it. We'll use this to check that the expected task chain
        # was set up, but we don't actually run any celery tasks.
        mock_agenda_data_refresh.map.side_effect = lambda x: list(x)

        meetings = MeetingFactory.create_batch(5, type_id="ietf")
        numbers = sorted(int(m.number) for m in meetings)
        agenda_data_refresh_all_task(batch_size=2)
        self.assertTrue(mock_chain.called)
        self.assertEqual(
            mock_chain.call_args,
            call(
                [numbers[0], numbers[1]],
                [numbers[2], numbers[3]],
                [numbers[4]],
            ),
        )
        self.assertEqual(mock_agenda_data_refresh.call_count, 0)
        self.assertEqual(mock_agenda_data_refresh.map.call_count, 3)

    @patch("ietf.meeting.tasks.generate_proceedings_content")
    def test_proceedings_content_refresh_task(self, mock_generate):
        # Generate a couple of meetings
        meeting120 = MeetingFactory(type_id="ietf", number="120")  # 24 * 5
        meeting127 = MeetingFactory(type_id="ietf", number="127")  # 24 * 5 + 7

        # Times to be returned
        now_utc = datetime.datetime.now(tz=datetime.UTC)
        hour_00_utc = now_utc.replace(hour=0)
        hour_01_utc = now_utc.replace(hour=1)
        hour_07_utc = now_utc.replace(hour=7)

        # hour 00 - should call meeting with number % 24 == 0
        with patch("ietf.meeting.tasks.timezone.now", return_value=hour_00_utc):
            proceedings_content_refresh_task()
        self.assertEqual(mock_generate.call_count, 1)
        self.assertEqual(mock_generate.call_args, call(meeting120, force_refresh=True))
        mock_generate.reset_mock()

        # hour 01 - should call no meetings
        with patch("ietf.meeting.tasks.timezone.now", return_value=hour_01_utc):
            proceedings_content_refresh_task()
        self.assertEqual(mock_generate.call_count, 0)

        # hour 07 - should call meeting with number % 24 == 0
        with patch("ietf.meeting.tasks.timezone.now", return_value=hour_07_utc):
            proceedings_content_refresh_task()
        self.assertEqual(mock_generate.call_count, 1)
        self.assertEqual(mock_generate.call_args, call(meeting127, force_refresh=True))
        mock_generate.reset_mock()

        # With all=True, all should be called regardless of time. Reuse hour_01_utc which called none before
        with patch("ietf.meeting.tasks.timezone.now", return_value=hour_01_utc):
            proceedings_content_refresh_task(all=True)
        self.assertEqual(mock_generate.call_count, 2)

    @patch("ietf.meeting.tasks.fetch_attendance_from_meetings")
    def test_fetch_meeting_attendance_task(self, mock_fetch_attendance):
        today = date_today()
        meetings = [
            MeetingFactory(type_id="ietf", date=today - datetime.timedelta(days=1)),
            MeetingFactory(type_id="ietf", date=today - datetime.timedelta(days=2)),
            MeetingFactory(type_id="ietf", date=today - datetime.timedelta(days=3)),
        ]
        data = {
            "created": 1,
            "updated": 2,
            "deleted": 0,
            "processed": 3,
        }

        mock_fetch_attendance.return_value = [data, data]

        fetch_meeting_attendance_task()
        self.assertEqual(mock_fetch_attendance.call_count, 1)
        self.assertCountEqual(mock_fetch_attendance.call_args[0][0], meetings[0:2])

        # test handling of RuntimeError
        mock_fetch_attendance.reset_mock()
        mock_fetch_attendance.side_effect = RuntimeError
        fetch_meeting_attendance_task()
        self.assertTrue(mock_fetch_attendance.called)
        # Good enough that we got here without raising an exception
