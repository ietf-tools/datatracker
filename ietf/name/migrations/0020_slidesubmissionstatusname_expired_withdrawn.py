# Copyright The IETF Trust 2026, All Rights Reserved

from django.db import migrations


def forward(apps, schema_editor):
    SlideSubmissionStatusName = apps.get_model("name", "SlideSubmissionStatusName")
    SlideSubmissionStatusName.objects.get_or_create(
        slug="expired",
        defaults={"name": "expired", "desc": "Expired: the meeting's materials closed with the proposal still pending", "order": 3},
    )
    SlideSubmissionStatusName.objects.get_or_create(
        slug="withdrawn",
        defaults={"name": "withdrawn", "desc": "Withdrawn by the proposer", "order": 4},
    )


def reverse(apps, schema_editor):
    SlideSubmissionStatusName = apps.get_model("name", "SlideSubmissionStatusName")
    SlideSubmissionStatusName.objects.filter(slug__in=["expired", "withdrawn"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("name", "0019_alter_sessionpurposename_timeslot_types"),
    ]

    operations = [migrations.RunPython(forward, reverse)]
