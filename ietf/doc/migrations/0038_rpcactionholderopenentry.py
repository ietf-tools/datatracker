# Copyright The IETF Trust 2026, All Rights Reserved

from django.db import migrations, models
import django.db.models.deletion
import ietf.utils.models


class Migration(migrations.Migration):

    dependencies = [
        ("person", "0005_alter_historicalperson_pronouns_selectable_and_more"),
        ("doc", "0037_rpcassignmentdocevent"),
    ]

    operations = [
        migrations.CreateModel(
            name="RpcActionHolderOpenEntry",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "purple_id",
                    models.PositiveIntegerField(
                        help_text="ID of the ActionHolder in the RPC tool", unique=True
                    ),
                ),
                (
                    "body",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Name of the body holding the action, if it is not a person",
                        max_length=64,
                    ),
                ),
                (
                    "display_name",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                ("comment", models.TextField(blank=True)),
                ("rfc_number", models.PositiveIntegerField(blank=True, null=True)),
                ("since_when", models.DateTimeField()),
                ("deadline", models.DateTimeField(blank=True, null=True)),
                ("time_captured", models.DateTimeField(auto_now=True)),
                (
                    "document",
                    ietf.utils.models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="doc.document"
                    ),
                ),
                (
                    "person",
                    ietf.utils.models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="person.person",
                    ),
                ),
            ],
        ),
    ]
