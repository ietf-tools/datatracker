# Copyright The IETF Trust 2023, All Rights Reserved

from django.db import migrations


def forward(apps, schema_editor):
    StateType = apps.get_model("doc", "StateType")
    State = apps.get_model("doc", "State")

    StateType.objects.create(slug="statement", label="Statement State")
    State.objects.create(
        slug="active",
        type_id="statement",
        name="Active",
        order=0,
        desc="The statement is active",
    )
    State.objects.create(
        slug="replaced",
        type_id="statement",
        name="Replaced",
        order=0,
        desc="The statement has been replaced",
    )


def reverse(apps, schema_editor):
    StateType = apps.get_model("doc", "StateType")
    State = apps.get_model("doc", "State")

    State.objects.filter(type_id="statement").delete()
    StateType.objects.filter(slug="statement").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("doc", "0005_alter_docevent_type"),
        ("name", "0004_statements"),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
