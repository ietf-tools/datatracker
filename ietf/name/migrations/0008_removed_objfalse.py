# Copyright The IETF Trust 2023, All Rights Reserved

from django.db import migrations

def forward(apps, schema_editor):
    IprDisclosureStateName = apps.get_model("name", "IprDisclosureStateName")
    IprDisclosureStateName.objects.create(slug="removed_objfalse", name="Removed Objectively False", order=5)
    IprEventTypeName = apps.get_model("name", "IprEventTypeName")
    IprEventTypeName.objects.create(slug="removed_objfalse", name="Removed Objectively False")

def reverse(apps, schema_editor):
    IprDisclosureStateName = apps.get_model("name", "IprDisclosureStateName")
    IprDisclosureStateName.objects.filter(slug="removed_objfalse").delete()
    IprEventTypeName = apps.get_model("name", "IprEventTypeName")
    IprEventTypeName.objects.filter(slug="removed_objfalse").delete()

class Migration(migrations.Migration):
    dependencies = [
        ("name", "0007_appeal_artifact_typename"),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
