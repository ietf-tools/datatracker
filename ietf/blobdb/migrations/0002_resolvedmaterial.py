# Copyright The IETF Trust 2025, All Rights Reserved

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("blobdb", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ResolvedMaterial",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(help_text="Name to resolve", max_length=300)),
                (
                    "meeting_number",
                    models.CharField(
                        help_text="Meeting material is related to", max_length=64
                    ),
                ),
                (
                    "bucket",
                    models.CharField(help_text="Resolved bucket name", max_length=255),
                ),
                (
                    "blob",
                    models.CharField(help_text="Resolved blob name", max_length=300),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="resolvedmaterial",
            constraint=models.UniqueConstraint(
                fields=("name", "meeting_number"), name="unique_name_per_meeting"
            ),
        ),
    ]
