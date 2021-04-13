# Copyright The IETF Trust 2021, All Rights Reserved
# -*- coding: utf-8 -*-

import datetime
from io import StringIO

from django.core.management import call_command, CommandError

from ietf.person.factories import PersonApiKeyEventFactory
from ietf.person.models import PersonApiKeyEvent, PersonEvent
from ietf.utils.test_utils import TestCase


class CommandTests(TestCase):
    @staticmethod
    def _call_command(command_name, *args, **options):
        out = StringIO()
        options['stdout'] = out
        call_command(command_name, *args, **options)
        return out.getvalue()

    def _assert_purge_results(self, cmd_output, expected_delete_count, expected_kept_events):
        self.assertNotIn('Dry run requested', cmd_output)
        if expected_delete_count == 0:
            delete_text = 'No events older than'
        else:
            delete_text = 'Deleting {} event'.format(expected_delete_count)
        self.assertIn(delete_text, cmd_output)
        self.assertCountEqual(
            PersonApiKeyEvent.objects.all(),
            expected_kept_events,
            'Wrong events were deleted'
        )

    def _assert_purge_dry_run_results(self, cmd_output, expected_delete_count, expected_kept_events):
        self.assertIn('Dry run requested', cmd_output)
        if expected_delete_count == 0:
            delete_text = 'No events older than'
        else:
            delete_text = 'Would delete {} event'.format(expected_delete_count)
        self.assertIn(delete_text, cmd_output)
        self.assertCountEqual(
            PersonApiKeyEvent.objects.all(),
            expected_kept_events,
            'Events were deleted when dry-run option was used'
        )

    def test_purge_old_personal_api_key_events(self):
        keep_days = 10

        # Remember how many PersonEvents were present so we can verify they're cleaned up properly.
        personevents_before = PersonEvent.objects.count()

        now = datetime.datetime.now()
        # The first of these events will be timestamped a fraction of a second more than keep_days
        # days ago by the time we call the management command, so will just barely chosen for purge.
        old_events = [
            PersonApiKeyEventFactory(time=now - datetime.timedelta(days=n))
            for n in range(keep_days, 2 * keep_days + 1)
        ]
        num_old_events = len(old_events)

        recent_events = [
            PersonApiKeyEventFactory(time=now - datetime.timedelta(days=n))
            for n in range(0, keep_days)
        ]
        # We did not create recent_event timestamped exactly keep_days ago because it would
        # be treated as an old_event by the management command. Create an event a few seconds
        # on the "recent" side of keep_days old to test the threshold.
        recent_events.append(
            PersonApiKeyEventFactory(
                time=now + datetime.timedelta(seconds=3) - datetime.timedelta(days=keep_days)
            )
        )
        num_recent_events = len(recent_events)

        # call with dry run
        output = self._call_command('purge_old_personal_api_key_events', str(keep_days), '--dry-run')
        self._assert_purge_dry_run_results(output, num_old_events, old_events + recent_events)

        # call for real
        output = self._call_command('purge_old_personal_api_key_events', str(keep_days))
        self._assert_purge_results(output, num_old_events, recent_events)
        self.assertEqual(PersonEvent.objects.count(), personevents_before + num_recent_events,
                         'PersonEvents were not cleaned up properly')

        # repeat - there should be nothing left to delete
        output = self._call_command('purge_old_personal_api_key_events', '--dry-run', str(keep_days))
        self._assert_purge_dry_run_results(output, 0, recent_events)

        output = self._call_command('purge_old_personal_api_key_events', str(keep_days))
        self._assert_purge_results(output, 0, recent_events)
        self.assertEqual(PersonEvent.objects.count(), personevents_before + num_recent_events,
                         'PersonEvents were not cleaned up properly')

        # and now delete the remaining events
        output = self._call_command('purge_old_personal_api_key_events', '0')
        self._assert_purge_results(output, num_recent_events, [])
        self.assertEqual(PersonEvent.objects.count(), personevents_before,
                         'PersonEvents were not cleaned up properly')

    def test_purge_old_personal_api_key_events_rejects_invalid_arguments(self):
        """The purge_old_personal_api_key_events command should reject invalid arguments"""
        event = PersonApiKeyEventFactory(time=datetime.datetime.now() - datetime.timedelta(days=30))

        with self.assertRaises(CommandError):
            self._call_command('purge_old_personal_api_key_events')

        with self.assertRaises(CommandError):
            self._call_command('purge_old_personal_api_key_events', '-15')

        with self.assertRaises(CommandError):
            self._call_command('purge_old_personal_api_key_events', '15.3')

        with self.assertRaises(CommandError):
            self._call_command('purge_old_personal_api_key_events', '15', '15')

        with self.assertRaises(CommandError):
            self._call_command('purge_old_personal_api_key_events', 'abc', '15')

        self.assertCountEqual(PersonApiKeyEvent.objects.all(), [event])
