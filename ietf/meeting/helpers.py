# Copyright The IETF Trust 2007, All Rights Reserved

#import models
import datetime
import os
import re
import tarfile

from tempfile import mkstemp

from django import forms
from django.http import Http404
from django.http import HttpRequest
from django.db.models import Max, Q
from django.conf import settings
from django.core.cache import cache
from django.utils.cache import get_cache_key

import debug
import urllib

from django.shortcuts import get_object_or_404
from ietf.idtracker.models import InternetDraft
from ietf.ietfauth.decorators import has_role
from ietf.utils.history import find_history_active_at
from ietf.doc.models import Document, State

from ietf.proceedings.models import Meeting as OldMeeting, IESGHistory, Switches

# New models
from ietf.meeting.models import Meeting, TimeSlot, Session
from ietf.meeting.models import Schedule, ScheduledSession
from ietf.group.models import Group

class NamedTimeSlot(object):
    """
    this encapsulates a TimeSlot with a Schedule, so that
    specific time slots can be returned as appropriate. It proxies
    most things to TimeSlot.  Agenda_info returns an array of these
    objects rather than actual Time Slots, as the templates do not
    permit multiple parameters to be passed into a relation.
    This may be irrelevant with Django 1.3+, given with argument extension
    to templating language.
    """
    def __init__(self, agenda, timeslot):
        self.agenda   = agenda
        self.timeslot = timeslot

    def scheduledsessions(self):
        self.timeslot.scheduledsessions_set.filter(schedule=self.agenda, session__isnull=False)

    @property
    def time(self):
        return self.timeslot.time

    @property
    def meeting_date(self):
        return self.timeslot.meeting_date

    @property
    def reg_info(self):
        return self.timeslot.reg_info

    @property
    def registration(self):
        return self.timeslot.registration

    @property
    def session_name(self):
        return self.timeslot.session_name

    @property
    def break_info(self):
        return self.timeslot.break_info

    @property
    def time_desc(self):
        return self.timeslot.time_desc

    @property
    def is_plenary(self):
        return self.timeslot.is_plenary

    @property
    def is_plenaryw(self):
        return self.timeslot.is_plenary_type("plenaryw")

    @property
    def is_plenaryt(self):
        return self.timeslot.is_plenary_type("plenaryt")

    @property
    def tzname(self):
        return self.timeslot.tzname

    @property
    def room_name(self):
        if self.timeslot:
            if self.timeslot.location:
                return self.timeslot.location.name
            else:
                return "no room set for plenary %u" % (self.timeslot.pk)
        else:
            return "bogus NamedTimeSlot"

    @property
    def sessions(self):
        return [ ss.session for ss in self.timeslot.scheduledsession_set.filter(schedule=self.agenda, schedule__isnull=False) ]

    @property
    def scheduledsessions_at_same_time(self):
        if not hasattr(self, "sessions_at_same_time_cache"):
            self.sessions_at_same_time_cache = self.timeslot.scheduledsessions_at_same_time(self.agenda)
        return self.sessions_at_same_time_cache

    @property
    def scheduledsessions(self):
        return self.timeslot.scheduledsession_set.filter(schedule=self.agenda)

    @property
    def scheduledsessions_by_area(self):
        things = self.scheduledsessions_at_same_time
        if things is not None:
            return [ {"area":ss.area+ss.acronym_name, "info":ss} for ss in things ]
        else:
            return [ ]

    @property
    def slot_decor(self):
        return self.timeslot.slot_decor

def get_ntimeslots_from_ss(agenda, scheduledsessions):
    ntimeslots = []
    time_seen = set()

    for ss in scheduledsessions:
        t = ss.timeslot
        if not t.time in time_seen:
            time_seen.add(t.time)
            ntimeslots.append(NamedTimeSlot(agenda, t))
    time_seen = None

    return ntimeslots

def get_ntimeslots_from_agenda(agenda):
    # now go through the timeslots, only keeping those that are
    # sessions/plenary/training and don't occur at the same time
    scheduledsessions = agenda.scheduledsession_set.all().order_by("timeslot__time").exclude(timeslot__type = "unavail")
    ntimeslots = get_ntimeslots_from_ss(agenda, scheduledsessions)
    return ntimeslots, scheduledsessions

def find_ads_for_meeting(meeting):
    ads = []
    meeting_time = datetime.datetime.combine(meeting.date, datetime.time(0, 0, 0))

    num = 0
    # get list of ADs which are/were active at the time of the meeting.
    #  (previous [x for x in y] syntax changed to aid debugging)
    for g in Group.objects.filter(type="area").order_by("acronym"):
        history = find_history_active_at(g, meeting_time)
        num = num +1
        if history and history != g:
            #print " history[%u]: %s" % (num, history)
            if history.state_id == "active":
                for x in history.rolehistory_set.filter(name="ad").select_related():
                    #print "xh[%u]: %s" % (num, x)
                    ads.append(IESGHistory().from_role(x, meeting_time))
        else:
            #print " group[%u]: %s" % (num, g)
            if g.state_id == "active":
                for x in g.role_set.filter(name="ad").select_related('group', 'person'):
                    #print "xg[%u]: %s (#%u)" % (num, x, x.pk)
                    ads.append(IESGHistory().from_role(x, meeting_time))
    return ads

def agenda_info(num=None, name=None):
    """
    XXX this should really be a method on Meeting
    """

    try:
        if num != None:
            meeting = OldMeeting.objects.get(number=num)
        else:
            meeting = OldMeeting.objects.all().order_by('-date')[:1].get()
    except OldMeeting.DoesNotExist:
        raise Http404("No meeting information for meeting %s available" % num)

    if name is not None:
        try:
            agenda = meeting.schedule_set.get(name=name)
        except Schedule.DoesNotExist:
            raise Http404("Meeting %s has no agenda named %s" % (num, name))
    else:
        agenda = meeting.agenda

    if agenda is None:
        raise Http404("Meeting %s has no agenda set yet" % (num))

    ntimeslots,scheduledsessions = get_ntimeslots_from_agenda(agenda)

    update = Switches().from_object(meeting)
    venue = meeting.meeting_venue

    ads = find_ads_for_meeting(meeting)

    active_agenda = State.objects.get(type='agenda', slug='active')
    plenary_agendas = Document.objects.filter(session__meeting=meeting, session__scheduledsession__timeslot__type="plenary", type="agenda", ).distinct()
    plenaryw_agenda = plenaryt_agenda = "The Plenary has not been scheduled"
    for agenda in plenary_agendas:
        if active_agenda in agenda.states.all():
            # we use external_url at the moment, should probably regularize
            # the filenames to match the document name instead
            path = os.path.join(settings.AGENDA_PATH, meeting.number, "agenda", agenda.external_url)
            try:
                f = open(path)
                s = f.read()
                f.close()
            except IOError:
                 s = "THE AGENDA HAS NOT BEEN UPLOADED YET"

            if "tech" in agenda.name.lower():
                plenaryt_agenda = s
            else:
                plenaryw_agenda = s

    return ntimeslots, scheduledsessions, update, meeting, venue, ads, plenaryw_agenda, plenaryt_agenda

# get list of all areas, + IRTF + IETF (plenaries).
def get_pseudo_areas():
    return Group.objects.filter(Q(state="active", name="IRTF")|
                                Q(state="active", name="IETF")|
                                Q(state="active", type="area")).order_by('acronym')

# get list of all areas, + IRTF.
def get_areas():
    return Group.objects.filter(Q(state="active",
                                  name="IRTF")|
                                Q(state="active", type="area")).order_by('acronym')

# get list of areas that are referenced.
def get_area_list_from_sessions(scheduledsessions, num):
    return scheduledsessions.filter(timeslot__type = 'Session',
                                    session__group__parent__isnull = False).order_by(
        'session__group__parent__acronym').distinct(
        'session__group__parent__acronym').values_list(
        'session__group__parent__acronym',flat=True)

def build_all_agenda_slices(scheduledsessions, all = False):
    time_slices = []
    date_slices = {}

    ids = []
    for ss in scheduledsessions:
        if(all or ss.session != None):# and len(ss.timeslot.session.agenda_note)>1):
            ymd = ss.timeslot.time.date()

            if ymd not in date_slices and ss.timeslot.location != None:
                date_slices[ymd] = []
                time_slices.append(ymd)

            if ymd in date_slices:
                if [ss.timeslot.time, ss.timeslot.time+ss.timeslot.duration] not in date_slices[ymd]:   # only keep unique entries
                    date_slices[ymd].append([ss.timeslot.time, ss.timeslot.time+ss.timeslot.duration])

    time_slices.sort()
    return time_slices,date_slices


def get_scheduledsessions_from_schedule(schedule):
   ss = schedule.scheduledsession_set.filter(timeslot__location__isnull = False).exclude(session__isnull = True).order_by('timeslot__time','timeslot__name','session__group__group')

   return ss

def get_all_scheduledsessions_from_schedule(schedule):
   ss = schedule.scheduledsession_set.filter(timeslot__location__isnull = False).order_by('timeslot__time','timeslot__name')

   return ss

def get_modified_from_scheduledsessions(scheduledsessions):
    return scheduledsessions.aggregate(Max('timeslot__modified'))['timeslot__modified__max']

def get_wg_name_list(scheduledsessions):
    return scheduledsessions.filter(timeslot__type = 'Session',
                                    session__group__isnull = False,
                                    session__group__parent__isnull = False).order_by(
        'session__group__acronym').distinct(
        'session__group').values_list(
        'session__group__acronym',flat=True)

def get_wg_list(scheduledsessions):
    wg_name_list = get_wg_name_list(scheduledsessions)
    return Group.objects.filter(acronym__in = set(wg_name_list)).order_by('parent__acronym','acronym')


def get_meeting(num=None):
    if (num == None):
        meeting = Meeting.objects.filter(type="ietf").order_by("-date")[:1].get()
    else:
        meeting = get_object_or_404(Meeting, number=num)
    return meeting

def get_schedule(meeting, name=None):
    if name is None:
        schedule = meeting.agenda
    else:
        schedule = get_object_or_404(meeting.schedule_set, name=name)
    return schedule

def get_schedule_by_id(meeting, schedid):
    if schedid is None:
        schedule = meeting.agenda
    else:
        schedule = get_object_or_404(meeting.schedule_set, id=int(schedid))
    return schedule

def agenda_permissions(meeting, schedule, user):
    # do this in positive logic.
    cansee = False
    canedit= False
    requestor= None

    try:
        requestor = user.get_profile()
    except:
        pass

    #sys.stdout.write("requestor: %s for sched: %s \n" % ( requestor, schedule ))
    if has_role(user, 'Secretariat'):
        cansee = True
        # secretariat is not superuser for edit!

    if (has_role(user, 'Area Director') and schedule.visible):
        cansee = True

    if (has_role(user, 'IAB Chair') and schedule.visible):
        cansee = True

    if (has_role(user, 'IRTF Chair') and schedule.visible):
        cansee = True

    if schedule.public:
        cansee = True

    if requestor is not None and schedule.owner == requestor:
        cansee = True
        canedit = True

    return cansee,canedit

def session_constraint_expire(session):
    from django.core.urlresolvers import reverse
    from ajax import session_constraints
    path = reverse(session_constraints, args=[session.meeting.number, session.pk])
    request = HttpRequest()
    request.path = path
    key = get_cache_key(request)
    if key is not None and cache.has_key(key):
        cache.delete(key)


