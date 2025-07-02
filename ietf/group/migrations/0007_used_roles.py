# Copyright The IETF Trust 2025, All Rights Reserved

from django.db import migrations


def forward(apps, schema_editor):
    Group = apps.get_model("group", "Group")
    GroupFeatures = apps.get_model("group", "GroupFeatures")
    iab = Group.objects.get(acronym="iab")
    iab.used_roles = [
        "chair",
        "delegate",
        "exofficio",
        "liaison",
        "liaison_coordinator",
        "member",
    ]
    iab.save()
    GroupFeatures.objects.filter(type_id="ietf").update(
        default_used_roles=[
            "ad",
            "member",
            "comdir",
            "delegate",
            "execdir",
            "recman",
            "secr",
            "chair",
        ]
    )


def reverse(apps, schema_editor):
    Group = apps.get_model("group", "Group")
    iab = Group.objects.get(acronym="iab")
    iab.used_roles = []
    iab.save()
    # Intentionally not putting trac-* back into grouptype ietf default_used_roles


class Migration(migrations.Migration):
    dependencies = [
        ("group", "0006_remove_liason_contacts"),
        ("name", "0018_alter_rolenames"),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
