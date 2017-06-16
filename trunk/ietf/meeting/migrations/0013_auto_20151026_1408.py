# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('meeting', '0012_auto_20151026_1406'),
    ]

    operations = [
        migrations.CreateModel(
            name='Dummy',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('modified', models.DateTimeField(default=datetime.datetime.now)),
                ('notes', models.TextField(blank=True)),
                ('badness', models.IntegerField(default=0, null=True, blank=True)),
                ('pinned', models.BooleanField(default=False, help_text=b'Do not move session during automatic placement.')),
                ('extendedfrom', models.ForeignKey(default=None, to='self', help_text='Timeslot this session is an extension of.', null=True)),
                ('schedule', models.ForeignKey(related_name='assignments', to='meeting.Schedule')),
                ('session', models.ForeignKey(related_name='timeslotassignments', default=None, to='meeting.Session', help_text='Scheduled session.', null=True)),
                ('timeslot', models.ForeignKey(related_name='sessionassignments', to='meeting.TimeSlot')),
            ],
            options={
                'ordering': ['timeslot__time', 'timeslot__type__slug', 'session__group__parent__name', 'session__group__acronym', 'session__name'],
            },
            bases=(models.Model,),
        ),
        migrations.AlterField(
            model_name='timeslot',
            name='sessions',
            field=models.ManyToManyField(related_name='slots', to='meeting.Session', through='meeting.Dummy', blank=True, help_text='Scheduled session, if any.', null=True),
            preserve_default=True,
        ),
    ]
