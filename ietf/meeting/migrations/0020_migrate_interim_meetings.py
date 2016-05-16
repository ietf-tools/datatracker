# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import datetime

from django.db import migrations


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


class Migration(migrations.Migration):

    dependencies = [
        ('meeting', '0019_session_remote_instructions'),
    ]

    operations = [
        migrations.RunPython(migrate_interim_meetings),
    ]
