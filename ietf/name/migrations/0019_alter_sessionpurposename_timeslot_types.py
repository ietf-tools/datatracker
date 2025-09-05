# Copyright The IETF Trust 2025, All Rights Reserved

from django.db import migrations, models
import ietf.utils.validators


class Migration(migrations.Migration):
    dependencies = [
        ("name", "0018_alter_rolenames"),
    ]

    operations = [
        migrations.AlterField(
            model_name="sessionpurposename",
            name="timeslot_types",
            field=models.JSONField(
                default=list,
                help_text="Allowed TimeSlotTypeNames",
                max_length=256,
                validators=[
                    ietf.utils.validators.JSONForeignKeyListValidator(
                        "name.TimeSlotTypeName"
                    )
                ],
            ),
        ),
    ]
