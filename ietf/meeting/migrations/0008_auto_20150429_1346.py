# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations

def extract_room_session_type_values(apps, schema_editor):

    Room  = apps.get_model('meeting', 'Room')

    for r in Room.objects.all():
        for ts in r.timeslot_set.all():
            if ts.scheduledsession_set.filter(schedule=models.F('schedule__meeting__agenda')):
                r.session_types.add(ts.type)

class Migration(migrations.Migration):

    dependencies = [
        ('name', '0004_auto_20150318_1140'),
        ('meeting', '0007_auto_20150429_1224'),
    ]

    operations = [
        migrations.AddField(
            model_name='room',
            name='session_types',
            field=models.ManyToManyField(to='name.TimeSlotTypeName', blank=True),
            preserve_default=True,
        ),
        migrations.RunPython(extract_room_session_type_values),
    ]
