# Copyright The IETF Trust 2025, All Rights Reserved

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("person", "0004_alter_person_photo_alter_person_photo_thumb"),
    ]

    operations = [
        migrations.AlterField(
            model_name="historicalperson",
            name="pronouns_selectable",
            field=models.JSONField(
                blank=True,
                default=list,
                max_length=120,
                null=True,
                verbose_name="Pronouns",
            ),
        ),
        migrations.AlterField(
            model_name="person",
            name="pronouns_selectable",
            field=models.JSONField(
                blank=True,
                default=list,
                max_length=120,
                null=True,
                verbose_name="Pronouns",
            ),
        ),
    ]
