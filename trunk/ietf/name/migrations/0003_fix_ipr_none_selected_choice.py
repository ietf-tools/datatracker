# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

def fix_non_selected_choice(apps, schema_editor):
    apps.get_model("name", "IprLicenseTypeName").objects.filter(slug="none-selected").update(desc="[None selected]")

class Migration(migrations.Migration):

    dependencies = [
        ('name', '0002_auto_20150208_1008'),
    ]

    operations = [
        migrations.RunPython(fix_non_selected_choice)
    ]
