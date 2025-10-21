# Copyright The IETF Trust 2025, All Rights Reserved

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ipr", "0004_holderiprdisclosure_is_blanket_disclosure"),
    ]

    operations = [
        migrations.CreateModel(
            name="RemovedIprDisclosure",
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
                ("removed_id", models.PositiveBigIntegerField(unique=True)),
                ("reason", models.TextField()),
            ],
        ),
    ]
