# Copyright The IETF Trust 2018-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from django.db import migrations


def forward(apps, schema_editor):
    MailTrigger = apps.get_model('mailtrigger', 'MailTrigger')
    Recipient = apps.get_model('mailtrigger', 'Recipient')

    review_reminder_overdue_assignment = MailTrigger.objects.create(
        slug="review_reminder_overdue_assignment",
        desc="Recipients for overdue review assignment reminders",
    )
    review_reminder_overdue_assignment.to.add(
        Recipient.objects.get(slug='group_secretaries')
    )


def reverse(apps, schema_editor):
    MailTrigger = apps.get_model('mailtrigger', 'MailTrigger')
    MailTrigger.objects.filter(slug='review_reminder_overdue_assignment').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('mailtrigger', '0009_custom_review_complete_mailtriggers'),
    ]

    operations = [
        migrations.RunPython(forward, reverse)
    ]
