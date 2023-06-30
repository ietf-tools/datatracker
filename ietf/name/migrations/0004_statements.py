# Copyright The IETF Trust 2023, All Rights Reserved

from django.db import migrations

def forward(apps, schema_editor):
    DocTypeName = apps.get_model("name", "DocTypeName")
    DocTypeName.objects.create(slug="statement", name="Statement", prefix="statement", desc="", used=True)


def reverse(apps, schema_editor):
    DocTypeName = apps.get_model("name", "DocTypeName")
    DocTypeName.objects.filter(slug="statement").delete()

class Migration(migrations.Migration):
    dependencies = [
        ("name", "0003_populate_telechatagendasectionname"),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
