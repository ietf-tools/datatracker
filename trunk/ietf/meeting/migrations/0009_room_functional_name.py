# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('meeting', '0008_auto_20150429_1346'),
    ]

    operations = [
        migrations.AddField(
            model_name='room',
            name='functional_name',
            field=models.CharField(default='', max_length=255, blank=True),
            preserve_default=False,
        ),
    ]
