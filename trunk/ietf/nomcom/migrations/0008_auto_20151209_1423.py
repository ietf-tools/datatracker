# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('nomcom', '0007_feedbacklastseen'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='position',
            name='description',
        ),
        migrations.AlterField(
            model_name='position',
            name='name',
            field=models.CharField(help_text=b'This short description will appear on the Nomination and Feedback pages. Be as descriptive as necessary. Past examples: "Transport AD", "IAB Member"', max_length=255, verbose_name=b'Name'),
            preserve_default=True,
        ),
    ]
