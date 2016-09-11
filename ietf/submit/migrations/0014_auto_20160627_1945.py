# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):
    def add_next_states(apps, schema_editor):
        DraftSubmissionStateName = apps.get_model("name", "DraftSubmissionStateName")

        cancelled = DraftSubmissionStateName.objects.get(slug="cancel")
        posted = DraftSubmissionStateName.objects.get(slug="posted")
        waiting = DraftSubmissionStateName.objects.get(slug="waiting-for-draft")
        
        waiting.next_states.add(cancelled)
        waiting.next_states.add(posted)

    def reverse(apps, schema_editor):
        DraftSubmissionStateName = apps.get_model("name", "DraftSubmissionStateName")

        try:
            waiting = DraftSubmissionStateName.objects.get(slug="waiting-for-draft")
            try:
                cancelled = DraftSubmissionStateName.objects.get(slug="cancel")
                waiting.next_states.remove(cancelled)
            except DraftSubmissionStateName.DoesNotExist:
                pass
            try:
                posted = DraftSubmissionStateName.objects.get(slug="posted")
                waiting.next_states.remove(posted)
            except DraftSubmissionStateName.DoesNotExist:
                pass
        except DraftSubmissionStateName.DoesNotExist:
            pass

    dependencies = [
        ('submit', '0013_auto_20160415_2120'),
    ]

    operations = [
        migrations.RunPython(add_next_states, reverse),
    ]
