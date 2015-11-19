# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('liaisons', '0008_auto_20151110_1352'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='liaisonstatement',
            name='from_name',
        ),
        migrations.RemoveField(
            model_name='liaisonstatement',
            name='to_name',
        ),
    ]
