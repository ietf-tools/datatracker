# Copyright The IETF Trust 2024, All Rights Reserved

from django.db import migrations
import django.db.models.deletion
import ietf.utils.models


class Migration(migrations.Migration):
    dependencies = [
        ("doc", "0021_narrativeminutes"),
        ("meeting", "0004_session_chat_room"),
    ]

    operations = [
        migrations.AlterField(
            model_name="sessionpresentation",
            name="document",
            field=ietf.utils.models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="presentations",
                to="doc.document",
            ),
        ),
        migrations.AlterField(
            model_name="sessionpresentation",
            name="session",
            field=ietf.utils.models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="presentations",
                to="meeting.session",
            ),
        ),
    ]
