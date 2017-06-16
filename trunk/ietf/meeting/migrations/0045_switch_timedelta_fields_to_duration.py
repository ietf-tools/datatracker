# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('meeting', '0044_convert_timedelta_data_to_duration'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='meeting',
            name='idsubmit_cutoff_time_utc',
        ),
        migrations.RenameField(
            model_name='meeting',
            old_name='xidsubmit_cutoff_time_utc',
            new_name='idsubmit_cutoff_time_utc',
        ),
        # 
        migrations.RemoveField(
            model_name='meeting',
            name='idsubmit_cutoff_warning_days',
        ),
        migrations.RenameField(
            model_name='meeting',
            old_name='xidsubmit_cutoff_warning_days',
            new_name='idsubmit_cutoff_warning_days',
        ),
        #
        migrations.RemoveField(
            model_name='timeslot',
            name='duration',
        ),
        migrations.RenameField(
            model_name='timeslot',
            old_name='xduration',
            new_name='duration',
        ),
        #
        migrations.RemoveField(
            model_name='session',
            name='requested_duration',
        ),
        migrations.RenameField(
            model_name='session',
            old_name='xrequested_duration',
            new_name='requested_duration',
        ),
    ]
