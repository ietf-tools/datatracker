# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations

def extract_session_type_values(apps, schema_editor):

    Session  = apps.get_model('meeting', 'Session')

    for s in Session.objects.all():
        t = s.scheduledsession_set.filter(schedule=models.F('schedule__meeting__agenda')).first()
        if t and t.timeslot.type.slug != 'session':
            s.type = t.timeslot.type
            s.save()

class Migration(migrations.Migration):

    dependencies = [
        ('name', '0004_auto_20150318_1140'),
        ('meeting', '0006_auto_20150318_1116'),
    ]

    operations = [
        migrations.AddField(
            model_name='session',
            name='type',
            field=models.ForeignKey(default='session', to='name.TimeSlotTypeName'),
            preserve_default=False,
        ),
        migrations.RunPython(extract_session_type_values),
    ]
