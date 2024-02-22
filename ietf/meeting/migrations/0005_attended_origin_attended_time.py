# Copyright The IETF Trust 2024, All Rights Reserved

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("meeting", "0004_session_chat_room"),
    ]

    operations = [
        migrations.AddField(
            model_name="attended",
            name="origin",
            field=models.CharField(default="datatracker", max_length=32),
        ),
        migrations.AddField(
            model_name="attended",
            name="time",
            field=models.DateTimeField(
                blank=True, default=django.utils.timezone.now, null=True
            ),
        ),
    ]
