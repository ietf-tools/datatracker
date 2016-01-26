# Copyright The IETF Trust 2007, All Rights Reserved

import datetime
import os
import re
from tempfile import mkstemp

from django.http import HttpRequest, Http404
from django.db.models import Max, Q, Prefetch, F
from django.conf import settings
from django.core.cache import cache
from django.utils.cache import get_cache_key
from django.shortcuts import get_object_or_404

import debug                            # pyflakes:ignore

from ietf.doc.models import Document
from ietf.group.models import Group
from ietf.ietfauth.utils import has_role, user_is_person
from ietf.person.models  import Person
from ietf.meeting.models import Meeting
from ietf.utils.history import find_history_active_at, find_history_replacements_active_at
from ietf.utils.pipe import pipe

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
def get_area_list_from_sessions(assignments, num):
    return assignments.filter(timeslot__type = 'Session',
                                    session__group__parent__isnull = False).order_by(
        'session__group__parent__acronym').distinct().values_list(
        'session__group__parent__acronym',flat=True)

def build_all_agenda_slices(meeting):
    time_slices = []
    date_slices = {}

    for ts in meeting.timeslot_set.filter(type__in=['session',]).order_by('time','name'):
            ymd = ts.time.date()

            if ymd not in date_slices and ts.location != None:
                date_slices[ymd] = []
                time_slices.append(ymd)

            if ymd in date_slices:
                if [ts.time, ts.time+ts.duration] not in date_slices[ymd]:   # only keep unique entries
                    date_slices[ymd].append([ts.time, ts.time+ts.duration])

    time_slices.sort()
    return time_slices,date_slices

def get_all_assignments_from_schedule(schedule):
   ss = schedule.assignments.filter(timeslot__location__isnull = False)
   ss = ss.filter(session__type__slug='session')
   ss = ss.order_by('timeslot__time','timeslot__name')

   return ss

def get_modified_from_assignments(assignments):
    return assignments.aggregate(Max('timeslot__modified'))['timeslot__modified__max']

def get_wg_name_list(assignments):
    return assignments.filter(timeslot__type = 'Session',
                                    session__group__isnull = False,
                                    session__group__parent__isnull = False).order_by(
        'session__group__acronym').distinct().values_list(
        'session__group__acronym',flat=True)

def get_wg_list(assignments):
    wg_name_list = get_wg_name_list(assignments)
    return Group.objects.filter(acronym__in = set(wg_name_list)).order_by('parent__acronym','acronym')


def get_meetings(num=None,type_in=['ietf',]):
    meetings = Meeting.objects
    if type_in:
        meetings = meetings.filter(type__in=type_in)
    if num == None:
        meetings = meetings.order_by("-date")
    else:
        meetings = meetings.filter(number=num)
    return meetings

def get_meeting(num=None,type_in=['ietf',]):
    meetings = get_meetings(num,type_in)
    if meetings.exists():
        return meetings.first()
    else:
        raise Http404("No such meeting found: %s" % num)

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

def preprocess_assignments_for_agenda(assignments_queryset, meeting):
    # prefetch some stuff to prevent a myriad of small, inefficient queries
    assignments_queryset = assignments_queryset.select_related(
        "timeslot", "timeslot__location", "timeslot__type",
        "session",
        "session__group", "session__group__charter", "session__group__charter__group",
    ).prefetch_related(
        Prefetch("session__materials",
                 queryset=Document.objects.exclude(states__type=F("type"),states__slug='deleted').select_related("group").order_by("order"),
                 to_attr="prefetched_active_materials",
             ),
        "timeslot__meeting",
    )

    assignments = list(assignments_queryset) # make sure we're set in stone

    meeting_time = datetime.datetime.combine(meeting.date, datetime.time())

    # replace groups with historic counterparts
    for a in assignments:
        if a.session:
            a.session.historic_group = None

    groups = [a.session.group for a in assignments if a.session and a.session.group]
    group_replacements = find_history_replacements_active_at(groups, meeting_time)

    for a in assignments:
        if a.session and a.session.group:
            a.session.historic_group = group_replacements.get(a.session.group_id)

    # replace group parents with historic counterparts
    for a in assignments:
        if a.session and a.session.historic_group:
            a.session.historic_group.historic_parent = None

    parents = Group.objects.filter(pk__in=set(a.session.historic_group.parent_id for a in assignments if a.session and a.session.historic_group and a.session.historic_group.parent_id))
    parent_replacements = find_history_replacements_active_at(parents, meeting_time)

    for a in assignments:
        if a.session and a.session.historic_group and a.session.historic_group.parent_id:
            a.session.historic_group.historic_parent = parent_replacements.get(a.session.historic_group.parent_id)

    return assignments

def read_agenda_file(num, doc):
    # XXXX FIXME: the path fragment in the code below should be moved to
    # settings.py.  The *_PATH settings should be generalized to format()
    # style python format, something like this:
    #  DOC_PATH_FORMAT = { "agenda": "/foo/bar/agenda-{meeting.number}/agenda-{meeting-number}-{doc.group}*", }
    path = os.path.join(settings.AGENDA_PATH, "%s/agenda/%s" % (num, doc.external_url))
    if os.path.exists(path):
        with open(path) as f:
            return f.read()
    else:
        return None

def convert_draft_to_pdf(doc_name):
    inpath = os.path.join(settings.IDSUBMIT_REPOSITORY_PATH, doc_name + ".txt")
    outpath = os.path.join(settings.INTERNET_DRAFT_PDF_PATH, doc_name + ".pdf")

    try:
        infile = open(inpath, "r")
    except IOError:
        return

    t,tempname = mkstemp()
    os.close(t)
    tempfile = open(tempname, "w")

    pageend = 0;
    newpage = 0;
    formfeed = 0;
    for line in infile:
        line = re.sub("\r","",line)
        line = re.sub("[ \t]+$","",line)
        if re.search("\[?[Pp]age [0-9ivx]+\]?[ \t]*$",line):
            pageend=1
            tempfile.write(line)
            continue
        if re.search("^[ \t]*\f",line):
            formfeed=1
            tempfile.write(line)
            continue
        if re.search("^ *INTERNET.DRAFT.+[0-9]+ *$",line) or re.search("^ *Internet.Draft.+[0-9]+ *$",line) or re.search("^draft-[-a-z0-9_.]+.*[0-9][0-9][0-9][0-9]$",line) or re.search("^RFC.+[0-9]+$",line):
            newpage=1
        if re.search("^[ \t]*$",line) and pageend and not newpage:
            continue
        if pageend and newpage and not formfeed:
            tempfile.write("\f")
        pageend=0
        formfeed=0
        newpage=0
        tempfile.write(line)

    infile.close()
    tempfile.close()
    t,psname = mkstemp()
    os.close(t)
    pipe("enscript --margins 76::76: -B -q -p "+psname + " " +tempname)
    os.unlink(tempname)
    pipe("ps2pdf "+psname+" "+outpath)
    os.unlink(psname)

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


