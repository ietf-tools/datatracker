# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

def rename_x3s3dot3_forwards(apps, schema_editor):
    Group = apps.get_model("group", "Group")
    Group.objects.filter(acronym="x3s3.3").update(acronym="x3s3dot3")

def rename_x3s3dot3_backwards(apps, schema_editor):
    Group = apps.get_model("group", "Group")
    Group.objects.filter(acronym="x3s3dot3").update(acronym="x3s3.3")

class Migration(migrations.Migration):

    dependencies = [
        ('group', '0006_auto_20150718_0509'),
    ]

    operations = [
        migrations.RunPython(rename_x3s3dot3_forwards, rename_x3s3dot3_backwards)
    ]
