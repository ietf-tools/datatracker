# Copyright The IETF Trust 2025, All Rights Reserved
from io import StringIO

from django.conf import settings
from django.core import management
from django.db import migrations, models
import django.db.models.deletion
import simple_history.models

from ietf.utils.log import log


def forward(apps, schema_editor):
    # Fill in history for existing data using the populate_history management command
    captured_stdout = StringIO()
    captured_stderr = StringIO()
    try:
        management.call_command(
            "populate_history",
            "mailtrigger.MailTrigger",
            "mailtrigger.Recipient",
            stdout=captured_stdout,
            stderr=captured_stderr,
        )
    except management.CommandError as err:
        log(
            "Failed to populate history for mailtrigger models.\n"
            "\n"
            f"stdout:\n{captured_stdout.getvalue() or '<none>'}\n"
            "\n"
            f"stderr:\n{captured_stderr.getvalue() or '<none>'}\n"
        )
        raise RuntimeError("Failed to populate history for mailtrigger models") from err
    log(
        "Populated history for mailtrigger models.\n"
        "\n"
        f"stdout:\n{captured_stdout.getvalue() or '<none>'}\n"
        "\n"
        f"stderr:\n{captured_stderr.getvalue() or '<none>'}\n"
    )


def reverse(apps, schema_editor):
    pass  # nothing to do


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("mailtrigger", "0006_call_for_adoption_and_last_call_issued"),
    ]

    operations = [
        migrations.CreateModel(
            name="HistoricalRecipient",
            fields=[
                ("slug", models.CharField(db_index=True, max_length=32)),
                ("desc", models.TextField(blank=True)),
                ("template", models.TextField(blank=True, null=True)),
                ("history_id", models.AutoField(primary_key=True, serialize=False)),
                ("history_date", models.DateTimeField(db_index=True)),
                ("history_change_reason", models.CharField(max_length=100, null=True)),
                (
                    "history_type",
                    models.CharField(
                        choices=[("+", "Created"), ("~", "Changed"), ("-", "Deleted")],
                        max_length=1,
                    ),
                ),
                (
                    "history_user",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "historical recipient",
                "verbose_name_plural": "historical recipients",
                "ordering": ("-history_date", "-history_id"),
                "get_latest_by": ("history_date", "history_id"),
            },
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
        migrations.CreateModel(
            name="HistoricalMailTrigger",
            fields=[
                ("slug", models.CharField(db_index=True, max_length=64)),
                ("desc", models.TextField(blank=True)),
                ("history_id", models.AutoField(primary_key=True, serialize=False)),
                ("history_date", models.DateTimeField(db_index=True)),
                ("history_change_reason", models.CharField(max_length=100, null=True)),
                (
                    "history_type",
                    models.CharField(
                        choices=[("+", "Created"), ("~", "Changed"), ("-", "Deleted")],
                        max_length=1,
                    ),
                ),
                (
                    "history_user",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "historical mail trigger",
                "verbose_name_plural": "historical mail triggers",
                "ordering": ("-history_date", "-history_id"),
                "get_latest_by": ("history_date", "history_id"),
            },
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
        migrations.RunPython(forward, reverse),
    ]
