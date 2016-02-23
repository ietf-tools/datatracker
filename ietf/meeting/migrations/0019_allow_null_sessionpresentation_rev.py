# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('meeting', '0018_auto_20160207_0537'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sessionpresentation',
            name='rev',
            field=models.CharField(max_length=16, null=True, verbose_name=b'revision', blank=True),
            preserve_default=True,
        ),
    ]
