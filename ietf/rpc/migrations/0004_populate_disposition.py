# Copyright The IETF Trust 2023, All Rights Reserved

from django.db import migrations

def forward(apps, schema_editor):
    Disposition = apps.get_model("rpc", "Disposition")

    Disposition.objects.create(
        slug = "in_progress",
        name = "In Progress",
        desc = "RfcToBe is a work in progress"
    )
    Disposition.objects.create(
        slug = "published",
        name = "Published",
        desc = "RfcToBe has been published as an RFC"
    )
    Disposition.objects.create(
        slug = "withdrawn",
        name = "Withdrawn",
        desc = "RfcToBe has been withdrawn"
    )


def reverse(apps, schema_editor):
    Disposition = apps.get_model("rpc", "Disposition")

    Disposition.objects.all().delete()

class Migration(migrations.Migration):
    dependencies = [
        ("rpc", "0003_populate_capability"),
    ]

    operations = [
        migrations.RunPython(forward, reverse)
    ]
