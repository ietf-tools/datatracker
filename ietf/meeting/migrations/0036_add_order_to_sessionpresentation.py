# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import debug         # pyflakes:ignore

from django.db import models, migrations

def forward(apps, schema_editor):
    SessionPresentation = apps.get_model("meeting","SessionPresentation")
    for sp in SessionPresentation.objects.filter(document__type__slug='slides',session__meeting__number__in=['95','96']):
        sp.order = int(sp.document.name.split('-')[-1])
        sp.save()

def reverse(apps, schema_editor):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('meeting', '0035_auto_20160818_1610'),
    ]

    operations = [
        migrations.AddField(
            model_name='sessionpresentation',
            name='order',
            field=models.PositiveSmallIntegerField(default=0),
            preserve_default=True,
        ),
        migrations.RunPython(forward,reverse)
    ]
