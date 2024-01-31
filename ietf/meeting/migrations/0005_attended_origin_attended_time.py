# Copyright The IETF Trust 2023, All Rights Reserved

from django.db import migrations, models


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
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
    ]
