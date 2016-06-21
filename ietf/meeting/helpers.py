# Copyright The IETF Trust 2007, All Rights Reserved

import datetime
import os
import re
from tempfile import mkstemp

from django.http import HttpRequest, Http404
from django.db.models import Max, Q, Prefetch, F
from django.conf import settings
from django.core.cache import cache
from django.core.urlresolvers import reverse
from django.utils.cache import get_cache_key
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string

import debug                            # pyflakes:ignore

from ietf.doc.models import Document
from ietf.doc.utils import get_document_content
from ietf.group.models import Group
from ietf.ietfauth.utils import has_role, user_is_person
from ietf.liaisons.utils import get_person_for_user
from ietf.mailtrigger.utils import gather_address_lists
from ietf.person.models  import Person
from ietf.meeting.models import Meeting, Schedule, TimeSlot, SchedTimeSessAssignment
from ietf.utils.history import find_history_active_at, find_history_replacements_active_at
from ietf.utils.mail import send_mail
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
    from ajax import session_constraints
    path = reverse(session_constraints, args=[session.meeting.number, session.pk])
    temp_request = HttpRequest()
    temp_request.path = path
    temp_request.META['HTTP_HOST'] = request.META['HTTP_HOST']
    key = get_cache_key(temp_request)
    if key is not None and cache.has_key(key):
        cache.delete(key)

# -------------------------------------------------
# Interim Meeting Helpers
# -------------------------------------------------


def assign_interim_session(form):
    """Helper function to create a timeslot and assign the interim session"""
    time = datetime.datetime.combine(
        form.cleaned_data['date'],
        form.cleaned_data['time'])
    session = form.instance
    if session.official_timeslotassignment():
        slot = session.official_timeslotassignment().timeslot
        slot.time = time
        slot.save()
    else:
        slot = TimeSlot.objects.create(
            meeting=session.meeting,
            type_id="session",
            duration=session.requested_duration,
            time=time)
        SchedTimeSessAssignment.objects.create(
            timeslot=slot,
            session=session,
            schedule=session.meeting.agenda)


def can_approve_interim_request(meeting, user):
    '''Returns True if the user has permissions to approve an interim meeting request'''
    if meeting.type.slug != 'interim':
        return False
    if has_role(user, 'Secretariat'):
        return True
    person = get_person_for_user(user)
    session = meeting.session_set.first()
    if not session:
        return False
    group = session.group
    if group.type.slug == 'wg' and group.parent.role_set.filter(name='ad', person=person):
        return True
    if group.type.slug == 'rg' and group.parent.role_set.filter(name='chair', person=person):
        return True
    return False


def can_edit_interim_request(meeting, user):
    '''Returns True if the user can edit the interim meeting request'''
    if meeting.type.slug != 'interim':
        return False
    if has_role(user, 'Secretariat'):
        return True
    person = get_person_for_user(user)
    session = meeting.session_set.first()
    if not session:
        return False
    group = session.group
    if group.role_set.filter(name='chair', person=person):
        return True
    elif can_approve_interim_request(meeting, user):
        return True
    else:
        return False


def can_request_interim_meeting(user):
    if has_role(user, ('Secretariat', 'Area Director', 'WG Chair', 'IRTF Chair', 'RG Chair')):
        return True
    return False


def can_view_interim_request(meeting, user):
    '''Returns True if the user can see the pending interim request in the pending interim view'''
    if meeting.type.slug != 'interim':
        return False
    if has_role(user, 'Secretariat'):
        return True
    person = get_person_for_user(user)
    session = meeting.session_set.first()
    if not session:
        return False
    group = session.group
    if has_role(user, 'Area Director') and group.type.slug == 'wg':
        return True
    if has_role(user, 'IRTF Chair') and group.type.slug == 'rg':
        return True
    if group.role_set.filter(name='chair', person=person):
        return True
    return False


def create_interim_meeting(group, date, city='', country='', timezone='UTC',
                           person=None):
    """Helper function to create interim meeting and associated schedule"""
    if not person:
        person = Person.objects.get(name='(System)')
    number = get_next_interim_number(group.acronym, date)
    meeting = Meeting.objects.create(
        number=number,
        type_id='interim',
        date=date,
        city=city,
        country=country,
        time_zone=timezone)
    schedule = Schedule.objects.create(
        meeting=meeting,
        owner=person,
        visible=True,
        public=True)
    meeting.agenda = schedule
    meeting.save()
    return meeting


def get_announcement_initial(meeting, is_change=False):
    '''Returns a dictionary suitable to initialize an InterimAnnouncementForm
    (Message ModelForm)'''
    group = meeting.session_set.first().group
    in_person = bool(meeting.city)
    initial = {}
    initial['to'] = settings.INTERIM_ANNOUNCE_TO_EMAIL
    initial['cc'] = group.list_email
    initial['frm'] = settings.INTERIM_ANNOUNCE_FROM_EMAIL
    if in_person:
        desc = 'Interim'
    else:
        desc = 'Virtual'
    if is_change:
        change = ' CHANGED'
    else:
        change = ''
    if group.type.slug == 'rg':
        type = 'RG'
    elif group.type.slug == 'wg' and group.state.slug == 'bof':
        type = 'BOF'
    else:
        type = 'WG'
    initial['subject'] = '{name} ({acronym}) {type} {desc} Meeting: {date}{change}'.format(
        name=group.name, 
        acronym=group.acronym,
        type=type,
        desc=desc,
        date=meeting.date,
        change=change)
    body = render_to_string('meeting/interim_announcement.txt', locals())
    initial['body'] = body
    return initial


def get_earliest_session_date(formset):
    '''Return earliest date from InterimSession Formset'''
    return sorted([f.cleaned_data['date'] for f in formset.forms if f.cleaned_data.get('date')])[0]


def get_interim_initial(meeting):
    '''Returns a dictionary suitable to initialize a InterimRequestForm'''
    initial = {}
    initial['group'] = meeting.session_set.first().group
    if meeting.city:
        initial['in_person'] = True
    else:
        initial['in_person'] = False
    if meeting.session_set.count() > 1:
        initial['meeting_type'] = 'multi-day'
    else:
        initial['meeting_type'] = 'single'
    if meeting.session_set.first().status.slug == 'apprw':
        initial['approved'] = False
    else:
        initial['approved'] = True
    return initial


def get_interim_session_initial(meeting):
    '''Returns a list of dictionaries suitable to initialize a InterimSessionForm'''
    initials = []
    for session in meeting.session_set.all():
        initial = {}
        initial['date'] = session.official_timeslotassignment().timeslot.time
        initial['time'] = session.official_timeslotassignment().timeslot.time
        initial['duration'] = session.requested_duration
        initial['remote_instructions'] = session.remote_instructions
        initial['agenda_note'] = session.agenda_note
        doc = session.agenda()
        if doc:
            path = os.path.join(doc.get_file_path(), doc.filename_with_rev())
            initial['agenda'] = get_document_content(os.path.basename(path), path, markup=False)
        initials.append(initial)

    return initials


def is_meeting_approved(meeting):
    """Returns True if the meeting is approved"""
    if meeting.session_set.first().status.slug == 'apprw':
        return False
    else:
        return True

def get_next_interim_number(acronym,date):
    '''
    This function takes a group acronym and date object and returns the next number
    to use for an interim meeting.  The format is interim-[year]-[acronym]-[01-99]
    '''
    base = 'interim-%s-%s-' % (date.year, acronym)
    # can't use count() to calculate the next number in case one was deleted
    meetings = Meeting.objects.filter(type='interim', number__startswith=base)
    if meetings:
        serial = sorted([ int(x.number.split('-')[-1]) for x in meetings ])[-1]
    else:
        serial = 0
    return "%s%02d" % (base, serial+1)

def get_next_agenda_name(meeting):
    """Returns the next name to use for an agenda document for *meeting*"""
    group = meeting.session_set.first().group
    documents = Document.objects.filter(type='agenda', session__meeting=meeting)
    if documents:
        sequences = [int(d.name.split('-')[-1]) for d in documents]
        last_sequence = sorted(sequences)[-1]
    else:
        last_sequence = 0
    return 'agenda-{meeting}-{group}-{sequence}'.format(
        meeting=meeting.number,
        group=group.acronym,
        sequence=str(last_sequence + 1).zfill(2))


def make_directories(meeting):
    '''
    This function takes a meeting object and creates the appropriate materials directories
    '''
    path = meeting.get_materials_path()
    os.umask(0)
    for leaf in ('slides','agenda','minutes','id','rfc','bluesheets'):
        target = os.path.join(path,leaf)
        if not os.path.exists(target):
            os.makedirs(target)


def send_interim_approval_request(meetings):
    """Sends an email to the secretariat, group chairs, and resposnible area
    director or the IRTF chair noting that approval has been requested for a
    new interim meeting.  Takes a list of one or more meetings."""
    group = meetings[0].session_set.first().group
    requester = meetings[0].session_set.first().requested_by
    (to_email, cc_list) = gather_address_lists('session_requested',group=group,person=requester)
    from_email = ('"IETF Meeting Session Request Tool"','session_request_developers@ietf.org')
    subject = '{group} - New Interim Meeting Request'.format(group=group.acronym)
    template = 'meeting/interim_approval_request.txt'
    approval_urls = []
    for meeting in meetings:
        url = settings.IDTRACKER_BASE_URL + reverse('ietf.meeting.views.interim_request_details', kwargs={'number': meeting.number})
        approval_urls.append(url)
    if len(meetings) > 1:
        is_series = True
    else:
        is_series = False
    context = locals()
    send_mail(None,
              to_email,
              from_email,
              subject,
              template,
              context,
              cc=cc_list)


def send_interim_cancellation_notice(meeting):
    """Sends an email that a scheduled interim meeting has been cancelled."""
    session = meeting.session_set.first()
    group = session.group
    to_email = settings.INTERIM_ANNOUNCE_TO_EMAIL
    (_, cc_list) = gather_address_lists('session_request_cancelled',group=group)
    from_email = settings.INTERIM_ANNOUNCE_FROM_EMAIL
    subject = '{group} ({acronym}) {type} Interim Meeting Cancelled (was {date})'.format(
        group=group.name,
        acronym=group.acronym,
        type=group.type.slug.upper(),
        date=meeting.date.strftime('%Y-%m-%d'))
    start_time = session.official_timeslotassignment().timeslot.time
    end_time = start_time + session.requested_duration
    if meeting.session_set.filter(status='sched').count() > 1:
        is_multi_day = True
    else:
        is_multi_day = False
    template = 'meeting/interim_cancellation_notice.txt'
    context = locals()
    send_mail(None,
              to_email,
              from_email,
              subject,
              template,
              context,
              cc=cc_list)


def send_interim_minutes_reminder(meeting):
    """Sends an email reminding chairs to submit minutes of interim *meeting*"""
    session = meeting.session_set.first()
    group = session.group
    (to_email, cc_list) = gather_address_lists('session_minutes_reminder',group=group)
    from_email = 'proceedings@ietf.org'
    subject = 'Action Required: Minutes from {group} ({acronym}) {type} Interim Meeting on {date}'.format(
        group=group.name,
        acronym=group.acronym,
        type=group.type.slug.upper(),
        date=meeting.date.strftime('%Y-%m-%d'))
    template = 'meeting/interim_minutes_reminder.txt'
    context = locals()
    send_mail(None,
              to_email,
              from_email,
              subject,
              template,
              context,
              cc=cc_list)


def check_interim_minutes():
    """Finds interim meetings that occured 10 days ago, if they don't
    have minutes send a reminder."""
    date = datetime.datetime.today() - datetime.timedelta(days=10)
    meetings = Meeting.objects.filter(type='interim', session__status='sched', date=date)
    for meeting in meetings:
        if not meeting.session_set.first().minutes():
            send_interim_minutes_reminder(meeting)


def sessions_post_save(forms):
    """Helper function to perform various post save operations on each form of a
    InterimSessionModelForm formset"""
    for form in forms:
        if not form.has_changed():
            continue
        if ('date' in form.changed_data) or ('time' in form.changed_data):
            assign_interim_session(form)
        if 'agenda' in form.changed_data:
            form.save_agenda()
