# Copyright The IETF Trust 2026, All Rights Reserved

from django.db import migrations, models
import django.db.models.deletion
import ietf.utils.models


class Migration(migrations.Migration):

    dependencies = [
        ("name", "0021_extresourcename_meeting_survey"),
        ("meeting", "0020_slidesubmission_time_default"),
    ]

    operations = [
        migrations.CreateModel(
            name="MeetingExtResource",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "display_name",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                ("value", models.CharField(max_length=2083)),
                (
                    "meeting",
                    ietf.utils.models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="meeting.meeting",
                    ),
                ),
                (
                    "name",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="name.extresourcename",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
    ]
