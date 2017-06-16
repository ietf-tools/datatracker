# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('meeting', '0003_auto_20150304_0738'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='scheduledsession',
            options={'ordering': ['timeslot__time', 'timeslot__type__slug', 'session__group__parent__name', 'session__group__acronym', 'session__name']},
        ),
    ]
