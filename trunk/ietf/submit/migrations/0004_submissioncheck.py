# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import jsonfield

class Migration(migrations.Migration):

    dependencies = [
        ('submit', '0003_auto_20150713_1104'),
    ]

    operations = [
        migrations.CreateModel(
            name='SubmissionCheck',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('time', models.DateTimeField(default=None, auto_now=True)),
                ('checker', models.CharField(max_length=256, blank=True)),
                ('passed', models.NullBooleanField(default=False)),
                ('message', models.TextField(null=True, blank=True)),
                ('warnings', models.IntegerField(null=True, blank=True, default=None)),
                ('errors', models.IntegerField(null=True, blank=True, default=None)),
                ('items', jsonfield.JSONField(null=True, blank=True, default=b'{}')),
                ('submission', models.ForeignKey(related_name='checks', to='submit.Submission')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
