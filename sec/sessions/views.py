from session_messages import create_message

from django.conf import settings
#from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse
from django.db import connection, transaction
from django.db.models import Max
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext

#from sec.core.forms import GroupSelectForm
#from sec.core.models import NotMeetingGroups
#from sec.proceedings.models import IRTFChair
#from sec.roles.models import Role
from sec.utils.decorators import check_permissions
from sec.utils.group import get_my_groups
#from sec2.utils.shortcuts import get_group_or_404
#from sec2.utils.sessions import add_session_activity
#from sec2.utils.ams_mail import get_ad_email_list, get_chair_email_list, get_cc_list

from ietf.ietfauth.decorators import has_role
from ietf.utils.mail import send_mail
from ietf.meeting.models import Meeting, Session

from redesign.group.models import Group, Role    

from forms import *

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
    Function to get the current meeting.  Simply returns the meeting with the most recent date
    '''
    return Meeting.objects.all().order_by('-date')[0]

def get_scheduled_sessions(user, meeting):
    '''
    Takes a request object (for user info) and a meeting object
    Returns a list of meeting session requests the user has access to
    '''
    scheduled_sessions = []
    # NOTE: need to exclude group_acronym_ids < 0 as these are training sessions    
    #all_sessions = WgMeetingSession.objects.filter(meeting=meeting,group_acronym_id__gte=0)
    # TODO do we need to exclude training?
    all_sessions = meeting.session_set.all()
    
    # short circuit for secretariat
    if has_role(user,'Secretariat'):
        return all_sessions
        
    my_groups = get_my_groups(user)
    my_groups_ids = [ x.pk for x in my_groups ]
    for session in all_sessions:
        if session.group_acronym_id in my_groups_ids:
            scheduled_sessions.append(session)
    
    return scheduled_sessions
    
def get_unscheduled_groups(user, meeting):
    '''
    This function takes a Django User object and a Meeting object.
    It returns a list of active groups that the user is related to 
    (as chair or secretary) that do not already have sessions requests for the named meeting.
    If the user is a secretariat than all groups are considered.
    '''
    unscheduled = Group.objects.active.exclude(session__meeting=meeting)
    
    # short circuit for secretariat
    if has_role(user,'Secretariat'):
        return unscheduled
        
    my_groups = get_my_groups(user)
    
    return unscheduled & my_groups
"""    
def save_conflicts(group, conflicts, meeting):
    '''
    This function takes a group (IETFWG or IRTF), a list of groups acronyms (conflicts),
    and a meeting object.  Save conflict records in session_conflict table.
    '''
    for name in conflicts:
        # get either IETFWG or IRTF id
        try:
            acronym = Acronym.objects.get(acronym=name)
            id = acronym.acronym_id
        except Acronym.DoesNotExist:
            id = IRTF.objects.get(acronym=name).irtf_id
                            
        session_conflict = SessionConflict(group_acronym_id=group.pk,
                                           conflict_gid=id,
                                           meeting_num=meeting)
        session_conflict.save()

def send_notification(request,group,meeting,user,session,action):
    '''
    This function generates email notifications for various session request activities.
    action argument is a string [new|update].
    '''
    to_email = SESSION_REQUEST_EMAIL
    cc_list = get_cc_list(group, user)
    from_email = ('"IETF Meeting Session Request Tool"','session_request_developers@ietf.org')
    subject = '%s - New Meeting Session Request for IETF %s' % (str(group), meeting.meeting_num)
    template = 'sessions/session_request_notification.txt'
    
    # send email
    context = {}
    context['session'] = session
    context['group_name'] = str(group)
    context['meeting'] = meeting
    context['header'] = 'A new'
    
    # update overrides
    if action == 'update':
        subject = '%s - Update to a Meeting Session Request for IETF %s' % (str(group), meeting.meeting_num)
        context['header'] = 'An update to a'
    
    # if third session requested approval is required
    # change headers TO=ADs, CC=session-request, submitter and cochairs
    if context['session'].length_session3:
        context['session'].num_session = 3
        to_email = get_ad_email_list(group)
        cc_list = get_chair_email_list(group)
        cc_list.append(SESSION_REQUEST_EMAIL)
        if user.email() not in cc_list:
            cc_list.append(user.email())
        subject = '%s - Request for meeting session approval for IETF %s' % (str(group), meeting.meeting_num)
        template = 'sessions/session_approval_notification.txt'
        status_text = 'the %s Directors for approval' % group.area_name
    send_mail(request,
              to_email,
              from_email,
              subject,
              template,
              context,
              cc=cc_list)

"""
def session_conflicts_as_string(group, meeting=None):
    '''
    Takes a IETFWG or IRTF object and optional meeting object
    builds list of other groups which have a conflict with this one
    NOTE: this isn't provided by a simple related_name reference on the group
    because session_conflicts cannot use ForeignKeys
    '''
    return ''
    """
    if not meeting:
        meeting = get_meeting()
    object_list = []
    session_conflicts = SessionConflict.objects.filter(meeting_num=meeting,conflict_gid=group.pk)
    for item in session_conflicts:
        object_list.append(get_group_or_404(item.group_acronym_id))
    names_list = [ str(x) for x in object_list ]
    other_groups = ', '.join(names_list)
    return other_groups
    
# -------------------------------------------------
# View Functions
# -------------------------------------------------
@check_permissions
def approve(request, session_id):
    '''
    This view approves the third session.  For use by ADs or Secretariat.
    '''
    
    # if an unauthorized user gets here return error
    if not request.user_is_secretariat and not request.user_is_ad:
        messages.error(request, 'Not authorized to approve the third session')
        url = reverse('sessions_view', kwargs={'session_id':session_id})
        return HttpResponseRedirect(url)
    
    session = get_object_or_404(WgMeetingSession, session_id=session_id)
    session.ts_status_id = 3
    session.save()
    
    messages.success(request, 'Third session approved')
    url = reverse('sessions_view', kwargs={'session_id':session_id})
    return HttpResponseRedirect(url)
    
@check_permissions
def cancel(request, session_id):
    '''
    This view cancels a session request and sends a notification
    '''
    meeting = get_meeting()
    session = get_object_or_404(WgMeetingSession, session_id=session_id)
    group = get_group_or_404(session.group_acronym_id)
    group_name = str(group)
    user = request.person
    
    # delete conflicts
    session_conflicts = SessionConflict.objects.filter(meeting_num=meeting,group_acronym_id=group.pk)
    session_conflicts.delete()
    
    # delete session
    session.delete()
    
    # log activity
    add_session_activity(group,'Session was cancelled',meeting,user)
    
    # unset meeting scheduled
    if isinstance(group, IRTF):
        group.meeting_scheduled = False
    else:
        group.meeting_scheduled = 'NO'
    group.save()
            
    # send notifitcation
    to_email = SESSION_REQUEST_EMAIL
    cc_list = get_cc_list(group, user)
    from_email = ('"IETF Meeting Session Request Tool"','session_request_developers@ietf.org')
    subject = '%s - Cancelling a meeting request for IETF %s' % (group_name, meeting.meeting_num)
    send_mail(request, to_email, from_email, subject, 'sessions/session_cancel_notification.txt',
              {'group_name':group_name,
               'meeting':meeting}, cc=cc_list)
               
    messages.success(request, 'The %s Session Request has been canceled' % group_name)
    url = reverse('sessions_main')
    return HttpResponseRedirect(url)

def confirm(request, group_id):
    '''
    This view displays details of the new session that has been requested for the user
    to confirm for submission.
    '''
    form = request.session.get('session_form',None)
    if not form:
        raise Http404
    meeting = get_meeting()
    group = get_group_or_404(group_id)
    user = request.person
    
    new_session = form.save(commit=False)
    new_session.meeting = meeting
    new_session.group_acronym_id = group_id
    new_session.requested_by = user
    if isinstance(group, IRTF):
        new_session.irtf = True
    
    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            # clear session data
            del request.session['session_form']
            messages.success(request, 'Session Request has been canceled')
            url = reverse('sessions_main')
            return HttpResponseRedirect(url)
            
        del request.session['session_form']
        
        # set IRTF flag
        if isinstance(group, IRTF):
            group.meeting_scheduled = True
        else:
            group.meeting_scheduled = 'YES'
        
        # if a third session is requested 
        if form.cleaned_data['length_session3']:
            new_session.ts_status_id = 2
        
        new_session.save()
        group.save()
        
        # write session_conflicts records
        all_conflicts = join_conflicts(form.cleaned_data)
        save_conflicts(group,all_conflicts,meeting)
    
        # log activity
        add_session_activity(group,'New session was requested',meeting,user)
        
        # clear not meeting
        clear_not_meeting(group,meeting)
        
        # send notification
        data = form.cleaned_data
        action = 'new'
        send_notification(request,group,meeting,user,new_session,action)
        
        status_text = 'IETF Agenda to be scheduled'
        messages.success(request, 'Your request has been sent to %s' % status_text)
        url = reverse('sessions_main')
        return HttpResponseRedirect(url)
        
    # GET logic
    session_conflicts = session_conflicts_as_string(group)
    
    return render_to_response('sessions/confirm.html', {
        'session': new_session,
        'group': group,
        'session_conflicts': session_conflicts},
        RequestContext(request, {}),
    )

@check_permissions            
def edit(request, session_id):    
    '''
    This view allows the user to edit details of the session request
    '''
    meeting = get_meeting()
    session = get_object_or_404(WgMeetingSession, session_id=session_id)
    group = get_group_or_404(session.group_acronym_id)
    group_name = str(group)
    session_conflicts = session_conflicts_as_string(group)
    user = request.person
    
    
    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            url = reverse('sessions_view', kwargs={'session_id':session_id})
            return HttpResponseRedirect(url)
        
        form = SessionForm(request.POST, instance=session)
        if form.is_valid():
            # Todo save stuff
            new_session = form.save(commit=False)
            
            # if a third session is requested 
            if form.cleaned_data['length_session3']:
                new_session.ts_status_id = 2
            else:
                new_session.ts_status_id = 0
                
            new_session.save()
            
            # delete and re-save conflicts
            session_conflicts = SessionConflict.objects.filter(meeting_num=meeting,group_acronym_id=group.pk)
            session_conflicts.delete()
            all_conflicts = join_conflicts(form.cleaned_data)
            save_conflicts(group,all_conflicts,meeting)
            
            # log activity
            add_session_activity(group,'Session Request was updated',meeting,user)
            
            # send notification
            data = form.cleaned_data
            action = 'update'
            send_notification(request,group,meeting,user,new_session,action)
            
            messages.success(request, 'Session Request updated')
            url = reverse('sessions_view', kwargs={'session_id':session_id})
            return HttpResponseRedirect(url)

    else:
        form = SessionForm(instance=session)
    
    return render_to_response('sessions/edit.html', {
        'meeting': meeting,
        'session': session,
        'form': form,
        'group': group,
        'group_name': group_name,
        'session_conflicts': session_conflicts},
        RequestContext(request, {}),
    )
"""
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
        return render_to_response('sessions/locked.html', {
        'message': message},
        RequestContext(request, {}),
    )
        
    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Group will not meet':
            url = reverse('sessions_no_session', kwargs={'group_id':request.POST['group']})
            return HttpResponseRedirect(url)
        else:
            redirect_url = reverse('sessions_new', kwargs={'group_id':request.POST['group']})
            return HttpResponseRedirect(redirect_url)
        
    meeting = get_meeting()
    
    scheduled_sessions = get_scheduled_sessions(request.user, meeting)
    sorted_scheduled_sessions = sorted(scheduled_sessions, key=lambda scheduled_sessions: scheduled_sessions.group.acronym)
    
    # load form select with unscheduled groups
    unscheduled_groups = get_unscheduled_groups(request.user, meeting)
    sorted_unscheduled_groups = sorted(unscheduled_groups, key=lambda unscheduled_groups: unscheduled_groups.acronym)
    choices = zip([ g.pk for g in unscheduled_groups ],
                  [ str(g) for g in unscheduled_groups ])
    sorted_choices = sorted(choices, key=lambda choices: choices[1])
    form = GroupSelectForm(choices=sorted_choices)
    
    return render_to_response('sessions/main.html', {
        'is_locked': is_locked,
        'form': form,
        'meeting': meeting,
        'scheduled_sessions': sorted_scheduled_sessions,
        'unscheduled_groups': sorted_unscheduled_groups},
        RequestContext(request, {}),
    )

@check_permissions
def new(request, group_id):
    '''
    This view gathers details for a new session request.  The user proceeds to confirm()
    to create the request.
    '''
    
    group = get_object_or_404(Group, id=group_id)
    group_name = str(group)
    session_conflicts = session_conflicts_as_string(group)
    meeting = get_meeting()
    user = request.user
  
    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            url = reverse('sessions')
            return HttpResponseRedirect(url)
            
        form = SessionForm(request.POST)
        if form.is_valid():
            # check if request already exists for this group
            if WgMeetingSession.objects.filter(group_acronym_id=group.pk,meeting=meeting):
                messages.warning(request, 'Sessions for working group %s have already been requested once.' % str(groupk))
                url = reverse('sessions_main')
                return HttpResponseRedirect(url)
            
            # save in user session
            request.session['session_form'] = form
            
            url = reverse('sessions_confirm',kwargs={'group_id':group_id})
            return HttpResponseRedirect(url)
        else:
            #assert False, form.errors
            pass
            
    # the "previous" querystring causes the form to be returned
    # pre-populated with data from last meeeting's session request
    elif request.method == 'GET' and request.GET.has_key('previous'):
        previous_meeting = Meeting.objects.get(meeting_num=meeting.meeting_num - 1)
        try:
            previous_session = WgMeetingSession.objects.get(meeting=previous_meeting,group_acronym_id=group.pk)
        except WgMeetingSession.DoesNotExist:
            messages.warning(request, 'No session scheduled for this group at meeting: %s' % previous_meeting.meeting_num)
            redirect_url = reverse('sessions_new', kwargs={'group_id':group_id})
            return HttpResponseRedirect(redirect_url)
            
        # setup initial dictionary ---------------
        initial = {}
        initial['num_session'] = previous_session.num_session
        
        # accessing these foreign key fields throw errors if they are unset so we
        # need to catch these
        try:
            initial['length_session1'] = previous_session.length_session1
        except ObjectDoesNotExist:
            pass
        try:
            initial['length_session2'] = previous_session.length_session2
        except ObjectDoesNotExist:
            pass
        try:
            initial['length_session3'] = previous_session.length_session3
        except ObjectDoesNotExist:
            pass
        initial['number_attendee'] = previous_session.number_attendee
        initial['conflict1'] = previous_session.conflict1
        initial['conflict2'] = previous_session.conflict2
        initial['conflict3'] = previous_session.conflict3
        initial['conflict_other'] = previous_session.conflict_other
        initial['special_req'] = previous_session.special_req
        # end initial setup ----------------------
        
        form = SessionForm(initial=initial)
    
    else:
        form = SessionForm()
        
    return render_to_response('sessions/new.html', {
        'meeting': meeting,
        'form': form,
        'group': group,
        'group_name': group_name,
        'session_conflicts': session_conflicts},
        RequestContext(request, {}),
    )

@check_permissions
def no_session(request, group_id):
    '''
    The user has indicated that the named group will not be having a session this IETF meeting.
    Actions:
    - update not_meeting_groups
    - send notification
    - update session_activity log
    '''
    pass
    """
    meeting = get_meeting()
    group = get_group_or_404(group_id)
    user = request.person
    
    if isinstance(group, IETFWG):
        group_name = group.group_acronym.acronym
        record = NotMeetingGroups(group=group,meeting=meeting)
        record.save()
    
    else:
        group_name = group.acronym
        record = NotMeetingIRTF(irtf=group,meeting=meeting)
        record.save()
    
    # send notification
    to_email = SESSION_REQUEST_EMAIL
    cc_list = get_cc_list(group, user)
    from_email = ('"IETF Meeting Session Request Tool"','session_request_developers@ietf.org')
    subject = '%s - Not having a session at IETF %s' % (group_name, meeting.meeting_num)
    send_mail(request, to_email, from_email, subject, 'sessions/not_meeting_notification.txt',
              {'group_name':group_name,
               'meeting':meeting}, cc=cc_list)
    
    # log activity
    text = 'A message was sent to notify not having a session at IETF %d' % meeting.meeting_num
    add_session_activity(group,text,meeting,request.person)
    
    # redirect
    messages.success(request, 'A message was sent to notify not having a session at IETF %s' % meeting.meeting_num)
    url = reverse('sessions_main')
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
            url = reverse('sessions_main')
            return HttpResponseRedirect(url)
        
        form = ToolStatusForm(request.POST)
        
        if button_text == 'Lock':
            if form.is_valid():
                f = open(LOCKFILE,'w')
                f.write(form.cleaned_data['message'])
                f.close()
                
                messages.success(request, 'Session Request Tool is now Locked')
                url = reverse('sessions_main')
                return HttpResponseRedirect(url)
            
        elif button_text == 'Unlock':
            os.remove(LOCKFILE)
                
            messages.success(request, 'Session Request Tool is now Unlocked')
            url = reverse('sessions_main')
            return HttpResponseRedirect(url)
    
    else:
        if is_locked:
            message = get_lock_message()
            initial = {'message': message}
            form = ToolStatusForm(initial=initial)
        else:
            form = ToolStatusForm()
    
    return render_to_response('sessions/tool_status.html', {
        'is_locked': is_locked,
        'form': form},
        RequestContext(request, {}),
    )
"""
def view(request, session_id):
    '''
    This view displays the session request info
    '''
    pass
"""
    meeting = get_meeting()
    session = get_object_or_404(WgMeetingSession, session_id=session_id)
    group = get_group_or_404(session.group_acronym_id)
    activities = SessionRequestActivity.objects.filter(group_acronym_id=session.group_acronym_id,meeting=meeting)
    # other groups that list this group in their conflicts
    session_conflicts = session_conflicts_as_string(group)
    show_approve_button = False
    
    # if this session request has a 3rd session waiting approval and the user can approve it
    # display approve button
    if session.ts_status_id == 2:
        if request.user_is_secretariat:
            show_approve_button = True
        
        if request.user_is_ad:
            ad = AreaDirector.objects.get(person=request.person)
            ags = AreaGroup.objects.filter(area=ad.area)
            if ags.filter(group=group.pk):
                show_approve_button = True
    
    return render_to_response('sessions/view.html', {
        'session': session,
        'activities': activities,
        'group': group,
        'session_conflicts': session_conflicts,
        'show_approve_button': show_approve_button},
        RequestContext(request, {}),
    )
"""
