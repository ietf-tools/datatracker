# Copyright The IETF Trust 2026, All Rights Reserved

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("utils", "0003_dirtybits"),
    ]

    operations = [
        migrations.AlterField(
            model_name="dirtybits",
            name="slug",
            field=models.CharField(
                choices=[("rfcindex", "RFC Index"), ("errata", "Errata Tags")],
                max_length=40,
                unique=True,
            ),
        ),
    ]
