# Copyright The IETF Trust 2023, All Rights Reserved

from django.db import migrations, models
import django.db.models.deletion
import ietf.utils.models
import ietf.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("name", "0007_appeal_artifact_typename"),
        ("group", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Appeal",
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
                ("name", models.CharField(max_length=512)),
                ("date", models.DateField(default=ietf.utils.timezone.date_today)),
                (
                    "group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, to="group.group"
                    ),
                ),
            ],
            options={
                "ordering": ["-date", "-id"],
            },
        ),
        migrations.CreateModel(
            name="AppealArtifact",
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
                ("date", models.DateField(default=ietf.utils.timezone.date_today)),
                (
                    "title",
                    models.CharField(
                        blank=True,
                        help_text="The artifact_type.name will be used if this field is blank",
                        max_length=256,
                    ),
                ),
                ("order", models.IntegerField(default=0)),
                ("content_type", models.CharField(max_length=32)),
                ("bits", models.BinaryField(editable=True)),
                (
                    "appeal",
                    ietf.utils.models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="group.appeal"
                    ),
                ),
                (
                    "artifact_type",
                    ietf.utils.models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="name.appealartifacttypename",
                    ),
                ),
            ],
            options={
                "ordering": ["date", "order", "artifact_type__order"],
            },
        ),
    ]
