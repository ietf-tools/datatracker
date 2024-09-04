# Copyright The IETF Trust 2024, All Rights Reserved

from django.db import migrations


def forward(apps, schema_editor):
    State = apps.get_model("doc", "State")
    State.objects.get_or_create(
        type_id="bofreq",
        slug="spam",
        defaults={"name": "Spam", "desc": "The BOF request is spam", "order": 5},
    )


def reverse(apps, schema_editor):
    State = apps.get_model("doc", "State")
    Document = apps.get_model("doc", "Document")
    assert not Document.objects.filter(
        states__type="bofreq", states__slug="spam"
    ).exists()
    State.objects.filter(type_id="bofreq", slug="spam").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("doc", "0022_remove_dochistory_internal_comments_and_more"),
    ]

    operations = [migrations.RunPython(forward, reverse)]
