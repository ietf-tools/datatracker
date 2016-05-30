# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('person', '0001_initial'),
        ('doc', '0001_initial'),
        ('group', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Message',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('time', models.DateTimeField(default=datetime.datetime.now)),
                ('subject', models.CharField(max_length=255)),
                ('frm', models.CharField(max_length=255)),
                ('to', models.CharField(max_length=1024)),
                ('cc', models.CharField(max_length=1024, blank=True)),
                ('bcc', models.CharField(max_length=255, blank=True)),
                ('reply_to', models.CharField(max_length=255, blank=True)),
                ('body', models.TextField()),
                ('content_type', models.CharField(default=b'text/plain', max_length=255, blank=True)),
                ('by', models.ForeignKey(to='person.Person')),
                ('related_docs', models.ManyToManyField(to='doc.Document', blank=True)),
                ('related_groups', models.ManyToManyField(to='group.Group', blank=True)),
            ],
            options={
                'ordering': ['time'],
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='SendQueue',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('time', models.DateTimeField(default=datetime.datetime.now)),
                ('send_at', models.DateTimeField(null=True, blank=True)),
                ('sent_at', models.DateTimeField(null=True, blank=True)),
                ('note', models.TextField(blank=True)),
                ('by', models.ForeignKey(to='person.Person')),
                ('message', models.ForeignKey(to='message.Message')),
            ],
            options={
                'ordering': ['time'],
            },
            bases=(models.Model,),
        ),
    ]
