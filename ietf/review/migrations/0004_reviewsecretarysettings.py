# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('person', '0014_auto_20160613_0751'),
        ('group', '0009_auto_20150930_0758'),
        ('review', '0003_auto_20161018_0254'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReviewSecretarySettings',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('remind_days_before_deadline', models.IntegerField(help_text=b"To get an email reminder in case an assigned review gets near its deadline, enter the number of days before a review deadline you want to receive it. Clear the field if you don't want a reminder.", null=True, blank=True)),
                ('person', models.ForeignKey(to='person.Person')),
                ('team', models.ForeignKey(to='group.Group')),
            ],
            options={
                'verbose_name_plural': 'review secretary settings',
            },
            bases=(models.Model,),
        ),
    ]
