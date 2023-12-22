# Copyright The IETF Trust 2023, All Rights Reserved
from django.db import migrations


def forward(apps, schema_editor):
    StateType = apps.get_model("doc", "StateType")
    for slug in ["bcp", "std", "fyi"]:
        StateType.objects.create(slug=slug, label=f"{slug} state")


def reverse(apps, schema_editor):
    StateType = apps.get_model("doc", "StateType")
    StateType.objects.filter(slug__in=["bcp", "std", "fyi"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("doc", "0018_move_dochistory"),
    ]

    operations = [migrations.RunPython(forward, reverse)]
