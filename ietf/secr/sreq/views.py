import datetime

from django.contrib import messages
from django.db.models import Q
from django.http import Http404
from django.shortcuts import render_to_response, get_object_or_404, redirect
from django.template import RequestContext

from ietf.group.models import Group
from ietf.ietfauth.utils import has_role, role_required
from ietf.meeting.models import Meeting, Session, Constraint, ResourceAssociation
from ietf.meeting.helpers import get_meeting
from ietf.name.models import SessionStatusName, ConstraintName
from ietf.secr.sreq.forms import SessionForm, GroupSelectForm, ToolStatusForm
from ietf.secr.utils.decorators import check_permissions
from ietf.secr.utils.group import groups_by_session
from ietf.utils.mail import send_mail
from ietf.person.models import Person
from ietf.mailtrigger.utils import gather_address_lists

# -------------------------------------------------
# Globals
# -------------------------------------------------
#TODO: DELETE
SESSION_REQUEST_EMAIL = 'session-request@ietf.org'
AUTHORIZED_ROLES=('WG Chair','WG Secretary','RG Chair','IAB Group Chair','Area Director','Secretariat','Team Chair','IRTF Chair')

# -------------------------------------------------
# Helper Functions
# -------------------------------------------------

def check_app_locked(meeting=None):
    '''
    This function returns True if the application is locked to non-secretariat users.
    '''
    if not meeting:
        meeting = get_meeting()
    return bool(meeting.session_request_lock_message)

def get_initial_session(sessions):
    '''
    This function takes a queryset of sessions ordered by 'id' for consistency.  It returns
    a dictionary to be used as the initial for a legacy session form
    '''
    initial = {}
    if(len(sessions) == 0):
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
    initial['conflict1'] = ' '.join([ c.target.acronym for c in conflicts.filter(name__slug='conflict') ])
    initial['conflict2'] = ' '.join([ c.target.acronym for c in conflicts.filter(name__slug='conflic2') ])
    initial['conflict3'] = ' '.join([ c.target.acronym for c in conflicts.filter(name__slug='conflic3') ])
    initial['comments'] = sessions[0].comments
    initial['resources'] = sessions[0].resources.all()
    initial['bethere'] = [x.person for x in sessions[0].constraints().filter(name='bethere').select_related("person")]
    return initial

def get_lock_message(meeting=None):
    '''
    Returns the message to display to non-secretariat users when the tool is locked.
    '''
    if not meeting:
        meeting = get_meeting()
    return meeting.session_request_lock_message

def get_requester_text(person,group):
    '''
    This function takes a Person object and a Group object and returns the text to use in the
    session request notification email, ie. Joe Smith, a Chair of the ancp working group
    '''
    roles = group.role_set.filter(name__in=('chair','secr'),person=person)
    if roles:
        return '%s, a %s of the %s working group' % (person.ascii, roles[0].name, group.acronym)
    if group.parent.role_set.filter(name='ad',person=person):
        return '%s, a %s Area Director' % (person.ascii, group.parent.acronym.upper())
    if person.role_set.filter(name='secr',group__acronym='secretariat'):
        return '%s, on behalf of the %s working group' % (person.ascii, group.acronym)

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
    from_email = ('"IETF Meeting Session Request Tool"','session_request_developers@ietf.org')
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
    group_list = [ g.source.acronym for g in group.constraint_target_set.filter(meeting=meeting) ]
    return ', '.join(group_list)

# -------------------------------------------------
# View Functions
# -------------------------------------------------
@check_permissions
def approve(request, acronym):
    '''
    This view approves the third session.  For use by ADs or Secretariat.
    '''
    meeting = get_meeting()
    group = get_object_or_404(Group, acronym=acronym)
    session = Session.objects.get(meeting=meeting,group=group,status='apprw')

    if has_role(request.user,'Secretariat') or group.parent.role_set.filter(name='ad',person=request.user.person):
        session.status = SessionStatusName.objects.get(slug='appr')
        session_save(session)

        messages.success(request, 'Third session approved')
        return redirect('sessions_view', acronym=acronym)
    else:
        # if an unauthorized user gets here return error
        messages.error(request, 'Not authorized to approve the third session')
        return redirect('sessions_view', acronym=acronym)

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
    meeting = get_meeting()
    group = get_object_or_404(Group, acronym=acronym)
    sessions = Session.objects.filter(meeting=meeting,group=group).order_by('id')
    login = request.user.person

    # delete conflicts
    Constraint.objects.filter(meeting=meeting,source=group).delete()

    # mark sessions as deleted
    for session in sessions:
        session.status_id = 'deleted'
        session_save(session)

        # clear schedule assignments if already scheduled
        session.scheduledsession_set.all().delete()

    # send notifitcation
    (to_email, cc_list) = gather_address_lists('session_request_cancelled',group=group,person=login)
    from_email = ('"IETF Meeting Session Request Tool"','session_request_developers@ietf.org')
    subject = '%s - Cancelling a meeting request for IETF %s' % (group.acronym, meeting.number)
    send_mail(request, to_email, from_email, subject, 'sreq/session_cancel_notification.txt',
              {'login':login,
               'group':group,
               'meeting':meeting}, cc=cc_list)

    messages.success(request, 'The %s Session Request has been canceled' % group.acronym)
    return redirect('sessions')

@role_required(*AUTHORIZED_ROLES)
def confirm(request, acronym):
    '''
    This view displays details of the new session that has been requested for the user
    to confirm for submission.
    '''
    # FIXME: this should be using form.is_valid/form.cleaned_data - invalid input will make it crash
    querydict = request.session.get('session_form',None)
    if not querydict:
        raise Http404
    form = querydict.copy()
    if 'resources' in form:
        form['resources'] = [ ResourceAssociation.objects.get(pk=pk) for pk in form['resources'].split(',')]
    if 'bethere' in form:
        person_id_list = [ id for id in form['bethere'].split(',') if id ]
        form['bethere'] = Person.objects.filter(pk__in=person_id_list)
    meeting = get_meeting()
    group = get_object_or_404(Group,acronym=acronym)
    login = request.user.person

    if request.method == 'POST':
        # clear http session data
        del request.session['session_form']

        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            messages.success(request, 'Session Request has been canceled')
            return redirect('sessions')

        # delete any existing session records with status = canceled or notmeet
        Session.objects.filter(group=group,meeting=meeting,status__in=('canceled','notmeet')).delete()

        # create new session records
        count = 0
        # lenth_session2 and length_session3 fields might be disabled by javascript and so
        # wouldn't appear in form data
        for duration in (form.get('length_session1',None),form.get('length_session2',None),form.get('length_session3',None)):
            count += 1
            if duration:
                slug = 'apprw' if count == 3 else 'schedw'
                new_session = Session(meeting=meeting,
                                      group=group,
                                      attendees=form['attendees'],
                                      requested=datetime.datetime.now(),
                                      requested_by=login,
                                      requested_duration=datetime.timedelta(0,int(duration)),
                                      comments=form['comments'],
                                      status=SessionStatusName.objects.get(slug=slug),
                                      type_id='session',
                                     )
                session_save(new_session)
                if 'resources' in form:
                    new_session.resources = form['resources']

        # write constraint records
        save_conflicts(group,meeting,form.get('conflict1',''),'conflict')
        save_conflicts(group,meeting,form.get('conflict2',''),'conflic2')
        save_conflicts(group,meeting,form.get('conflict3',''),'conflic3')

        if 'bethere' in form:
            bethere_cn = ConstraintName.objects.get(slug='bethere')
            for p in form.get('bethere', []):
                Constraint.objects.create(name=bethere_cn, source=group, person=p, meeting=new_session.meeting)

        # deprecated in new schema
        # log activity
        #add_session_activity(group,'New session was requested',meeting,user)

        # clear not meeting
        Session.objects.filter(group=group,meeting=meeting,status='notmeet').delete()

        # send notification
        send_notification(group,meeting,login,form,'new')

        status_text = 'IETF Agenda to be scheduled'
        messages.success(request, 'Your request has been sent to %s' % status_text)
        return redirect('sessions')

    # GET logic
    session_conflicts = session_conflicts_as_string(group, meeting)

    return render_to_response('sreq/confirm.html', {
        'session': form,
        'group': group,
        'session_conflicts': session_conflicts},
        RequestContext(request, {}),
    )

#Move this into make_initial
def add_essential_people(group,initial):
    # This will be easier when the form uses Person instead of Email
    people = set()
    if 'bethere' in initial:
        people.update(initial['bethere'])
    people.update(Person.objects.filter(role__group=group, role__name__in=['chair','ad']))
    initial['bethere'] = list(people)
    

def edit(request, *args, **kwargs):
    return edit_mtg(request, None, *args, **kwargs)

def session_save(session):
    session.save()
    if session.status_id == "schedw" and session.meeting.agenda != None:
        # send an email to iesg-secretariat to alert to change
        pass

@check_permissions
def edit_mtg(request, num, acronym):
    '''
    This view allows the user to edit details of the session request
    '''
    meeting = get_meeting(num)
    group = get_object_or_404(Group, acronym=acronym)
    sessions = Session.objects.filter(meeting=meeting,group=group).order_by('id')
    sessions_count = sessions.count()
    initial = get_initial_session(sessions)
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
            return redirect('sessions_view', acronym=acronym)

        form = SessionForm(request.POST,initial=initial)
        if form.is_valid():
            if form.has_changed():
                # might be cleaner to simply delete and rewrite all records (but maintain submitter?)
                # adjust duration or add sessions
                # session 1
                if 'length_session1' in form.changed_data:
                    session = sessions[0]
                    session.requested_duration = datetime.timedelta(0,int(form.cleaned_data['length_session1']))
                    session_save(session)

                # session 2
                if 'length_session2' in form.changed_data:
                    length_session2 = form.cleaned_data['length_session2']
                    if length_session2 == '':
                        sessions[1].delete()
                    elif sessions_count < 2:
                        duration = datetime.timedelta(0,int(form.cleaned_data['length_session2']))
                        new_session = Session(meeting=meeting,
                                              group=group,
                                              attendees=form.cleaned_data['attendees'],
                                              requested=datetime.datetime.now(),
                                              requested_by=login,
                                              requested_duration=duration,
                                              comments=form.cleaned_data['comments'],
                                              status=SessionStatusName.objects.get(slug='schedw'),
                                              type_id='session',
                                             )
                        new_session.save()
                    else:
                        duration = datetime.timedelta(0,int(form.cleaned_data['length_session2']))
                        session = sessions[1]
                        session.requested_duration = duration
                        session_save(session)

                # session 3
                if 'length_session3' in form.changed_data:
                    length_session3 = form.cleaned_data['length_session3']
                    if length_session3 == '':
                        sessions[2].delete()
                    elif sessions_count < 3:
                        duration = datetime.timedelta(0,int(form.cleaned_data['length_session3']))
                        new_session = Session(meeting=meeting,
                                              group=group,
                                              attendees=form.cleaned_data['attendees'],
                                              requested=datetime.datetime.now(),
                                              requested_by=login,
                                              requested_duration=duration,
                                              comments=form.cleaned_data['comments'],
                                              status=SessionStatusName.objects.get(slug='apprw'),
                                              type_id='session',
                                             )
                        new_session.save()
                    else:
                        duration = datetime.timedelta(0,int(form.cleaned_data['length_session3']))
                        session = sessions[2]
                        session.requested_duration = duration
                        session_save(session)


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

                # deprecated
                # log activity
                #add_session_activity(group,'Session Request was updated',meeting,user)

                # send notification
                send_notification(group,meeting,login,form.cleaned_data,'update')

            # nuke any cache that might be lingering around.
            from ietf.meeting.helpers import session_constraint_expire
            session_constraint_expire(request,session)

            messages.success(request, 'Session Request updated')
            return redirect('sessions_view', acronym=acronym)

    else:
        if not sessions:
            return redirect('sessions_new', acronym=acronym)
        form = SessionForm(initial=initial)

    return render_to_response('sreq/edit.html', {
        'is_locked': is_locked,
        'meeting': meeting,
        'form': form,
        'group': group,
        'session_conflicts': session_conflicts},
        RequestContext(request, {}),
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
        return render_to_response('sreq/locked.html', {
        'message': message},
        RequestContext(request, {}),
    )

    # TODO this is not currently used in the main template
    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Group will not meet':
            return redirect('sessions_no_session', acronym=request.POST['group'])
        else:
            return redirect('sessions_new', acronym=request.POST['group'])

    meeting = get_meeting()
    scheduled_groups,unscheduled_groups = groups_by_session(request.user, meeting)

    # warn if there are no associated groups
    if not scheduled_groups and not unscheduled_groups:
        messages.warning(request, 'The account %s is not associated with any groups.  If you have multiple Datatracker accounts you may try another or report a problem to ietf-action@ietf.org' % request.user)
     
    # load form select with unscheduled groups
    choices = zip([ g.pk for g in unscheduled_groups ],
                  [ str(g) for g in unscheduled_groups ])
    form = GroupSelectForm(choices=choices)

    # add session status messages for use in template
    for group in scheduled_groups:
        sessions = group.session_set.filter(meeting=meeting)
        if sessions.count() < 3:
            group.status_message = sessions[0].status
        else:
            group.status_message = 'First two sessions: %s, Third session: %s' % (sessions[0].status,sessions[2].status)

    # add not meeting indicators for use in template
    for group in unscheduled_groups:
        if group.session_set.filter(meeting=meeting,status='notmeet'):
            group.not_meeting = True

    return render_to_response('sreq/main.html', {
        'is_locked': is_locked,
        'form': form,
        'meeting': meeting,
        'scheduled_groups': scheduled_groups,
        'unscheduled_groups': unscheduled_groups},
        RequestContext(request, {}),
    )

@check_permissions
def new(request, acronym):
    '''
    This view gathers details for a new session request.  The user proceeds to confirm()
    to create the request.
    '''
    group = get_object_or_404(Group, acronym=acronym)
    meeting = get_meeting()
    session_conflicts = session_conflicts_as_string(group, meeting)

    # check if app is locked
    is_locked = check_app_locked()
    if is_locked:
        messages.warning(request, "The Session Request Tool is closed")
        return redirect('sessions')
    
    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            return redirect('sessions')

        form = SessionForm(request.POST)
        if form.is_valid():
            # check if request already exists for this group
            if Session.objects.filter(group=group,meeting=meeting).exclude(status__in=('deleted','notmeet')):
                messages.warning(request, 'Sessions for working group %s have already been requested once.' % group.acronym)
                return redirect('sessions')

            # save in user session
            request.session['session_form'] = form.data

            return redirect('sessions_confirm',acronym=acronym)

    # the "previous" querystring causes the form to be returned
    # pre-populated with data from last meeeting's session request
    elif request.method == 'GET' and request.GET.has_key('previous'):
        previous_meeting = Meeting.objects.get(number=str(int(meeting.number) - 1))
        previous_sessions = Session.objects.filter(meeting=previous_meeting,group=group).exclude(status__in=('notmeet','deleted')).order_by('id')
        if not previous_sessions:
            messages.warning(request, 'This group did not meet at %s' % previous_meeting)
            return redirect('sessions_new', acronym=acronym)

        initial = get_initial_session(previous_sessions)
        add_essential_people(group,initial)
        if 'resources' in initial:
            initial['resources'] = [x.pk for x in initial['resources']]
        form = SessionForm(initial=initial)

    else:
        initial={}
        add_essential_people(group,initial)
        form = SessionForm(initial=initial)

    return render_to_response('sreq/new.html', {
        'meeting': meeting,
        'form': form,
        'group': group,
        'session_conflicts': session_conflicts},
        RequestContext(request, {}),
    )

@check_permissions
def no_session(request, acronym):
    '''
    The user has indicated that the named group will not be having a session this IETF meeting.
    Actions:
    - send notification
    - update session_activity log
    '''
    meeting = get_meeting()
    group = get_object_or_404(Group, acronym=acronym)
    login = request.user.person

    # delete canceled record if there is one
    Session.objects.filter(group=group,meeting=meeting,status='canceled').delete()

    # skip if state is already notmeet
    if Session.objects.filter(group=group,meeting=meeting,status='notmeet'):
        messages.info(request, 'The group %s is already marked as not meeting' % group.acronym)
        return redirect('sessions')

    session = Session(group=group,
                      meeting=meeting,
                      requested=datetime.datetime.now(),
                      requested_by=login,
                      requested_duration=0,
                      status=SessionStatusName.objects.get(slug='notmeet'),
                      type_id='session',
                      )
    session_save(session)

    # send notification
    (to_email, cc_list) = gather_address_lists('session_request_not_meeting',group=group,person=login)
    from_email = ('"IETF Meeting Session Request Tool"','session_request_developers@ietf.org')
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
    return redirect('sessions')

@role_required('Secretariat')
def tool_status(request):
    '''
    This view handles locking and unlocking of the tool to the public.
    '''
    meeting = get_meeting()
    is_locked = check_app_locked(meeting=meeting)
    
    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Back':
            return redirect('sessions')

        form = ToolStatusForm(request.POST)

        if button_text == 'Lock':
            if form.is_valid():
                meeting.session_request_lock_message = form.cleaned_data['message']
                meeting.save()
                messages.success(request, 'Session Request Tool is now Locked')
                return redirect('sessions')

        elif button_text == 'Unlock':
            meeting.session_request_lock_message = ''
            meeting.save()
            messages.success(request, 'Session Request Tool is now Unlocked')
            return redirect('sessions')

    else:
        if is_locked:
            message = get_lock_message()
            initial = {'message': message}
            form = ToolStatusForm(initial=initial)
        else:
            form = ToolStatusForm()

    return render_to_response('sreq/tool_status.html', {
        'is_locked': is_locked,
        'form': form},
        RequestContext(request, {}),
    )

@role_required(*AUTHORIZED_ROLES)
def view(request, acronym, num = None):
    '''
    This view displays the session request info
    '''
    meeting = get_meeting(num)
    group = get_object_or_404(Group, acronym=acronym)
    sessions = Session.objects.filter(~Q(status__in=('canceled','notmeet','deleted')),meeting=meeting,group=group).order_by('id')

    # check if app is locked
    is_locked = check_app_locked()
    if is_locked:
        messages.warning(request, "The Session Request Tool is closed")
        
    # if there are no session requests yet, redirect to new session request page
    if not sessions:
        if is_locked:
            return redirect('sessions')
        else:
            return redirect('sessions_new', acronym=acronym)

    # TODO simulate activity records
    activities = [{'act_date':sessions[0].requested.strftime('%b %d, %Y'),
                   'act_time':sessions[0].requested.strftime('%H:%M:%S'),
                   'activity':'New session was requested',
                   'act_by':sessions[0].requested_by}]
    if sessions[0].scheduled:
        activities.append({'act_date':sessions[0].scheduled.strftime('%b %d, %Y'),
                       'act_time':sessions[0].scheduled.strftime('%H:%M:%S'),
                       'activity':'Session was scheduled',
                       'act_by':'Secretariat'})

    # other groups that list this group in their conflicts
    session_conflicts = session_conflicts_as_string(group, meeting)
    show_approve_button = False

    # if sessions include a 3rd session waiting approval and the user is a secretariat or AD of the group
    # display approve button
    if sessions.filter(status='apprw'):
        if has_role(request.user,'Secretariat') or group.parent.role_set.filter(name='ad',person=request.user.person):
            show_approve_button = True

    # build session dictionary (like querydict from new session request form) for use in template
    session = get_initial_session(sessions)

    return render_to_response('sreq/view.html', {
        'is_locked': is_locked,
        'session': session,
        'activities': activities,
        'meeting': meeting,
        'group': group,
        'session_conflicts': session_conflicts,
        'show_approve_button': show_approve_button},
        RequestContext(request, {}),
    )

