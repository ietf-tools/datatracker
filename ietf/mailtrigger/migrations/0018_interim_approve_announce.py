# Copyright The IETF Trust 2020 All Rights Reserved

from django.db import migrations

def forward(apps,schema_editor):
    MailTrigger = apps.get_model('mailtrigger', 'MailTrigger')
    Recipient = apps.get_model('mailtrigger', 'Recipient')

    interim_approved = MailTrigger.objects.get(slug='interim_approved')
    interim_approved.desc = 'Recipients when an interim meeting is approved'
    interim_approved.save()
    interim_approved.to.set(Recipient.objects.filter(slug__in=('group_chairs','logged_in_person')))

    interim_announce_requested = MailTrigger.objects.create(
        slug='interim_announce_requested',
        desc='Recipients when an interim announcement is requested',
    )
    interim_announce_requested.to.set(Recipient.objects.filter(slug='iesg_secretary'))


def reverse(apps,schema_editor):
    MailTrigger = apps.get_model('mailtrigger', 'MailTrigger')
    Recipient = apps.get_model('mailtrigger', 'Recipient')

    MailTrigger.objects.filter(slug='interim_announce_requested').delete()

    interim_approved = MailTrigger.objects.get(slug='interim_approved')
    interim_approved.desc = 'Recipients when an interim meeting is approved and an announcement needs to be sent'
    interim_approved.save()
    interim_approved.to.set(Recipient.objects.filter(slug='iesg_secretary'))


class Migration(migrations.Migration):

    dependencies = [
        ('mailtrigger', '0017_lc_to_yang_doctors'),
    ]

    operations = [
        migrations.RunPython(forward,reverse)
    ]
