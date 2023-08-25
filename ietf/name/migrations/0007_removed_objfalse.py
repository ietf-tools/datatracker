# Copyright The IETF Trust 2023, All Rights Reserved

from django.db import migrations

def forward(apps, schema_editor):
    IprDisclosureStateName = apps.get_model("name", "IprDisclosureStateName")
    IprDisclosureStateName.objects.create(slug="removed_objfalse", name="Removed Objectively False", order=5)

def reverse(apps, schema_editor):
    IprDisclosureStateName = apps.get_model("name", "IprDisclosureStateName")
    IprDisclosureStateName.objects.filter(slug="removed_objfalse").delete()

class Migration(migrations.Migration):
    dependencies = [
        ("name", "0006_feedbacktypename_data"),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
