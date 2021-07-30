# Copyright The IETF Trust 2016-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime
import itertools
import re
import requests

from collections import defaultdict
from urllib.error import HTTPError

from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import format_html
from django.utils.safestring import mark_safe

import debug                            # pyflakes:ignore

from ietf.dbtemplate.models import DBTemplate
from ietf.meeting.models import Session, SchedulingEvent, TimeSlot, Constraint, SchedTimeSessAssignment
from ietf.group.models import Group
from ietf.group.utils import can_manage_materials
from ietf.name.models import SessionStatusName, ConstraintName
from ietf.person.models import Person
from ietf.secr.proceedings.proc_utils import import_audio_files

def session_time_for_sorting(session, use_meeting_date):
    official_timeslot = TimeSlot.objects.filter(sessionassignments__session=session, sessionassignments__schedule__in=[session.meeting.schedule, session.meeting.schedule.base if session.meeting.schedule else None]).first()
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

def reverse_editor_label(label):
    reverse_sign = "-"

    m = re.match(r"(<[^>]+>)([^<].*)", label)
    if m:
        return m.groups()[0] + reverse_sign + m.groups()[1]
    else:
        return reverse_sign + label

def preprocess_constraints_for_meeting_schedule_editor(meeting, sessions):
    # process constraint names - we synthesize extra names to be able
    # to treat the concepts in the same manner as the modelled ones
    constraint_names = {n.pk: n for n in meeting.enabled_constraint_names()}

    joint_with_groups_constraint_name = ConstraintName(
        slug='joint_with_groups',
        name="Joint session with",
        editor_label="<i class=\"fa fa-clone\"></i>",
        order=8,
    )
    constraint_names[joint_with_groups_constraint_name.slug] = joint_with_groups_constraint_name

    ad_constraint_name = ConstraintName(
        slug='responsible_ad',
        name="Responsible AD",
        editor_label="<span class=\"encircled\">AD</span>",
        order=9,
    )
    constraint_names[ad_constraint_name.slug] = ad_constraint_name
    
    for n in list(constraint_names.values()):
        # add reversed version of the name
        reverse_n = ConstraintName(
            slug=n.slug + "-reversed",
            name="{} - reversed".format(n.name),
        )
        reverse_n.formatted_editor_label = mark_safe(reverse_editor_label(n.editor_label))
        constraint_names[reverse_n.slug] = reverse_n

        n.formatted_editor_label = mark_safe(n.editor_label)
        n.countless_formatted_editor_label = format_html(n.formatted_editor_label, count="") if "{count}" in n.formatted_editor_label else n.formatted_editor_label

    # convert human-readable rules in the database to constraints on actual sessions
    constraints = list(meeting.enabled_constraints().prefetch_related('target', 'person', 'timeranges'))

    # synthesize AD constraints - we can treat them as a special kind of 'bethere'
    responsible_ad_for_group = {}
    session_groups = set(s.group for s in sessions if s.group and s.group.parent and s.group.parent.type_id == 'area')
    meeting_time = datetime.datetime.combine(meeting.date, datetime.time(0, 0, 0))

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
                    a.modified = datetime.datetime.now()
                    a.save()
                swapped = True

            if not swapped:
                for a in lts_assignments:
                    a.delete()

def preprocess_meeting_important_dates(meetings):
    for m in meetings:
        m.cached_updated = m.updated()
        m.important_dates = m.importantdate_set.prefetch_related("name")
        for d in m.important_dates:
            d.midnight_cutoff = "UTC 23:59" in d.name.name
    
