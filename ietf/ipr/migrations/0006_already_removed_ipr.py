# Copyright The IETF Trust 2025, All Rights Reserved
from django.db import migrations


def forward(apps, schema_editor):
    RemovedIprDisclosure = apps.get_model("ipr", "RemovedIprDisclosure")
    for id in (6544, 6068):
        RemovedIprDisclosure.objects.create(
            removed_id=id,
            reason="This IPR disclosure was removed as objectively false.",
        )


def reverse(apps, schema_editor):
    RemovedIprDisclosure = apps.get_model("ipr", "RemovedIprDisclosure")
    RemovedIprDisclosure.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("ipr", "0005_removediprdisclosure"),
    ]

    operations = [migrations.RunPython(forward, reverse)]
