# Copyright The IETF Trust 2026, All Rights Reserved

from django.db import migrations
from django.db.models import Count


def forward(apps, schema_editor):
    pass


def restore(apps, schema_editor):
    SlideSubmission = apps.get_model("meeting", "SlideSubmission")
    SlideSubmission.objects.annotate(n=Count("sessions")).filter(n__gt=1).update(apply_to_all=True)


class Migration(migrations.Migration):

    dependencies = [
        ("meeting", "0017_slidesubmission_sessions"),
    ]

    operations = [
        migrations.RunPython(forward, restore),
        migrations.RemoveField(
            model_name="slidesubmission",
            name="apply_to_all",
        ),
    ]
