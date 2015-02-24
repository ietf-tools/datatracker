# Copyright The IETF Trust 2007, All Rights Reserved

import datetime
import pytz

from django.http import HttpRequest
from django.db.models import Max, Q
from django.conf import settings
from django.core.cache import cache
from django.utils.cache import get_cache_key
from django.shortcuts import get_object_or_404

import debug                            # pyflakes:ignore

from ietf.group.models import Group
from ietf.ietfauth.utils import has_role, user_is_person
from ietf.person.models  import Person
from ietf.meeting.models import Meeting
from ietf.utils.history import find_history_active_at

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
                for x in history.rolehistory_set.filter(name="ad",group__type='area').select_related('group', 'person', 'email'):
                    #print "xh[%u]: %s" % (num, x)
                    ads.append(x)
        else:
            #print " group[%u]: %s" % (num, g)
            if g.state_id == "active":
                for x in g.role_set.filter(name="ad",group__type='area').select_related('group', 'person', 'email'):
                    #print "xg[%u]: %s (#%u)" % (num, x, x.pk)
                    ads.append(x)
    return ads


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
        'session__group__parent__acronym').distinct().values_list(
        'session__group__parent__acronym',flat=True)

def build_all_agenda_slices(meeting):
    time_slices = []
    date_slices = {}

    for ts in meeting.timeslot_set.exclude(type__in=['reg','break']).order_by('time','name'):
            ymd = ts.time.date()

            if ymd not in date_slices and ts.location != None:
                date_slices[ymd] = []
                time_slices.append(ymd)

            if ymd in date_slices:
                if [ts.time, ts.time+ts.duration] not in date_slices[ymd]:   # only keep unique entries
                    date_slices[ymd].append([ts.time, ts.time+ts.duration])

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
        'session__group__acronym').distinct().values_list(
        'session__group__acronym',flat=True)

def get_wg_list(scheduledsessions):
    wg_name_list = get_wg_name_list(scheduledsessions)
    return Group.objects.filter(acronym__in = set(wg_name_list)).order_by('parent__acronym','acronym')


def get_meeting(num=None):
    if num == None:
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

# seems this belongs in ietf/person/utils.py?
def get_person_by_email(email):
    # email == None may actually match people who haven't set an email!
    if email is None:
        return None
    return Person.objects.filter(email__address=email).distinct().first()

def get_schedule_by_name(meeting, owner, name):
    if owner is not None:
        return meeting.schedule_set.filter(owner = owner, name = name).first()
    else:
        return meeting.schedule_set.filter(name = name).first()

def meeting_updated(meeting):
    meeting_time = datetime.datetime(*(meeting.date.timetuple()[:7]))
    ts = max(meeting.timeslot_set.aggregate(Max('modified'))["modified__max"] or meeting_time,
             meeting.session_set.aggregate(Max('modified'))["modified__max"] or meeting_time)
    tz = pytz.timezone(settings.PRODUCTION_TIMEZONE)
    ts = tz.localize(ts)
    return ts

def agenda_permissions(meeting, schedule, user):
    # do this in positive logic.
    cansee = False
    canedit = False
    secretariat = False

    if has_role(user, 'Secretariat'):
        cansee = True
        secretariat = True
        # NOTE: secretariat is not superuser for edit!
    elif schedule.public:
        cansee = True
    elif schedule.visible and has_role(user, ['Area Director', 'IAB Chair', 'IRTF Chair']):
        cansee = True

    if user_is_person(user, schedule.owner):
        cansee = True
        canedit = True

    return cansee, canedit, secretariat

def session_constraint_expire(request,session):
    from django.core.urlresolvers import reverse
    from ajax import session_constraints
    path = reverse(session_constraints, args=[session.meeting.number, session.pk])
    temp_request = HttpRequest()
    temp_request.path = path
    temp_request.META['HTTP_HOST'] = request.META['HTTP_HOST']
    key = get_cache_key(temp_request)
    if key is not None and cache.has_key(key):
        cache.delete(key)


