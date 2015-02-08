# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('meeting', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Registration',
            fields=[
                ('rsn', models.AutoField(serialize=False, primary_key=True)),
                ('fname', models.CharField(max_length=255)),
                ('lname', models.CharField(max_length=255)),
                ('company', models.CharField(max_length=255)),
                ('country', models.CharField(max_length=2)),
            ],
            options={
                'db_table': 'registrations',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='InterimMeeting',
            fields=[
            ],
            options={
                'proxy': True,
            },
            bases=('meeting.meeting',),
        ),
    ]
