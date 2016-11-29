# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('review', '0002_auto_20161017_1218'),
    ]

    operations = [
        migrations.AlterField(
            model_name='reviewersettings',
            name='min_interval',
            field=models.IntegerField(blank=True, null=True, verbose_name=b'Can review at most', choices=[(7, b'Once per week'), (14, b'Once per fortnight'), (30, b'Once per month'), (61, b'Once per two months'), (91, b'Once per quarter')]),
            preserve_default=True,
        ),
    ]
