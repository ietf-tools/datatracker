# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

def forward(apps, schema_editor):
    MailTrigger=apps.get_model('mailtrigger','MailTrigger')
    Recipient=apps.get_model('mailtrigger','Recipient')

    Recipient.objects.create(
        slug='group_stream_announce',
        desc="The group's stream's announce list",
        template="{% if group.type_id == 'wg' %}IETF-Announce <ietf-announce@ietf.org>{% elif group.type_id == 'rg' %}IRTF-Announce <irtf-announce@irtf.org>{% endif %}"
    )

    annc = MailTrigger.objects.create(
        slug='interim_announced',
        desc='Recipients when an interim meeting is announced',
    )
    annc.to = Recipient.objects.filter(slug__in=['ietf_announce','stream_announce'])
    annc.cc = Recipient.objects.filter(slug__in=['group_mail_list',])

    annc = MailTrigger.objects.create(
        slug='interim_cancelled',
        desc='Recipients when an interim meeting is cancelled',
    )
    annc.to = Recipient.objects.filter(slug__in=['ietf_announce','stream_aanounce'])
    annc.cc = Recipient.objects.filter(slug__in=['group_chairs','group_mail_list','logged_in_person'])


def reverse(apps, schema_editor):
    MailTrigger=apps.get_model('mailtrigger','MailTrigger')
    Recipient=apps.get_model('mailtrigger','Recipient')

    MailTrigger.objects.filter(slug__in=['interim_announced','interim_cancelled']).delete()
    Recipient.objects.filter(slug='group_stream_announce').delete()
  

class Migration(migrations.Migration):

    dependencies = [
        ('mailtrigger', '0006_auto_20160707_1933'),
    ]

    operations = [
       migrations.RunPython(forward,reverse),
    ]
