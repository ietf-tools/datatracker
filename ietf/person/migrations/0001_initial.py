# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Alias',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=255, db_index=True)),
            ],
            options={
                'verbose_name_plural': 'Aliases',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Email',
            fields=[
                ('address', models.CharField(max_length=64, serialize=False, primary_key=True)),
                ('time', models.DateTimeField(auto_now_add=True)),
                ('active', models.BooleanField(default=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Person',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('time', models.DateTimeField(default=datetime.datetime.now)),
                ('name', models.CharField(max_length=255, db_index=True)),
                ('ascii', models.CharField(max_length=255)),
                ('ascii_short', models.CharField(max_length=32, null=True, blank=True)),
                ('address', models.TextField(max_length=255, blank=True)),
                ('affiliation', models.CharField(max_length=255, blank=True)),
                ('user', models.OneToOneField(null=True, blank=True, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='PersonHistory',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('time', models.DateTimeField(default=datetime.datetime.now)),
                ('name', models.CharField(max_length=255, db_index=True)),
                ('ascii', models.CharField(max_length=255)),
                ('ascii_short', models.CharField(max_length=32, null=True, blank=True)),
                ('address', models.TextField(max_length=255, blank=True)),
                ('affiliation', models.CharField(max_length=255, blank=True)),
                ('person', models.ForeignKey(related_name='history_set', to='person.Person')),
                ('user', models.ForeignKey(blank=True, to=settings.AUTH_USER_MODEL, null=True)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='email',
            name='person',
            field=models.ForeignKey(to='person.Person', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='alias',
            name='person',
            field=models.ForeignKey(to='person.Person'),
            preserve_default=True,
        ),
    ]
