# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('meeting', '0004_auto_20150308_0446'),
    ]

    operations = [
        migrations.AlterField(
            model_name='meeting',
            name='agenda_note',
            field=models.TextField(help_text=b'Text in this field will be placed at the top of the html agenda page for the meeting.  HTML can be used, but will not be validated.', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='schedule',
            name='public',
            field=models.BooleanField(default=True, help_text='Make this agenda publically available.'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='schedule',
            name='visible',
            field=models.BooleanField(default=True, help_text='Make this agenda available to those who know about it.'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='scheduledsession',
            name='extendedfrom',
            field=models.ForeignKey(default=None, to='meeting.ScheduledSession', help_text='Timeslot this session is an extension of.', null=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='scheduledsession',
            name='pinned',
            field=models.BooleanField(default=False, help_text=b'Do not move session during automatic placement.'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='scheduledsession',
            name='session',
            field=models.ForeignKey(default=None, to='meeting.Session', help_text='Scheduled session.', null=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='session',
            name='name',
            field=models.CharField(help_text=b'Name of session, in case the session has a purpose rather than just being a group meeting.', max_length=255, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='session',
            name='short',
            field=models.CharField(help_text=b"Short version of 'name' above, for use in filenames.", max_length=32, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='timeslot',
            name='sessions',
            field=models.ManyToManyField(related_name='slots', to='meeting.Session', through='meeting.ScheduledSession', blank=True, help_text='Scheduled session, if any.', null=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='timeslot',
            name='show_location',
            field=models.BooleanField(default=True, help_text=b'Show location in agenda.'),
            preserve_default=True,
        ),
    ]
