# Copyright 2025, IETF Trust

from django.db import migrations


def forward(apps, schema_editor):
    ReviewTypeName = apps.get_model("name", "ReviewTypeName")
    ReviewTypeName.objects.filter(slug="lc").update(name="IETF Last Call")

def reverse(apps, schema_editor):
    ReviewTypeName = apps.get_model("name", "ReviewTypeName")
    ReviewTypeName.objects.filter(slug="lc").update(name="Last Call")

class Migration(migrations.Migration):

    dependencies = [
        ("name", "0014_change_legacy_stream_desc"),
    ]

    operations = [
        migrations.RunPython(forward, reverse)
    ]
