# Copyright The IETF Trust 2023, All Rights Reserved

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('meeting', '0003_populate_session_has_onsite_tool'),
    ]

    operations = [
        migrations.AddField(
            model_name='session',
            name='chat_room',
            field=models.CharField(blank=True, help_text='Name of Zulip stream, if different from group acronym', max_length=32),
        ),
    ]
