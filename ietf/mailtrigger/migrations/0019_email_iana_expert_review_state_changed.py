# Copyright The IETF Trust 2020 All Rights Reserved

from django.db import migrations

def forward(apps,schema_editor):
    MailTrigger = apps.get_model('mailtrigger', 'MailTrigger')
    Recipient = apps.get_model('mailtrigger', 'Recipient')

    iana_er_state_changed = MailTrigger.objects.create(
        slug='iana_expert_review_state_changed',
        desc='Recipients when the IANA expert review for a document changes',
    )

    iana_er_state_changed.to.set(
        Recipient.objects.filter(slug__in=[
            'doc_ad', 'doc_authors', 'doc_group_chairs', 'doc_group_responsible_directors', 'doc_notify', 'doc_shepherd'
        ])
    )

def reverse(apps,schema_editor):
    MailTrigger = apps.get_model('mailtrigger', 'MailTrigger')

    MailTrigger.objects.filter(slug='iana_expert_review_state_changed').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('mailtrigger', '0018_interim_approve_announce'),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
