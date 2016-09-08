# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('message', '__first__'),
        ('submit', '0010_data_set_submission_check_symbol'),
    ]

    operations = [
        migrations.CreateModel(
            name='SubmissionEmailEvent',
            fields=[
                ('submissionevent_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='submit.SubmissionEvent')),
                ('msgtype', models.CharField(max_length=25)),
                ('in_reply_to', models.ForeignKey(related_name='irtomanual', blank=True, to='message.Message', null=True)),
                ('message', models.ForeignKey(related_name='manualevents', blank=True, to='message.Message', null=True)),
            ],
            options={
                'ordering': ['-time', '-id'],
            },
            bases=('submit.submissionevent',),
        ),
    ]
