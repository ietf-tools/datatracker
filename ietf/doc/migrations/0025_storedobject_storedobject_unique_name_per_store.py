# Copyright The IETF Trust 2025, All Rights Reserved

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("doc", "0024_remove_ad_is_watching_states"),
    ]

    operations = [
        migrations.CreateModel(
            name="StoredObject",
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
                ("store", models.CharField(max_length=256)),
                ("name", models.CharField(max_length=1024)),
                ("sha384", models.CharField(max_length=96)),
                ("len", models.PositiveBigIntegerField()),
                (
                    "store_created",
                    models.DateTimeField(
                        help_text="The instant the object ws first placed in the store"
                    ),
                ),
                (
                    "created",
                    models.DateTimeField(
                        help_text="Instant object became known. May not be the same as the storage's created value for the instance. It will hold ctime for objects imported from older disk storage"
                    ),
                ),
                (
                    "modified",
                    models.DateTimeField(
                        help_text="Last instant object was modified. May not be the same as the storage's modified value for the instance. It will hold mtime for objects imported from older disk storage unless they've actually been overwritten more recently"
                    ),
                ),
                ("doc_name", models.CharField(blank=True, max_length=255, null=True)),
                ("doc_rev", models.CharField(blank=True, max_length=16, null=True)),
                ("deleted", models.DateTimeField(null=True)),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["doc_name", "doc_rev"],
                        name="doc_storedo_doc_nam_d04465_idx",
                    )
                ],
            },
        ),
        migrations.AddConstraint(
            model_name="storedobject",
            constraint=models.UniqueConstraint(
                fields=("store", "name"), name="unique_name_per_store"
            ),
        ),
    ]
