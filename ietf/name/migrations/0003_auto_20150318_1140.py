# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations




def make_new_slot_types(apps, schema_editor):

        TimeSlotTypeName = apps.get_model("name","TimeSlotTypeName")
        TimeSlotTypeName.objects.create(slug='lead',name='Leadership',desc='Leadership Meetings',used=True)
        TimeSlotTypeName.objects.create(slug='offagenda',name='Off Agenda',desc='Other Meetings Not Published on Agenda',used=True)

class Migration(migrations.Migration):

    dependencies = [
        ('name', '0002_auto_20150208_1008'),
    ]

    operations = [
        migrations.RunPython(make_new_slot_types)
    ]
