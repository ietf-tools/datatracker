# Copyright The IETF Trust 2023, All Rights Reserved

from django.db import migrations

def forward(apps, schema_editor):
    MailTrigger = apps.get_model("mailtrigger", "MailTrigger")
    Recipient = apps.get_model("mailtrigger", "Recipient")
    mt = MailTrigger.objects.create(pk="iab_doc_state_changed", desc="Recipients when an IAB document's state is changed")
    mt.to.set(MailTrigger.objects.get(pk="doc_state_edited").to.all())
    mt.cc.add(Recipient.objects.get(slug="iab"))

def reverse(apps, schema_editor):
    MailTrigger = apps.get_model("mailtrigger", "MailTrigger")
    mt = MailTrigger.objects.get(pk="iab_doc_state_changed")
    mt.delete()

class Migration(migrations.Migration):
    dependencies = [
        ("mailtrigger", "0004_slides_approved"),
    ]

    operations = [
        migrations.RunPython(forward, reverse)
    ]
