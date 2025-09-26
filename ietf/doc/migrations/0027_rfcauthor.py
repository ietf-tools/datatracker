# Copyright The IETF Trust 2025, All Rights Reserved

from django.db import migrations, models
import django.db.models.deletion
import ietf.utils.models


class Migration(migrations.Migration):
    dependencies = [
        ("person", "0005_alter_historicalperson_pronouns_selectable_and_more"),
        ("doc", "0026_change_wg_state_descriptions"),
    ]

    operations = [
        migrations.CreateModel(
            name="RfcAuthor",
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
                ("titlepage_name", models.CharField(max_length=128)),
                ("is_editor", models.BooleanField(default=False)),
                (
                    "affiliation",
                    models.CharField(
                        blank=True,
                        help_text="Organization/company used by author for submission",
                        max_length=100,
                    ),
                ),
                (
                    "country",
                    models.CharField(
                        blank=True,
                        help_text="Country used by author for submission",
                        max_length=255,
                    ),
                ),
                ("order", models.IntegerField(default=1)),
                (
                    "document",
                    ietf.utils.models.ForeignKey(
                        limit_choices_to={"type_id": "rfc"},
                        on_delete=django.db.models.deletion.CASCADE,
                        to="doc.document",
                    ),
                ),
                (
                    "email",
                    ietf.utils.models.ForeignKey(
                        blank=True,
                        help_text="Email address used by author for submission",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="person.email",
                    ),
                ),
                (
                    "person",
                    ietf.utils.models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="person.person",
                    ),
                ),
            ],
            options={
                "ordering": ["document", "order"],
                "indexes": [
                    models.Index(
                        fields=["document", "order"],
                        name="doc_rfcauth_documen_6b5dc4_idx",
                    )
                ],
            },
        ),
    ]
