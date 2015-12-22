# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

def forward(apps, schema_editor):

    Recipient=apps.get_model('mailtrigger','Recipient')
    MailTrigger=apps.get_model('mailtrigger','MailTrigger')

    m = MailTrigger.objects.create(
            slug='person_merge_requested',
            desc="Recipients for a message requesting that duplicated Person records be merged ")
    m.to = Recipient.objects.filter(slug__in=['ietf_secretariat', ])

def reverse(apps, schema_editor):
    MailTrigger=apps.get_model('mailtrigger','MailTrigger')
    MailTrigger.objects.filter(slug='person_merge_requested').delete()

class Migration(migrations.Migration):

    dependencies = [
        ('mailtrigger', '0002_auto_20150809_1314'),
    ]

    operations = [
        migrations.RunPython(forward, reverse)
    ]
