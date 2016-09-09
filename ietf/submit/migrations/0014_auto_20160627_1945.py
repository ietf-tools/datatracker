# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):
    def add_next_states(apps, schema_editor):
        DraftSubmissionStateName = apps.get_model("name", "DraftSubmissionStateName")

        cancelled = DraftSubmissionStateName.objects.get(slug="cancel")
        posted = DraftSubmissionStateName.objects.get(slug="posted")
        mad = DraftSubmissionStateName.objects.get(slug="waiting-for-draft")
        
        mad.next_states.add(cancelled)
        mad.next_states.add(posted)
        mad.save()

    dependencies = [
        ('submit', '0013_auto_20160415_2120'),
    ]

    operations = [
        migrations.RunPython(add_next_states),
    ]
