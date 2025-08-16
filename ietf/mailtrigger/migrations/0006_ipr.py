# Copyright The IETF Trust 2023, All Rights Reserved

from django.db import migrations

def forward(apps, schema_editor):
    MailTrigger = apps.get_model("mailtrigger", "MailTrigger")
    Recipient = apps.get_model("mailtrigger", "Recipient")
    mt = MailTrigger.objects.create(
        slug="doc_stream_state_edited_ipr",
        desc="Recipients when the stream state of a document is set to CFA or WGLC", # ipr notif
    )
    mt.to.add(Recipient.objects.get(slug="group_mail_list"))
    mt.to.add(Recipient.objects.get(slug="doc_authors"))
    mt.to.add(Recipient.objects.get(slug="doc_group_chairs"))
    mt.to.add(Recipient.objects.get(slug="doc_shepherd"))

def reverse(apps, schema_editor):
    MailTrigger = apps.get_model("mailtrigger", "MailTrigger")
    mt = MailTrigger.objects.get(slug="doc_stream_state_edited_ipr")
    mt.delete()

class Migration(migrations.Migration):
    dependencies = [
        ("mailtrigger", "0005_rfc_recipients"),
    ]

    operations = [
        migrations.RunPython(forward, reverse)
    ]
