# Copyright The IETF Trust 2026, All Rights Reserved

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("doc", "0036_alter_docevent_type"),
    ]

    operations = [
        migrations.CreateModel(
            name="RpcAssignmentDocEvent",
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
                ("assignments", models.TextField(blank=True)),
            ],
            bases=("doc.docevent",),
        ),
    ]
