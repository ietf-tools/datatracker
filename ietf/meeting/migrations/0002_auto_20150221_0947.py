# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import timedelta.fields


class Migration(migrations.Migration):

    dependencies = [
        ('meeting', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='meeting',
            name='idsubmit_cutoff_day_offset_00',
            field=models.IntegerField(default=20, help_text=b'The number of days before the meeting start date when the submission of -00 drafts will be closed.'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='meeting',
            name='idsubmit_cutoff_day_offset_01',
            field=models.IntegerField(default=13, help_text=b'The number of days before the meeting start date when the submission of -01 drafts etc. will be closed.'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='meeting',
            name='idsubmit_cutoff_time_utc',
            field=timedelta.fields.TimedeltaField(default=86399.0, help_text=b'The time of day (UTC) after which submission will be closed.  Use for example 23 hours, 59 minutes, 59 seconds.'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='meeting',
            name='idsubmit_cutoff_warning_days',
            field=timedelta.fields.TimedeltaField(default=1814400.0, help_text=b'How long before the 00 cutoff to start showing cutoff warnings.  Use for example 21 days or 3 weeks.'),
            preserve_default=True,
        ),
    ]
