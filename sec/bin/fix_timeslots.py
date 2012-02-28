#!/usr/bin/python

from django.core.management import setup_environ
from django.contrib.auth.models import User
from sec import settings

setup_environ(settings)

from ietf.group.models import *
from ietf.person.models import *
from ietf.name.models import *
from ietf.meeting.models import *


'''
This script creates empty timeslots that were missed in the migration

to run first do
export DJANGO_SETTINGS_MODULE=sec.settings
'''
timeslots = []
time_seen = set()
count = 0

slots = TimeSlot.objects.filter(meeting=83,type='session')
meeting = Meeting.objects.get(number=83)
rooms = Room.objects.filter(meeting=meeting)

for t in slots:
    if not t.time in time_seen:
        time_seen.add(t.time)
        timeslots.append(t)

for t in time_seen:
    for room in rooms:
        if not TimeSlot.objects.filter(meeting=meeting,location=room,time=t):
            print "create timeslot meeting: %s, location: %s, time: %s" % (meeting, room,t)
            count += 1
            '''
            TimeSlot.objects.create(type_id='session',
                                meeting=meeting,
                                name=t.name,
                                time=new_time,
                                location=room,
                                duration=t.duration)
            '''
print "Total created: %s" % count