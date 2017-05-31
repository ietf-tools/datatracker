# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('name', '0019_add_docrelationshipname_downref_approval'),
    ]

    operations = [
        migrations.CreateModel(
            name='FormalLanguageName',
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
    ]
