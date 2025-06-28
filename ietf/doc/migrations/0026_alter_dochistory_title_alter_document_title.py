# Copyright The IETF Trust 2025, All Rights Reserved

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("doc", "0025_storedobject_storedobject_unique_name_per_store"),
    ]

    operations = [
        migrations.AlterField(
            model_name="dochistory",
            name="title",
            field=models.CharField(
                max_length=255,
                validators=[
                    django.core.validators.ProhibitNullCharactersValidator,
                    django.core.validators.RegexValidator(
                        message="Please enter a string without control characters.",
                        regex="^[^\x01-\x1f]*$",
                    ),
                ],
            ),
        ),
        migrations.AlterField(
            model_name="document",
            name="title",
            field=models.CharField(
                max_length=255,
                validators=[
                    django.core.validators.ProhibitNullCharactersValidator,
                    django.core.validators.RegexValidator(
                        message="Please enter a string without control characters.",
                        regex="^[^\x01-\x1f]*$",
                    ),
                ],
            ),
        ),
    ]
