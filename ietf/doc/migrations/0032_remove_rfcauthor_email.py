# Copyright The IETF Trust 2026, All Rights Reserved

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("doc", "0031_change_draft_stream_ietf_state_descriptions"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="rfcauthor",
            name="email",
        ),
    ]
