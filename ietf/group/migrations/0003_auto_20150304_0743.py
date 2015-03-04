# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('group', '0002_auto_20150208_1012'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='group',
            name='ad',
        ),
        migrations.RemoveField(
            model_name='grouphistory',
            name='ad',
        ),
    ]
