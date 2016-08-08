# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


def reverse(apps, schema_editor):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('meeting', '0030_add_material_day_offsets'),
    ]

    operations = [
        migrations.AddField(
            model_name='meeting',
            name='proceedings_final',
            field=models.BooleanField(default=False, help_text='Are the proceedings for this meeting complete?'),
            preserve_default=True,
        ),
    ]
