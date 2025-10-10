# Copyright The IETF Trust 2007-2025, All Rights Reserved
# -*- coding: utf-8 -*-

import datetime
import inflect
from collections import defaultdict, OrderedDict

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.shortcuts import render, get_object_or_404, redirect
from django.http import Http404

from ietf.group.models import Group, GroupFeatures
from ietf.ietfauth.utils import has_role, role_required
from ietf.meeting.helpers import get_meeting
from ietf.meeting.models import Session, Meeting, Constraint, ResourceAssociation, SchedulingEvent
from ietf.meeting.utils import add_event_info_to_session_qs
from ietf.meeting.forms import (SessionRequestStatusForm, SessionRequestForm, allowed_conflicting_groups,
    JOINT_FOR_SESSION_CHOICES)
from ietf.name.models import SessionStatusName, ConstraintName
from ietf.secr.utils.decorators import check_permissions
from ietf.utils.mail import send_mail
from ietf.mailtrigger.utils import gather_address_lists

# -------------------------------------------------
# Globals
# -------------------------------------------------
# TODO: This needs to be replaced with something that pays attention to groupfeatures
AUTHORIZED_ROLES = (
    'WG Chair',
    'WG Secretary',
    'RG Chair',
    'IAB Group Chair',
    'Area Director',
    'Secretariat',
    'Team Chair',
    'IRTF Chair',
    'Program Chair',
    'Program Lead',
    'Program Secretary',
    'EDWG Chair')

# -------------------------------------------------
# Helper Functions
# -------------------------------------------------


def check_app_locked(meeting=None):
    '''
    This function returns True if the application is locked to non-secretariat users.
    '''
    if not meeting:
        meeting = get_meeting(days=14)
    return bool(meeting.session_request_lock_message)


def get_lock_message(meeting=None):
    '''
    Returns the message to display to non-secretariat users when the tool is locked.
    '''
    if not meeting:
        meeting = get_meeting(days=14)
    return meeting.session_request_lock_message


def get_my_groups(user, conclude=False):
    '''
    Takes a Django user object (from request)
    Returns a list of groups the user has access to.  Rules are as follows
    secretariat - has access to all groups
    area director - has access to all groups in their area
    wg chair or secretary - has access to their own group
    chair of irtf has access to all irtf groups

    If user=None than all groups are returned.
    concluded=True means include concluded groups.  Need this to upload materials for groups
    after they've been concluded.  it happens.
    '''
    my_groups = set()
    states = ['bof', 'proposed', 'active']
    if conclude:
        states.extend(['conclude', 'bof-conc'])

    all_groups = Group.objects.filter(type__features__has_meetings=True, state__in=states).order_by('acronym')
    if user is None or has_role(user, 'Secretariat'):
        return all_groups

    try:
        person = user.person
    except ObjectDoesNotExist:
        return list()

    for group in all_groups:
        if group.role_set.filter(person=person, name__in=('chair', 'secr', 'ad')):
            my_groups.add(group)
            continue
        if group.parent and group.parent.role_set.filter(person=person, name__in=('ad', 'chair')):
            my_groups.add(group)
            continue

    return list(my_groups)


def get_initial_session(sessions, prune_conflicts=False):
    '''
    This function takes a queryset of sessions ordered by 'id' for consistency.  It returns
    a dictionary to be used as the initial for a legacy session form
    '''
    initial = {}
    if len(sessions) == 0:
        return initial

    meeting = sessions[0].meeting
    group = sessions[0].group

    constraints = group.constraint_source_set.filter(meeting=meeting)  # all constraints with this group as source
    conflicts = constraints.filter(name__is_group_conflict=True)  # only the group conflict constraints

    if group.features.acts_like_wg:
        # even if there are three sessions requested, the old form has 2 in this field
        initial['num_session'] = min(sessions.count(), 2)
        initial['third_session'] = sessions.count() > 2
    else:
        initial['num_session'] = sessions.count()
        initial['third_session'] = False
    initial['attendees'] = sessions[0].attendees

    def valid_conflict(conflict):
        return conflict.target != sessions[0].group and allowed_conflicting_groups().filter(pk=conflict.target_id).exists()
    if prune_conflicts:
        conflicts = [c for c in conflicts if valid_conflict(c)]

    conflict_name_ids = set(c.name_id for c in conflicts)
    for name_id in conflict_name_ids:
        target_acros = [c.target.acronym for c in conflicts if c.name_id == name_id]
        initial['constraint_{}'.format(name_id)] = ' '.join(target_acros)

    initial['comments'] = sessions[0].comments
    initial['resources'] = sessions[0].resources.all()
    initial['bethere'] = [x.person for x in sessions[0].constraints().filter(name='bethere').select_related("person")]
    wg_adjacent = constraints.filter(name__slug='wg_adjacent')
    initial['adjacent_with_wg'] = wg_adjacent[0].target.acronym if wg_adjacent else None
    time_relation = constraints.filter(name__slug='time_relation')
    initial['session_time_relation'] = time_relation[0].time_relation if time_relation else None
    initial['session_time_relation_display'] = time_relation[0].get_time_relation_display if time_relation else None
    timeranges = constraints.filter(name__slug='timerange')
    initial['timeranges'] = timeranges[0].timeranges.all() if timeranges else []
    initial['timeranges_display'] = [t.desc for t in initial['timeranges']]
    for idx, session in enumerate(sessions):
        if session.joint_with_groups.count():
            initial['joint_with_groups'] = ' '.join(session.joint_with_groups_acronyms())
            initial['joint_for_session'] = str(idx + 1)
            initial['joint_for_session_display'] = dict(JOINT_FOR_SESSION_CHOICES)[initial['joint_for_session']]
    return initial


def inbound_session_conflicts_as_string(group, meeting):
    '''
    Takes a Group object and Meeting object and returns a string of other groups which have
    a conflict with this one
    '''
    constraints = group.constraint_target_set.filter(meeting=meeting, name__is_group_conflict=True)
    group_set = set(constraints.values_list('source__acronym', flat=True))  # set to de-dupe
    group_list = sorted(group_set)  # give a consistent order
    return ', '.join(group_list)


def get_outbound_conflicts(form: SessionRequestForm):
    """extract wg conflict constraint data from a SessionForm"""
    outbound_conflicts = []
    for conflictname, cfield_id in form.wg_constraint_field_ids():
        conflict_groups = form.cleaned_data[cfield_id]
        if len(conflict_groups) > 0:
            outbound_conflicts.append(dict(name=conflictname, groups=conflict_groups))
    return outbound_conflicts


def save_conflicts(group, meeting, conflicts, name):
    '''
    This function takes a Group, Meeting a string which is a list of Groups acronyms (conflicts),
    and the constraint name (conflict|conflic2|conflic3) and creates Constraint records
    '''
    constraint_name = ConstraintName.objects.get(slug=name)
    acronyms = conflicts.replace(',',' ').split()
    for acronym in acronyms:
        target = Group.objects.get(acronym=acronym)

        constraint = Constraint(source=group,
                                target=target,
                                meeting=meeting,
                                name=constraint_name)
        constraint.save()


def get_requester_text(person, group):
    """
    This function takes a Person object and a Group object and returns the text to use
    in the session request notification email, ie. Joe Smith, a Chair of the ancp
    working group
    """
    roles = group.role_set.filter(name__in=("chair", "secr", "ad"), person=person)
    if roles:
        rolename = str(roles[0].name)
        return "%s, %s of the %s %s" % (
            person.name,
            inflect.engine().a(rolename),
            group.acronym.upper(),
            group.type.verbose_name,
        )
    if person.role_set.filter(name="secr", group__acronym="secretariat"):
        return "%s, on behalf of the %s %s" % (
            person.name,
            group.acronym.upper(),
            group.type.verbose_name,
        )


def send_notification(group, meeting, login, sreq_data, session_data, action):
    '''
    This function generates email notifications for various session request activities.
    sreq_data argument is a dictionary of fields from the session request form
    session_data is an array of data from individual session subforms
    action argument is a string [new|update].
    '''
    (to_email, cc_list) = gather_address_lists('session_requested', group=group, person=login)
    from_email = (settings.SESSION_REQUEST_FROM_EMAIL)
    subject = '%s - New Meeting Session Request for IETF %s' % (group.acronym, meeting.number)
    template = 'meeting/session_request_notification.txt'

    # send email
    context = {}
    context['session'] = sreq_data
    context['group'] = group
    context['meeting'] = meeting
    context['login'] = login
    context['header'] = 'A new'
    context['requester'] = get_requester_text(login, group)

    # update overrides
    if action == 'update':
        subject = '%s - Update to a Meeting Session Request for IETF %s' % (group.acronym, meeting.number)
        context['header'] = 'An update to a'

    # if third session requested approval is required
    # change headers TO=ADs, CC=session-request, submitter and cochairs
    if len(session_data) > 2:
        (to_email, cc_list) = gather_address_lists('session_requested_long', group=group, person=login)
        subject = '%s - Request for meeting session approval for IETF %s' % (group.acronym, meeting.number)
        template = 'meeting/session_approval_notification.txt'
        # status_text = 'the %s Directors for approval' % group.parent

    context['session_lengths'] = [sd['requested_duration'] for sd in session_data]

    send_mail(None,
              to_email,
              from_email,
              subject,
              template,
              context,
              cc=cc_list)


def session_changed(session):
    latest_event = SchedulingEvent.objects.filter(session=session).order_by('-time', '-id').first()

    if latest_event and latest_event.status_id == "schedw" and session.meeting.schedule is not None:
        # send an email to iesg-secretariat to alert to change
        pass


def status_slug_for_new_session(session, session_number):
    if session.group.features.acts_like_wg and session_number == 2:
        return 'apprw'
    return 'schedw'

# -------------------------------------------------
# View Functions
# -------------------------------------------------


@role_required(*AUTHORIZED_ROLES)
def list_view(request):
    '''
    Display list of groups the user has access to.
    '''
    meeting = get_meeting(days=14)

    # check for locked flag
    is_locked = check_app_locked()
    if is_locked and not has_role(request.user, 'Secretariat'):
        message = get_lock_message()
        return render(request, 'meeting/session_request_locked.html', {
            'message': message,
            'meeting': meeting})

    scheduled_groups = []
    unscheduled_groups = []

    group_types = GroupFeatures.objects.filter(has_meetings=True).values_list('type', flat=True)

    my_groups = [g for g in get_my_groups(request.user, conclude=True) if g.type_id in group_types]

    sessions_by_group = defaultdict(list)
    for s in add_event_info_to_session_qs(Session.objects.filter(meeting=meeting, group__in=my_groups)).filter(current_status__in=['schedw', 'apprw', 'appr', 'sched']):
        sessions_by_group[s.group_id].append(s)

    for group in my_groups:
        group.meeting_sessions = sessions_by_group.get(group.pk, [])

        if group.pk in sessions_by_group:
            # include even if concluded as we need to to see that the
            # sessions are there
            scheduled_groups.append(group)
        else:
            if group.state_id not in ['conclude', 'bof-conc']:
                # too late for unscheduled if concluded
                unscheduled_groups.append(group)

    # warn if there are no associated groups
    if not scheduled_groups and not unscheduled_groups:
        messages.warning(request, 'The account %s is not associated with any groups.  If you have multiple Datatracker accounts you may try another or report a problem to %s' % (request.user, settings.SECRETARIAT_ACTION_EMAIL))

    # add session status messages for use in template
    for group in scheduled_groups:
        if not group.features.acts_like_wg or (len(group.meeting_sessions) < 3):
            group.status_message = group.meeting_sessions[0].current_status
        else:
            group.status_message = 'First two sessions: %s, Third session: %s' % (group.meeting_sessions[0].current_status, group.meeting_sessions[2].current_status)

    # add not meeting indicators for use in template
    for group in unscheduled_groups:
        if any(s.current_status == 'notmeet' for s in group.meeting_sessions):
            group.not_meeting = True

    return render(request, 'meeting/session_request_list.html', {
        'is_locked': is_locked,
        'meeting': meeting,
        'scheduled_groups': scheduled_groups,
        'unscheduled_groups': unscheduled_groups},
    )


@role_required('Secretariat')
def status(request):
    '''
    This view handles locking and unlocking of the session request tool to the public.
    '''
    meeting = get_meeting(days=14)
    is_locked = check_app_locked(meeting=meeting)

    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Back':
            return redirect('ietf.meeting.views_session_request.list_view')

        form = SessionRequestStatusForm(request.POST)

        if button_text == 'Lock':
            if form.is_valid():
                meeting.session_request_lock_message = form.cleaned_data['message']
                meeting.save()
                messages.success(request, 'Session Request Tool is now Locked')
                return redirect('ietf.meeting.views_session_request.list_view')

        elif button_text == 'Unlock':
            meeting.session_request_lock_message = ''
            meeting.save()
            messages.success(request, 'Session Request Tool is now Unlocked')
            return redirect('ietf.meeting.views_session_request.list_view')

    else:
        if is_locked:
            message = get_lock_message()
            initial = {'message': message}
            form = SessionRequestStatusForm(initial=initial)
        else:
            form = SessionRequestStatusForm()

    return render(request, 'meeting/session_request_status.html', {
        'is_locked': is_locked,
        'form': form},
    )


@check_permissions
def new_request(request, acronym):
    '''
    This view gathers details for a new session request.  The user proceeds to confirm()
    to create the request.
    '''
    group = get_object_or_404(Group, acronym=acronym)
    if len(group.features.session_purposes) == 0:
        raise Http404(f'Cannot request sessions for group "{acronym}"')
    meeting = get_meeting(days=14)
    session_conflicts = dict(inbound=inbound_session_conflicts_as_string(group, meeting))

    # check if app is locked
    is_locked = check_app_locked()
    if is_locked and not has_role(request.user, 'Secretariat'):
        messages.warning(request, "The Session Request Tool is closed")
        return redirect('ietf.meeting.views_session_request.list_view')

    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            return redirect('ietf.meeting.views_session_request.list_view')

        form = SessionRequestForm(group, meeting, request.POST, notifications_optional=has_role(request.user, "Secretariat"))
        if form.is_valid():
            return confirm(request, acronym)

    # the "previous" querystring causes the form to be returned
    # pre-populated with data from last meeeting's session request
    elif request.method == 'GET' and 'previous' in request.GET:
        latest_session = add_event_info_to_session_qs(Session.objects.filter(meeting__type_id='ietf', group=group)).exclude(current_status__in=['notmeet', 'deleted', 'canceled',]).order_by('-meeting__date').first()
        if latest_session:
            previous_meeting = Meeting.objects.get(number=latest_session.meeting.number)
            previous_sessions = add_event_info_to_session_qs(Session.objects.filter(meeting=previous_meeting, group=group)).exclude(current_status__in=['notmeet', 'deleted']).order_by('id')
            if not previous_sessions:
                messages.warning(request, 'This group did not meet at %s' % previous_meeting)
                return redirect('ietf.meeting.views_session_request.new_request', acronym=acronym)
            else:
                messages.info(request, 'Fetched session info from %s' % previous_meeting)
        else:
            messages.warning(request, 'Did not find any previous meeting')
            return redirect('ietf.meeting.views_session_request.new_request', acronym=acronym)

        initial = get_initial_session(previous_sessions, prune_conflicts=True)
        if 'resources' in initial:
            initial['resources'] = [x.pk for x in initial['resources']]
        form = SessionRequestForm(group, meeting, initial=initial, notifications_optional=has_role(request.user, "Secretariat"))

    else:
        initial = {}
        form = SessionRequestForm(group, meeting, initial=initial, notifications_optional=has_role(request.user, "Secretariat"))

    return render(request, 'meeting/session_request_form.html', {
        'meeting': meeting,
        'form': form,
        'group': group,
        'is_create': True,
        'session_conflicts': session_conflicts},
    )


@role_required(*AUTHORIZED_ROLES)
def confirm(request, acronym):
    '''
    This view displays details of the new session that has been requested for the user
    to confirm for submission.
    '''
    # FIXME: this should be using form.is_valid/form.cleaned_data - invalid input will make it crash
    group = get_object_or_404(Group, acronym=acronym)
    if len(group.features.session_purposes) == 0:
        raise Http404(f'Cannot request sessions for group "{acronym}"')
    meeting = get_meeting(days=14)
    form = SessionRequestForm(group, meeting, request.POST, hidden=True, notifications_optional=has_role(request.user, "Secretariat"))
    form.is_valid()

    login = request.user.person

    # check if request already exists for this group
    if add_event_info_to_session_qs(Session.objects.filter(group=group, meeting=meeting)).filter(Q(current_status__isnull=True) | ~Q(current_status__in=['deleted', 'notmeet'])):
        messages.warning(request, 'Sessions for working group %s have already been requested once.' % group.acronym)
        return redirect('ietf.meeting.views_session_request.list_view')

    session_data = form.data.copy()
    # use cleaned_data for the 'bethere' field so we get the Person instances
    session_data['bethere'] = form.cleaned_data['bethere'] if 'bethere' in form.cleaned_data else []
    if session_data.get('session_time_relation'):
        session_data['session_time_relation_display'] = dict(Constraint.TIME_RELATION_CHOICES)[session_data['session_time_relation']]
    if session_data.get('joint_for_session'):
        session_data['joint_for_session_display'] = dict(JOINT_FOR_SESSION_CHOICES)[session_data['joint_for_session']]
    if form.cleaned_data.get('timeranges'):
        session_data['timeranges_display'] = [t.desc for t in form.cleaned_data['timeranges']]
    session_data['resources'] = [ResourceAssociation.objects.get(pk=pk) for pk in request.POST.getlist('resources')]

    # extract wg conflict constraint data for the view / notifications
    outbound_conflicts = get_outbound_conflicts(form)

    button_text = request.POST.get('submit', '')
    if button_text == 'Cancel':
        messages.success(request, 'Session Request has been cancelled')
        return redirect('ietf.meeting.views_session_request.list_view')

    if request.method == 'POST' and button_text == 'Submit':
        # delete any existing session records with status = canceled or notmeet
        add_event_info_to_session_qs(Session.objects.filter(group=group, meeting=meeting)).filter(current_status__in=['canceled', 'notmeet']).delete()
        num_sessions = int(form.cleaned_data['num_session']) + (1 if form.cleaned_data['third_session'] else 0)
        # Create new session records
        form.session_forms.save()
        for count, sess_form in enumerate(form.session_forms[:num_sessions]):
            new_session = sess_form.instance
            SchedulingEvent.objects.create(
                session=new_session,
                status=SessionStatusName.objects.get(slug=status_slug_for_new_session(new_session, count)),
                by=login,
            )
            if 'resources' in form.data:
                new_session.resources.set(session_data['resources'])
            jfs = form.data.get('joint_for_session', '-1')
            if not jfs:  # jfs might be ''
                jfs = '-1'
            if int(jfs) == count + 1:  # count is zero-indexed
                groups_split = form.cleaned_data.get('joint_with_groups').replace(',', ' ').split()
                joint = Group.objects.filter(acronym__in=groups_split)
                new_session.joint_with_groups.set(joint)
            new_session.save()
            session_changed(new_session)

        # write constraint records
        for conflictname, cfield_id in form.wg_constraint_field_ids():
            save_conflicts(group, meeting, form.data.get(cfield_id, ''), conflictname.slug)
        save_conflicts(group, meeting, form.data.get('adjacent_with_wg', ''), 'wg_adjacent')

        if form.cleaned_data.get('session_time_relation'):
            cn = ConstraintName.objects.get(slug='time_relation')
            Constraint.objects.create(source=group, meeting=meeting, name=cn,
                                      time_relation=form.cleaned_data['session_time_relation'])

        if form.cleaned_data.get('timeranges'):
            cn = ConstraintName.objects.get(slug='timerange')
            constraint = Constraint.objects.create(source=group, meeting=meeting, name=cn)
            constraint.timeranges.set(form.cleaned_data['timeranges'])

        if 'bethere' in form.data:
            bethere_cn = ConstraintName.objects.get(slug='bethere')
            for p in session_data['bethere']:
                Constraint.objects.create(name=bethere_cn, source=group, person=p, meeting=new_session.meeting)

        # clear not meeting
        add_event_info_to_session_qs(Session.objects.filter(group=group, meeting=meeting)).filter(current_status='notmeet').delete()

        # send notification
        if form.cleaned_data.get("send_notifications"):
            session_data['outbound_conflicts'] = [f"{d['name']}: {d['groups']}" for d in outbound_conflicts]
            send_notification(
                group,
                meeting,
                login,
                session_data,
                [sf.cleaned_data for sf in form.session_forms[:num_sessions]],
                'new',
            )

        status_text = 'IETF Agenda to be scheduled'
        messages.success(request, 'Your request has been sent to %s' % status_text)
        return redirect('ietf.meeting.views_session_request.list_view')

    # POST from request submission
    session_conflicts = dict(
        outbound=outbound_conflicts,  # each is a dict with name and groups as keys
        inbound=inbound_session_conflicts_as_string(group, meeting),
    )
    if form.cleaned_data.get('third_session'):
        messages.warning(request, 'Note: Your request for a third session must be approved by an area director before being submitted to agenda@ietf.org.  Click "Submit" below to email an approval request to the area directors')

    return render(request, 'meeting/session_request_confirm.html', {
        'form': form,
        'session': session_data,
        'group': group,
        'meeting': meeting,
        'session_conflicts': session_conflicts},
    )


@role_required(*AUTHORIZED_ROLES)
def view_request(request, acronym, num=None):
    '''
    This view displays the session request info
    '''
    meeting = get_meeting(num, days=14)
    group = get_object_or_404(Group, acronym=acronym)
    query = Session.objects.filter(meeting=meeting, group=group)
    status_is_null = Q(current_status__isnull=True)
    status_allowed = ~Q(current_status__in=("canceled", "notmeet", "deleted"))
    sessions = (
        add_event_info_to_session_qs(query)
        .filter(status_is_null | status_allowed)
        .order_by("id")
    )

    # check if app is locked
    is_locked = check_app_locked()
    if is_locked:
        messages.warning(request, "The Session Request Tool is closed")

    # if there are no session requests yet, redirect to new session request page
    if not sessions:
        if is_locked:
            return redirect('ietf.meeting.views_session_request.list_view')
        else:
            return redirect('ietf.meeting.views_session_request.new_request', acronym=acronym)

    activities = [{
        'act_date': e.time.strftime('%b %d, %Y'),
        'act_time': e.time.strftime('%H:%M:%S'),
        'activity': e.status.name,
        'act_by': e.by,
    } for e in sessions[0].schedulingevent_set.select_related('status', 'by')]

    # gather outbound conflicts
    outbound_dict = OrderedDict()
    for obc in group.constraint_source_set.filter(meeting=meeting, name__is_group_conflict=True):
        if obc.name.slug not in outbound_dict:
            outbound_dict[obc.name.slug] = []
        outbound_dict[obc.name.slug].append(obc.target.acronym)

    session_conflicts = dict(
        inbound=inbound_session_conflicts_as_string(group, meeting),
        outbound=[dict(name=ConstraintName.objects.get(slug=slug), groups=' '.join(groups))
                  for slug, groups in outbound_dict.items()],
    )

    show_approve_button = False

    # if sessions include a 3rd session waiting approval and the user is a secretariat or AD of the group
    # display approve button
    if any(s.current_status == 'apprw' for s in sessions):
        if has_role(request.user, 'Secretariat') or group.parent.role_set.filter(name='ad', person=request.user.person):
            show_approve_button = True

    # build session dictionary (like querydict from new session request form) for use in template
    session = get_initial_session(sessions)

    return render(request, 'meeting/session_request_view.html', {
        'can_edit': (not is_locked) or has_role(request.user, 'Secretariat'),
        'can_cancel': (not is_locked) or has_role(request.user, 'Secretariat'),
        'session': session,  # legacy processed data
        'sessions': sessions,  # actual session instances
        'activities': activities,
        'meeting': meeting,
        'group': group,
        'session_conflicts': session_conflicts,
        'show_approve_button': show_approve_button},
    )


@check_permissions
def edit_request(request, acronym, num=None):
    '''
    This view allows the user to edit details of the session request
    '''
    meeting = get_meeting(num, days=14)
    group = get_object_or_404(Group, acronym=acronym)
    if len(group.features.session_purposes) == 0:
        raise Http404(f'Cannot request sessions for group "{acronym}"')
    sessions = add_event_info_to_session_qs(
        Session.objects.filter(group=group, meeting=meeting)
    ).filter(
        Q(current_status__isnull=True) | ~Q(current_status__in=['canceled', 'notmeet', 'deleted'])
    ).order_by('id')
    initial = get_initial_session(sessions)

    if 'resources' in initial:
        initial['resources'] = [x.pk for x in initial['resources']]

    # check if app is locked
    is_locked = check_app_locked(meeting=meeting)
    if is_locked:
        messages.warning(request, "The Session Request Tool is closed")

    # Only need the inbound conflicts here, the form itself renders the outbound
    session_conflicts = dict(
        inbound=inbound_session_conflicts_as_string(group, meeting),
    )
    login = request.user.person

    first_session = Session()
    if (len(sessions) > 0):
        first_session = sessions[0]

    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            return redirect('ietf.meeting.views_session_request.view_request', acronym=acronym)

        form = SessionRequestForm(group, meeting, request.POST, initial=initial, notifications_optional=has_role(request.user, "Secretariat"))
        if form.is_valid():
            if form.has_changed():
                changed_session_forms = [sf for sf in form.session_forms.forms_to_keep if sf.has_changed()]
                form.session_forms.save()
                for n, subform in enumerate(form.session_forms):
                    if subform.instance in form.session_forms.new_objects:
                        SchedulingEvent.objects.create(
                            session=subform.instance,
                            status_id=status_slug_for_new_session(subform.instance, n),
                            by=request.user.person,
                        )
                for sf in changed_session_forms:
                    session_changed(sf.instance)

                # New sessions may have been created, refresh the sessions list
                sessions = add_event_info_to_session_qs(
                    Session.objects.filter(group=group, meeting=meeting)).filter(
                    Q(current_status__isnull=True) | ~Q(
                        current_status__in=['canceled', 'notmeet'])).order_by('id')

                if 'joint_with_groups' in form.changed_data or 'joint_for_session' in form.changed_data:
                    joint_with_groups_list = form.cleaned_data.get('joint_with_groups').replace(',', ' ').split()
                    new_joint_with_groups = Group.objects.filter(acronym__in=joint_with_groups_list)
                    new_joint_for_session_idx = int(form.data.get('joint_for_session', '-1')) - 1
                    current_joint_for_session_idx = None
                    current_joint_with_groups = None
                    for idx, sess in enumerate(sessions):
                        if sess.joint_with_groups.count():
                            current_joint_for_session_idx = idx
                            current_joint_with_groups = sess.joint_with_groups.all()

                    if current_joint_with_groups != new_joint_with_groups or current_joint_for_session_idx != new_joint_for_session_idx:
                        if current_joint_for_session_idx is not None:
                            sessions[current_joint_for_session_idx].joint_with_groups.clear()
                            session_changed(sessions[current_joint_for_session_idx])
                        sessions[new_joint_for_session_idx].joint_with_groups.set(new_joint_with_groups)
                        session_changed(sessions[new_joint_for_session_idx])

                # Update sessions to match changes to shared form fields
                if 'attendees' in form.changed_data:
                    sessions.update(attendees=form.cleaned_data['attendees'])
                if 'comments' in form.changed_data:
                    sessions.update(comments=form.cleaned_data['comments'])

                # Handle constraints
                for cname, cfield_id in form.wg_constraint_field_ids():
                    if cfield_id in form.changed_data:
                        Constraint.objects.filter(meeting=meeting, source=group, name=cname.slug).delete()
                        save_conflicts(group, meeting, form.cleaned_data[cfield_id], cname.slug)

                # see if any inactive constraints should be deleted
                for cname, field_id in form.inactive_wg_constraint_field_ids():
                    if form.cleaned_data[field_id]:
                        Constraint.objects.filter(meeting=meeting, source=group, name=cname.slug).delete()

                if 'adjacent_with_wg' in form.changed_data:
                    Constraint.objects.filter(meeting=meeting, source=group, name='wg_adjacent').delete()
                    save_conflicts(group, meeting, form.cleaned_data['adjacent_with_wg'], 'wg_adjacent')

                if 'resources' in form.changed_data:
                    new_resource_ids = form.cleaned_data['resources']
                    new_resources = [ResourceAssociation.objects.get(pk=a)
                                     for a in new_resource_ids]
                    first_session.resources = new_resources

                if 'bethere' in form.changed_data and set(form.cleaned_data['bethere']) != set(initial['bethere']):
                    first_session.constraints().filter(name='bethere').delete()
                    bethere_cn = ConstraintName.objects.get(slug='bethere')
                    for p in form.cleaned_data['bethere']:
                        Constraint.objects.create(name=bethere_cn, source=group, person=p, meeting=first_session.meeting)

                if 'session_time_relation' in form.changed_data:
                    Constraint.objects.filter(meeting=meeting, source=group, name='time_relation').delete()
                    if form.cleaned_data['session_time_relation']:
                        cn = ConstraintName.objects.get(slug='time_relation')
                        Constraint.objects.create(source=group, meeting=meeting, name=cn,
                                                  time_relation=form.cleaned_data['session_time_relation'])

                if 'timeranges' in form.changed_data:
                    Constraint.objects.filter(meeting=meeting, source=group, name='timerange').delete()
                    if form.cleaned_data['timeranges']:
                        cn = ConstraintName.objects.get(slug='timerange')
                        constraint = Constraint.objects.create(source=group, meeting=meeting, name=cn)
                        constraint.timeranges.set(form.cleaned_data['timeranges'])

                # deprecated
                # log activity
                # add_session_activity(group,'Session Request was updated',meeting,user)

                # send notification
                if form.cleaned_data.get("send_notifications"):
                    outbound_conflicts = get_outbound_conflicts(form)
                    session_data = form.cleaned_data.copy()  # do not add things to the original cleaned_data
                    session_data['outbound_conflicts'] = [f"{d['name']}: {d['groups']}" for d in outbound_conflicts]
                    send_notification(
                        group,
                        meeting,
                        login,
                        session_data,
                        [sf.cleaned_data for sf in form.session_forms.forms_to_keep],
                        'update',
                    )

            messages.success(request, 'Session Request updated')
            return redirect('ietf.meeting.views_session_request.view_request', acronym=acronym)

    else:  # method is not POST
        # gather outbound conflicts for initial value
        outbound_constraints = defaultdict(list)
        for obc in group.constraint_source_set.filter(meeting=meeting, name__is_group_conflict=True):
            outbound_constraints[obc.name.slug].append(obc.target.acronym)
        for slug, groups in outbound_constraints.items():
            initial['constraint_{}'.format(slug)] = ' '.join(groups)

        if not sessions:
            return redirect('ietf.meeting.views_session_request.new_request', acronym=acronym)
        form = SessionRequestForm(group, meeting, initial=initial, notifications_optional=has_role(request.user, "Secretariat"))

    return render(request, 'meeting/session_request_form.html', {
        'is_locked': is_locked and not has_role(request.user, 'Secretariat'),
        'meeting': meeting,
        'form': form,
        'group': group,
        'is_create': False,
        'session_conflicts': session_conflicts},
    )


@check_permissions
def approve_request(request, acronym):
    '''
    This view approves the third session.  For use by ADs or Secretariat.
    '''
    meeting = get_meeting(days=14)
    group = get_object_or_404(Group, acronym=acronym)

    session = add_event_info_to_session_qs(Session.objects.filter(meeting=meeting, group=group)).filter(current_status='apprw').first()
    if session is None:
        raise Http404

    if has_role(request.user, 'Secretariat') or group.parent.role_set.filter(name='ad', person=request.user.person):
        SchedulingEvent.objects.create(
            session=session,
            status=SessionStatusName.objects.get(slug='appr'),
            by=request.user.person,
        )
        session_changed(session)

        messages.success(request, 'Third session approved')
        return redirect('ietf.meeting.views_session_request.view_request', acronym=acronym)
    else:
        # if an unauthorized user gets here return error
        messages.error(request, 'Not authorized to approve the third session')
        return redirect('ietf.meeting.views_session_request.view_request', acronym=acronym)


@check_permissions
def no_session(request, acronym):
    '''
    The user has indicated that the named group will not be having a session this IETF meeting.
    Actions:
    - send notification
    - update session_activity log
    '''
    meeting = get_meeting(days=14)
    group = get_object_or_404(Group, acronym=acronym)
    login = request.user.person

    # delete canceled record if there is one
    add_event_info_to_session_qs(Session.objects.filter(group=group, meeting=meeting)).filter(current_status='canceled').delete()

    # skip if state is already notmeet
    if add_event_info_to_session_qs(Session.objects.filter(group=group, meeting=meeting)).filter(current_status='notmeet'):
        messages.info(request, 'The group %s is already marked as not meeting' % group.acronym)
        return redirect('ietf.meeting.views_session_request.list_view')

    session = Session.objects.create(
        group=group,
        meeting=meeting,
        requested_duration=datetime.timedelta(0),
        type_id='regular',
        purpose_id='regular',
        has_onsite_tool=group.features.acts_like_wg,
    )
    SchedulingEvent.objects.create(
        session=session,
        status=SessionStatusName.objects.get(slug='notmeet'),
        by=login,
    )
    session_changed(session)

    # send notification
    (to_email, cc_list) = gather_address_lists('session_request_not_meeting', group=group, person=login)
    from_email = (settings.SESSION_REQUEST_FROM_EMAIL)
    subject = '%s - Not having a session at IETF %s' % (group.acronym, meeting.number)
    send_mail(request, to_email, from_email, subject, 'meeting/session_not_meeting_notification.txt',
              {'login': login,
               'group': group,
               'meeting': meeting}, cc=cc_list)

    # deprecated?
    # log activity
    # text = 'A message was sent to notify not having a session at IETF %d' % meeting.meeting_num
    # add_session_activity(group,text,meeting,request.person)

    # redirect
    messages.success(request, 'A message was sent to notify not having a session at IETF %s' % meeting.number)
    return redirect('ietf.meeting.views_session_request.list_view')


@check_permissions
def cancel_request(request, acronym):
    '''
    This view cancels a session request and sends a notification.
    To cancel, or withdraw the request set status = deleted.
    "canceled" status is used by the secretariat.

    NOTE: this function can also be called after a session has been
    scheduled during the period when the session request tool is
    reopened.  In this case be sure to clear the timeslot assignment as well.
    '''
    meeting = get_meeting(days=14)
    group = get_object_or_404(Group, acronym=acronym)
    sessions = Session.objects.filter(meeting=meeting, group=group).order_by('id')
    login = request.user.person

    # delete conflicts
    Constraint.objects.filter(meeting=meeting, source=group).delete()

    # mark sessions as deleted
    for session in sessions:
        SchedulingEvent.objects.create(
            session=session,
            status=SessionStatusName.objects.get(slug='deleted'),
            by=request.user.person,
        )
        session_changed(session)

        # clear schedule assignments if already scheduled
        session.timeslotassignments.all().delete()

    # send notifitcation
    (to_email, cc_list) = gather_address_lists('session_request_cancelled', group=group, person=login)
    from_email = (settings.SESSION_REQUEST_FROM_EMAIL)
    subject = '%s - Cancelling a meeting request for IETF %s' % (group.acronym, meeting.number)
    send_mail(request, to_email, from_email, subject, 'meeting/session_cancel_notification.txt',
              {'requester': get_requester_text(login, group),
               'meeting': meeting}, cc=cc_list)

    messages.success(request, 'The %s Session Request has been cancelled' % group.acronym)
    return redirect('ietf.meeting.views_session_request.list_view')
