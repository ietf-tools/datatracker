# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

def forward(apps, schema_editor):
    MailTrigger=apps.get_model('mailtrigger','MailTrigger')
    Recipient=apps.get_model('mailtrigger','Recipient')

    annc = MailTrigger.objects.create(
        slug='review_assignments_summarized',
        desc='Recipients when an review team secretary send a summary of open review assignments',
    )
    annc.to = Recipient.objects.filter(slug__in=['group_mail_list',])
    annc.cc = []


def reverse(apps, schema_editor):
    MailTrigger=apps.get_model('mailtrigger','MailTrigger')
    MailTrigger.objects.filter(slug__in=['review_assignments_summarized']).delete()

class Migration(migrations.Migration):

    dependencies = [
        ('mailtrigger', '0007_add_interim_announce'),
    ]

    operations = [
        migrations.RunPython(forward, reverse)
    ]
