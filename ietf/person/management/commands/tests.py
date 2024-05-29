# Copyright The IETF Trust 2021, All Rights Reserved
# -*- coding: utf-8 -*-

import datetime
from io import StringIO

from django.core.management import call_command, CommandError
from django.utils import timezone

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
