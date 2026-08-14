# Copyright The IETF Trust 2023, All Rights Reserved

from django.db import migrations


def forward(apps, schema_editor):
    MailTrigger = apps.get_model("mailtrigger", "MailTrigger")
    Recipient = apps.get_model("mailtrigger", "Recipient")
    recipients = list(
        Recipient.objects.filter(
            slug__in=(
                "doc_group_mail_list",
                "doc_authors",
                "doc_group_chairs",
                "doc_shepherd",
            )
        )
    )
    call_for_adoption = MailTrigger.objects.create(
        slug="doc_wg_call_for_adoption_issued",
        desc="Recipients when a working group call for adoption is issued",
    )
    call_for_adoption.to.add(*recipients)
    wg_last_call = MailTrigger.objects.create(
        slug="doc_wg_last_call_issued",
        desc="Recipients when a working group last call is issued",
    )
    wg_last_call.to.add(*recipients)


def reverse(apps, schema_editor):
    MailTrigger = apps.get_model("mailtrigger", "MailTrigger")
    MailTrigger.objects.filter(
        slug_in=("doc_wg_call_for_adoption_issued", "doc_wg_last_call_issued")
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("mailtrigger", "0005_rfc_recipients"),
    ]

    operations = [migrations.RunPython(forward, reverse)]
