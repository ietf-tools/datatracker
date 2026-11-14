# Copyright The IETF Trust 2026, All Rights Reserved

from django.db import migrations


def forward(apps, schema_editor):
    ProceedingsMaterialTypeName = apps.get_model("name", "ProceedingsMaterialTypeName")
    ProceedingsMaterialTypeName.objects.get_or_create(
        slug="meeting_survey",
        defaults={
            "name": "Post-Meeting Survey Results",
            "desc": "Results of the post-meeting survey",
            "used": True,
            "order": 5,
        },
    )


def reverse(apps, schema_editor):
    ProceedingsMaterialTypeName = apps.get_model("name", "ProceedingsMaterialTypeName")
    ProceedingsMaterialTypeName.objects.filter(slug="meeting_survey").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("name", "0020_slidesubmissionstatusname_expired_withdrawn"),
    ]

    operations = [migrations.RunPython(forward, reverse)]
