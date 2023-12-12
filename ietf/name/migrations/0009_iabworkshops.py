# Copyright The IETF Trust 2023, All Rights Reserved

from django.db import migrations

def forward(apps, schema_editor):
    GroupTypeName = apps.get_model("name", "GroupTypeName")
    GroupTypeName.objects.create(
        slug = "iabworkshop",
        name = "IAB Workshop",
        desc = "IAB Workshop",
        used = True,
        order = 0,
        verbose_name = "IAB Workshop",

    )

def reverse(apps, schema_editor):
    GroupTypeName = apps.get_model("name", "GroupTypeName")
    GroupTypeName.objects.filter(slug="iabworkshop").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("name", "0008_removed_objfalse"),
    ]

    operations = [
        migrations.RunPython(forward, reverse)
    ]
