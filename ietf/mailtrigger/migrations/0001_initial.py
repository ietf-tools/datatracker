# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='MailTrigger',
            fields=[
                ('slug', models.CharField(max_length=32, serialize=False, primary_key=True)),
                ('desc', models.TextField(blank=True)),
            ],
            options={
                'ordering': ['slug'],
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Recipient',
            fields=[
                ('slug', models.CharField(max_length=32, serialize=False, primary_key=True)),
                ('desc', models.TextField(blank=True)),
                ('template', models.TextField(null=True, blank=True)),
            ],
            options={
                'ordering': ['slug'],
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='mailtrigger',
            name='cc',
            field=models.ManyToManyField(related_name='used_in_cc', null=True, to='mailtrigger.Recipient', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='mailtrigger',
            name='to',
            field=models.ManyToManyField(related_name='used_in_to', null=True, to='mailtrigger.Recipient', blank=True),
            preserve_default=True,
        ),
    ]
