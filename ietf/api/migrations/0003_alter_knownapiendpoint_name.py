# Copyright The IETF Trust 2026, All Rights Reserved

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0002_dedup_knownapiendpoint_name"),
    ]

    operations = [
        migrations.AlterField(
            model_name="knownapiendpoint",
            name="name",
            field=models.CharField(
                help_text="API endpoint name", max_length=1000, unique=True
            ),
        ),
    ]
