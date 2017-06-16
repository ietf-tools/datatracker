# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import datetime
import os
import re
import subprocess

from django.conf import settings
from django.db import migrations


def get_old_path(meeting):
    """Return old path to interim materials file"""
    path = os.path.join(settings.AGENDA_PATH,
                        'interim',
                        meeting.date.strftime('%Y'),
                        meeting.date.strftime('%m'),
                        meeting.date.strftime('%d'),
                        meeting.session_set.first().group.acronym) + '/'
                        #doc.type_id,
                        #doc.external_url)
    return path

def get_new_path(meeting):
    """Returns new path to document"""
    return os.path.join(settings.AGENDA_PATH,meeting.number) + '/'

def copy_materials(meeting):
    """Copy all materials files to new location on disk"""
    source = get_old_path(meeting)
    target = get_new_path(meeting)
    if not os.path.isdir(target):
        os.makedirs(target)
    subprocess.call(['rsync','-a',source,target])

def migrate_interim_meetings_forward(apps, schema_editor):
    """For all existing interim meetings create an official schedule and timeslot assignments"""
    Meeting = apps.get_model("meeting", "Meeting")
    Schedule = apps.get_model("meeting", "Schedule")
    TimeSlot = apps.get_model("meeting", "TimeSlot")
    SchedTimeSessAssignment = apps.get_model("meeting", "SchedTimeSessAssignment")
    Person = apps.get_model("person", "Person")
    system = Person.objects.get(name="(system)")

    meetings = Meeting.objects.filter(type='interim')
    for meeting in meetings:
        single_digit_serial = re.search('^(.+)-([0-9])$', meeting.number)
        dirty = False
        if single_digit_serial:
            name   = single_digit_serial.group(1)
            serial = single_digit_serial.group(2)
            meeting.number = "%s-%02d" % (name, int(serial))
            dirty = True
        if not meeting.agenda:
            meeting.agenda = Schedule.objects.create(
                meeting=meeting,
                owner=system,
                name='Official')
            dirty = True
        if dirty:
            meeting.save()
            dirty = False
        session = meeting.session_set.first()   # all legacy interim meetings have one session
        time = datetime.datetime.combine(meeting.date, datetime.time(0))
        if TimeSlot.objects.filter(meeting=meeting, type_id="session", time=time).exists():
            slot = TimeSlot.objects.get(meeting=meeting, type_id="session", time=time).exists()
        else:
            slot = TimeSlot.objects.create(
                meeting=meeting,
                type_id="session",
                duration=session.requested_duration,
                time=time)
        SchedTimeSessAssignment.objects.get_or_create(
            timeslot=slot,
            session=session,
            schedule=meeting.agenda)

def migrate_interim_meetings_backward(apps, schema_editor):
    Meeting = apps.get_model("meeting", "Meeting")
    meetings = Meeting.objects.filter(type='interim')
    for meeting in meetings:
        zero_digit_serial = re.search('^(.+)-0([0-9])$', meeting.number)
        if zero_digit_serial:
            name   = zero_digit_serial.group(1)
            serial = zero_digit_serial.group(2)
            meeting.number = "%s-%s" % (name, serial)
            meeting.save()

def migrate_interim_materials_files_forward(apps, schema_editor):
    """Copy interim materials files to new location"""
    Meeting = apps.get_model("meeting", "Meeting")
    
    for meeting in Meeting.objects.filter(type='interim'):
        copy_materials(meeting)
        
def migrate_interim_materials_files_backward(apps, schema_editor):
    """Copy interim materials files to new location"""
    pass
        
class Migration(migrations.Migration):

    dependencies = [
        ('meeting', '0023_session_remote_instructions'),
    ]

    operations = [
        migrations.RunPython(migrate_interim_meetings_forward, migrate_interim_meetings_backward),
        migrations.RunPython(migrate_interim_materials_files_forward, migrate_interim_materials_files_backward),
    ]
