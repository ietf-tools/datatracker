# Copyright The IETF Trust 2025, All Rights Reserved

from django.db import migrations


def forward(apps, schema_editor):
    Mailtrigger = apps.get_model("mailtrigger", "MailTrigger")
    Recipient = apps.get_model("mailtrigger", "Recipient")
    recipients_to = Recipient.objects.get(pk="liaison_to_contacts")
    recipients_cc = list(
        Recipient.objects.filter(
            slug__in=(
                "liaison_cc",
                "liaison_coordinators",
                "liaison_response_contacts",
                "liaison_technical_contacts",
            )
        )
    )
    recipient_from = Recipient.objects.get(pk="liaison_from_contact")

    liaison_posted_outgoing = Mailtrigger.objects.create(
        slug="liaison_statement_posted_outgoing",
        desc="Recipients for a message when a new outgoing liaison statement is posted",
    )
    liaison_posted_outgoing.to.add(recipients_to)
    liaison_posted_outgoing.cc.add(*recipients_cc)
    liaison_posted_outgoing.cc.add(recipient_from)

    liaison_posted_incoming = Mailtrigger.objects.create(
        slug="liaison_statement_posted_incoming",
        desc="Recipients for a message when a new incoming liaison statement is posted",
    )
    liaison_posted_incoming.to.add(recipients_to)
    liaison_posted_incoming.cc.add(*recipients_cc)

    Mailtrigger.objects.filter(slug=("liaison_statement_posted")).delete()


def reverse(apps, schema_editor):
    Mailtrigger = apps.get_model("mailtrigger", "MailTrigger")
    Recipient = apps.get_model("mailtrigger", "Recipient")

    Mailtrigger.objects.filter(
        slug__in=(
            "liaison_statement_posted_outgoing",
            "liaison_statement_posted_incoming",
        )
    ).delete()

    liaison_statement_posted = Mailtrigger.objects.create(
        slug="liaison_statement_posted",
        desc="Recipients for a message when a new liaison statement is posted",
    )

    liaison_to_contacts = Recipient.objects.get(slug="liaison_to_contacts")
    recipients_ccs = Recipient.objects.filter(
        slug__in=(
            "liaison_cc",
            "liaison_coordinators",
            "liaison_response_contacts",
            "liaison_technical_contacts",
        )
    )
    liaison_statement_posted.to.add(liaison_to_contacts)
    liaison_statement_posted.cc.add(*recipients_ccs)


class Migration(migrations.Migration):
    dependencies = [("mailtrigger", "0007_historicalrecipient_historicalmailtrigger")]

    operations = [migrations.RunPython(forward, reverse)]
