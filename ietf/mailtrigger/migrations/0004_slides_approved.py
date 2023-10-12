# Copyright The IETF Trust 2023, All Rights Reserved

from django.db import migrations

def forward(apps, schema_editor):
    MailTrigger = apps.get_model("mailtrigger", "MailTrigger")
    Recipient = apps.get_model("mailtrigger", "Recipient")
    mt = MailTrigger.objects.create(
        slug="slides_approved",
        desc="Recipients when slides are approved for a given session",
    )
    mt.to.add(Recipient.objects.get(slug="slides_proposer"))
    mt.cc.add(Recipient.objects.get(slug="group_chairs"))

def reverse(apps, schema_editor):
    MailTrigger = apps.get_model("mailtrigger", "MailTrigger")
    mt = MailTrigger.objects.get(pk="slides_approved")
    mt.delete()

class Migration(migrations.Migration):
    dependencies = [
        ("mailtrigger", "0003_ballot_approved_charter"),
    ]

    operations = [
        migrations.RunPython(forward, reverse)
    ]
