# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

def populate_names(apps, schema_editor):
    LiaisonStatementEventTypeName = apps.get_model("name", "LiaisonStatementEventTypeName")
    LiaisonStatementEventTypeName.objects.create(slug="private_comment", order=10, name="Private Comment")


class Migration(migrations.Migration):

    dependencies = [
        ('name', '0009_auto_20151021_1102'),
    ]

    operations = [
        migrations.RunPython(populate_names),
    ]
