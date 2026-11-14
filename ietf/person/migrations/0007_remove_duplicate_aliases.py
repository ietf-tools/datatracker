# Copyright The IETF Trust 2026, All Rights Reserved

from django.db import migrations
from django.db.models import Min


def forward(apps, schema_editor):
    """Delete repeated aliases of the same name for a person, keeping the oldest row."""
    Alias = apps.get_model("person", "Alias")
    keep = Alias.objects.values("person", "name").annotate(keep_pk=Min("pk")).values("keep_pk")
    Alias.objects.exclude(pk__in=keep).delete()


def reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("person", "0006_personuuid"),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
