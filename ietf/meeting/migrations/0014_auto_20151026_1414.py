# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('meeting', '0013_auto_20151026_1408'),
    ]

    operations = [
        migrations.RenameModel('ScheduledSession', 'SchedTimeSessAssignment'),

        migrations.AlterField(
            model_name='timeslot',
            name='sessions',
            field=models.ManyToManyField(related_name='slots', to='meeting.Session', through='meeting.SchedTimeSessAssignment', blank=True, help_text='Scheduled session, if any.', null=True),
            preserve_default=True,
        ),

        migrations.RemoveField(
            model_name='dummy',
            name='extendedfrom',
        ),
        migrations.RemoveField(
            model_name='dummy',
            name='schedule',
        ),
        migrations.RemoveField(
            model_name='dummy',
            name='session',
        ),
        migrations.RemoveField(
            model_name='dummy',
            name='timeslot',
        ),
        migrations.DeleteModel(
            name='Dummy',
        ),

    ]
