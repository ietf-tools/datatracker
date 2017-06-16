# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('meeting', '0017_schedule_approved_interims'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='timeslot',
            options={'ordering': ['-time']},
        ),
        migrations.AlterField(
            model_name='schedtimesessassignment',
            name='modified',
            field=models.DateTimeField(auto_now=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='session',
            name='modified',
            field=models.DateTimeField(auto_now=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='timeslot',
            name='modified',
            field=models.DateTimeField(auto_now=True),
            preserve_default=True,
        ),
    ]
