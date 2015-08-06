# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Ingredient',
            fields=[
                ('slug', models.CharField(max_length=32, serialize=False, primary_key=True)),
                ('desc', models.TextField(blank=True)),
                ('template', models.CharField(max_length=512, null=True, blank=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Recipe',
            fields=[
                ('slug', models.CharField(max_length=32, serialize=False, primary_key=True)),
                ('desc', models.TextField(blank=True)),
                ('ingredients', models.ManyToManyField(to='eventmail.Ingredient', null=True, blank=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
