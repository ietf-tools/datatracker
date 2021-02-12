# Copyright The IETF Trust 2020 All Rights Reserved

from django.db import migrations


def forward(apps,schema_editor):
    MailTrigger = apps.get_model('mailtrigger', 'MailTrigger')
    Recipient = apps.get_model('mailtrigger', 'Recipient')

    (doc_action_holders, _) = Recipient.objects.get_or_create(
        slug='doc_action_holders',
        desc='Action holders for a document',
        template='{% for action_holder in doc.action_holders.all %}{% if doc.shepherd and action_holder == doc.shepherd.person %}{{ doc.shepherd }}{% else %}{{ action_holder.email }}{% endif %}{% if not forloop.last %},{%endif %}{% endfor %}',
    )
    (doc_remind_action_holders, _) = MailTrigger.objects.get_or_create(
        slug='doc_remind_action_holders',
        desc='Recipients when sending a reminder email to action holders for a document',
    )
    doc_remind_action_holders.to.set([doc_action_holders])


def reverse(apps,schema_editor):
    MailTrigger = apps.get_model('mailtrigger', 'MailTrigger')
    Recipient = apps.get_model('mailtrigger', 'Recipient')

    MailTrigger.objects.filter(slug='doc_remind_action_holders').delete()
    Recipient.objects.filter(slug='doc_action_holders').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('mailtrigger', '0020_add_ad_approval_request_mailtriggers'),
    ]

    operations = [
        migrations.RunPython(forward, reverse)
    ]
