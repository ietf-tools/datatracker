# Copyright The IETF Trust 2025, All Rights Reserved

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Blob",
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
                (
                    "name",
                    models.CharField(help_text="Name of the blob", max_length=1024),
                ),
                (
                    "bucket",
                    models.CharField(
                        help_text="Name of the bucket containing this blob",
                        max_length=1024,
                    ),
                ),
                (
                    "modified",
                    models.DateTimeField(
                        default=django.utils.timezone.now,
                        help_text="Last modification time of the blob",
                    ),
                ),
                ("content", models.BinaryField(help_text="Content of the blob")),
                (
                    "checksum",
                    models.CharField(
                        editable=False,
                        help_text="SHA-384 digest of the content",
                        max_length=96,
                    ),
                ),
                (
                    "mtime",
                    models.DateTimeField(
                        blank=True,
                        default=None,
                        help_text="mtime associated with the blob as a filesystem object",
                        null=True,
                    ),
                ),
                (
                    "content_type",
                    models.CharField(
                        blank=True,
                        help_text="content-type header value for the blob contents",
                        max_length=1024,
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="blob",
            constraint=models.UniqueConstraint(
                fields=("bucket", "name"), name="unique_name_per_bucket"
            ),
        ),
    ]
