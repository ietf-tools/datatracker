# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import datetime
import os
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

def migrate_interim_meetings(apps, schema_editor):
    """For all existing interim meetings create an official schedule and timeslot assignments"""
    Meeting = apps.get_model("meeting", "Meeting")
    Schedule = apps.get_model("meeting", "Schedule")
    TimeSlot = apps.get_model("meeting", "TimeSlot")
    SchedTimeSessAssignment = apps.get_model("meeting", "SchedTimeSessAssignment")
    Person = apps.get_model("person", "Person")
    system = Person.objects.get(name="(system)")

    meetings = Meeting.objects.filter(type='interim')
    for meeting in meetings:
        if not meeting.agenda:
            meeting.agenda = Schedule.objects.create(
                meeting=meeting,
                owner=system,
                name='Official')
            meeting.save()
        session = meeting.session_set.first()   # all legacy interim meetings have one session
        time = datetime.datetime.combine(meeting.date, datetime.time(0))
        slot = TimeSlot.objects.create(
            meeting=meeting,
            type_id="session",
            duration=session.requested_duration,
            time=time)
        SchedTimeSessAssignment.objects.create(
            timeslot=slot,
            session=session,
            schedule=meeting.agenda)

def migrate_interim_materials_files(apps, schema_editor):
    """Copy interim materials files to new location"""
    Meeting = apps.get_model("meeting", "Meeting")
    
    for meeting in Meeting.objects.filter(type='interim'):
        copy_materials(meeting)
        
class Migration(migrations.Migration):

    dependencies = [
        ('meeting', '0023_session_remote_instructions'),
    ]

    operations = [
        migrations.RunPython(migrate_interim_meetings),
        migrations.RunPython(migrate_interim_materials_files),
    ]
