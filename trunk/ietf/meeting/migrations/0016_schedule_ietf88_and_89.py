# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

def forward(apps, schema_editor):
    Session = apps.get_model('meeting','Session')
    assert(Session.objects.filter(meeting__number__in=['88','89'],group__type__in=['ag','iab','rg','wg'],status_id='sched').count() == 0)
    Session.objects.filter(meeting__number__in=['88','89'],group__type__in=['ag','iab','rg','wg'],status_id='schedw').update(status_id='sched')

def reverse(apps, schema_editor):
    Session = apps.get_model('meeting','Session')
    Session.objects.filter(meeting__number__in=['88','89'],group__type__in=['ag','iab','rg','wg'],status_id='sched').update(status_id='schedw')

class Migration(migrations.Migration):

    dependencies = [
        ('meeting', '0015_auto_20151102_1845'),
    ]

    operations = [
        migrations.RunPython(forward,reverse),
    ]
