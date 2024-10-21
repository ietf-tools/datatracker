# Copyright The IETF Trust 2024, All Rights Reserved

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("meeting", "0008_remove_schedtimesessassignment_notes"),
    ]

    operations = [
        migrations.AddField(
            model_name="session",
            name="meetecho_recording_name",
            field=models.CharField(
                blank=True, help_text="Name of the meetecho recording", max_length=64
            ),
        ),
    ]
