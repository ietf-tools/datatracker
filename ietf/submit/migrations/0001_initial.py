# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime
import ietf.utils.accesstoken


class Migration(migrations.Migration):

    dependencies = [
        ('group', '0001_initial'),
        ('name', '0001_initial'),
        ('person', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Preapproval',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=255, db_index=True)),
                ('time', models.DateTimeField(default=datetime.datetime.now)),
                ('by', models.ForeignKey(to='person.Person')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Submission',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('remote_ip', models.CharField(max_length=100, blank=True)),
                ('access_key', models.CharField(default=ietf.utils.accesstoken.generate_random_key, max_length=255)),
                ('auth_key', models.CharField(max_length=255, blank=True)),
                ('name', models.CharField(max_length=255, db_index=True)),
                ('title', models.CharField(max_length=255, blank=True)),
                ('abstract', models.TextField(blank=True)),
                ('rev', models.CharField(max_length=3, blank=True)),
                ('pages', models.IntegerField(null=True, blank=True)),
                ('authors', models.TextField(help_text=b'List of author names and emails, one author per line, e.g. "John Doe &lt;john@example.org&gt;"', blank=True)),
                ('note', models.TextField(blank=True)),
                ('replaces', models.CharField(max_length=255, blank=True)),
                ('first_two_pages', models.TextField(blank=True)),
                ('file_types', models.CharField(max_length=50, blank=True)),
                ('file_size', models.IntegerField(null=True, blank=True)),
                ('document_date', models.DateField(null=True, blank=True)),
                ('submission_date', models.DateField(default=datetime.date.today)),
                ('submitter', models.CharField(help_text=b'Name and email of submitter, e.g. "John Doe &lt;john@example.org&gt;"', max_length=255, blank=True)),
                ('idnits_message', models.TextField(blank=True)),
                ('group', models.ForeignKey(blank=True, to='group.Group', null=True)),
                ('state', models.ForeignKey(to='name.DraftSubmissionStateName')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='SubmissionEvent',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('time', models.DateTimeField(default=datetime.datetime.now)),
                ('desc', models.TextField()),
                ('by', models.ForeignKey(blank=True, to='person.Person', null=True)),
                ('submission', models.ForeignKey(to='submit.Submission')),
            ],
            options={
                'ordering': ('-time', '-id'),
            },
            bases=(models.Model,),
        ),
    ]
