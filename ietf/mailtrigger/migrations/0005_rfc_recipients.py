# Copyright The IETF Trust 2023, All Rights Reserved

from django.db import migrations


def forward(apps, schema_editor):
    Recipient = apps.get_model("mailtrigger", "Recipient")
    Recipient.objects.filter(slug="doc_authors").update(
        template='{% if doc.type_id == "draft" or doc.type_id == "rfc" %}<{{doc.name}}@ietf.org>{% endif %}'
    )


def reverse(apps, schema_editor):
    Recipient = apps.get_model("mailtrigger", "Recipient")
    Recipient.objects.filter(slug="doc_authors").update(
        template='{% if doc.type_id == "draft" %}<{{doc.name}}@ietf.org>{% endif %}'
    )


class Migration(migrations.Migration):
    dependencies = [
        ("mailtrigger", "0004_slides_approved"),
    ]

    operations = [migrations.RunPython(forward, reverse)]
