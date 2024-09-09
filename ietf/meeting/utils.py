# Copyright The IETF Trust 2016-2024, All Rights Reserved
# -*- coding: utf-8 -*-
import datetime
import itertools
import os
import pytz
import subprocess
import tempfile

from collections import defaultdict
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.db.models import OuterRef, Subquery, TextField, Q, Value
from django.db.models.functions import Coalesce
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.encoding import smart_str

import debug                            # pyflakes:ignore

from ietf.dbtemplate.models import DBTemplate
from ietf.meeting.models import (Session, SchedulingEvent, TimeSlot,
    Constraint, SchedTimeSessAssignment, SessionPresentation, Attended)
from ietf.doc.models import Document, State, NewRevisionDocEvent
from ietf.doc.models import DocEvent
from ietf.group.models import Group
from ietf.group.utils import can_manage_materials
from ietf.name.models import SessionStatusName, ConstraintName, DocTypeName
from ietf.person.models import Person
from ietf.stats.models import MeetingRegistration
from ietf.utils.html import sanitize_document
from ietf.utils.log import log
from ietf.utils.timezone import date_today


def session_time_for_sorting(session, use_meeting_date):
    if hasattr(session, "_otsa"):
        official_timeslot=session._otsa.timeslot
    else:
        official_timeslot = TimeSlot.objects.filter(sessionassignments__session=session, sessionassignments__schedule__in=[session.meeting.schedule, session.meeting.schedule.base if session.meeting.schedule else None]).first()
    if official_timeslot:
        return official_timeslot.time
    elif use_meeting_date and session.meeting.date:
        return session.meeting.tz().localize(
            datetime.datetime.combine(session.meeting.date, datetime.time.min)
        )
    else:
        first_event = SchedulingEvent.objects.filter(session=session).order_by('time', 'id').first()
        if first_event:
            return first_event.time
        else:
            # n.b. cannot interpret this in timezones west of UTC. That is not expected to be necessary,
            # but could probably safely add a day to the minimum datetime to make that possible.
            return pytz.utc.localize(datetime.datetime.min)

def session_requested_by(session):
    first_event = SchedulingEvent.objects.filter(session=session).order_by('time', 'id').first()
    if first_event:
        return first_event.by

    return None

def current_session_status(session):
    last_event = SchedulingEvent.objects.filter(session=session).select_related('status').order_by('-time', '-id').first()
    if last_event:
        return last_event.status

    return None


def group_sessions(sessions):
    status_names = {n.slug: n.name for n in SessionStatusName.objects.all()}
    for s in sessions:
        s.time = session_time_for_sorting(s, use_meeting_date=True)
        s.current_status_name = status_names.get(s.current_status, s.current_status)

    sessions = sorted(sessions,key=lambda s:s.time)

    future = []
    in_progress = []
    recent = []
    past = []

    for s in sessions:
        today = date_today(s.meeting.tz())
        if s.meeting.date > today:
            future.append(s)
        elif s.meeting.end_date() >= today:
            in_progress.append(s)
        elif not getattr(s, "cached_is_cutoff", lambda: s.is_material_submission_cutoff):
            recent.append(s)
        else:
            past.append(s)

    # List future and in_progress meetings with ascending time, but past
    # meetings with descending time
    recent.reverse()
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

    today = date_today()

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


def bluesheet_data(session):
    attendance = (
        Attended.objects.filter(session=session)
        .annotate(
            affiliation=Coalesce(
                Subquery(
                    MeetingRegistration.objects.filter(
                        Q(meeting=session.meeting),
                        Q(person=OuterRef("person")) | Q(email=OuterRef("person__email")),
                    ).values("affiliation")[:1]
                ),
                Value(""),
                output_field=TextField(),
            )
        ).distinct()
        .order_by("time")
    )

    return [
        {
            "name": attended.person.plain_name(),
            "affiliation": attended.affiliation,
        }
        for attended in attendance
    ]


def save_bluesheet(request, session, file, encoding='utf-8'):
    bluesheet_sp = session.presentations.filter(document__type='bluesheets').first()
    _, ext = os.path.splitext(file.name)

    if bluesheet_sp:
        doc = bluesheet_sp.document
        doc.rev = '%02d' % (int(doc.rev)+1)
        bluesheet_sp.rev = doc.rev
        bluesheet_sp.save()
    else:
        ota = session.official_timeslotassignment()
        sess_time = ota and ota.timeslot.time

        if session.meeting.type_id=='ietf':
            name = 'bluesheets-%s-%s-%s' % (session.meeting.number, 
                                            session.group.acronym, 
                                            sess_time.strftime("%Y%m%d%H%M"))
            title = 'Bluesheets IETF%s: %s : %s' % (session.meeting.number, 
                                                    session.group.acronym, 
                                                    sess_time.strftime("%a %H:%M"))
        else:
            name = 'bluesheets-%s-%s' % (session.meeting.number, sess_time.strftime("%Y%m%d%H%M"))
            title = 'Bluesheets %s: %s' % (session.meeting.number, sess_time.strftime("%a %H:%M"))
        doc = Document.objects.create(
                  name = name,
                  type_id = 'bluesheets',
                  title = title,
                  group = session.group,
                  rev = '00',
              )
        doc.states.add(State.objects.get(type_id='bluesheets',slug='active'))
        session.presentations.create(document=doc,rev='00')
    filename = '%s-%s%s'% ( doc.name, doc.rev, ext)
    doc.uploaded_filename = filename
    e = NewRevisionDocEvent.objects.create(doc=doc, rev=doc.rev, by=request.user.person, type='new_revision', desc='New revision available: %s'%doc.rev)
    save_error = handle_upload_file(file, filename, session.meeting, 'bluesheets', request=request, encoding=encoding)
    if not save_error:
        doc.save_with_history([e])
    return save_error


def generate_bluesheet(request, session):
    data = bluesheet_data(session)
    if not data:
        return
    text = render_to_string('meeting/bluesheet.txt', {
            'session': session,
            'data': data,
        })
    fd, name = tempfile.mkstemp(suffix=".txt", text=True)
    os.close(fd)
    with open(name, "w") as file:
        file.write(text)
    with open(name, "br") as file:
        return save_bluesheet(request, session, file)


def finalize(request, meeting):
    end_date = meeting.end_date()
    end_time = meeting.tz().localize(
        datetime.datetime.combine(
            end_date,
            datetime.time.min,
        )
    ).astimezone(pytz.utc) + datetime.timedelta(days=1)
    for session in meeting.session_set.all():
        for sp in session.presentations.filter(document__type='draft',rev=None):
            rev_before_end = [e for e in sp.document.docevent_set.filter(newrevisiondocevent__isnull=False).order_by('-time') if e.time <= end_time ]
            if rev_before_end:
                sp.rev = rev_before_end[-1].newrevisiondocevent.rev
            else:
                sp.rev = '00'
            sp.save()

        # Don't try to generate a bluesheet if it's before we had Attended records.
        if int(meeting.number) >= 108:
            save_error = generate_bluesheet(request, session)
            if save_error:
                messages.error(request, save_error)
    
    create_proceedings_templates(meeting)
    meeting.proceedings_final = True
    meeting.save()
    return

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
    qs = session.presentations.filter(document__type_id='slides').order_by('order')
    order_list = qs.values_list('order',flat=True)
    if list(order_list) != list(range(1,qs.count()+1)):
        for num, sp in enumerate(qs, start=1):
            sp.order=num
            sp.save()

def add_event_info_to_session_qs(qs, current_status=True, requested_by=False, requested_time=False):
    """Take a session queryset and add attributes computed from the
    scheduling events. A queryset is returned and the added attributes
    can be further filtered on.
    
    Treat this method as deprecated. Use the SessionQuerySet methods directly, chaining if needed.
    """
    if current_status:
        qs = qs.with_current_status()

    if requested_by:
        qs = qs.with_requested_by()

    if requested_time:
        qs = qs.with_requested_time()

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

    sessions = Session.objects.filter(
        meeting__in=meetings
    ).order_by(
        'meeting', 'pk'
    ).with_current_status(
    ).select_related(
        'group', 'group__parent'
    )

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


def preprocess_constraints_for_meeting_schedule_editor(meeting, sessions):
    # process constraint names - we synthesize extra names to be able
    # to treat the concepts in the same manner as the modelled ones
    constraint_names = {n.pk: n for n in meeting.enabled_constraint_names()}

    joint_with_groups_constraint_name = ConstraintName(
        slug='joint_with_groups',
        name="Joint session with",
        order=8,
    )
    constraint_names[joint_with_groups_constraint_name.slug] = joint_with_groups_constraint_name

    ad_constraint_name = ConstraintName(
        slug='responsible_ad',
        name="Responsible AD",
        order=9,
    )
    constraint_names[ad_constraint_name.slug] = ad_constraint_name
    
    for n in list(constraint_names.values()):
        # add reversed version of the name
        reverse_n = ConstraintName(
            slug=n.slug + "-reversed",
            name="{} - reversed".format(n.name),
        )
        constraint_names[reverse_n.slug] = reverse_n

    # convert human-readable rules in the database to constraints on actual sessions
    constraints = list(meeting.enabled_constraints().prefetch_related('target', 'person', 'timeranges'))

    # synthesize AD constraints - we can treat them as a special kind of 'bethere'
    responsible_ad_for_group = {}
    session_groups = set(s.group for s in sessions if s.group and s.group.parent and s.group.parent.type_id == 'area')
    meeting_time = meeting.tz().localize(
        datetime.datetime.combine(meeting.date, datetime.time(0, 0, 0))
    )

    # dig up historic AD names
    for group_id, history_time, pk in Person.objects.filter(rolehistory__name='ad', rolehistory__group__group__in=session_groups, rolehistory__group__time__lte=meeting_time).values_list('rolehistory__group__group', 'rolehistory__group__time', 'pk').order_by('rolehistory__group__time'):
        responsible_ad_for_group[group_id] = pk
    for group_id, pk in Person.objects.filter(role__name='ad', role__group__in=session_groups, role__group__time__lte=meeting_time).values_list('role__group', 'pk'):
        responsible_ad_for_group[group_id] = pk

    ad_person_lookup = {p.pk: p for p in Person.objects.filter(pk__in=set(responsible_ad_for_group.values()))}
    for group in session_groups:
        ad = ad_person_lookup.get(responsible_ad_for_group.get(group.pk))
        if ad is not None:
            constraints.append(Constraint(meeting=meeting, source=group, person=ad, name=ad_constraint_name))

    # process must not be scheduled at the same time constraints
    constraints_for_sessions = defaultdict(list)

    person_needed_for_groups = {cn.slug: defaultdict(set) for cn in constraint_names.values()}
    for c in constraints:
        if c.person_id is not None:
            person_needed_for_groups[c.name_id][c.person_id].add(c.source_id)

    sessions_for_group = defaultdict(list)
    for s in sessions:
        if s.group_id is not None:
            sessions_for_group[s.group_id].append(s.pk)

    def add_group_constraints(g1_pk, g2_pk, name_id, person_id):
        if g1_pk != g2_pk:
            for s1_pk in sessions_for_group.get(g1_pk, []):
                for s2_pk in sessions_for_group.get(g2_pk, []):
                    if s1_pk != s2_pk:
                        constraints_for_sessions[s1_pk].append((name_id, s2_pk, person_id))

    reverse_constraints = []
    seen_forward_constraints_for_groups = set()

    for c in constraints:
        if c.target_id and c.name_id != 'wg_adjacent':
            add_group_constraints(c.source_id, c.target_id, c.name_id, c.person_id)
            seen_forward_constraints_for_groups.add((c.source_id, c.target_id, c.name_id))
            reverse_constraints.append(c)

        elif c.person_id:
            for g in person_needed_for_groups[c.name_id].get(c.person_id):
                add_group_constraints(c.source_id, g, c.name_id, c.person_id)

    for c in reverse_constraints:
        # suppress reverse constraints in case we have a forward one already
        if (c.target_id, c.source_id, c.name_id) not in seen_forward_constraints_for_groups:
            add_group_constraints(c.target_id, c.source_id, c.name_id + "-reversed", c.person_id)

    # formatted constraints
    def format_constraint(c):
        if c.name_id == "time_relation":
            return c.get_time_relation_display()
        elif c.name_id == "timerange":
            return ", ".join(t.desc for t in c.timeranges.all())
        elif c.person:
            return c.person.plain_name()
        elif c.target:
            return c.target.acronym
        else:
            return "UNKNOWN"

    formatted_constraints_for_sessions = defaultdict(dict)
    for (group_pk, cn_pk), cs in itertools.groupby(sorted(constraints, key=lambda c: (c.source_id, constraint_names[c.name_id].order, c.name_id, c.pk)), key=lambda c: (c.source_id, c.name_id)):
        cs = list(cs)
        for s_pk in sessions_for_group.get(group_pk, []):
            formatted_constraints_for_sessions[s_pk][constraint_names[cn_pk]] = [format_constraint(c) for c in cs]

    # synthesize joint_with_groups constraints
    for s in sessions:
        joint_groups = s.joint_with_groups.all()
        if joint_groups:
            formatted_constraints_for_sessions[s.pk][joint_with_groups_constraint_name] = [g.acronym for g in joint_groups]

    return constraints_for_sessions, formatted_constraints_for_sessions, constraint_names


def diff_meeting_schedules(from_schedule, to_schedule):
    """Compute the difference between the two meeting schedules as a list
    describing the set of actions that will turn the schedule of from into
    the schedule of to, like:

    [
      {'change': 'schedule', 'session': session_id, 'to': timeslot_id},
      {'change': 'move', 'session': session_id, 'from': timeslot_id, 'to': timeslot_id2},
      {'change': 'unschedule', 'session': session_id, 'from': timeslot_id},
    ]

    Uses .assignments.all() so that it can be prefetched.
    """
    diffs = []

    from_session_timeslots = {
        a.session_id: a.timeslot_id
        for a in from_schedule.assignments.all()
    }

    session_ids_in_to = set()

    for a in to_schedule.assignments.all():
        session_ids_in_to.add(a.session_id)

        from_timeslot_id = from_session_timeslots.get(a.session_id)

        if from_timeslot_id is None:
            diffs.append({'change': 'schedule', 'session': a.session_id, 'to': a.timeslot_id})
        elif a.timeslot_id != from_timeslot_id:
            diffs.append({'change': 'move', 'session': a.session_id, 'from': from_timeslot_id, 'to': a.timeslot_id})

    for from_session_id, from_timeslot_id in from_session_timeslots.items():
        if from_session_id not in session_ids_in_to:
            diffs.append({'change': 'unschedule', 'session': from_session_id, 'from': from_timeslot_id})

    return diffs


def prefetch_schedule_diff_objects(diffs):
    session_ids = set()
    timeslot_ids = set()

    for d in diffs:
        session_ids.add(d['session'])

        if d['change'] == 'schedule':
            timeslot_ids.add(d['to'])
        elif d['change'] == 'move':
            timeslot_ids.add(d['from'])
            timeslot_ids.add(d['to'])
        elif d['change'] == 'unschedule':
            timeslot_ids.add(d['from'])

    session_lookup = {s.pk: s for s in Session.objects.filter(pk__in=session_ids)}
    timeslot_lookup = {t.pk: t for t in TimeSlot.objects.filter(pk__in=timeslot_ids).prefetch_related('location')}

    res = []
    for d in diffs:
        d_objs = {
            'change': d['change'],
            'session': session_lookup.get(d['session'])
        }

        if d['change'] == 'schedule':
            d_objs['to'] = timeslot_lookup.get(d['to'])
        elif d['change'] == 'move':
            d_objs['from'] = timeslot_lookup.get(d['from'])
            d_objs['to'] = timeslot_lookup.get(d['to'])
        elif d['change'] == 'unschedule':
            d_objs['from'] = timeslot_lookup.get(d['from'])

        res.append(d_objs)

    return res

def swap_meeting_schedule_timeslot_assignments(schedule, source_timeslots, target_timeslots, source_target_offset):
    """Swap the assignments of the two meeting schedule timeslots in one
    go, automatically matching them up based on the specified offset,
    e.g. timedelta(days=1). For timeslots where no suitable swap match
    is found, the sessions are unassigned. Doesn't take tombstones into
    account."""

    assignments_by_timeslot = defaultdict(list)

    for a in SchedTimeSessAssignment.objects.filter(schedule=schedule, timeslot__in=source_timeslots + target_timeslots):
        assignments_by_timeslot[a.timeslot_id].append(a)

    timeslots_to_match_up = [(source_timeslots, target_timeslots, source_target_offset), (target_timeslots, source_timeslots, -source_target_offset)]
    for lhs_timeslots, rhs_timeslots, lhs_offset in timeslots_to_match_up:
        timeslots_by_location = defaultdict(list)
        for rts in rhs_timeslots:
            timeslots_by_location[rts.location_id].append(rts)

        for lts in lhs_timeslots:
            lts_assignments = assignments_by_timeslot.pop(lts.pk, [])
            if not lts_assignments:
                continue

            swapped = False

            most_overlapping_rts, max_overlap = max([
                (rts, max(datetime.timedelta(0), min(lts.end_time() + lhs_offset, rts.end_time()) - max(lts.time + lhs_offset, rts.time)))
                for rts in timeslots_by_location.get(lts.location_id, [])
            ] + [(None, datetime.timedelta(0))], key=lambda t: t[1])

            if max_overlap > datetime.timedelta(minutes=5):
                for a in lts_assignments:
                    a.timeslot = most_overlapping_rts
                    a.modified = timezone.now()
                    a.save()
                swapped = True

            if not swapped:
                for a in lts_assignments:
                    a.delete()

def bulk_create_timeslots(meeting, times, locations, other_props):
    """Creates identical timeslots for Cartesian product of times and locations"""
    for time in times:
        for loc in locations:
            properties = dict(time=time, location=loc)
            properties.update(other_props)
            meeting.timeslot_set.create(**properties)

def preprocess_meeting_important_dates(meetings):
    for m in meetings:
        # cached_updated must be present, set it to 1970-01-01 if necessary
        m.cached_updated = m.updated() or pytz.utc.localize(datetime.datetime(1970, 1, 1, 0, 0, 0))
        m.important_dates = m.importantdate_set.prefetch_related("name")
        for d in m.important_dates:
            d.midnight_cutoff = "UTC 23:59" in d.name.name
    

def get_meeting_sessions(num, acronym):
    types = ['regular','plenary','other']
    sessions = Session.objects.filter(
        meeting__number=num,
        group__acronym=acronym,
        type__in=types,
    )
    if not sessions:
        sessions = Session.objects.filter(
            meeting__number=num,
            short=acronym,
            type__in=types,
        )
    return sessions


class SessionNotScheduledError(Exception):
    """Indicates failure because operation requires a scheduled session"""
    pass


class SaveMaterialsError(Exception):
    """Indicates failure saving session materials"""
    pass


def save_session_minutes_revision(session, file, ext, request, encoding=None, apply_to_all=False, narrative=False):
    """Creates or updates session minutes records

    This updates the database models to reflect a new version. It does not handle
    storing the new file contents, that should be handled via handle_upload_file()
    or similar.

    If the session does not already have minutes, it must be a scheduled
    session. If not, SessionNotScheduledError will be raised.

    Returns (Document, [DocEvents]), which should be passed to doc.save_with_history()
    if the file contents are stored successfully.
    """
    document_type = DocTypeName.objects.get(slug= 'narrativeminutes' if narrative else 'minutes')
    minutes_sp = session.presentations.filter(document__type=document_type).first()
    if minutes_sp:
        doc = minutes_sp.document
        doc.rev = '%02d' % (int(doc.rev)+1)
        minutes_sp.rev = doc.rev
        minutes_sp.save()
    else:
        ota = session.official_timeslotassignment()
        sess_time = ota and ota.timeslot.time
        if not sess_time:
            raise SessionNotScheduledError
        if session.meeting.type_id=='ietf':
            name = f"{document_type.prefix}-{session.meeting.number}-{session.group.acronym}"
            title = f"{document_type.name} IETF{session.meeting.number}: {session.group.acronym}"
            if not apply_to_all:
                name += '-%s' % (sess_time.strftime("%Y%m%d%H%M"),)
                title += ': %s' % (sess_time.strftime("%a %H:%M"),)
        else:
            name =f"{document_type.prefix}-{session.meeting.number}-{sess_time.strftime('%Y%m%d%H%M')}"
            title = f"{document_type.name} {session.meeting.number}: {sess_time.strftime('%a %H:%M')}"
        if Document.objects.filter(name=name).exists():
            doc = Document.objects.get(name=name)
            doc.rev = '%02d' % (int(doc.rev)+1)
        else:
            doc = Document.objects.create(
                name = name,
                type = document_type,
                title = title,
                group = session.group,
                rev = '00',
            )
        doc.states.add(State.objects.get(type_id=document_type.slug,slug='active'))
        if session.presentations.filter(document=doc).exists():
            sp = session.presentations.get(document=doc)
            sp.rev = doc.rev
            sp.save()
        else:
            session.presentations.create(document=doc,rev=doc.rev)
    if apply_to_all:
        for other_session in get_meeting_sessions(session.meeting.number, session.group.acronym):
            if other_session != session:
                other_session.presentations.filter(document__type=document_type).delete()
                other_session.presentations.create(document=doc,rev=doc.rev)
    filename = f'{doc.name}-{doc.rev}{ext}'
    doc.uploaded_filename = filename
    e = NewRevisionDocEvent.objects.create(
        doc=doc,
        by=request.user.person,
        type='new_revision',
        desc=f'New revision available: {doc.rev}',
        rev=doc.rev,
    )

    # The way this function builds the filename it will never trigger the file delete in handle_file_upload.
    save_error = handle_upload_file(
        file=file,
        filename=doc.uploaded_filename,
        meeting=session.meeting,
        subdir=document_type.slug,
        request=request,
        encoding=encoding,
    )
    if save_error:
        raise SaveMaterialsError(save_error)
    else:
        doc.save_with_history([e])


def handle_upload_file(file, filename, meeting, subdir, request=None, encoding=None):
    """Accept an uploaded materials file

    This function takes a _binary mode_ file object, a filename and a meeting object and subdir as string.
    It saves the file to the appropriate directory, get_materials_path() + subdir.
    If the file is a zip file, it creates a new directory in 'slides', which is the basename of the
    zip file and unzips the file in the new directory.
    """
    filename = Path(filename)
    is_zipfile = filename.suffix == '.zip'

    path = Path(meeting.get_materials_path()) / subdir
    if is_zipfile:
        path = path / filename.stem
    path.mkdir(parents=True, exist_ok=True)

    # agendas and minutes can only have one file instance so delete file if it already exists
    if subdir in ('agenda', 'minutes'):
        for f in path.glob(f'{filename.stem}.*'):
            try:
                f.unlink()
            except FileNotFoundError:
                pass  # if the file is already gone, so be it

    with (path / filename).open('wb+') as destination:
        # prep file for reading
        if hasattr(file, "chunks"):
            chunks = file.chunks()
        else:
            try:
                file.seek(0)
            except AttributeError:
                pass
            chunks = [file.read()]  # pretend we have chunks

        if filename.suffix in settings.MEETING_VALID_MIME_TYPE_EXTENSIONS['text/html']:
            text = b"".join(chunks)
            if encoding:
                try:
                    text = text.decode(encoding)
                except LookupError as e:
                    return (
                        f"Failure trying to save '{filename}': "
                        f"Could not identify the file encoding, got '{str(e)[:120]}'. "
                        f"Hint: Try to upload as UTF-8."
                    )
            else:
                try:
                    text = smart_str(text)
                except UnicodeDecodeError as e:
                    return "Failure trying to save '%s'. Hint: Try to upload as UTF-8: %s..." % (filename, str(e)[:120])
            # Whole file sanitization; add back what's missing from a complete
            # document (sanitize will remove these).
            clean = sanitize_document(text)
            destination.write(clean.encode('utf8'))
            if request and clean != text:
                messages.warning(request,
                                 (
                                     f"Uploaded html content is sanitized to prevent unsafe content. "
                                     f"Your upload {filename} was changed by the sanitization; "
                                     f"please check the resulting content.  "
                                 ))
        else:
            for chunk in chunks:
                destination.write(chunk)

    # unzip zipfile
    if is_zipfile:
        subprocess.call(['unzip', filename], cwd=path)

    return None

def new_doc_for_session(type_id, session):
    typename = DocTypeName.objects.get(slug=type_id)
    ota = session.official_timeslotassignment()
    if ota is None:
        return None
    sess_time = ota.timeslot.local_start_time()
    if session.meeting.type_id == "ietf":
        name = f"{typename.prefix}-{session.meeting.number}-{session.group.acronym}-{sess_time.strftime('%Y%m%d%H%M')}"
        title = f"{typename.name} IETF{session.meeting.number}: {session.group.acronym}: {sess_time.strftime('%a %H:%M')}"
    else:
        name = f"{typename.prefix}-{session.meeting.number}-{sess_time.strftime('%Y%m%d%H%M')}"
        title = f"{typename.name} {session.meeting.number}: {sess_time.strftime('%a %H:%M')}"
    doc = Document.objects.create(
                name = name,
                type_id = type_id,
                title = title,
                group = session.group,
                rev = '00',
            )
    doc.states.add(State.objects.get(type_id=type_id, slug='active'))
    session.presentations.create(document=doc,rev='00')
    return doc

def write_doc_for_session(session, type_id, filename, contents):
    filename = Path(filename)
    path = Path(session.meeting.get_materials_path()) / type_id
    path.mkdir(parents=True, exist_ok=True)
    with open(path / filename, "wb") as file:
        file.write(contents.encode('utf-8'))
    return

def create_recording(session, url, title=None, user=None):
    '''
    Creates the Document type=recording, setting external_url and creating
    NewRevisionDocEvent
    '''
    sequence = get_next_sequence(session.group,session.meeting,'recording')
    name = 'recording-{}-{}-{}'.format(session.meeting.number,session.group.acronym,sequence)
    time = session.official_timeslotassignment().timeslot.time.strftime('%Y-%m-%d %H:%M')
    if not title:
        if url.endswith('mp3'):
            title = 'Audio recording for {}'.format(time)
        else:
            title = 'Video recording for {}'.format(time)
        
    doc = Document.objects.create(name=name,
                                  title=title,
                                  external_url=url,
                                  group=session.group,
                                  rev='00',
                                  type_id='recording')
    doc.set_state(State.objects.get(type='recording', slug='active'))
    
    # create DocEvent
    NewRevisionDocEvent.objects.create(type='new_revision',
                                       by=user or Person.objects.get(name='(System)'),
                                       doc=doc,
                                       rev=doc.rev,
                                       desc='New revision available',
                                       time=doc.time)
    pres = SessionPresentation.objects.create(session=session,document=doc,rev=doc.rev)
    session.presentations.add(pres)

    return doc

def get_next_sequence(group, meeting, type):
    '''
    Returns the next sequence number to use for a document of type = type.
    Takes a group=Group object, meeting=Meeting object, type = string
    '''
    docs = Document.objects.filter(name__startswith='{}-{}-{}-'.format(type, meeting.number, group.acronym))
    if not docs:
        return 1
    docs = docs.order_by('name')
    sequence = int(docs.last().name.split('-')[-1]) + 1
    return sequence

def get_activity_stats(sdate, edate):
    '''
    This function takes a date range and produces a dictionary of statistics / objects for
    use in an activity report.  Generally the end date will be the date of the last meeting
    and the start date will be the date of the meeting before that.

    Data between midnight UTC on the specified dates are included in the stats.
    '''
    sdatetime = pytz.utc.localize(datetime.datetime.combine(sdate, datetime.time()))
    edatetime = pytz.utc.localize(datetime.datetime.combine(edate, datetime.time()))

    data = {}
    data['sdate'] = sdate
    data['edate'] = edate

    events = DocEvent.objects.filter(doc__type='draft', time__gte=sdatetime, time__lt=edatetime)
    
    data['actions_count'] = events.filter(type='iesg_approved').count()
    data['last_calls_count'] = events.filter(type='sent_last_call').count()
    new_draft_events = events.filter(newrevisiondocevent__rev='00')
    new_drafts = list(set([e.doc_id for e in new_draft_events]))
    data['new_docs'] = list(set([e.doc for e in new_draft_events]))
    data['new_drafts_count'] = len(new_drafts)
    data['new_drafts_updated_count'] = events.filter(doc__id__in=new_drafts,newrevisiondocevent__rev='01').count()
    data['new_drafts_updated_more_count'] = events.filter(doc__id__in=new_drafts,newrevisiondocevent__rev='02').count()
    
    update_events = events.filter(type='new_revision').exclude(doc__id__in=new_drafts)
    data['updated_drafts_count'] = len(set([e.doc_id for e in update_events]))
    
    # Calculate Final Four Weeks stats (ffw)
    ffwdate = edatetime - datetime.timedelta(days=28)
    ffw_new_count = events.filter(time__gte=ffwdate, newrevisiondocevent__rev='00').count()
    try:
        ffw_new_percent = format(ffw_new_count / float(data['new_drafts_count']), '.0%')
    except ZeroDivisionError:
        ffw_new_percent = 0
        
    data['ffw_new_count'] = ffw_new_count
    data['ffw_new_percent'] = ffw_new_percent
    
    ffw_update_events = events.filter(time__gte=ffwdate, type='new_revision').exclude(doc__id__in=new_drafts)
    ffw_update_count = len(set([e.doc_id for e in ffw_update_events]))
    try:
        ffw_update_percent = format(ffw_update_count / float(data['updated_drafts_count']),'.0%')
    except ZeroDivisionError:
        ffw_update_percent = 0
    
    data['ffw_update_count'] = ffw_update_count
    data['ffw_update_percent'] = ffw_update_percent

    rfcs = events.filter(type='published_rfc')
    data['rfcs'] = rfcs.select_related('doc').select_related('doc__group').select_related('doc__intended_std_level')

    data['counts'] = {'std': rfcs.filter(doc__intended_std_level__in=('ps', 'ds', 'std')).count(),
                      'bcp': rfcs.filter(doc__intended_std_level='bcp').count(),
                      'exp': rfcs.filter(doc__intended_std_level='exp').count(),
                      'inf': rfcs.filter(doc__intended_std_level='inf').count()}

    data['new_groups'] = Group.objects.filter(
        type='wg',
        groupevent__changestategroupevent__state='active',
        groupevent__time__gte=sdatetime,
        groupevent__time__lt=edatetime)
        
    data['concluded_groups'] = Group.objects.filter(
        type='wg',
        groupevent__changestategroupevent__state='conclude',
        groupevent__time__gte=sdatetime,
        groupevent__time__lt=edatetime)

    return data

def is_powerpoint(doc):
    '''
    Returns true if document is a Powerpoint presentation
    '''
    return doc.file_extension() in ('ppt', 'pptx')

def post_process(doc):
    '''
    Does post processing on uploaded file.
    - Convert PPT to PDF
    '''
    if is_powerpoint(doc) and hasattr(settings, 'PPT2PDF_COMMAND'):
        try:
            cmd = list(settings.PPT2PDF_COMMAND)   # Don't operate on the list actually in settings
            cmd.append(doc.get_file_path())                                 # outdir
            cmd.append(os.path.join(doc.get_file_path(), doc.uploaded_filename))  # filename
            subprocess.check_call(cmd)
        except (subprocess.CalledProcessError, OSError) as error:
            log("Error converting PPT: %s" % (error))
            return
        # change extension
        base, ext = os.path.splitext(doc.uploaded_filename)
        doc.uploaded_filename = base + '.pdf'

        e = DocEvent.objects.create(
            type='changed_document',
            by=Person.objects.get(name="(System)"),
            doc=doc,
            rev=doc.rev,
            desc='Converted document to PDF',
        )
        doc.save_with_history([e])


def participants_for_meeting(meeting):
    """ Return a tuple (checked_in, attended)
        checked_in = queryset of onsite, checkedin participants values_list('person')
        attended = queryset of remote participants who attended a session values_list('person')
    """
    checked_in = meeting.meetingregistration_set.filter(reg_type='onsite', checkedin=True).values_list('person', flat=True).distinct()
    sessions = meeting.session_set.filter(Q(type='plenary') | Q(group__type__in=['wg', 'rg']))
    attended = Attended.objects.filter(session__in=sessions).values_list('person', flat=True).distinct()
    return (checked_in, attended)
