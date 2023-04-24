# Copyright The IETF Trust 2019-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from django.db import migrations

def forward(apps, schema_editor):
    MailTrigger = apps.get_model('mailtrigger', 'MailTrigger')
    Recipient = apps.get_model('mailtrigger', 'Recipient')

    Recipient.objects.create(
        slug = 'new_wg_doc_list',
        desc = "The email list for announcing new WG -00 submissions",
        template = '<new-wg-docs@ietf.org>'
    )
    changed = MailTrigger.objects.create(
        slug = 'sub_new_wg_00',
        desc = 'Recipients when a new IETF WG -00 draft is announced',
    )
    changed.to.set(Recipient.objects.filter(slug__in=['new_wg_doc_list']))


def reverse(apps, schema_editor):
    MailTrigger = apps.get_model('mailtrigger','MailTrigger')
    Recipient = apps.get_model('mailtrigger', 'Recipient')

    MailTrigger.objects.filter(slug='sub_new_wg_00').delete()
    Recipient.objects.filter(slug='new_wg_doc_list').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('mailtrigger', '0005_slides_proposed'),
    ]

    operations = [
        migrations.RunPython(forward,reverse)
    ]
