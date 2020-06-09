# Copyright The IETF Trust 2016-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime
import requests

from urllib.error import HTTPError
from django.conf import settings
from django.template.loader import render_to_string
from django.db.models.expressions import Subquery, OuterRef

import debug                            # pyflakes:ignore

from ietf.dbtemplate.models import DBTemplate
from ietf.meeting.models import Session, Meeting, SchedulingEvent, TimeSlot
from ietf.group.models import Group, Role
from ietf.group.utils import can_manage_materials
from ietf.name.models import SessionStatusName
from ietf.nomcom.utils import DISQUALIFYING_ROLE_QUERY_EXPRESSION
from ietf.person.models import Email
from ietf.secr.proceedings.proc_utils import import_audio_files

def session_time_for_sorting(session, use_meeting_date):
    official_timeslot = TimeSlot.objects.filter(sessionassignments__session=session, sessionassignments__schedule=session.meeting.schedule).first()
    if official_timeslot:
        return official_timeslot.time
    elif use_meeting_date and session.meeting.date:
        return datetime.datetime.combine(session.meeting.date, datetime.time.min)
    else:
        first_event = SchedulingEvent.objects.filter(session=session).order_by('time', 'id').first()
        if first_event:
            return first_event.time
        else:
            return datetime.datetime.min

def session_requested_by(session):
    first_event = SchedulingEvent.objects.filter(session=session).order_by('time', 'id').first()
    if first_event:
        return first_event.by

    return None

def current_session_status(session):
    last_event = SchedulingEvent.objects.filter(session=session).order_by('-time', '-id').first()
    if last_event:
        return last_event.status

    return None


def group_sessions(sessions):
    status_names = {n.slug: n.name for n in SessionStatusName.objects.all()}
    for s in sessions:
        s.time = session_time_for_sorting(s, use_meeting_date=True)
        s.current_status_name = status_names.get(s.current_status, s.current_status)

    sessions = sorted(sessions,key=lambda s:s.time)

    today = datetime.date.today()
    future = []
    in_progress = []
    recent = []
    past = []
    for s in sessions:
        if s.meeting.date > today:
            future.append(s)
        elif s.meeting.end_date() >= today:
            in_progress.append(s)
        elif not s.is_material_submission_cutoff():
            recent.append(s)
        else:
            past.append(s)

    # List future and in_progress meetings with ascending time, but past
    # meetings with descending time
    past.reverse()

    return future, in_progress, recent, past

def get_upcoming_manageable_sessions(user):
    """  Find all the sessions for meetings that haven't ended that the user could affect """

    # Consider adding an argument that has some Qs to append to the queryset
    # to allow filtering to a particular group, etc. if we start seeing a lot of code
    # that calls this function and then immediately starts whittling down the returned list

    # Note the days=15 - this allows this function to find meetings in progress that last up to two weeks.
    # This notion of searching by end-of-meeting is also present in Document.future_presentations.
    # It would be nice to make it easier to use querysets to talk about meeting endings wthout a heuristic like this one

    # We can in fact do that with something like
    # .filter(date__gte=today - F('days')), but unfortunately, it
    # doesn't work correctly with Django 1.11 and MySQL/SQLite

    today = datetime.date.today()

    candidate_sessions = add_event_info_to_session_qs(
        Session.objects.filter(meeting__date__gte=today - datetime.timedelta(days=15))
    ).exclude(
        current_status__in=['canceled', 'disappr', 'notmeet', 'deleted']
    ).prefetch_related('meeting')

    return [
        sess for sess in candidate_sessions if sess.meeting.end_date() >= today and can_manage_materials(user, sess.group)
    ]

def sort_sessions(sessions):
    return sorted(sessions, key=lambda s: (s.meeting.number, s.group.acronym, session_time_for_sorting(s, use_meeting_date=False)))

def create_proceedings_templates(meeting):
    '''Create DBTemplates for meeting proceedings'''
    # Get meeting attendees from registration system
    url = settings.STATS_REGISTRATION_ATTENDEES_JSON_URL.format(number=meeting.number)
    try:
        attendees = requests.get(url).json()
    except (ValueError, HTTPError):
        attendees = []

    if attendees:
        attendees = sorted(attendees, key = lambda a: a['LastName'])
        content = render_to_string('meeting/proceedings_attendees_table.html', {
            'attendees':attendees})
        try:
            template = DBTemplate.objects.get(path='/meeting/proceedings/%s/attendees.html' % (meeting.number, ))
            template.title='IETF %s Attendee List' % meeting.number
            template.type_id='django'
            template.content=content
            template.save()
        except DBTemplate.DoesNotExist:
            DBTemplate.objects.create(
                path='/meeting/proceedings/%s/attendees.html' % (meeting.number, ),
                title='IETF %s Attendee List' % meeting.number,
                type_id='django',
                content=content)    
    # Make copy of default IETF Overview template
    if not meeting.overview:
        path = '/meeting/proceedings/%s/overview.rst' % (meeting.number, )
        try:
            template = DBTemplate.objects.get(path=path)
        except DBTemplate.DoesNotExist:
            template = DBTemplate.objects.get(path='/meeting/proceedings/defaults/overview.rst')
            template.id = None
            template.path = path
            template.title = 'IETF %s Proceedings Overview' % (meeting.number)
            template.save()
        meeting.overview = template
        meeting.save()

def finalize(meeting):
    end_date = meeting.end_date()
    end_time = datetime.datetime.combine(end_date, datetime.datetime.min.time())+datetime.timedelta(days=1)
    for session in meeting.session_set.all():
        for sp in session.sessionpresentation_set.filter(document__type='draft',rev=None):
            rev_before_end = [e for e in sp.document.docevent_set.filter(newrevisiondocevent__isnull=False).order_by('-time') if e.time <= end_time ]
            if rev_before_end:
                sp.rev = rev_before_end[-1].newrevisiondocevent.rev
            else:
                sp.rev = '00'
            sp.save()
    
    import_audio_files(meeting)
    create_proceedings_templates(meeting)
    meeting.proceedings_final = True
    meeting.save()
    return

def attended_ietf_meetings(person):
    email_addresses = Email.objects.filter(person=person).values_list('address',flat=True)
    return Meeting.objects.filter(
                type='ietf',
                meetingregistration__email__in=email_addresses,
                meetingregistration__attended=True,
            )

def attended_in_last_five_ietf_meetings(person, date=datetime.datetime.today()):
    previous_five = Meeting.objects.filter(type='ietf',date__lte=date).order_by('-date')[:5]
    attended = attended_ietf_meetings(person)
    return set(previous_five).intersection(attended)

def is_nomcom_eligible(person, date=datetime.date.today()):
    attended = attended_in_last_five_ietf_meetings(person, date)
    disqualifying_roles = Role.objects.filter(person=person).filter(DISQUALIFYING_ROLE_QUERY_EXPRESSION)
    return len(attended)>=3 and not disqualifying_roles.exists()


def sort_accept_tuple(accept):
    tup = []
    if accept:
        accept_types = accept.split(',')
        for at in accept_types:
            keys = at.split(';', 1)
            q = 1.0
            if len(keys) != 1:
                qlist = keys[1].split('=', 1)
                if len(qlist) == 2:
                    try:
                        q = float(qlist[1])
                    except ValueError:
                        q = 0.0
            tup.append((keys[0], q))
        return sorted(tup, key = lambda x: float(x[1]), reverse = True)
    return tup

def condition_slide_order(session):
    qs = session.sessionpresentation_set.filter(document__type_id='slides').order_by('order')
    order_list = qs.values_list('order',flat=True)
    if list(order_list) != list(range(1,qs.count()+1)):
        for num, sp in enumerate(qs, start=1):
            sp.order=num
            sp.save()

def add_event_info_to_session_qs(qs, current_status=True, requested_by=False, requested_time=False):
    """Take a session queryset and add attributes computed from the
    scheduling events. A queryset is returned and the added attributes
    can be further filtered on."""
    from django.db.models import TextField, Value
    from django.db.models.functions import Coalesce
    if current_status:
        qs = qs.annotate(
            # coalesce with '' to avoid nulls which give funny
            # results, e.g. .exclude(current_status='canceled') also
            # skips rows with null in them
            current_status=Coalesce(Subquery(SchedulingEvent.objects.filter(session=OuterRef('pk')).order_by('-time', '-id').values('status')[:1]), Value(''), output_field=TextField()),
        )

    if requested_by:
        qs = qs.annotate(
            requested_by=Subquery(SchedulingEvent.objects.filter(session=OuterRef('pk')).order_by('time', 'id').values('by')[:1]),
        )

    if requested_time:
        qs = qs.annotate(
            requested_time=Subquery(SchedulingEvent.objects.filter(session=OuterRef('pk')).order_by('time', 'id').values('time')[:1]),
        )

    return qs

def only_sessions_that_can_meet(session_qs):
    qs = add_event_info_to_session_qs(session_qs).exclude(current_status__in=['notmeet', 'disappr', 'deleted', 'apprw'])

    # Restrict graphical scheduling to meeting requests (Sessions) of type 'regular' for now
    qs = qs.filter(type__slug='regular')

    return qs


# Keeping this as a note that might help when returning Customization to the /meetings/upcoming page
#def group_parents_from_sessions(sessions):
#    group_parents = list()
#    parents = {}
#    for s in sessions:
#        if s.group.parent_id not in parents:
#            parent = s.group.parent
#            parent.group_list = set()
#            group_parents.append(parent)
#            parents[s.group.parent_id] = parent
#        parent.group_list.add(s.group)
#
#    for p in parents.values():
#        p.group_list = list(p.group_list)
#        p.group_list.sort(key=lambda g: g.acronym)
#
#    return group_parents


def data_for_meetings_overview(meetings, interim_status=None):
    """Return filtered meetings with sessions and group hierarchy (for the
    interim menu)."""

    # extract sessions
    for m in meetings:
        m.sessions = []

    sessions = add_event_info_to_session_qs(
        Session.objects.filter(meeting__in=meetings).order_by('meeting', 'pk')
    ).select_related('group', 'group__parent')

    meeting_dict = {m.pk: m for m in meetings}
    for s in sessions.iterator():
        meeting_dict[s.meeting_id].sessions.append(s)

    # filter
    if interim_status == 'apprw':
        meetings = [
            m for m in meetings
            if not m.type_id == 'interim' or any(s.current_status == 'apprw' for s in m.sessions)
        ]

    elif interim_status == 'scheda':
        meetings = [
            m for m in meetings
            if not m.type_id == 'interim' or any(s.current_status == 'scheda' for s in m.sessions)
        ]

    else:
        meetings = [
            m for m in meetings
            if not m.type_id == 'interim' or not all(s.current_status in ['apprw', 'scheda', 'canceledpa'] for s in m.sessions)
        ]

    ietf_group = Group.objects.get(acronym='ietf')

    # set some useful attributes
    for m in meetings:
        m.end = m.date + datetime.timedelta(days=m.days)
        m.responsible_group = (m.sessions[0].group if m.sessions else None) if m.type_id == 'interim' else ietf_group
        m.interim_meeting_cancelled = m.type_id == 'interim' and all(s.current_status == 'canceled' for s in m.sessions)

    return meetings
