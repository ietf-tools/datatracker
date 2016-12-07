# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('meeting', '0040_fix_mext_meeting_materials'),
    ]

    operations = [
        migrations.AlterField(
            model_name='timeslot',
            name='sessions',
            field=models.ManyToManyField(help_text='Scheduled session, if any.', related_name='slots', through='meeting.SchedTimeSessAssignment', to='meeting.Session', blank=True),
        ),
    ]
