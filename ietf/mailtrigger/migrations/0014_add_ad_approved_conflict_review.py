# Copyright The IETF Trust 2020, All Rights Reserved

from django.db import migrations


def forward(apps, schema_editor):
    MailTrigger = apps.get_model('mailtrigger', 'MailTrigger')
    Recipient = apps.get_model('mailtrigger', 'Recipient')

    ad_approved_conflict_review = MailTrigger.objects.create(
        slug='ad_approved_conflict_review',
        desc='Recipients when AD approves a conflict review pending announcement',
    )
    ad_approved_conflict_review.to.add(
        Recipient.objects.get(pk='iesg_secretary')
    )


def reverse(apps, schema_editor):
    MailTrigger = apps.get_model('mailtrigger', 'MailTrigger')
    MailTrigger.objects.filter(slug='ad_approved_conflict_review').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('mailtrigger', '0013_add_irsg_ballot_saved'),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
