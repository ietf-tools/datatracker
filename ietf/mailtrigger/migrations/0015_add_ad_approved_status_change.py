# Copyright The IETF Trust 2020, All Rights Reserved

from django.db import migrations


def forward(apps, schema_editor):
    MailTrigger = apps.get_model('mailtrigger', 'MailTrigger')
    Recipient = apps.get_model('mailtrigger', 'Recipient')

    ad_approved_conflict_review = MailTrigger.objects.create(
        slug='ad_approved_status_change',
        desc='Recipients when AD approves a status change pending announcement',
    )
    ad_approved_conflict_review.to.add(
        Recipient.objects.get(pk='iesg_secretary')
    )


def reverse(apps, schema_editor):
    MailTrigger = apps.get_model('mailtrigger', 'MailTrigger')
    MailTrigger.objects.filter(slug='ad_approved_status_change').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('mailtrigger', '0014_add_ad_approved_conflict_review'),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
