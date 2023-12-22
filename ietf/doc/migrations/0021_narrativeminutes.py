# Copyright The IETF Trust 2023, All Rights Reserved

from django.db import migrations


def forward(apps, schema_editor):
    StateType = apps.get_model("doc", "StateType")
    State = apps.get_model("doc", "State")

    StateType.objects.create(
        slug="narrativeminutes",
        label="State",
    )
    for order, slug in enumerate(["active", "deleted"]):
        State.objects.create(
            slug=slug,
            type_id="narrativeminutes",
            name=slug.capitalize(),
            order=order,
            desc="",
            used=True,
        )


def reverse(apps, schema_editor):
    StateType = apps.get_model("doc", "StateType")
    State = apps.get_model("doc", "State")

    State.objects.filter(type_id="narrativeminutes").delete()
    StateType.objects.filter(slug="narrativeminutes").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("doc", "0020_move_errata_tags"),
        ("name", "0013_narrativeminutes"),
    ]

    operations = [migrations.RunPython(forward, reverse)]
