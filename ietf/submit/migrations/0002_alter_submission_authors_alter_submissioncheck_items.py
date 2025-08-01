# Copyright The IETF Trust 2025, All Rights Reserved

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("submit", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="submission",
            name="authors",
            field=models.JSONField(
                default=list,
                help_text="List of authors with name, email, affiliation and country.",
            ),
        ),
        migrations.AlterField(
            model_name="submissioncheck",
            name="items",
            field=models.JSONField(blank=True, default=dict, null=True),
        ),
    ]
