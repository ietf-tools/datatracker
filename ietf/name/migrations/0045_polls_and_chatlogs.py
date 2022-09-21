# Copyright The IETF Trust 2022, All Rights Reserved
from django.db import migrations

def forward(apps, schema_editor):
    DocTypeName = apps.get_model("name", "DocTypeName")
    DocTypeName.objects.create(
        slug = "chatlogs",
        name = "Chat Logs",
        prefix = "chatlogs",
        desc = "",
        order = 0,
        used = True,
    )
    DocTypeName.objects.create(
        slug = "polls",
        name = "Polls",
        prefix = "polls",
        desc = "",
        order = 0,
        used = True,
    )

def reverse(apps, schema_editor):
    DocTypeName = apps.get_model("name", "DocTypeName")
    DocTypeName.objects.filter(slug__in=("chatlogs", "polls")).delete()

class Migration(migrations.Migration):

    dependencies = [
        ('name', '0044_validating_draftsubmissionstatename'),
    ]

    operations = [
        migrations.RunPython(forward, reverse)
    ]
