# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('meeting', '0041_auto_20161209_0436'),
    ]

    operations = [
        migrations.AlterField(
            model_name='timeslot',
            name='sessions',
            field=models.ManyToManyField(help_text='Scheduled session, if any.', related_name='slots', through='meeting.SchedTimeSessAssignment', to='meeting.Session', blank=True),
        ),
    ]
