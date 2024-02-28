# Copyright The IETF Trust 2023, All Rights Reserved

from django.db import migrations, models


def forward(apps, schema_editor):
    DocTypeName = apps.get_model("name", "DocTypeName")
    DocTypeName.objects.create(
        slug="narrativeminutes",
        name="Narrative Minutes",
        desc="",
        used=True,
        order=0,
        prefix="narrative-minutes",
    )


def reverse(apps, schema_editor):
    DocTypeName = apps.get_model("name", "DocTypeName")
    DocTypeName.objects.filter(slug="narrativeminutes").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("name", "0012_adjust_important_dates"),
    ]

    operations = [
        migrations.AlterField(
            model_name="doctypename",
            name="prefix",
            field=models.CharField(default="", max_length=32),
        ),
        migrations.RunPython(forward, reverse),
    ]
