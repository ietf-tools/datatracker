# Copyright The IETF Trust 2023, All Rights Reserved

from django.db import migrations

def forward(apps, schema_editor):
    MailTrigger = apps.get_model("mailtrigger", "MailTrigger")
    Recipient = apps.get_model("mailtrigger", "Recipient")
    mt = MailTrigger.objects.get(pk="ballot_approved_charter")
    mt.to.remove(mt.to.first())
    mt.to.add(Recipient.objects.get(slug="group_stream_announce"))

def reverse(apps, schema_editor):
    MailTrigger = apps.get_model("mailtrigger", "MailTrigger")
    Recipient = apps.get_model("mailtrigger", "Recipient")
    mt = MailTrigger.objects.get(pk="ballot_approved_charter")
    mt.to.remove(mt.to.first())
    mt.to.add(Recipient.objects.get(slug="ietf_announce"))

class Migration(migrations.Migration):
    dependencies = [
        ("mailtrigger", "0002_slidesubmitter"),
    ]

    operations = [
        migrations.RunPython(forward, reverse)
    ]
