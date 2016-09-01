# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


def forward(apps, schema_editor):

    Recipient=apps.get_model('mailtrigger','Recipient')

    rc = Recipient.objects.create

    rc(slug='submission_manualpost_handling',
       desc='IETF manual post handling',
       template='<ietf-manualpost@ietf.org>')


def reverse(apps, schema_editor):
    Recipient=apps.get_model('mailtrigger','Recipient')

    Recipient.objects.filter(slug='submission_manualpost_handling').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('mailtrigger', '0005_interim_trigger'),
    ]

    operations = [
        migrations.RunPython(forward, reverse)
    ]
