# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime

def forward(apps,schema_editor):
    Room = apps.get_model('meeting','Room')
    FloorPlan = apps.get_model('meeting','FloorPlan')
    for room in Room.objects.all():
        room.time = room.meeting.date+datetime.timedelta(days=5)
        room.save()
    for plan in FloorPlan.objects.all():
        plan.time = plan.meeting.date+datetime.timedelta(days=5)
        plan.save()

class Migration(migrations.Migration):

    dependencies = [
        ('meeting', '0028_add_audio_stream_data'),
    ]

    operations = [
        migrations.AddField(
            model_name='floorplan',
            name='time',
            field=models.DateTimeField(default=datetime.datetime.now),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='room',
            name='time',
            field=models.DateTimeField(default=datetime.datetime.now),
            preserve_default=True,
        ),
        migrations.RunPython(forward,None)
    ]
