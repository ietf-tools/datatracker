# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('meeting', '0042_auto_20161207_1137'),
    ]

    operations = [
        migrations.AddField(
            model_name='meeting',
            name='xidsubmit_cutoff_time_utc',
            field=models.DurationField(default=datetime.timedelta(0, 86399), help_text=b"The time of day (UTC) after which submission will be closed.  Use for example 23:59:59.", blank=True),
        ),
        migrations.AddField(
            model_name='meeting',
            name='xidsubmit_cutoff_warning_days',
            field=models.DurationField(default=datetime.timedelta(21), help_text=b"How long before the 00 cutoff to start showing cutoff warnings.  Use for example '21' or '21 days'.", blank=True),
        ),
        migrations.AddField(
            model_name='session',
            name='xrequested_duration',
            field=models.DurationField(default=datetime.timedelta(0)),
        ),
        migrations.AddField(
            model_name='timeslot',
            name='xduration',
            field=models.DurationField(default=datetime.timedelta(0)),
        ),
    ]
