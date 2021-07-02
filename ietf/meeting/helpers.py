# Copyright The IETF Trust 2013-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from collections import defaultdict
import datetime
import io
import os
import re
from tempfile import mkstemp

from django.http import HttpRequest, Http404
from django.db.models import F, Max, Q, Prefetch
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.urls import reverse
from django.utils.cache import get_cache_key
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string

import debug                            # pyflakes:ignore

from ietf.doc.models import Document
from ietf.group.models import Group
from ietf.group.utils import can_manage_some_groups, can_manage_group
from ietf.ietfauth.utils import has_role, user_is_person
from ietf.liaisons.utils import get_person_for_user
from ietf.mailtrigger.utils import gather_address_lists
from ietf.person.models  import Person
from ietf.meeting.models import Meeting, Schedule, TimeSlot, SchedTimeSessAssignment, ImportantDate, SchedulingEvent, Session
from ietf.meeting.utils import session_requested_by, add_event_info_to_session_qs
from ietf.name.models import ImportantDateName
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
    return assignments.filter(timeslot__type = 'regular',
                                    session__group__parent__isnull = False).order_by(
        'session__group__parent__acronym').distinct().values_list(
        'session__group__parent__acronym',flat=True)

def build_all_agenda_slices(meeting):
    time_slices = []
    date_slices = {}

    for ts in meeting.timeslot_set.filter(type__in=['regular',]).order_by('time','name'):
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
   ss = ss.filter(session__type__slug='regular')
   ss = ss.order_by('timeslot__time','timeslot__name')

   return ss

def get_modified_from_assignments(assignments):
    return assignments.aggregate(Max('timeslot__modified'))['timeslot__modified__max']

def get_wg_name_list(assignments):
    return assignments.filter(timeslot__type = 'regular',
                                    session__group__isnull = False,
                                    session__group__parent__isnull = False).order_by(
        'session__group__acronym').distinct().values_list(
        'session__group__acronym',flat=True)

def get_wg_list(assignments):
    wg_name_list = get_wg_name_list(assignments)
    return Group.objects.filter(acronym__in = set(wg_name_list)).order_by('parent__acronym','acronym')

def get_meeting(num=None,type_in=['ietf',],days=28):
    meetings = Meeting.objects
    if type_in:
        meetings = meetings.filter(type__in=type_in)
    if num == None:
        meetings = meetings.filter(date__gte=datetime.datetime.today()-datetime.timedelta(days=days)).order_by('date')
    else:
        meetings = meetings.filter(number=num)
    if meetings.exists():
        return meetings.first()
    else:
        raise Http404("No such meeting found: %s" % num)

def get_current_ietf_meeting():
    meetings = Meeting.objects.filter(type='ietf',date__gte=datetime.datetime.today()-datetime.timedelta(days=31)).order_by('date')
    return meetings.first()

def get_current_ietf_meeting_num():
    return get_current_ietf_meeting().number

def get_ietf_meeting(num=None):
    if num:
        meeting = Meeting.objects.filter(number=num).first()
    else:
        meeting = get_current_ietf_meeting()
    return meeting

def get_schedule(meeting, name=None):
    if name is None:
        schedule = meeting.schedule
    else:
        schedule = get_object_or_404(meeting.schedule_set, name=name)
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

def preprocess_assignments_for_agenda(assignments_queryset, meeting, extra_prefetches=()):
    """Add computed properties to assignments

    For each assignment a, adds
      a.start_timestamp
      a.end_timestamp
      a.session.historic_group
      a.session.historic_parent
      a.session.rescheduled_to (if rescheduled)
      a.session.prefetched_active_materials
    """
    assignments_queryset = assignments_queryset.prefetch_related(
            'timeslot', 'timeslot__type', 'timeslot__meeting',
            'timeslot__location', 'timeslot__location__floorplan', 'timeslot__location__urlresource_set',
            Prefetch(
                "session",
                queryset=add_event_info_to_session_qs(Session.objects.all().prefetch_related(
                    'group', 'group__charter', 'group__charter__group',
                    Prefetch('materials',
                             queryset=Document.objects.exclude(states__type=F("type"), states__slug='deleted').order_by('sessionpresentation__order').prefetch_related('states'),
                             to_attr='prefetched_active_materials'
                    )
                ))
            ),
            *extra_prefetches
        )


    # removed list(); it was consuming a very large amount of processor time
    # assignments = list(assignments_queryset) # make sure we're set in stone
    assignments = assignments_queryset

    meeting_time = datetime.datetime.combine(meeting.date, datetime.time())

    # replace groups with historic counterparts
    groups = [ ]
    for a in assignments:
        if a.session:
            a.session.historic_group = None
            a.session.order_number = None

            if a.session.group and a.session.group not in groups:
                groups.append(a.session.group)

    sessions_for_groups = defaultdict(list)
    for a in assignments:
        if a.session and a.session.group:
            sessions_for_groups[(a.session.group, a.session.type_id)].append(a)

    group_replacements = find_history_replacements_active_at(groups, meeting_time)

    parent_id_set = set()
    for a in assignments:
        if a.session and a.session.group:
            a.session.historic_group = group_replacements.get(a.session.group_id)

            if a.session.historic_group:
                a.session.historic_group.historic_parent = None
                
                if a.session.historic_group.parent_id:
                    parent_id_set.add(a.session.historic_group.parent_id)

            l = sessions_for_groups.get((a.session.group, a.session.type_id), [])
            a.session.order_number = l.index(a) + 1 if a in l else 0
            
    parents = Group.objects.filter(pk__in=parent_id_set)
    parent_replacements = find_history_replacements_active_at(parents, meeting_time)

    timeslot_by_session_pk = {a.session_id: a.timeslot for a in assignments}

    for a in assignments:
        if a.session and a.session.historic_group and a.session.historic_group.parent_id:
            a.session.historic_group.historic_parent = parent_replacements.get(a.session.historic_group.parent_id)

        if a.session.current_status == 'resched':
            a.session.rescheduled_to = timeslot_by_session_pk.get(a.session.tombstone_for_id)

        for d in a.session.prefetched_active_materials:
            # make sure these are precomputed with the meeting instead
            # of having to look it up
            d.get_href(meeting=meeting)
            d.get_versionless_href(meeting=meeting)

        a.start_timestamp = int(a.timeslot.utc_start_time().timestamp())
        a.end_timestamp = int(a.timeslot.utc_end_time().timestamp())

    return assignments

def is_regular_agenda_filter_group(group):
    """Should this group appear in the 'regular' agenda filter button lists?"""
    return group.type_id in ('wg', 'rg', 'ag', 'rag', 'iab', 'program')

def tag_assignments_with_filter_keywords(assignments):
    """Add keywords for agenda filtering
    
    Keywords are all lower case.
    """
    for a in assignments:
        a.filter_keywords = {a.timeslot.type.slug.lower()}
        a.filter_keywords.update(filter_keywords_for_session(a.session))
        a.filter_keywords = sorted(list(a.filter_keywords))

def filter_keywords_for_session(session):
    keywords = {session.type.slug.lower()}
    group = getattr(session, 'historic_group', session.group)
    if group is not None:
        if group.state_id == 'bof':
            keywords.add('bof')
        keywords.add(group.acronym.lower())
        specific_kw = filter_keyword_for_specific_session(session)
        if specific_kw is not None:
            keywords.add(specific_kw)
        area = getattr(group, 'historic_parent', group.parent)

        # Only sessions belonging to "regular" groups should respond to the
        # parent group filter keyword (often the 'area'). This must match
        # the test used by the agenda() view to decide whether a group
        # gets an area or non-area filter button.
        if is_regular_agenda_filter_group(group) and area is not None:
            keywords.add(area.acronym.lower())
    office_hours_match = re.match(r'^ *\w+(?: +\w+)* +office hours *$', session.name, re.IGNORECASE)
    if office_hours_match is not None:
        keywords.update(['officehours', session.name.lower().replace(' ', '')])
    return sorted(list(keywords))

def filter_keyword_for_specific_session(session):
    """Get keyword that identifies a specific session

    Returns None if the session cannot be selected individually.
    """
    group = getattr(session, 'historic_group', session.group)
    if group is None:
        return None
    kw = group.acronym.lower()  # start with this
    token = session.docname_token_only_for_multiple()
    return kw if token is None else '{}-{}'.format(kw, token)

def read_session_file(type, num, doc):
    # XXXX FIXME: the path fragment in the code below should be moved to
    # settings.py.  The *_PATH settings should be generalized to format()
    # style python format, something like this:
    #  DOC_PATH_FORMAT = { "agenda": "/foo/bar/agenda-{meeting.number}/agenda-{meeting-number}-{doc.group}*", }
    #
    # FIXME: uploaded_filename should be replaced with a function call that computes names that are fixed
    path = os.path.join(settings.AGENDA_PATH, "%s/%s/%s" % (num, type, doc.uploaded_filename))
    if doc.uploaded_filename and os.path.exists(path):
        with io.open(path, 'rb') as f:
            return f.read(), path
    else:
        return None, path

def read_agenda_file(num, doc):
    return read_session_file('agenda', num, doc)

def convert_draft_to_pdf(doc_name):
    inpath = os.path.join(settings.IDSUBMIT_REPOSITORY_PATH, doc_name + ".txt")
    outpath = os.path.join(settings.INTERNET_DRAFT_PDF_PATH, doc_name + ".pdf")

    try:
        infile = io.open(inpath, "r")
    except IOError:
        return

    t,tempname = mkstemp()
    os.close(t)
    tempfile = io.open(tempname, "w")

    pageend = 0;
    newpage = 0;
    formfeed = 0;
    for line in infile:
        line = re.sub("\r","",line)
        line = re.sub("[ \t]+$","",line)
        if re.search(r"\[?[Pp]age [0-9ivx]+\]?[ \t]*$",line):
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

def schedule_permissions(meeting, schedule, user):
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
        canedit = not schedule.is_official_record

    return cansee, canedit, secretariat

def session_constraint_expire(request,session):
    from .ajax import session_constraints
    path = reverse(session_constraints, args=[session.meeting.number, session.pk])
    temp_request = HttpRequest()
    temp_request.path = path
    temp_request.META['HTTP_HOST'] = request.META['HTTP_HOST']
    key = get_cache_key(temp_request)
    if key is not None and key in cache:
        cache.delete(key)

# -------------------------------------------------
# Interim Meeting Helpers
# -------------------------------------------------


def can_approve_interim_request(meeting, user):
    '''Returns True if the user has permissions to approve an interim meeting request'''
    if not user or isinstance(user,AnonymousUser):
        return False
    if meeting.type.slug != 'interim':
        return False
    if has_role(user, 'Secretariat'):
        return True
    person = get_person_for_user(user)
    session = meeting.session_set.first()
    if not session:
        return False
    group = session.group
    if group.type.slug in ['wg','ag']:
        if group.parent.role_set.filter(name='ad', person=person) or group.role_set.filter(name='ad', person=person):
            return True
    if group.type.slug in ['rg','rag'] and group.parent.role_set.filter(name='chair', person=person):
        return True
    if group.type.slug == 'program':
        if person.role_set.filter(group__acronym='iab', name='member'):
            return True
    return False


def can_edit_interim_request(meeting, user):
    '''Returns True if the user can edit the interim meeting request'''
    if meeting.type.slug != 'interim':
        return False
    if has_role(user, 'Secretariat'): # Consider removing - can_manage_group should handle this
        return True
    session = meeting.session_set.first()
    if not session:
        return False
    group = session.group
    if can_manage_group(user, group):
        return True
    elif can_approve_interim_request(meeting, user):
        return True
    else:
        return False


def can_request_interim_meeting(user):
    return can_manage_some_groups(user)

def can_view_interim_request(meeting, user):
    '''Returns True if the user can see the pending interim request in the pending interim view'''
    if meeting.type.slug != 'interim':
        return False
    session = meeting.session_set.first()
    if not session:
        return False
    group = session.group
    return can_manage_group(user, group)


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
        days=1,
        city=city,
        country=country,
        time_zone=timezone)
    schedule = Schedule.objects.create(
        meeting=meeting,
        owner=person,
        visible=True,
        public=True)
    meeting.schedule = schedule
    meeting.save()
    return meeting


def get_announcement_initial(meeting, is_change=False):
    '''Returns a dictionary suitable to initialize an InterimAnnouncementForm
    (Message ModelForm)'''
    group = meeting.session_set.first().group
    in_person = bool(meeting.city)
    initial = {}
    addrs = gather_address_lists('interim_announced',group=group).as_strings()
    initial['to'] = addrs.to
    initial['cc'] = addrs.cc
    initial['frm'] = settings.INTERIM_ANNOUNCE_FROM_EMAIL_PROGRAM if group.type_id=='program' else settings.INTERIM_ANNOUNCE_FROM_EMAIL_DEFAULT
    if in_person:
        desc = 'Interim'
    else:
        desc = 'Virtual'
    if is_change:
        change = ' CHANGED'
    else:
        change = ''
    type = group.type.slug.upper()
    if group.type.slug == 'wg' and group.state.slug == 'bof':
        type = 'BOF'

    assignments = SchedTimeSessAssignment.objects.filter(
        schedule__in=[meeting.schedule, meeting.schedule.base if meeting.schedule else None],
        session__in=meeting.session_set.not_canceled()
    ).order_by('timeslot__time')

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


def is_interim_meeting_approved(meeting):
    return add_event_info_to_session_qs(meeting.session_set.all()).first().current_status == 'apprw'

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


def make_materials_directories(meeting):
    '''
    This function takes a meeting object and creates the appropriate materials directories
    '''
    path = meeting.get_materials_path()
    # Default umask is 0x022, meaning strip write premission for group and others.
    # Change this temporarily to 0x0, to keep write permission for group and others.
    # (WHY??) (Note: this code is old -- was present already when the secretariat code
    # was merged with the regular datatracker code; then in secr/proceedings/views.py
    # in make_directories())
    saved_umask = os.umask(0)   
    for leaf in ('slides','agenda','minutes','id','rfc','bluesheets'):
        target = os.path.join(path,leaf)
        if not os.path.exists(target):
            os.makedirs(target)
    os.umask(saved_umask)


def send_interim_approval_request(meetings):
    """Sends an email to the secretariat, group chairs, and responsible area
    director or the IRTF chair noting that approval has been requested for a
    new interim meeting.  Takes a list of one or more meetings."""
    first_session = meetings[0].session_set.first()
    group = first_session.group
    requester = session_requested_by(first_session)
    (to_email, cc_list) = gather_address_lists('session_requested',group=group,person=requester)
    from_email = (settings.SESSION_REQUEST_FROM_EMAIL)
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
    approver_set = set()
    for authrole in group.features.groupman_authroles: # NOTE: This makes an assumption that the authroles are exactly the set of approvers
        approver_set.add(authrole)
    approvers = list(approver_set)
    context = {
        'group': group,
        'is_series': is_series,
        'meetings': meetings,
        'approvers': approvers,
        'requester': requester,
        'approval_urls': approval_urls,
    }
    send_mail(None,
              to_email,
              from_email,
              subject,
              template,
              context,
              cc=cc_list)

def send_interim_approval(user, meeting):
    """Send an email to chairs and whoever initiated the action that resulted in approval that an interim is approved"""
    first_session = meeting.session_set.first()
    (to_email,cc_list) = gather_address_lists('interim_approved',group=first_session.group,person=user.person)
    from_email = (settings.SESSION_REQUEST_FROM_EMAIL)
    subject = f'{meeting.number} interim approved'
    template = 'meeting/interim_approval.txt'
    context = { 
        'meeting': meeting,
    }
    send_mail(None,
              to_email,
              from_email,
              subject,
              template,
              context,
              cc=cc_list)

def send_interim_announcement_request(meeting):
    """Sends an email to the secretariat that an interim meeting is ready for 
    announcement, includes the link to send the official announcement"""
    first_session = meeting.session_set.first()
    group = first_session.group
    requester = session_requested_by(first_session)
    (to_email, cc_list) = gather_address_lists('interim_announce_requested')
    from_email = (settings.SESSION_REQUEST_FROM_EMAIL)
    subject = '{group} - interim meeting ready for announcement'.format(group=group.acronym)
    template = 'meeting/interim_announcement_request.txt'
    announce_url = settings.IDTRACKER_BASE_URL + reverse('ietf.meeting.views.interim_request_details', kwargs={'number': meeting.number})
    context = locals()
    send_mail(None,
              to_email,
              from_email,
              subject,
              template,
              context,
              cc_list)

def send_interim_meeting_cancellation_notice(meeting):
    """Sends an email that a scheduled interim meeting has been cancelled."""
    session = meeting.session_set.first()
    group = session.group
    (to_email, cc_list) = gather_address_lists('interim_cancelled',group=group)
    from_email = settings.INTERIM_ANNOUNCE_FROM_EMAIL_PROGRAM if group.type_id=='program' else settings.INTERIM_ANNOUNCE_FROM_EMAIL_DEFAULT
    subject = '{group} ({acronym}) {type} Interim Meeting Cancelled (was {date})'.format(
        group=group.name,
        acronym=group.acronym,
        type=group.type.slug.upper(),
        date=meeting.date.strftime('%Y-%m-%d'))
    start_time = session.official_timeslotassignment().timeslot.time
    end_time = start_time + session.requested_duration
    is_multi_day = session.meeting.session_set.with_current_status().filter(current_status='sched').count() > 1
    template = 'meeting/interim_meeting_cancellation_notice.txt'
    context = locals()
    send_mail(None,
              to_email,
              from_email,
              subject,
              template,
              context,
              cc=cc_list)


def send_interim_session_cancellation_notice(session):
    """Sends an email that one session of a scheduled interim meeting has been cancelled."""
    group = session.group
    start_time = session.official_timeslotassignment().timeslot.time
    end_time = start_time + session.requested_duration
    (to_email, cc_list) = gather_address_lists('interim_cancelled',group=group)
    from_email = settings.INTERIM_ANNOUNCE_FROM_EMAIL_PROGRAM if group.type_id=='program' else settings.INTERIM_ANNOUNCE_FROM_EMAIL_DEFAULT

    if session.name:
        description = '"%s" session' % session.name
    else:
        description = 'interim meeting session'

    subject = '{group} ({acronym}) {type} {description} cancelled (was {date})'.format(
        group=group.name,
        acronym=group.acronym,
        type=group.type.slug.upper(),
        description=description,
        date=start_time.date().strftime('%Y-%m-%d'))
    is_multi_day = session.meeting.session_set.with_current_status().filter(current_status='sched').count() > 1
    template = 'meeting/interim_session_cancellation_notice.txt'
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


def sessions_post_save(request, forms):
    """Helper function to perform various post save operations on each form of a
    InterimSessionModelForm formset"""
    for form in forms:
        if not form.has_changed():
            continue

        if form.instance.pk is not None and not SchedulingEvent.objects.filter(session=form.instance).exists():
            if not form.requires_approval:
                status_id = 'scheda'
            else:
                status_id = 'apprw'
            SchedulingEvent.objects.create(
                session=form.instance,
                status_id=status_id,
                by=request.user.person,
            )
        
        if ('date' in form.changed_data) or ('time' in form.changed_data):
            update_interim_session_assignment(form)
        if 'agenda' in form.changed_data:
            form.save_agenda()


def update_interim_session_assignment(form):
    """Helper function to create / update timeslot assigned to interim session"""
    time = datetime.datetime.combine(
        form.cleaned_data['date'],
        form.cleaned_data['time'])
    session = form.instance
    if session.official_timeslotassignment():
        slot = session.official_timeslotassignment().timeslot
        slot.time = time
        slot.duration = session.requested_duration
        slot.save()
    else:
        slot = TimeSlot.objects.create(
            meeting=session.meeting,
            type_id='regular',
            duration=session.requested_duration,
            time=time)
        SchedTimeSessAssignment.objects.create(
            timeslot=slot,
            session=session,
            schedule=session.meeting.schedule)

def populate_important_dates(meeting):
    assert ImportantDate.objects.filter(meeting=meeting).exists() is False
    assert meeting.type_id=='ietf'
    for datename in ImportantDateName.objects.filter(used=True):
        ImportantDate.objects.create(meeting=meeting,name=datename,date=meeting.date+datetime.timedelta(days=datename.default_offset_days))

def update_important_dates(meeting):
    assert meeting.type_id=='ietf'
    for datename in ImportantDateName.objects.filter(used=True):
        date = meeting.date+datetime.timedelta(days=datename.default_offset_days)
        d = ImportantDate.objects.filter(meeting=meeting, name=datename).first()
        if d:
            d.date = date
            d.save()
        else:
            ImportantDate.objects.create(meeting=meeting, name=datename, date=date)
