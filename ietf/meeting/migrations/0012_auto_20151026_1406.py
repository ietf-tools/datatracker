# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('meeting', '0011_ietf92_meetings'),
    ]

    operations = [
        migrations.AlterField(
            model_name='scheduledsession',
            name='session',
            field=models.ForeignKey(related_name='timeslotassignments', default=None, to='meeting.Session', help_text='Scheduled session.', null=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='scheduledsession',
            name='timeslot',
            field=models.ForeignKey(related_name='sessionassignments', to='meeting.TimeSlot'),
            preserve_default=True,
        ),
    ]
