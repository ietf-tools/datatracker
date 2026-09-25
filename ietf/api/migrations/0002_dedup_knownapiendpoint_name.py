# Copyright The IETF Trust 2026, All Rights Reserved

from django.db import migrations


def forward(apps, schema_editor):
    # Eliminate any duplicate KnownApiEndpoint names, grouping existing API tokens
    # under the one that is kept. Ignores enabled flag, so check that after the
    # migration.
    KnownApiEndpoint = apps.get_model("api", "KnownApiEndpoint")
    endpoints = list(KnownApiEndpoint.objects.all())  # small number, work in python
    endpoints_to_keep = {}  # name -> Endpoint
    for ep in endpoints:
        endpoints_to_keep.setdefault(ep.name, ep)  # keeps first per name
    endpoints_to_delete = [
        ep for ep in endpoints if ep not in endpoints_to_keep.values()
    ]
    for ep_to_delete in endpoints_to_delete:
        replacement = endpoints_to_keep[ep_to_delete.name]
        for token in ep_to_delete.tokens.all():
            token.endpoints.add(replacement)
        ep_to_delete.delete()


def reverse(apps, schema_editor):
    pass  # nothing to do


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
