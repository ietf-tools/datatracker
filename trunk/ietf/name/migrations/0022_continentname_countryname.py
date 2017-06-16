# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('name', '0021_add_formlang_names'),
    ]

    operations = [
        migrations.CreateModel(
            name='ContinentName',
            fields=[
                ('slug', models.CharField(max_length=32, serialize=False, primary_key=True)),
                ('name', models.CharField(max_length=255)),
                ('desc', models.TextField(blank=True)),
                ('used', models.BooleanField(default=True)),
                ('order', models.IntegerField(default=0)),
            ],
            options={
                'ordering': ['order', 'name'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='CountryName',
            fields=[
                ('slug', models.CharField(max_length=32, serialize=False, primary_key=True)),
                ('name', models.CharField(max_length=255)),
                ('desc', models.TextField(blank=True)),
                ('used', models.BooleanField(default=True)),
                ('order', models.IntegerField(default=0)),
                ('in_eu', models.BooleanField(default=False, verbose_name='In EU')),
                ('continent', models.ForeignKey(to='name.ContinentName')),
            ],
            options={
                'ordering': ['order', 'name'],
                'abstract': False,
            },
        ),
    ]
