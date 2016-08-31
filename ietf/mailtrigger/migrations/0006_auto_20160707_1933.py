# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


def forward(apps, schema_editor):

    Recipient=apps.get_model('mailtrigger','Recipient')

    rc = Recipient.objects.create

    rc(slug='manualpost_message',
       desc='The IETF manual post processing system',
       template='<ietf-manualpost@ietf.org>')


def reverse(apps, schema_editor):
    Recipient=apps.get_model('mailtrigger','Recipient')

    Recipient.objects.filter(slug='manualpost_message').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('mailtrigger', '0005_interim_trigger'),
    ]

    operations = [
        migrations.RunPython(forward, reverse)
    ]
