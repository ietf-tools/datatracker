# Copyright The IETF Trust 2017, All Rights Reserved
# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from django.db import migrations


new_room_resources = [
    ('u-shape', True, 0, 'boardroom-layout.png', 'Experimental Room Setup (U-Shape and classroom)',
        'Experimental Room Setup (U-Shape and classroom, subject to availability)', None),
    ('flipcharts', True, 0, 'flipchart.png', 'Flipcharts',
        'Flipchars', 'Flipcharts: please specify number in Special Requests field'),
]

unused_room_resources = [
    'boardroom',
    'project',
    'proj2',
    'meetecho',
]

def forwards(apps,schema_editor):
    RoomResourceName = apps.get_model('name','RoomResourceName')
    ResourceAssociation = apps.get_model('meeting','ResourceAssociation')

    for item in new_room_resources:
        slug, used, order, icon, name, desc, help = item
        if not help:
            help = desc
        name, __ = RoomResourceName.objects.get_or_create(slug=slug, name=name, desc=desc, used=used, order=order)
        ResourceAssociation.objects.get_or_create(name=name, icon=icon, desc=help)

    for slug in unused_room_resources:
        res = RoomResourceName.objects.get(slug=slug)
        res.used = False
        res.save()

def backwards(apps,schema_editor):
    RoomResourceName = apps.get_model('name','RoomResourceName')
    ResourceAssociation = apps.get_model('meeting','ResourceAssociation')

    for item in new_room_resources:
        slug, used, order, icon, name, desc, help = item
        if not help:
            help = desc
        RoomResourceName.objects.filter(slug=slug, name=name, desc=desc, used=used, order=order).delete()
        ResourceAssociation.objects.filter(name=name, icon=icon, desc=help).delete()

    for slug in unused_room_resources:
        res = RoomResourceName.objects.get(slug=slug)
        res.used = True
        res.save()


class Migration(migrations.Migration):

    dependencies = [
        ('meeting', '0049_auto_20170412_0528'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
