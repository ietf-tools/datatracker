# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

def forward(apps, schema_editor):
    Meeting = apps.get_model('meeting', 'Meeting')
    TimeSlot = apps.get_model('meeting', 'TimeSlot')
    Session = apps.get_model('meeting', 'Session')
    import sys
    sys.stderr.write("\n")
    sys.stderr.write("Setting duration fields in Meeting objects...\n")
    for m in Meeting.objects.all():
        if m.xidsubmit_cutoff_time_utc != m.idsubmit_cutoff_time_utc:
            m.xidsubmit_cutoff_time_utc = m.idsubmit_cutoff_time_utc
            m.xidsubmit_cutoff_warning_days = m.idsubmit_cutoff_warning_days
            m.save()
    sys.stderr.write("Setting duration fields in TimeSlot objects...\n")
    for t in TimeSlot.objects.all():
        if t.xduration != t.duration:
            t.xduration = t.duration
            t.save()
    sys.stderr.write("Setting duration fields in Session objects...\n")
    for s in Session.objects.all():
        if s.xrequested_duration != s.requested_duration:
            s.xrequested_duration = s.requested_duration
            s.save()

def backward(apps, schema_editor):
    Meeting = apps.get_model('meeting', 'Meeting')
    TimeSlot = apps.get_model('meeting', 'TimeSlot')
    Session = apps.get_model('meeting', 'Session')
    import sys
    sys.stderr.write("\n")
    sys.stderr.write("Setting timedelta fields in Meeting objects...\n")
    for m in Meeting.objects.all():
        if m.idsubmit_cutoff_time_utc != m.xidsubmit_cutoff_time_utc:
            m.idsubmit_cutoff_time_utc = m.xidsubmit_cutoff_time_utc
            m.idsubmit_cutoff_warning_days = m.xidsubmit_cutoff_warning_days
            m.save()
    sys.stderr.write("Setting timedelta fields in TimeSlot objects...\n")
    for t in TimeSlot.objects.all():
        if t.duration != t.xduration:
            t.duration = t.xduration
            t.save()
    sys.stderr.write("Setting timedelta fields in Session objects...\n")
    for s in Session.objects.all():
        if s.requested_duration != s.xrequested_duration:
            s.requested_duration = s.xrequested_duration
            s.save()

class Migration(migrations.Migration):

    dependencies = [
        ('meeting', '0043_auto_20161219_1345'),
    ]

    operations = [
        migrations.RunPython(forward, backward)
    ]
