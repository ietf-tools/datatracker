# Copyright The IETF Trust 2023, All Rights Reserved

from django.db import migrations

def forward(apps, schema_editor):
    MailTrigger = apps.get_model("mailtrigger", "MailTrigger")
    Recipient = apps.get_model("mailtrigger", "Recipient")
    r = Recipient.objects.create(
        slug="slides_proposer",
        desc="Person who proposed slides",
        template="{{ proposer.email }}"
    )
    mt = MailTrigger.objects.get(slug="slides_proposed")
    mt.cc.add(r)

def reverse(apps, schema_editor):
    MailTrigger = apps.get_model("mailtrigger", "MailTrigger")
    Recipient = apps.get_model("mailtrigger", "Recipient")
    mt = MailTrigger.objects.get(slug="slides_proposed")
    r = Recipient.objects.get(slug="slides_proposer")
    mt.cc.remove(r)
    r.delete()

class Migration(migrations.Migration):
    dependencies = [
        ("mailtrigger", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(forward, reverse)
    ]
