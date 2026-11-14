# Copyright The IETF Trust 2026, All Rights Reserved

from django.db import migrations


def forward(apps, schema_editor):
    ProceedingsMaterialTypeName = apps.get_model("name", "ProceedingsMaterialTypeName")
    # Move meeting_survey to position 6 so it appears after the RFC Editor report
    ProceedingsMaterialTypeName.objects.filter(slug="meeting_survey").update(order=6)
    ProceedingsMaterialTypeName.objects.get_or_create(
        slug="rfc_editor_report",
        defaults={
            "name": "RFC Editor Report",
            "desc": "Report from the RFC Editor",
            "used": True,
            "order": 5,
        },
    )


def reverse(apps, schema_editor):
    ProceedingsMaterialTypeName = apps.get_model("name", "ProceedingsMaterialTypeName")
    ProceedingsMaterialTypeName.objects.filter(slug="rfc_editor_report").delete()
    ProceedingsMaterialTypeName.objects.filter(slug="meeting_survey").update(order=5)


class Migration(migrations.Migration):
    dependencies = [
        ("name", "0021_proceedingsmaterialtypename_meeting_survey"),
    ]

    operations = [migrations.RunPython(forward, reverse)]
