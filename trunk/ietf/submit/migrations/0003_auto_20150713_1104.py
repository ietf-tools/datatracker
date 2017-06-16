# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('submit', '0002_auto_20150430_0847'),
    ]

    operations = [
        migrations.AlterField(
            model_name='submission',
            name='replaces',
            field=models.CharField(max_length=1000, blank=True),
            preserve_default=True,
        ),
    ]
