# Copyright The IETF Trust 2024, All Rights Reserved

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("meeting", "0004_session_chat_room"),
    ]

    operations = [
        migrations.AlterField(
            model_name="session",
            name="agenda_note",
            field=models.CharField(blank=True, max_length=512),
        ),
    ]
