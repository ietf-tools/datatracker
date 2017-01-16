# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doc', '0019_auto_20161207_1036'),
    ]

    operations = [
        migrations.AddField(
            model_name='dochistory',
            name='words',
            field=models.IntegerField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='document',
            name='words',
            field=models.IntegerField(null=True, blank=True),
        ),
    ]
