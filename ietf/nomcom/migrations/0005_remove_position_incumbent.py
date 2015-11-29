# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('nomcom', '0004_auto_20151027_0829'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='position',
            name='incumbent',
        ),
    ]
