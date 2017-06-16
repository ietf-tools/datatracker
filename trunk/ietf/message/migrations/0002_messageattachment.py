# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('message', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='MessageAttachment',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('filename', models.CharField(db_index=True, max_length=255, blank=True)),
                ('content_type', models.CharField(max_length=255, blank=True)),
                ('encoding', models.CharField(max_length=255, blank=True)),
                ('removed', models.BooleanField(default=False)),
                ('body', models.TextField()),
                ('message', models.ForeignKey(to='message.Message')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
