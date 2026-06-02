# Copyright The IETF Trust 2025, All Rights Reserved

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("doc", "0028_rfcauthor"),
    ]

    operations = [
        migrations.CreateModel(
            name="EditedRfcAuthorsDocEvent",
            fields=[
                (
                    "docevent_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to="doc.docevent",
                    ),
                ),
            ],
            bases=("doc.docevent",),
        ),
    ]
