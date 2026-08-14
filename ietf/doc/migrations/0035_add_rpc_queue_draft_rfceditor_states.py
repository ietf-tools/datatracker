# Copyright The IETF Trust 2026, All Rights Reserved

from django.db import migrations


def forward(apps, schema_editor):
    State = apps.get_model("doc", "State")
    for slug, name in [("in_progress", "In Progress"), ("blocked", "Blocked")]:
        State.objects.get_or_create(
            type_id="draft-rfceditor",
            slug=slug,
            defaults={"name": name, "used": True, "desc": "", "order": 0},
        )


def reverse(apps, schema_editor):
    State = apps.get_model("doc", "State")
    Document = apps.get_model("doc", "Document")
    for slug in ("in_progress", "blocked"):
        assert not Document.objects.filter(
            states__type="draft-rfceditor", states__slug=slug
        ).exists()
        State.objects.filter(type_id="draft-rfceditor", slug=slug).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("doc", "0034_alter_dochistory_keywords_alter_document_keywords"),
    ]

    operations = [migrations.RunPython(forward, reverse)]
