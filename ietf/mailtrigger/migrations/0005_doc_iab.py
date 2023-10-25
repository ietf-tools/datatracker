# Copyright The IETF Trust 2023, All Rights Reserved

from django.db import migrations

def forward(apps, schema_editor):
    MailTrigger = apps.get_model("mailtrigger", "MailTrigger")
    Recipient = apps.get_model("mailtrigger", "Recipient")
    mt = MailTrigger.objects.get(pk="doc_state_edited")
    r = Recipient.objects.create(slug="doc_iab", desc="The IAB if the document is in the iab stream", template="{% if doc.stream_id == 'iab' %}iab@iab.org{% endif %}")
    mt.cc.add(r)

def reverse(apps, schema_editor):
    MailTrigger = apps.get_model("mailtrigger", "MailTrigger")
    Recipient = apps.get_model("mailtrigger", "Recipient")
    mt = MailTrigger.objects.get(pk="doc_state_edited")
    r = Recipient.objects.get(slug="doc_iab")
    mt.cc.remove(r)
    r.delete()

class Migration(migrations.Migration):
    dependencies = [
        ("mailtrigger", "0004_slides_approved"),
    ]

    operations = [
        migrations.RunPython(forward, reverse)
    ]
