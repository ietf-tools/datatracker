# Copyright The IETF Trust 2022, All Rights Reserved
from django.db import migrations


def forward(apps, schema_editor):
    State = apps.get_model("doc", "State")
    StateType = apps.get_model("doc", "StateType")
    StateType.objects.create(
        slug="draft-stream-editorial", label="Editorial stream state"
    )
    for slug, name, order in (
        ("repl", "Replaced editorial stream document", 0),
        ("active", "Active editorial stream document", 2),
        ("rsabpoll", "Editorial stream document under RSAB review", 3),
        ("pub", "Published RFC", 4),
        ("dead", "Dead editorial stream document", 5),
    ):
        State.objects.create(
            type_id="draft-stream-editorial",
            slug=slug,
            name=name,
            order=order,
            used=True,
        )


def reverse(apps, schema_editor):
    State = apps.get_model("doc", "State")
    StateType = apps.get_model("doc", "StateType")
    State.objects.filter(type_id="draft-stream-editorial").delete()
    StateType.objects.filter(slug="draft-stream-editorial").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("doc", "0049_add_rsab_doc_positions"),
    ]

    operations = [migrations.RunPython(forward, reverse)]
