# Copyright The IETF Trust 2013-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime
from collections import defaultdict

from django.conf import settings
from django.contrib import messages
from django.db.models import Q
from django.shortcuts import render, get_object_or_404, redirect
from django.http import Http404

import debug                            # pyflakes:ignore

from ietf.group.models import Group, GroupFeatures
from ietf.ietfauth.utils import has_role, role_required
from ietf.meeting.models import Meeting, Session, Constraint, ResourceAssociation, SchedulingEvent
from ietf.meeting.helpers import get_meeting
from ietf.meeting.utils import add_event_info_to_session_qs
from ietf.name.models import SessionStatusName, ConstraintName
from ietf.secr.sreq.forms import (SessionForm, ToolStatusForm, allowed_conflicting_groups,
    JOINT_FOR_SESSION_CHOICES, VirtualSessionForm)
from ietf.secr.utils.decorators import check_permissions
from ietf.secr.utils.group import get_my_groups
from ietf.utils.mail import send_mail
from ietf.person.models import Person
from ietf.mailtrigger.utils import gather_address_lists

# -------------------------------------------------
# Globals
# -------------------------------------------------
# TODO: This needs to be replaced with something that pays attention to groupfeatures
AUTHORIZED_ROLES=('WG Chair','WG Secretary','RG Chair','IAB Group Chair','Area Director','Secretariat','Team Chair','IRTF Chair','Program Chair','Program Lead','Program Secretary')

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
    conflicts = group.constraint_source_set.filter(meeting=meeting)

    # even if there are three sessions requested, the old form has 2 in this field
    initial['num_session'] = min(sessions.count(), 2)

    # accessing these foreign key fields throw errors if they are unset so we
    # need to catch these
    initial['length_session1'] = str(sessions[0].requested_duration.seconds)
    try:
        initial['length_session2'] = str(sessions[1].requested_duration.seconds)
        initial['length_session3'] = str(sessions[2].requested_duration.seconds)
    except IndexError:
        pass
    initial['attendees'] = sessions[0].attendees

    def valid_conflict(conflict):
        return conflict.target != sessions[0].group and allowed_conflicting_groups().filter(pk=conflict.target_id).exists()

    initial['conflict1'] = ' '.join(c.target.acronym for c in conflicts.filter(name__slug='conflict') if not prune_conflicts or valid_conflict(c))
    initial['conflict2'] = ' '.join(c.target.acronym for c in conflicts.filter(name__slug='conflic2') if not prune_conflicts or valid_conflict(c))
    initial['conflict3'] = ' '.join(c.target.acronym for c in conflicts.filter(name__slug='conflic3') if not prune_conflicts or valid_conflict(c))
    initial['comments'] = sessions[0].comments
    initial['resources'] = sessions[0].resources.all()
    initial['bethere'] = [x.person for x in sessions[0].constraints().filter(name='bethere').select_related("person")]
    wg_adjacent = conflicts.filter(name__slug='wg_adjacent')
    initial['adjacent_with_wg'] = wg_adjacent[0].target.acronym if wg_adjacent else None
    time_relation = conflicts.filter(name__slug='time_relation')
    initial['session_time_relation'] = time_relation[0].time_relation if time_relation else None
    initial['session_time_relation_display'] = time_relation[0].get_time_relation_display if time_relation else None
    timeranges = conflicts.filter(name__slug='timerange')
    initial['timeranges'] = timeranges[0].timeranges.all() if timeranges else []
    initial['timeranges_display'] = [t.desc for t in initial['timeranges']]
    for idx, session in enumerate(sessions):
        if session.joint_with_groups.count():
            initial['joint_with_groups'] = ' '.join(session.joint_with_groups_acronyms())
            initial['joint_for_session'] = str(idx + 1)
            initial['joint_for_session_display'] = dict(JOINT_FOR_SESSION_CHOICES)[initial['joint_for_session']]
    return initial

def get_lock_message(meeting=None):
    '''
    Returns the message to display to non-secretariat users when the tool is locked.
    '''
    if not meeting:
        meeting = get_meeting(days=14)
    return meeting.session_request_lock_message

def get_requester_text(person,group):
    '''
    This function takes a Person object and a Group object and returns the text to use in the
    session request notification email, ie. Joe Smith, a Chair of the ancp working group
    '''
    roles = group.role_set.filter(name__in=('chair','secr'),person=person)
    if roles:
        return '%s, a %s of the %s working group' % (person.ascii, roles[0].name, group.acronym)
    if group.parent and group.parent.role_set.filter(name='ad',person=person):
        return '%s, a %s Area Director' % (person.ascii, group.parent.acronym.upper())
    if person.role_set.filter(name='secr',group__acronym='secretariat'):
        return '%s, on behalf of the %s working group' % (person.ascii, group.acronym)

def get_session_form_class():
    meeting = get_meeting(days=14)
    if meeting.number in settings.SECR_VIRTUAL_MEETINGS:
        return VirtualSessionForm
    else:
        return SessionForm

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

def send_notification(group,meeting,login,session,action):
    '''
    This function generates email notifications for various session request activities.
    session argument is a dictionary of fields from the session request form
    action argument is a string [new|update].
    '''
    (to_email, cc_list) = gather_address_lists('session_requested',group=group,person=login)
    from_email = (settings.SESSION_REQUEST_FROM_EMAIL)
    subject = '%s - New Meeting Session Request for IETF %s' % (group.acronym, meeting.number)
    template = 'sreq/session_request_notification.txt'

    # send email
    context = {}
    context['session'] = session
    context['group'] = group
    context['meeting'] = meeting
    context['login'] = login
    context['header'] = 'A new'
    context['requester'] = get_requester_text(login,group)

    # update overrides
    if action == 'update':
        subject = '%s - Update to a Meeting Session Request for IETF %s' % (group.acronym, meeting.number)
        context['header'] = 'An update to a'

    # if third session requested approval is required
    # change headers TO=ADs, CC=session-request, submitter and cochairs
    if session.get('length_session3',None):
        context['session']['num_session'] = 3
        (to_email, cc_list) = gather_address_lists('session_requested_long',group=group,person=login)
        subject = '%s - Request for meeting session approval for IETF %s' % (group.acronym, meeting.number)
        template = 'sreq/session_approval_notification.txt'
        #status_text = 'the %s Directors for approval' % group.parent
    send_mail(None,
              to_email,
              from_email,
              subject,
              template,
              context,
              cc=cc_list)

def session_conflicts_as_string(group, meeting):
    '''
    Takes a Group object and Meeting object and returns a string of other groups which have
    a conflict with this one
    '''
    groups = group.constraint_target_set.filter(meeting=meeting, name__in=['conflict', 'conflic2', 'conflic3'])
    group_list = [g.source.acronym for g in groups]
    return ', '.join(group_list)

# -------------------------------------------------
# View Functions
# -------------------------------------------------
@check_permissions
def approve(request, acronym):
    '''
    This view approves the third session.  For use by ADs or Secretariat.
    '''
    meeting = get_meeting(days=14)
    group = get_object_or_404(Group, acronym=acronym)

    session = add_event_info_to_session_qs(Session.objects.filter(meeting=meeting, group=group)).filter(current_status='apprw').first()
    if session is None:
        raise Http404

    if has_role(request.user,'Secretariat') or group.parent.role_set.filter(name='ad',person=request.user.person):
        SchedulingEvent.objects.create(
            session=session,
            status=SessionStatusName.objects.get(slug='appr'),
            by=request.user.person,
        )
        session_changed(session)

        messages.success(request, 'Third session approved')
        return redirect('ietf.secr.sreq.views.view', acronym=acronym)
    else:
        # if an unauthorized user gets here return error
        messages.error(request, 'Not authorized to approve the third session')
        return redirect('ietf.secr.sreq.views.view', acronym=acronym)

@check_permissions
def cancel(request, acronym):
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
    sessions = Session.objects.filter(meeting=meeting,group=group).order_by('id')
    login = request.user.person

    # delete conflicts
    Constraint.objects.filter(meeting=meeting,source=group).delete()

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
    (to_email, cc_list) = gather_address_lists('session_request_cancelled',group=group,person=login)
    from_email = (settings.SESSION_REQUEST_FROM_EMAIL)
    subject = '%s - Cancelling a meeting request for IETF %s' % (group.acronym, meeting.number)
    send_mail(request, to_email, from_email, subject, 'sreq/session_cancel_notification.txt',
              {'requester':get_requester_text(login,group),
               'meeting':meeting}, cc=cc_list)

    messages.success(request, 'The %s Session Request has been cancelled' % group.acronym)
    return redirect('ietf.secr.sreq.views.main')

@role_required(*AUTHORIZED_ROLES)
def confirm(request, acronym):
    '''
    This view displays details of the new session that has been requested for the user
    to confirm for submission.
    '''
    # FIXME: this should be using form.is_valid/form.cleaned_data - invalid input will make it crash
    group = get_object_or_404(Group,acronym=acronym)
    meeting = get_meeting(days=14)
    FormClass = get_session_form_class()

    form = FormClass(group, request.POST, hidden=True)
    form.is_valid()
    
    login = request.user.person

    # check if request already exists for this group
    if add_event_info_to_session_qs(Session.objects.filter(group=group, meeting=meeting)).filter(Q(current_status__isnull=True) | ~Q(current_status__in=['deleted', 'notmeet'])):
        messages.warning(request, 'Sessions for working group %s have already been requested once.' % group.acronym)
        return redirect('ietf.secr.sreq.views.main')
                
    session_data = form.data.copy()
    if 'bethere' in session_data:
        person_id_list = [ id for id in form.data['bethere'].split(',') if id ]
        session_data['bethere'] = Person.objects.filter(pk__in=person_id_list)
    if session_data.get('session_time_relation'):
        session_data['session_time_relation_display'] = dict(Constraint.TIME_RELATION_CHOICES)[session_data['session_time_relation']]
    if session_data.get('joint_for_session'):
        session_data['joint_for_session_display'] = dict(JOINT_FOR_SESSION_CHOICES)[session_data['joint_for_session']]
    if form.cleaned_data.get('timeranges'):
        session_data['timeranges_display'] = [t.desc for t in form.cleaned_data['timeranges']]
    session_data['resources'] = [ ResourceAssociation.objects.get(pk=pk) for pk in request.POST.getlist('resources') ]
    
    button_text = request.POST.get('submit', '')
    if button_text == 'Cancel':
        messages.success(request, 'Session Request has been cancelled')
        return redirect('ietf.secr.sreq.views.main')

    button_text = request.POST.get('submit', '')
    if button_text == 'Cancel':
        messages.success(request, 'Session Request has been cancelled')
        return redirect('ietf.secr.sreq.views.main')

    if request.method == 'POST' and button_text == 'Submit':
        # delete any existing session records with status = canceled or notmeet
        add_event_info_to_session_qs(Session.objects.filter(group=group, meeting=meeting)).filter(current_status__in=['canceled', 'notmeet']).delete()

        # create new session records
        count = 0
        # lenth_session2 and length_session3 fields might be disabled by javascript and so
        # wouldn't appear in form data
        for duration in (form.data.get('length_session1',None),form.data.get('length_session2',None),form.data.get('length_session3',None)):
            count += 1
            if duration:
                slug = 'apprw' if count == 3 else 'schedw'
                new_session = Session.objects.create(
                    meeting=meeting,
                    group=group,
                    attendees=form.cleaned_data['attendees'],
                    requested_duration=datetime.timedelta(0,int(duration)),
                    comments=form.cleaned_data['comments'],
                    type_id='regular',
                )
                SchedulingEvent.objects.create(
                    session=new_session,
                    status=SessionStatusName.objects.get(slug=slug),
                    by=login,
                )
                if 'resources' in form.data:
                    new_session.resources.set(session_data['resources'])
                jfs = form.data.get('joint_for_session', '-1')
                if not jfs: # jfs might be ''
                    jfs = '-1'
                if int(jfs) == count:
                    groups_split = form.cleaned_data.get('joint_with_groups').replace(',',' ').split()
                    joint = Group.objects.filter(acronym__in=groups_split)
                    new_session.joint_with_groups.set(joint)
                session_changed(new_session)

        # write constraint records
        save_conflicts(group,meeting,form.data.get('conflict1',''),'conflict')
        save_conflicts(group,meeting,form.data.get('conflict2',''),'conflic2')
        save_conflicts(group,meeting,form.data.get('conflict3',''),'conflic3')
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
        send_notification(group,meeting,login,session_data,'new')

        status_text = 'IETF Agenda to be scheduled'
        messages.success(request, 'Your request has been sent to %s' % status_text)
        return redirect('ietf.secr.sreq.views.main')

    # POST from request submission
    session_conflicts = session_conflicts_as_string(group, meeting)

    return render(request, 'sreq/confirm.html', {
        'form': form,
        'is_virtual': meeting.number in settings.SECR_VIRTUAL_MEETINGS,
        'session': session_data,
        'group': group,
        'session_conflicts': session_conflicts},
    )

#Move this into make_initial
def add_essential_people(group,initial):
    # This will be easier when the form uses Person instead of Email
    people = set()
    if 'bethere' in initial:
        people.update(initial['bethere'])
    people.update(Person.objects.filter(role__group=group, role__name__in=['chair','ad']))
    initial['bethere'] = list(people)
    

def session_changed(session):
    latest_event = SchedulingEvent.objects.filter(session=session).order_by('-time', '-id').first()

    if latest_event and latest_event.status_id == "schedw" and session.meeting.schedule != None:
        # send an email to iesg-secretariat to alert to change
        pass

@check_permissions
def edit(request, acronym, num=None):
    '''
    This view allows the user to edit details of the session request
    '''
    meeting = get_meeting(num,days=14)
    group = get_object_or_404(Group, acronym=acronym)
    sessions = add_event_info_to_session_qs(Session.objects.filter(group=group, meeting=meeting)).filter(Q(current_status__isnull=True) | ~Q(current_status__in=['canceled', 'notmeet'])).order_by('id')
    sessions_count = sessions.count()
    initial = get_initial_session(sessions)
    FormClass = get_session_form_class()

    if 'resources' in initial:
        initial['resources'] = [x.pk for x in initial['resources']]

    # check if app is locked
    is_locked = check_app_locked(meeting=meeting)
    if is_locked:
        messages.warning(request, "The Session Request Tool is closed")
        
    session_conflicts = session_conflicts_as_string(group, meeting)
    login = request.user.person

    session = Session()
    if(len(sessions) > 0):
        session = sessions[0]

    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            return redirect('ietf.secr.sreq.views.view', acronym=acronym)

        form = FormClass(group, request.POST, initial=initial)
        if form.is_valid():
            if form.has_changed():
                # might be cleaner to simply delete and rewrite all records (but maintain submitter?)
                # adjust duration or add sessions
                # session 1
                if 'length_session1' in form.changed_data:
                    session = sessions[0]
                    session.requested_duration = datetime.timedelta(0,int(form.cleaned_data['length_session1']))
                    session.save()
                    session_changed(session)

                # session 2
                if 'length_session2' in form.changed_data:
                    length_session2 = form.cleaned_data['length_session2']
                    if length_session2 == '':
                        sessions[1].delete()
                    elif sessions_count < 2:
                        duration = datetime.timedelta(0,int(form.cleaned_data['length_session2']))
                        new_session = Session.objects.create(
                            meeting=meeting,
                            group=group,
                            attendees=form.cleaned_data['attendees'],
                            requested_duration=duration,
                            comments=form.cleaned_data['comments'],
                            type_id='regular',
                        )
                        SchedulingEvent.objects.create(
                            session=new_session,
                            status=SessionStatusName.objects.get(slug='schedw'),
                            by=request.user.person,
                        )
                    else:
                        duration = datetime.timedelta(0,int(form.cleaned_data['length_session2']))
                        session = sessions[1]
                        session.requested_duration = duration
                        session.save()

                # session 3
                if 'length_session3' in form.changed_data:
                    length_session3 = form.cleaned_data['length_session3']
                    if length_session3 == '':
                        sessions[2].delete()
                    elif sessions_count < 3:
                        duration = datetime.timedelta(0,int(form.cleaned_data['length_session3']))
                        new_session = Session.objects.create(
                            meeting=meeting,
                            group=group,
                            attendees=form.cleaned_data['attendees'],
                            requested_duration=duration,
                            comments=form.cleaned_data['comments'],
                            type_id='regular',
                        )
                        SchedulingEvent.objects.create(
                            session=new_session,
                            status=SessionStatusName.objects.get(slug='apprw'),
                            by=request.user.person,
                        )
                    else:
                        duration = datetime.timedelta(0,int(form.cleaned_data['length_session3']))
                        session = sessions[2]
                        session.requested_duration = duration
                        session.save()
                        session_changed(session)

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
                    for idx, session in enumerate(sessions):
                        if session.joint_with_groups.count():
                            current_joint_for_session_idx = idx
                            current_joint_with_groups = session.joint_with_groups.all()

                    if current_joint_with_groups != new_joint_with_groups or current_joint_for_session_idx != new_joint_for_session_idx:
                        if current_joint_for_session_idx is not None:
                            sessions[current_joint_for_session_idx].joint_with_groups.clear()
                            session_changed(sessions[current_joint_for_session_idx])
                        sessions[new_joint_for_session_idx].joint_with_groups.set(new_joint_with_groups)
                        session_changed(sessions[new_joint_for_session_idx])
                            
                if 'attendees' in form.changed_data:
                    sessions.update(attendees=form.cleaned_data['attendees'])
                if 'comments' in form.changed_data:
                    sessions.update(comments=form.cleaned_data['comments'])
                if 'conflict1' in form.changed_data:
                    Constraint.objects.filter(meeting=meeting,source=group,name='conflict').delete()
                    save_conflicts(group,meeting,form.cleaned_data['conflict1'],'conflict')
                if 'conflict2' in form.changed_data:
                    Constraint.objects.filter(meeting=meeting,source=group,name='conflic2').delete()
                    save_conflicts(group,meeting,form.cleaned_data['conflict2'],'conflic2')
                if 'conflict3' in form.changed_data:
                    Constraint.objects.filter(meeting=meeting,source=group,name='conflic3').delete()
                    save_conflicts(group,meeting,form.cleaned_data['conflict3'],'conflic3')
                if 'adjacent_with_wg' in form.changed_data:
                    Constraint.objects.filter(meeting=meeting, source=group, name='wg_adjacent').delete()
                    save_conflicts(group, meeting, form.cleaned_data['adjacent_with_wg'], 'wg_adjacent')

                if 'resources' in form.changed_data:
                    new_resource_ids = form.cleaned_data['resources']
                    new_resources = [ ResourceAssociation.objects.get(pk=a)
                                      for a in new_resource_ids]
                    session.resources = new_resources

                if 'bethere' in form.changed_data and set(form.cleaned_data['bethere'])!=set(initial['bethere']):
                    session.constraints().filter(name='bethere').delete()
                    bethere_cn = ConstraintName.objects.get(slug='bethere')
                    for p in form.cleaned_data['bethere']:
                        Constraint.objects.create(name=bethere_cn, source=group, person=p, meeting=session.meeting)

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
                #add_session_activity(group,'Session Request was updated',meeting,user)

                # send notification
                send_notification(group,meeting,login,form.cleaned_data,'update')

            # nuke any cache that might be lingering around.
            from ietf.meeting.helpers import session_constraint_expire
            session_constraint_expire(request,session)

            messages.success(request, 'Session Request updated')
            return redirect('ietf.secr.sreq.views.view', acronym=acronym)

    else:
        if not sessions:
            return redirect('ietf.secr.sreq.views.new', acronym=acronym)
        form = FormClass(group, initial=initial)

    return render(request, 'sreq/edit.html', {
        'is_locked': is_locked,
        'is_virtual': meeting.number in settings.SECR_VIRTUAL_MEETINGS,
        'meeting': meeting,
        'form': form,
        'group': group,
        'session_conflicts': session_conflicts},
    )

@role_required(*AUTHORIZED_ROLES)
def main(request):
    '''
    Display list of groups the user has access to.

    Template variables
    form: a select box populated with unscheduled groups
    meeting: the current meeting
    scheduled_sessions:
    '''
    # check for locked flag
    is_locked = check_app_locked()

    if is_locked and not has_role(request.user,'Secretariat'):
        message = get_lock_message()
        return render(request, 'sreq/locked.html', {
        'message': message},
    )

    meeting = get_meeting(days=14)

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
        if len(group.meeting_sessions) < 3:
            group.status_message = group.meeting_sessions[0].current_status
        else:
            group.status_message = 'First two sessions: %s, Third session: %s' % (group.meeting_sessions[0].current_status, group.meeting_sessions[2].current_status)

    # add not meeting indicators for use in template
    for group in unscheduled_groups:
        if any(s.current_status == 'notmeet' for s in group.meeting_sessions):
            group.not_meeting = True

    return render(request, 'sreq/main.html', {
        'is_locked': is_locked,
        'meeting': meeting,
        'scheduled_groups': scheduled_groups,
        'unscheduled_groups': unscheduled_groups},
    )

@check_permissions
def new(request, acronym):
    '''
    This view gathers details for a new session request.  The user proceeds to confirm()
    to create the request.
    '''
    group = get_object_or_404(Group, acronym=acronym)
    meeting = get_meeting(days=14)
    session_conflicts = session_conflicts_as_string(group, meeting)
    is_virtual = meeting.number in settings.SECR_VIRTUAL_MEETINGS,
    FormClass = get_session_form_class()

    # check if app is locked
    is_locked = check_app_locked()
    if is_locked and not has_role(request.user,'Secretariat'):
        messages.warning(request, "The Session Request Tool is closed")
        return redirect('ietf.secr.sreq.views.main')
    
    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            return redirect('ietf.secr.sreq.views.main')

        form = FormClass(group, request.POST)
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
                return redirect('ietf.secr.sreq.views.new', acronym=acronym)
            else:
                messages.info(request, 'Fetched session info from %s' % previous_meeting)
        else:
            messages.warning(request, 'Did not find any previous meeting')
            return redirect('ietf.secr.sreq.views.new', acronym=acronym)

        initial = get_initial_session(previous_sessions, prune_conflicts=True)
        add_essential_people(group,initial)
        if 'resources' in initial:
            initial['resources'] = [x.pk for x in initial['resources']]
        form = FormClass(group, initial=initial)

    else:
        initial={}
        add_essential_people(group,initial)
        form = FormClass(group, initial=initial)

    return render(request, 'sreq/new.html', {
        'meeting': meeting,
        'is_virtual': is_virtual,
        'form': form,
        'group': group,
        'session_conflicts': session_conflicts},
    )

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
        return redirect('ietf.secr.sreq.views.main')

    session = Session.objects.create(
        group=group,
        meeting=meeting,
        requested_duration=datetime.timedelta(0),
        type_id='regular',
    )
    SchedulingEvent.objects.create(
        session=session,
        status=SessionStatusName.objects.get(slug='notmeet'),
        by=login,
    )
    session_changed(session)

    # send notification
    (to_email, cc_list) = gather_address_lists('session_request_not_meeting',group=group,person=login)
    from_email = (settings.SESSION_REQUEST_FROM_EMAIL)
    subject = '%s - Not having a session at IETF %s' % (group.acronym, meeting.number)
    send_mail(request, to_email, from_email, subject, 'sreq/not_meeting_notification.txt',
              {'login':login,
               'group':group,
               'meeting':meeting}, cc=cc_list)

    # deprecated?
    # log activity
    #text = 'A message was sent to notify not having a session at IETF %d' % meeting.meeting_num
    #add_session_activity(group,text,meeting,request.person)

    # redirect
    messages.success(request, 'A message was sent to notify not having a session at IETF %s' % meeting.number)
    return redirect('ietf.secr.sreq.views.main')

@role_required('Secretariat')
def tool_status(request):
    '''
    This view handles locking and unlocking of the tool to the public.
    '''
    meeting = get_meeting(days=14)
    is_locked = check_app_locked(meeting=meeting)
    
    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Back':
            return redirect('ietf.secr.sreq.views.main')

        form = ToolStatusForm(request.POST)

        if button_text == 'Lock':
            if form.is_valid():
                meeting.session_request_lock_message = form.cleaned_data['message']
                meeting.save()
                messages.success(request, 'Session Request Tool is now Locked')
                return redirect('ietf.secr.sreq.views.main')

        elif button_text == 'Unlock':
            meeting.session_request_lock_message = ''
            meeting.save()
            messages.success(request, 'Session Request Tool is now Unlocked')
            return redirect('ietf.secr.sreq.views.main')

    else:
        if is_locked:
            message = get_lock_message()
            initial = {'message': message}
            form = ToolStatusForm(initial=initial)
        else:
            form = ToolStatusForm()

    return render(request, 'sreq/tool_status.html', {
        'is_locked': is_locked,
        'form': form},
    )

@role_required(*AUTHORIZED_ROLES)
def view(request, acronym, num = None):
    '''
    This view displays the session request info
    '''
    meeting = get_meeting(num,days=14)
    group = get_object_or_404(Group, acronym=acronym)
    sessions = add_event_info_to_session_qs(Session.objects.filter(meeting=meeting, group=group)).filter(Q(current_status__isnull=True) | ~Q(current_status__in=('canceled','notmeet','deleted'))).order_by('id')

    # check if app is locked
    is_locked = check_app_locked()
    if is_locked:
        messages.warning(request, "The Session Request Tool is closed")

    # if there are no session requests yet, redirect to new session request page
    if not sessions:
        if is_locked:
            return redirect('ietf.secr.sreq.views.main')
        else:
            return redirect('ietf.secr.sreq.views.new', acronym=acronym)

    activities = [{
        'act_date': e.time.strftime('%b %d, %Y'),
        'act_time': e.time.strftime('%H:%M:%S'),
        'activity': e.status.name,
        'act_by': e.by,
    } for e in sessions[0].schedulingevent_set.select_related('status', 'by')]

    # other groups that list this group in their conflicts
    session_conflicts = session_conflicts_as_string(group, meeting)
    show_approve_button = False

    # if sessions include a 3rd session waiting approval and the user is a secretariat or AD of the group
    # display approve button
    if any(s.current_status == 'apprw' for s in sessions):
        if has_role(request.user,'Secretariat') or group.parent.role_set.filter(name='ad',person=request.user.person):
            show_approve_button = True

    # build session dictionary (like querydict from new session request form) for use in template
    session = get_initial_session(sessions)

    return render(request, 'sreq/view.html', {
        'is_locked': is_locked,
        'is_virtual': meeting.number in settings.SECR_VIRTUAL_MEETINGS,
        'session': session,
        'activities': activities,
        'meeting': meeting,
        'group': group,
        'session_conflicts': session_conflicts,
        'show_approve_button': show_approve_button},
    )

