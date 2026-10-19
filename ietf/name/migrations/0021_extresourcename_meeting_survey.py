# Copyright The IETF Trust 2026, All Rights Reserved

from django.db import migrations


def forward(apps, schema_editor):
    ExtResourceName = apps.get_model("name", "ExtResourceName")
    ExtResourceName.objects.get_or_create(
        slug="meeting_survey",
        defaults={
            "name": "Meeting Survey Results",
            "desc": "Results of the post-meeting survey",
            "used": True,
            "order": 0,
            "type_id": "url",
        },
    )


def reverse(apps, schema_editor):
    ExtResourceName = apps.get_model("name", "ExtResourceName")
    ExtResourceName.objects.filter(slug="meeting_survey").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("name", "0020_slidesubmissionstatusname_expired_withdrawn"),
    ]

    operations = [migrations.RunPython(forward, reverse)]
