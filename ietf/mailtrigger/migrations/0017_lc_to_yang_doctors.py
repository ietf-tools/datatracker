# Copyright The IETF Trust 2019-2020, All Rights Reserved

from django.db import migrations

def forward(apps, schema_editor):
    MailTrigger = apps.get_model('mailtrigger', 'MailTrigger')
    Recipient = apps.get_model('mailtrigger', 'Recipient')

    Recipient.objects.create(
        slug = 'yang_doctors_secretaries',
        desc = 'Yang Doctors Secretaries',
        template = ''
    )

    lc_to_yang_doctors = MailTrigger.objects.create(
        slug='last_call_of_doc_with_yang_issued',
        desc='Recipients when IETF LC is issued on a document with yang checks',
    )

    lc_to_yang_doctors.to.set(Recipient.objects.filter(slug='yang_doctors_secretaries'))

def reverse(apps, schema_editor):
    MailTrigger = apps.get_model('mailtrigger', 'MailTrigger')
    Recipient = apps.get_model('mailtrigger', 'Recipient')

    MailTrigger.objects.filter(slug='last_call_of_doc_with_yang_issued').delete()
    Recipient.objects.filter(slug='yang_doctors_secretaries').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('mailtrigger', '0016_add_irsg_ballot_issued'),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
