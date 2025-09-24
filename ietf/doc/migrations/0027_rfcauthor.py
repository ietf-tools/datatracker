# Copyright The IETF Trust 2025, All Rights Reserved

from django.db import migrations, models
import django.db.models.deletion
import ietf.utils.models


class Migration(migrations.Migration):
    dependencies = [
        ("person", "0004_alter_person_photo_alter_person_photo_thumb"),
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
                ("titlepage_name", models.CharField(max_length=128, blank=False)),
                ("is_editor", models.BooleanField(default=False)),
                (
                    "affiliation",
                    models.CharField(
                        blank=True,
                        help_text="Organization/company used by author for submission",
                        max_length=100,
                    ),
                ),
                ("order", models.IntegerField(default=1)),
                (
                    "document",
                    ietf.utils.models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="doc.document"
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
