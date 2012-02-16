from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse
from django.db.models import Q
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext

from sec.utils.mail import get_ad_email_list, get_chair_email_list, get_cc_list
from sec.utils.decorators import check_permissions, sec_only
from sec.utils.group import get_my_groups, groups_by_session

from ietf.ietfauth.decorators import has_role
from ietf.utils.mail import send_mail
from ietf.meeting.models import Meeting, Session, Constraint

from ietf.group.models import Group, Role    
from ietf.name.models import SessionStatusName, ConstraintName

from forms import *

from itertools import chain
import datetime
import itertools

# -------------------------------------------------
# Globals
# -------------------------------------------------
SESSION_REQUEST_EMAIL = 'session-request@ietf.org'
LOCKFILE = os.path.join(settings.PROCEEDINGS_DIR,'session_request.lock')
# -------------------------------------------------
# Helper Functions
# -------------------------------------------------

def check_app_locked():
    '''
    This function returns True if the application is locked to non-secretariat users.
    '''
    return os.path.exists(LOCKFILE)

def get_initial_session(sessions):
    '''
    This function takes a queryset of sessions ordered by 'id' for consistency.  It returns
    a dictionary to be used as the initial for a legacy session form
    '''
    meeting = sessions[0].meeting
    group = sessions[0].group
    conflicts = group.constraint_source_set.filter(meeting=meeting)
    initial = {}
    # even if there are three sessions requested, the old form has 2 in this field
    initial['num_session'] = sessions.count() if sessions.count() <= 2 else 2
    
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
    return initial
    
def get_lock_message():
    '''
    Returns the message to display to non-secretariat users when the tool is locked.
    '''
    try:
        f = open(LOCKFILE,'r')
        message = f.read()
        f.close()
    except IOError:
        message = "This application is currently locked."
    return message

def get_meeting():
    '''
    Function to get the current IETF regular meeting.  Simply returns the meeting with the most recent date
    '''
    return Meeting.objects.filter(type='ietf').order_by('-date')[0]

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
    to_email = SESSION_REQUEST_EMAIL
    cc_list = get_cc_list(group, login)
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
    
    # update overrides
    if action == 'update':
        subject = '%s - Update to a Meeting Session Request for IETF %s' % (group.acronym, meeting.number)
        context['header'] = 'An update to a'
    
    # if third session requested approval is required
    # change headers TO=ADs, CC=session-request, submitter and cochairs
    if session.get('length_session3',None):
        context['session']['num_session'] = 3
        to_email = get_ad_email_list(group)
        cc_list = get_chair_email_list(group)
        cc_list.append(SESSION_REQUEST_EMAIL)
        if login.role_email(role_name='wg').address not in cc_list:
            cc_list.append(login.role_email(role_name='wg').address)
        subject = '%s - Request for meeting session approval for IETF %s' % (group.acronym, meeting.number)
        template = 'sreq/session_approval_notification.txt'
        status_text = 'the %s Directors for approval' % group.parent
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
    
    if has_role(request.user,'Secretariat') or group.parent.role_set.filter(name='ad',person=request.user.get_profile()):
        session.status = SessionStatusName.objects.get(slug='appr')
        session.save()
        
        messages.success(request, 'Third session approved')
        url = reverse('sessions_view', kwargs={'acronym':acronym})
        return HttpResponseRedirect(url)
    else:
        # if an unauthorized user gets here return error
        messages.error(request, 'Not authorized to approve the third session')
        url = reverse('sessions_view', kwargs={'acronym':acronym})
        return HttpResponseRedirect(url)

@check_permissions
def cancel(request, acronym):
    '''
    This view cancels a session request and sends a notification.
    To cancel, or withdraw the request set status = deleted.
    "canceled" status is used by the secretariat.
    '''
    meeting = get_meeting()
    group = get_object_or_404(Group, acronym=acronym)
    sessions = Session.objects.filter(meeting=meeting,group=group).order_by('id')
    login = request.user.get_profile()
    
    # delete conflicts
    Constraint.objects.filter(meeting=meeting,source=group).delete()
    
    # mark sessions as deleted
    for session in sessions:
        session.status_id = 'deleted'
        session.save()
        
    # log activity
    #add_session_activity(group,'Session was cancelled',meeting,user)
    
    # send notifitcation
    to_email = SESSION_REQUEST_EMAIL
    cc_list = get_cc_list(group, login)
    from_email = ('"IETF Meeting Session Request Tool"','session_request_developers@ietf.org')
    subject = '%s - Cancelling a meeting request for IETF %s' % (group.acronym, meeting.number)
    send_mail(request, to_email, from_email, subject, 'sreq/session_cancel_notification.txt',
              {'login':login,
               'group':group,
               'meeting':meeting}, cc=cc_list)
               
    messages.success(request, 'The %s Session Request has been canceled' % group.acronym)
    url = reverse('sessions')
    return HttpResponseRedirect(url)

def confirm(request, acronym):
    '''
    This view displays details of the new session that has been requested for the user
    to confirm for submission.
    '''
    querydict = request.session.get('session_form',None)
    if not querydict:
        raise Http404
    form = querydict.copy()
    meeting = get_meeting()
    group = get_object_or_404(Group,acronym=acronym)
    login = request.user.get_profile()
    
    if request.method == 'POST':
        # clear http session data
        del request.session['session_form']
        
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            messages.success(request, 'Session Request has been canceled')
            url = reverse('sessions')
            return HttpResponseRedirect(url)
        
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
                                      status=SessionStatusName.objects.get(slug=slug))
                new_session.save()
        
        # write constraint records
        save_conflicts(group,meeting,form['conflict1'],'conflict')
        save_conflicts(group,meeting,form['conflict2'],'conflic2')
        save_conflicts(group,meeting,form['conflict3'],'conflic3')
    
        # deprecated in new schema
        # log activity
        #add_session_activity(group,'New session was requested',meeting,user)
        
        # clear not meeting
        Session.objects.filter(group=group,meeting=meeting,status='notmeet').delete()
        
        # send notification
        send_notification(group,meeting,login,form,'new')
        
        status_text = 'IETF Agenda to be scheduled'
        messages.success(request, 'Your request has been sent to %s' % status_text)
        url = reverse('sessions')
        return HttpResponseRedirect(url)
        
    # GET logic
    session_conflicts = session_conflicts_as_string(group, meeting)
    
    return render_to_response('sreq/confirm.html', {
        'session': form,
        'group': group,
        'session_conflicts': session_conflicts},
        RequestContext(request, {}),
    )

@check_permissions
def edit(request, acronym):    
    '''
    This view allows the user to edit details of the session request
    '''
    meeting = get_meeting()
    group = get_object_or_404(Group, acronym=acronym)
    sessions = Session.objects.filter(meeting=meeting,group=group).order_by('id')
    sessions_count = sessions.count()
    initial = get_initial_session(sessions)
    session_conflicts = session_conflicts_as_string(group, meeting)
    login = request.user.get_profile()
    
    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            url = reverse('sessions_view', kwargs={'acronym':acronym})
            return HttpResponseRedirect(url)
        
        form = SessionForm(request.POST,initial=initial)
        if form.is_valid():
            if form.has_changed():
                # might be cleaner to simply delete and rewrite all records (but maintain submitter?)
                # adjust duration or add sessions
                # session 1
                if 'length_session1' in form.changed_data:
                    session = sessions[0]
                    session.requested_duration = datetime.timedelta(0,int(form.cleaned_data['length_session1']))
                    session.save()
                    
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
                                              status=SessionStatusName.objects.get(slug='schedw'))
                        new_session.save()
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
                        new_session = Session(meeting=meeting,
                                              group=group,
                                              attendees=form.cleaned_data['attendees'],
                                              requested=datetime.datetime.now(),
                                              requested_by=login,
                                              requested_duration=duration,
                                              comments=form.cleaned_data['comments'],
                                              status=SessionStatusName.objects.get(slug='apprw'))
                        new_session.save()
                    else:
                        duration = datetime.timedelta(0,int(form.cleaned_data['length_session3']))
                        session = sessions[2]
                        session.requested_duration = duration
                        session.save()
                    
                
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
                
                # deprecated
                # log activity
                #add_session_activity(group,'Session Request was updated',meeting,user)
                
                # send notification
                send_notification(group,meeting,login,form.cleaned_data,'update')
                
            messages.success(request, 'Session Request updated')
            url = reverse('sessions_view', kwargs={'acronym':acronym})
            return HttpResponseRedirect(url)
                
    else:
        form = SessionForm(initial=initial)
    
    return render_to_response('sreq/edit.html', {
        'meeting': meeting,
        'form': form,
        'group': group,
        'session_conflicts': session_conflicts},
        RequestContext(request, {}),
    )

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
            url = reverse('sessions_no_session', kwargs={'acronym':request.POST['group']})
            return HttpResponseRedirect(url)
        else:
            redirect_url = reverse('sessions_new', kwargs={'acronym':request.POST['group']})
            return HttpResponseRedirect(redirect_url)
        
    meeting = get_meeting()
    scheduled_groups,unscheduled_groups = groups_by_session(request.user, meeting)
    
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
    user = request.user
  
    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            url = reverse('sessions')
            return HttpResponseRedirect(url)
            
        form = SessionForm(request.POST)
        if form.is_valid():
            # check if request already exists for this group
            if Session.objects.filter(group=group,meeting=meeting).exclude(status__in=('deleted','notmeet')):
                messages.warning(request, 'Sessions for working group %s have already been requested once.' % group.acronym)
                url = reverse('sessions')
                return HttpResponseRedirect(url)
            
            # save in user session
            request.session['session_form'] = form.data
            
            url = reverse('sessions_confirm',kwargs={'acronym':acronym})
            return HttpResponseRedirect(url)
            
    # the "previous" querystring causes the form to be returned
    # pre-populated with data from last meeeting's session request
    elif request.method == 'GET' and request.GET.has_key('previous'):
        previous_meeting = Meeting.objects.get(number=str(int(meeting.number) - 1))
        previous_sessions = Session.objects.filter(meeting=previous_meeting,group=group).exclude(status__in=('notmeet','deleted')).order_by('id')
        if not previous_sessions:
            messages.warning(request, 'This group did not meet at %s' % previous_meeting)
            redirect_url = reverse('sessions_new', kwargs={'acronym':acronym})
            return HttpResponseRedirect(redirect_url)

        initial = get_initial_session(previous_sessions)
        form = SessionForm(initial=initial)
    
    else:
        form = SessionForm()
        
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
    login = request.user.get_profile()
    
    # delete canceled record if there is one
    Session.objects.filter(group=group,meeting=meeting,status='canceled').delete()

    # skip if state is already notmeet
    if Session.objects.filter(group=group,meeting=meeting,status='notmeet'):
        messages.info(request, 'The group %s is already marked as not meeting' % group.acronym)
        url = reverse('sessions')
        return HttpResponseRedirect(url)
    
    session = Session(group=group,
                      meeting=meeting,
                      requested=datetime.datetime.now(),
                      requested_by=login,
                      requested_duration=0,
                      status=SessionStatusName.objects.get(slug='notmeet'))
    session.save()
    
    # send notification
    to_email = SESSION_REQUEST_EMAIL
    cc_list = get_cc_list(group, login)
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
    url = reverse('sessions')
    return HttpResponseRedirect(url)

@sec_only
def tool_status(request):
    '''
    This view handles locking and unlocking of the tool to the public.
    '''
    is_locked = check_app_locked()
    
    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Done':
            url = reverse('sessions')
            return HttpResponseRedirect(url)
        
        form = ToolStatusForm(request.POST)
        
        if button_text == 'Lock':
            if form.is_valid():
                f = open(LOCKFILE,'w')
                f.write(form.cleaned_data['message'])
                f.close()
                
                messages.success(request, 'Session Request Tool is now Locked')
                url = reverse('sessions')
                return HttpResponseRedirect(url)
            
        elif button_text == 'Unlock':
            os.remove(LOCKFILE)
                
            messages.success(request, 'Session Request Tool is now Unlocked')
            url = reverse('sessions')
            return HttpResponseRedirect(url)
    
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

def view(request, acronym):
    '''
    This view displays the session request info
    '''
    meeting = get_meeting()
    group = get_object_or_404(Group, acronym=acronym)
    sessions = Session.objects.filter(~Q(status__in=('canceled','notmeet','deleted')),meeting=meeting,group=group).order_by('id')
    
    # if there are no session requests yet, redirect to new session request page
    if not sessions:
        redirect_url = reverse('sessions_new', kwargs={'acronym':acronym})
        return HttpResponseRedirect(redirect_url)
    
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
        if has_role(request.user,'Secretariat') or group.parent.role_set.filter(name='ad',person=request.user.get_profile()):
            show_approve_button = True
    
    # build session dictionary (like querydict from new session request form) for use in template
    session = get_initial_session(sessions)
    
    return render_to_response('sreq/view.html', {
        'session': session,
        'activities': activities,
        'meeting': meeting,
        'group': group,
        'session_conflicts': session_conflicts,
        'show_approve_button': show_approve_button},
        RequestContext(request, {}),
    )

