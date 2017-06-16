# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('meeting', '0029_add_time_to_room_and_floorplan'),
    ]

    operations = [
        migrations.AddField(
            model_name='meeting',
            name='submission_correction_day_offset',
            field=models.IntegerField(default=50, help_text=b'The number of days after the meeting start date in which updates to existing meeting materials will be accepted.', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='meeting',
            name='submission_cutoff_day_offset',
            field=models.IntegerField(default=26, help_text=b'The number of days after the meeting start date in which new meeting materials will be accepted.', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='meeting',
            name='submission_start_day_offset',
            field=models.IntegerField(default=90, help_text=b'The number of days before the meeting start date after which meeting materials will be accepted.', blank=True),
            preserve_default=True,
        ),
    ]
