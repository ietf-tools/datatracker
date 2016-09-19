# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('group', '0008_auto_20160505_0523'),
        ('name', '0013_add_group_type_verbose_name_data'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReviewRequestStateName',
            fields=[
                ('slug', models.CharField(max_length=32, serialize=False, primary_key=True)),
                ('name', models.CharField(max_length=255)),
                ('desc', models.TextField(blank=True)),
                ('used', models.BooleanField(default=True)),
                ('order', models.IntegerField(default=0)),
            ],
            options={
                'ordering': ['order'],
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ReviewResultName',
            fields=[
                ('slug', models.CharField(max_length=32, serialize=False, primary_key=True)),
                ('name', models.CharField(max_length=255)),
                ('desc', models.TextField(blank=True)),
                ('used', models.BooleanField(default=True)),
                ('order', models.IntegerField(default=0)),
            ],
            options={
                'ordering': ['order'],
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ReviewTypeName',
            fields=[
                ('slug', models.CharField(max_length=32, serialize=False, primary_key=True)),
                ('name', models.CharField(max_length=255)),
                ('desc', models.TextField(blank=True)),
                ('used', models.BooleanField(default=True)),
                ('order', models.IntegerField(default=0)),
            ],
            options={
                'ordering': ['order'],
                'abstract': False,
            },
            bases=(models.Model,),
        ),
    ]
