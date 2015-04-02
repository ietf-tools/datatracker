# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import timedelta.fields


class Migration(migrations.Migration):

    dependencies = [
        ('meeting', '0002_auto_20150221_0947'),
    ]

    operations = [
        migrations.AlterField(
            model_name='meeting',
            name='idsubmit_cutoff_day_offset_00',
            field=models.IntegerField(default=13, help_text=b'The number of days before the meeting start date when the submission of -00 drafts will be closed.', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='meeting',
            name='idsubmit_cutoff_day_offset_01',
            field=models.IntegerField(default=13, help_text=b'The number of days before the meeting start date when the submission of -01 drafts etc. will be closed.', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='meeting',
            name='idsubmit_cutoff_time_utc',
            field=timedelta.fields.TimedeltaField(default=86399.0, help_text=b'The time of day (UTC) after which submission will be closed.  Use for example 23 hours, 59 minutes, 59 seconds.', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='meeting',
            name='idsubmit_cutoff_warning_days',
            field=timedelta.fields.TimedeltaField(default=1814400.0, help_text=b'How long before the 00 cutoff to start showing cutoff warnings.  Use for example 21 days or 3 weeks.', blank=True),
            preserve_default=True,
        ),
    ]
