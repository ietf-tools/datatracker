# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='MailToken',
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
                ('template', models.CharField(max_length=512, null=True, blank=True)),
            ],
            options={
                'ordering': ['slug'],
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='mailtoken',
            name='recipients',
            field=models.ManyToManyField(to='mailtoken.Recipient', null=True, blank=True),
            preserve_default=True,
        ),
    ]
