# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('doc', '0008_auto_20150930_0242'),
        ('ipr', '0006_auto_20150930_0235'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='docalias',
            name='id',
        ),
        migrations.AlterField(
            model_name='docalias',
            name='name',
            field=models.CharField(max_length=255, serialize=False, primary_key=True),
            preserve_default=True,
        ),
    ]
