# Copyright The IETF Trust 2024, All Rights Reserved

from django.db import migrations

def forward(apps, schema_editor):
    StreamName = apps.get_model("name", "StreamName")
    StreamName.objects.filter(pk="legacy").update(desc="Legacy")

def reverse(apps, schema_editor):
    StreamName = apps.get_model("name", "StreamName")
    StreamName.objects.filter(pk="legacy").update(desc="Legacy stream")

class Migration(migrations.Migration):

    dependencies = [
        ("name", "0013_narrativeminutes"),
    ]

    operations = [
        migrations.RunPython(forward, reverse)
    ]
