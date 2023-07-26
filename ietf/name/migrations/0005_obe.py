# Copyright The IETF Trust 2023, All Rights Reserved

from django.db import migrations

def forward(apps, schema_editor):
    FeedbackTypeName = apps.get_model("name", "FeedbackTypeName")
    FeedbackTypeName.objects.create(slug="obe", name="Overcome by events")

def reverse(apps, schema_editor):
    FeedbackTypeName = apps.get_model("name", "FeedbackTypeName")
    FeedbackTypeName.objects.filter(slug="obe").delete()

class Migration(migrations.Migration):
    dependencies = [
        ("name", "0004_statements"),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
