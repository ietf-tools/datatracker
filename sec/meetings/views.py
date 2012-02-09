from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.core.urlresolvers import reverse
from django.db.models import Max, Min, Q
from django.forms.formsets import formset_factory
from django.forms.models import inlineformset_factory, modelformset_factory
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.utils.functional import curry

from ietf.utils.mail import send_mail
from ietf.meeting.models import Meeting, Session, Room, TimeSlot
from ietf.group.models import Group
from ietf.name.models import SessionStatusName, TimeSlotTypeName
from sec.proceedings.views import build_choices
from sec.sreq.forms import GroupSelectForm
from sec.sreq.views import get_initial_session, session_conflicts_as_string
from sec.utils.mail import get_cc_list
from sec.utils.meeting import get_upload_root

from forms import *

import os
import datetime

# --------------------------------------------------
# Globals
# --------------------------------------------------
INFO_TYPES = {'ack':'Acknowledgement',
              'overview1':'IETF Overview Part 1',
              'overview2':'IETF Overview Part 2',
              'future_meeting':'Future Meeting',
              'irtf':'IRTF Home Page in HTML'}

"""             
all_refs = NonSessionRef.objects.all().order_by('id')
NON_SESSION_INITIAL = ((0,all_refs[1]),
                       (1,all_refs[1]),
                       (2,all_refs[1]),
                       (3,all_refs[1]),
                       (4,all_refs[1]),
                       (5,all_refs[1]),
                       (None,all_refs[3]),
                       (None,all_refs[2]),
                       (None,all_refs[0]),
                       (1,all_refs[4]),
                       (2,all_refs[4]),
                       (3,all_refs[4]),
                       (4,all_refs[4]),
                       (5,all_refs[4]),
                       (1,all_refs[5]),
                       (2,all_refs[5]),
                       (3,all_refs[5]),
                       (4,all_refs[5]),
                       (5,all_refs[5]),
                       (1,all_refs[7]),
                       (2,all_refs[7]),
                       (3,all_refs[7]),
                       (4,all_refs[7]),
                       (5,all_refs[7]))

# --------------------------------------------------
# Helper Functions
# --------------------------------------------------
"""
def build_timeslots(meeting,room=None):
    '''
    This function takes a Meeting object and an optional room argument.  If room isn't passed we 
    pre-create the full set of timeslot records using the last meeting as a template.  
    If room is passed pre-create timeslots for the new room.  Call this after saving new rooms 
    or adding a room.
    '''
    slots = meeting.timeslot_set.filter(type='session')
    if room:
        rooms = [room]
    else:
        rooms = meeting.room_set.all()
    if not slots or room:
        last_meeting = get_last_meeting(meeting)
        delta = meeting.date - last_meeting.date
        initial = []
        timeslots = []
        time_seen = set()
        for t in last_meeting.timeslot_set.filter(type='session'):
            if not t.time in time_seen:
                time_seen.add(t.time)
                timeslots.append(t)
        for t in timeslots:
            new_time = t.time + delta
            for room in rooms:
                TimeSlot.objects.create(type_id='session',
                                        meeting=meeting,
                                        name=t.name,
                                        time=new_time,
                                        location=room,
                                        duration=t.duration)

def get_last_meeting(meeting):
    last_number = int(meeting.number) - 1
    return Meeting.objects.get(number=last_number)
    
def make_directories(meeting):
    '''
    This function takes a meeting object and creates the appropriate materials directories
    '''
    path = get_upload_root(meeting)
    os.umask(0)
    if not os.path.exists(path):
        os.makedirs(path)
    os.mkdir(os.path.join(path,'slides'))
    os.mkdir(os.path.join(path,'agenda'))
    os.mkdir(os.path.join(path,'minutes'))
    os.mkdir(os.path.join(path,'id'))
    os.mkdir(os.path.join(path,'rfc'))

def send_notification(request, sessions):
    '''
    This view generates email notifications for schedule sessions
    '''
    session_info_template = '''{0} Session {1} ({2})
    {3}, {4} {5}
    Room Name: {6}
    ---------------------------------------------
    '''
    group = sessions[0].group
    try:
        to_email = sessions[0].requested_by.email_address()
    except ObjectDoesNotExist:
        to_email = '[requested_by not found]'
    cc_list = get_cc_list(group, request.user.get_profile())
    from_email = ('"IETF Secretariat"','agenda@ietf.org')
    if sessions.count() == 1:
        subject = '%s - Requested session has been scheduled for IETF %s' % (group.acronym, sessions[0].meeting.number)
    else:
        subject = '%s - Requested sessions have been scheduled for IETF %s' % (group.acronym, sessions[0].meeting.number)
    template = 'meetings/session_schedule_notification.txt'
    
    # easier to populate template from timeslot perspective. assuming one-to-one timeslot-session
    count = 0
    session_info = ''
    data = [ (s,s.timeslot_set.all()[0]) for s in sessions ]
    for s,t in data:
        count += 1
        session_info += session_info_template.format(group.acronym, 
                                                     count, 
                                                     s.requested_duration,
                                                     t.time.strftime('%A'),
                                                     t.name,
                                                     '%s-%s' % (t.time.strftime('%H%M'),(t.time + t.duration).strftime('%H%M')),
                                                     t.location)
                                                     
    # send email
    context = {}
    context['to_name'] = sessions[0].requested_by
    context['agenda_note'] = sessions[0].agenda_note
    context['session'] = get_initial_session(sessions)
    context['session_info'] = session_info

    send_mail(request,
              to_email,
              from_email,
              subject,
              template,
              context,
              cc=cc_list)

"""
def update_switches():
    '''
    Updates the "switches" table.  This just stores the date and time that the meeting agenda
    was last updated.  This funtion should be called if a session is scheduled or edited.
    '''
    rec = Switches.objects.get(name='agenda_updated')
    rec.updated_date = datetime.date.today()
    rec.updated_time = datetime.datetime.now().strftime("%H:%M:%S")
    rec.save()
"""
# --------------------------------------------------
# STANDARD VIEW FUNCTIONS
# --------------------------------------------------
def add(request):
    '''
    Add a new IETF Meeting.  Creates Meeting and Proceeding objects.

    **Templates:**

    * ``meetings/add.html``

    **Template Variables:**

    * proceedingform

    '''
    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            url = reverse('meetings')
            return HttpResponseRedirect(url)

        form = MeetingModelForm(request.POST)
        if form.is_valid():
            meeting = form.save()
            
            #Create Physical new meeting directory and subdirectories
            make_directories(meeting)

            messages.success(request, 'The Meeting was created successfully!')
            url = reverse('meetings')
            return HttpResponseRedirect(url)
    else:
        # display initial forms
        max_number = Meeting.objects.filter(type='ietf').aggregate(Max('number'))['number__max']
        form = MeetingModelForm(initial={'number':int(max_number) + 1})

    return render_to_response('meetings/add.html', {
        'form': form},
        RequestContext(request, {}),
    )


def add_tutorial(request, meeting_id):
    '''
    This function essentially adds an entry to the acronym table.  The acronym_id set to the 
    lowest (negative) acronym_id minus one. This designates the acronym as a tutorial and will 
    now appear in the tutorial drop down list when scheduling sessions.
    '''
    pass
    """
    meeting = get_object_or_404(Meeting, meeting_num=meeting_id)

    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            url = reverse('meetings_select_group', kwargs={'meeting_id':meeting.pk})
            return HttpResponseRedirect(url)
            
        form = AddTutorialForm(request.POST)
        if form.is_valid():
            acronym = form.save(commit=False)
            new_id = Acronym.objects.all().aggregate(Min('acronym_id'))['acronym_id__min'] - 1
            acronym.acronym_id = new_id
            acronym.save()
            
            messages.success(request, 'The Tutorial was created successfully!')
            url = reverse('meetings_select_group', kwargs={'meeting_id':meeting.pk})
            return HttpResponseRedirect(url)
            
    else:
        form = AddTutorialForm()
    
    return render_to_response('meetings/add_tutorial.html', {
        'form': form,
        'meeting': meeting},
        RequestContext(request, {}),
    )
        
def blue_sheet(request):
    
    groups = IETFWG.objects.filter(meeting_scheduled="YES").select_related().order_by('group_acronym__acronym')
    meeting = Meeting.objects.all().order_by('-meeting_num')[0]
    
    file = open(settings.BLUE_SHEET_PATH, 'w')
    
    header = '''{\\rtf1\\ansi\\ansicpg1252\\uc1 \\deff0\\deflang1033\\deflangfe1033
 {\\fonttbl{\\f0\\froman\\fcharset0\\fprq2{\\*\\panose 02020603050405020304}Times New Roman;}}
 {\\colortbl;\\red0\\green0\\blue0;\\red0\\green0\\blue255;\\red0\\green255\\blue255;\\red0\\green255\\blue0;
\\red255\\green0\\blue255;\\red255\\green0\\blue0;\\red255\\green255\\blue0;\\red255\\green255\\blue255;
\\red0\\green0\\blue128;\\red0\\green128\\blue128;\\red0\\green128\\blue0;\\red128\\green0\\blue128;
\\red128\\green0\\blue0;\\red128\\green128\\blue0;\\red128\\green128\\blue128;
\\red192\\green192\\blue192;}
 \\widowctrl\\ftnbj\\aenddoc\\hyphcaps0\\formshade\\viewkind1\\viewscale100\\pgbrdrhead\\pgbrdrfoot
 \\fet0\\sectd \\pgnrestart\\linex0\\endnhere\\titlepg\\sectdefaultcl'''

    file.write(header)
    
    for group in groups:
        group_header = ''' {\\header \\pard\\plain \\s15\\qr\\nowidctlpar\\widctlpar\\tqc\\tx4320\\tqr\\tx8640\\adjustright \\fs20\\cgrid
 { Meeting # %s  %s (%s) \\par }
 \\pard \\s15\\nowidctlpar\\widctlpar\\tqc\\tx4320\\tqr\\tx8640\\adjustright
 {\\b\\fs24 Mailing List: %s 
 \\par
 \\par \\tab The NOTE WELL statement included in your registration packet applies to this meeting.
 \\par
 \\par                               NAME                                                  EMAIL ADDRESS
 \\par \\tab
 \\par }}
 {\\footer \\pard\\plain \\s16\\qc\\nowidctlpar\\widctlpar\\tqc\\tx4320\\tqr\\tx8640\\adjustright \\fs20\\cgrid {\\cs17 Page }
 {\\field{\\*\\fldinst {\\cs17  PAGE }}}
 { \\par }}
  {\\headerf \\pard\\plain \\s15\\qr\\nowidctlpar\\widctlpar\\tqc\\tx4320\\tqr\\tx8640\\adjustright \\fs20\\cgrid
  {\\b\\fs24 Meeting # %s %s (%s) \\par }}
 {\\footerf \\pard\\plain \\s16\\qc\\nowidctlpar\\widctlpar\\tqc\\tx4320\\tqr\\tx8640\\adjustright \\fs20\\cgrid
  {Page 1 \\par }}
  \\pard\\plain \\qc\\nowidctlpar\\widctlpar\\adjustright \\fs20\\cgrid
  {\\b\\fs32 %s IETF Working Group Roster \\par }
  \\pard \\nowidctlpar\\widctlpar\\adjustright
  {\\fs28 \\par Working Group Session: %s \\par \\par }
{\\b \\fs24 Mailing List: %s                    Actual Start Time: __________        \\par \\par Chairperson:_______________________________     Actua
l End Time: __________ \\par \\par }
 {\\tab \\tab      }
{\\par \\tab The NOTE WELL statement included in your registration packet applies to this meeting. \\par \\par
\\b NAME\\tab \\tab \\tab \\tab \\tab \\tab EMAIL ADDRESS \\par }
  \\pard \\fi-90\\li90\\nowidctlpar\\widctlpar\\adjustright
 {\\fs16''' % (meeting.meeting_num, group.acronym, group.group_type, group.email_address, meeting.meeting_num, group.acronym, group.group_type, meeting.meeting_num, group.group_name, group.email_address)
        file.write(group_header)
        for x in range(1,131):
            line = '''\\par %s._________________________________________________ \\tab _____________________________________________________
 \\par
 ''' % x
            file.write(line)
            
        footer = '''}
\\pard \\nowidctlpar\\widctlpar\\adjustright
{\\fs16 \\sect }
\\sectd \\pgnrestart\\linex0\\endnhere\\titlepg\\sectdefaultcl
'''
        file.write(footer)

    file.write('\n}')
    file.close()

    url = settings.BLUE_SHEET_URL
    
    messages.success(request, 'Blue Sheet Doc created')
    return render_to_response('meetings/blue_sheet.html', {
        'meeting': meeting,
        'url': url,},
        RequestContext(request, {}),
    )
            
def clear_meeting_scheduled(request):
    '''
    This view implements the "Clear all groups who are Meeting" button of the legacy groups app.
    See /a/cf/system/group/meeting/meeting2.cfm
    The legacy app also concluded BOFs but Wanda said not to implement that.
    '''
    groups = IETFWG.objects.all()
    for group in groups:
        group.meeting_scheduled_old = group.meeting_scheduled
        group.meeting_scheduled = 'NO'
        group.save()
        
    irtfs = IRTF.objects.all()
    for irtf in irtfs:
        irtf.meeting_scheduled = False
        irtf.save()
        
    messages.success(request, 'Cleared meeting_scheduled')
    url = reverse('meetings')
    return HttpResponseRedirect(url)
    
"""
def edit_meeting(request, meeting_id):
    '''
    Edit Meeting information.

    **Templates:**

    * ``meetings/meeting_edit.html``

    **Template Variables:**

    * meeting, form

    '''
    meeting = get_object_or_404(Meeting, number=meeting_id)

    if request.method == 'POST':
        button_text = request.POST.get('submit','')
        if button_text == 'Save':
            form = MeetingModelForm(request.POST, instance=meeting)
            if form.is_valid():
                form.save()
                messages.success(request,'The meeting entry was changed successfully')
                url = reverse('meetings_view', kwargs={'meeting_id':meeting_id})
                return HttpResponseRedirect(url)

        else:
            url = reverse('meetings_view', kwargs={'meeting_id':meeting_id})
            return HttpResponseRedirect(url)
    else:
        form = MeetingModelForm(instance=meeting)

    return render_to_response('meetings/edit_meeting.html', {
        'meeting': meeting,
        'form' : form, },
        RequestContext(request,{}),
    )

def edit_session(request, meeting_id, acronym):
    '''
    Edit session scheduling details
    '''
    meeting = get_object_or_404(Meeting, number=meeting_id)
    group = get_object_or_404(Group, acronym=acronym)
    sessions = Session.objects.filter(meeting=meeting,group=group)
    
    # NOTE special cases for Tutorials / BOFs
    if group.type_id != 'wg':
        show_request = False
        num_session = 1
    else:
        show_request = True
        num_session = sessions.count()
    
    # need to use curry here to pass custom variable to form init
    NewSessionFormset = formset_factory(NewSessionForm, extra=0)
    NewSessionFormset.form = staticmethod(curry(NewSessionForm, meeting=meeting))
    
    if request.method == 'POST':
        formset = NewSessionFormset(request.POST)
        extra_form = ExtraSessionForm(request.POST)
        if formset.is_valid() and extra_form.is_valid():
            for form in formset.forms:
                pass
            
            #update_switches()
            
            # update session activity
            #add_session_activity(group.pk,'Session was scheduled',meeting,request.person)
            
            # notify.  dont send if Tutorial, BOF or indicated on form
            notification_message = "No notification has been sent to anyone for this session."
            if not extra_form.cleaned_data.get('no_notify',False):
                if group.state.slug != 'bof':
                    send_notification(request, sessions)
                    notification_message = "Notification sent."
                            
            messages.success(request, 'Session(s) Scheduled for %s.  %s' %  (group.acronym, notification_message))
            url = reverse('meetings_select_group', kwargs={'meeting_id':meeting.pk})
            return HttpResponseRedirect(url)
            
    else:
        # intitialize forms
        initial = []


        formset = NewSessionFormset(initial=initial)
        extra_form = ExtraSessionForm(initial={'note':sessions[0].agenda_note})
        
    return render_to_response('meetings/edit_session.html', {
        'extra_form': extra_form,
        'show_request': show_request,
        'session': session,
        'formset': formset},
        RequestContext(request, {}),
    )

def main(request):
    '''
    In this view the user can choose a meeting to manage or elect to create a new meeting.
    '''
    meetings = Meeting.objects.filter(type='ietf').order_by('-number')
    
    if request.method == 'POST':
        redirect_url = reverse('meetings_view', kwargs={'meeting_id':request.POST['group']})
        return HttpResponseRedirect(redirect_url)
        
    choices = [ (str(x.number),str(x.number)) for x in meetings ]
    form = GroupSelectForm(choices=choices)
    
    return render_to_response('meetings/main.html', {
        'form': form,
        'meetings': meetings},
        RequestContext(request, {}),
    )
    

def new_session(request, meeting_id, acronym):
    '''
    Schedule a session
    Requirements:
    - display third session status if not 0
    - display session request info if it exists
    '''
    meeting = get_object_or_404(Meeting, number=meeting_id)
    group = get_object_or_404(Group, acronym=acronym)
    sessions = Session.objects.filter(meeting=meeting_id,group=group)
    legacy_session = get_initial_session(sessions)
    session_conflicts = session_conflicts_as_string(group, meeting)
    
    # warn and redirect to edit if there is already a scheduled session for this group
    if sessions:
        if sessions[0].status == 'sched':
            messages.error(request, 'The session for %s is already scheduled for meeting %s' % (sessions[0].group, meeting_id))
            url = reverse('meetings_edit_session', kwargs={'session_id':sessions[0].id})
            return HttpResponseRedirect(url)
            
    # set number of sessions
    if sessions:
        num_session = sessions.count()
    else:
        num_session = 1
        
    # need to use curry here to pass custom variable to form init
    NewSessionFormset = formset_factory(NewSessionForm, extra=0)
    NewSessionFormset.form = staticmethod(curry(NewSessionForm, meeting=meeting))

    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            url = reverse('meetings_select_group', kwargs={'meeting_id':meeting_id})
            return HttpResponseRedirect(url)

        formset = NewSessionFormset(request.POST)
        extra_form = ExtraSessionForm(request.POST)       
        
        if formset.is_valid() and extra_form.is_valid():
            note = extra_form.cleaned_data['note']
            
            # create session now if it doesn't exist (tutorials, BOFs)
            if not sessions:
                session = Session(meeting=meeting,group=group,status_id='schedw')
                session.save()
                    
            for form in formset.forms:
                timeslot = form.cleaned_data['time']
                id = form.cleaned_data['session']
                session = Session.objects.get(id=id)
                now = datetime.datetime.now()
                
                # handle "combine" option, this must be done before scheduling first slot
                if form.cleaned_data.get('combine',None):
                    # there must be a next slot or validation would have failed
                    next_slot = get_next_slot(timeslot)
                    next_slot.session = session
                    next_slot.modified = now
                    next_slot.save()
                    
                timeslot.session = session
                timeslot.modified = now
                timeslot.save()
                
                session.status_id = 'sched'
                if note:
                    session.agenda_note = note
                session.scheduled = now
                session.modified = now
                session.save()
                
            #update_switches()
            
            # update session activity
            #add_session_activity(group.id,'Session was scheduled',meeting,request.person)
            
            # notify.  dont send if Tutorial, BOF or indicated on form
            notification_message = "No notification has been sent to anyone for this session."
            if not extra_form.cleaned_data.get('no_notify',False):
                if group.state.slug != 'bof':
                    send_notification(request, sessions)
                    notification_message = "Notification sent."
                
            messages.success(request, 'Session(s) Scheduled for %s.  %s' %  (group.acronym, notification_message))
            url = reverse('meetings_select_group', kwargs={'meeting_id':meeting_id})
            return HttpResponseRedirect(url)
    else:
        initial = [ {'session':x.id} for x in sessions ]
        formset = NewSessionFormset(initial=initial)
        extra_form = ExtraSessionForm()

    return render_to_response('meetings/new_session.html', {
        'legacy_session':legacy_session,
        'group':group,
        'extra_form': extra_form,
        'formset': formset,
        'meeting': meeting,
        'sessions': sessions,
        'session_conflicts':session_conflicts},
        RequestContext(request, {}),
    )

def non_session(request, meeting_id):
    '''
    Display and edit "non-session" time slots, ie. registration, beverage and snack breaks
    '''
    pass
    """
    meeting = get_object_or_404(Meeting, meeting_num=meeting_id)
    
    # if the NonSession records don't exist yet (new meeting) create them
    if not NonSession.objects.filter(meeting=meeting):
        for record in NON_SESSION_INITIAL:
            new = NonSession(day_id=record[0],
                             non_session_ref=record[1],
                             meeting=meeting)
            new.save()
        
    NonSessionFormset = inlineformset_factory(Meeting, NonSession, form=NonSessionForm, can_delete=False,extra=0)
    
    if request.method == 'POST':
        formset = NonSessionFormset(request.POST, instance=meeting, prefix='non_session')
        if formset.is_valid():
            formset.save()
            messages.success(request, 'Non-Sessions updated successfully')
            url = reverse('meetings_non_session', kwargs={'meeting_id':meeting_id})
            return HttpResponseRedirect(url)
    else:       
        formset = NonSessionFormset(instance=meeting, prefix='non_session')
    
    return render_to_response('meetings/non_session.html', {
        'formset': formset,
        'meeting': meeting},
        RequestContext(request, {}),
    )

def remove_session(request, session_id):
    '''
    Remove session from agenda.  Deletes WgMeetingSession record entirely, meaning new session
    request will need to be submitted to re-schedule.
    '''
    session = get_object_or_404(WgMeetingSession, session_id=session_id)
    meeting = get_object_or_404(Meeting, meeting_num=session.meeting.meeting_num)
    group = session.group
    
    # delete the conflicts
    SessionConflict.objects.filter(meeting_num=meeting.meeting_num,group_acronym_id=group.pk).delete()
    
    # update group record
    # set specific values for IETFWG and IRTF, do nothing if group is a tutorial (Acronym)
    if isinstance(group, IRTF):
        group.meeting_scheduled = False
        group.save()
    if isinstance(group, IETFWG):
        group.meeting_scheduled = 'NO'
        group.save()
    
    # delete session record
    session.delete()
    
    # log activity
    add_session_activity(group.pk,'Session was removed from agenda',meeting,request.person)
    
    messages.success(request, '%s Session removed from agenda' % (session.group))
    url = reverse('meetings_select_group', kwargs={'meeting_id':meeting.meeting_num})
    return HttpResponseRedirect(url)
"""
def rooms(request, meeting_id):
    '''
    Display and edit MeetingRoom records for the specified meeting
    '''
    meeting = get_object_or_404(Meeting, number=meeting_id)
    
    # if no rooms exist yet (new meeting) formset extra=10
    first_time = not bool(meeting.room_set.all())
    extra = 10 if first_time else 0
    RoomFormset = inlineformset_factory(Meeting, Room, form=MeetingRoomForm, formset=BaseMeetingRoomFormSet, can_delete=True, extra=extra)

    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            url = reverse('meetings', kwargs={'meeting_id':meeting_id})
            return HttpResponseRedirect(url)

        formset = RoomFormset(request.POST, instance=meeting, prefix='room')
        if formset.is_valid():
            formset.save()
            
            # if we are creating rooms for the first time create full set of timeslots
            if first_time:
                build_timeslots(meeting)
                
            # otherwise if we're modifying rooms
            else:
                # add timeslots for new rooms, deleting rooms automatically deletes timeslots
                for form in formset.forms[formset.initial_form_count():]:
                    if form.instance.pk:
                        build_timeslots(meeting,room=form.instance)
            
            messages.success(request, 'Meeting Rooms changed successfully')
            url = reverse('meetings_rooms', kwargs={'meeting_id':meeting_id})
            return HttpResponseRedirect(url)
    else:
        formset = RoomFormset(instance=meeting, prefix='room')

    return render_to_response('meetings/rooms.html', {
        'meeting': meeting,
        'formset': formset},
        RequestContext(request, {}),
    )

def select_group(request, meeting_id):
    '''
    This view presents lists of WGs, Tutorials, BOFs for the secretariat user to select from to 
    schedule a session
    WGs: those that have pending session requests are listed.
    Tutorials: those that aren't already scheduled are listed
    BOFs: all BOFs which aren't already scheduled are lists
    IRTF: those that have pending session requests are listed.
    '''
    meeting = get_object_or_404(Meeting, number=meeting_id)
    
    if request.method == 'POST':
        redirect_url = reverse('meetings_new_session', kwargs={'meeting_id':meeting.number,'acronym':request.POST['group']})
        return HttpResponseRedirect(redirect_url)
            
    # get groups that have been scheduled
    
    scheduled_groups = Group.objects.filter(session__meeting=meeting,session__timeslot__isnull=False).order_by('acronym')
    
    # prep group form
    sessions = Session.objects.filter(~Q(status='sched'),group__type='wg',group__state='active',meeting=meeting)
    choices = build_choices( [ s.group for s in sessions ] )
    group_form = GroupSelectForm(choices=choices)
    
    # prep tutorial form
    # TODO change this feature
    #tutorials = Acronym.objects.filter(acronym_id__lt=0).order_by('name')
    #unscheduled_tutorials = [ t for t in tutorials if t.acronym_id not in scheduled_group_ids ]
    #tut_choices = zip([ x.pk for x in unscheduled_tutorials ],
    #              [ x.name for x in unscheduled_tutorials ])
    tutorial_form = GroupSelectForm(choices='')
    
    # prep BOFs form
    # seems like these should appear in group list above but maybe no request is filled out for them
    # include BOFs and PWG group types (3,2) per Wanda
    #bofs = Acronym.objects.filter(ietfwg__group_type__in=(2,3),ietfwg__status=1).order_by('acronym')
    bofs = Group.objects.filter(type='wg',state__in=('bof','proposed')).order_by('acronym')
    unscheduled_bofs = [ b for b in bofs if b not in scheduled_groups ]
    bof_choices = build_choices(unscheduled_bofs)
    bof_form = GroupSelectForm(choices=bof_choices)
    
    # prep IRTF form

    irtfs = Group.objects.filter(type='rg',state='active').order_by('acronym')
    unscheduled_irtfs = [ i for i in irtfs if i not in scheduled_groups ]
    irtf_choices = build_choices(unscheduled_irtfs)
    irtf_form = GroupSelectForm(choices=irtf_choices)
    
    return render_to_response('meetings/select_group.html', {
        'group_form': group_form,
        'tutorial_form': tutorial_form,
        'bof_form': bof_form,
        'irtf_form': irtf_form,
        'scheduled_groups': scheduled_groups,
        'meeting': meeting},
        RequestContext(request, {}),
    )

def times(request, meeting_id):
    '''
    Display and edit time slots (TimeSlots).  It doesn't display every TimeSlot
    object for the meeting because there is one timeslot per time per room, 
    rather it displays all the unique times.
    The first time this view is called for a meeting it creates a form with times
    prepopulated from the last meeting
    '''
    meeting = get_object_or_404(Meeting, number=meeting_id)
    
    # build list of timeslots
    slots = []
    timeslots = []
    time_seen = set()
    for t in meeting.timeslot_set.filter(type='session'):
        if not t.time in time_seen:
            time_seen.add(t.time)
            timeslots.append(t)
    for t in timeslots:
        slots.append({'name':t.name,
                      'time':t.time,
                      'duration':t.duration})
    times = sorted(slots, key=lambda a: a['time'])
                          
    if request.method == 'POST':
        form = TimeSlotForm(request.POST)
        if form.is_valid():
            day = form.cleaned_data['day']
            time = form.cleaned_data['time']
            duration = form.cleaned_data['duration']
            name = form.cleaned_data['name']
            
            t = meeting.date + datetime.timedelta(days=int(day))
            new_time = datetime.datetime(t.year,t.month,t.day,time.hour,time.minute)
            for room in meeting.room_set.all():
                TimeSlot.objects.create(type_id='session',
                                        meeting=meeting,
                                        name=name,
                                        time=new_time,
                                        location=room,
                                        duration=duration)
            
            messages.success(request, 'Timeslots created')
            url = reverse('meetings_times', kwargs={'meeting_id':meeting_id})
            return HttpResponseRedirect(url)
        
    else:
        form = TimeSlotForm()
        
    return render_to_response('meetings/times.html', {
        'form': form,
        'meeting': meeting,
        'times': times},
        RequestContext(request, {}),
    )
    
def times_delete(request, meeting_id, time):
    '''
    This view handles bulk delete of all timeslots matching time (datetime) for the given
    meeting.  There is one timeslot for each room.
    '''
    meeting = get_object_or_404(Meeting, number=meeting_id)
    
    parts = [ int(x) for x in time.split(':') ]
    dtime = datetime.datetime(*parts)
    
    if Session.objects.filter(timeslot__time=dtime,timeslot__meeting=meeting):
        messages.error(request, 'ERROR deleting timeslot.  There is one or more sessions scheduled for this timeslot.')
        url = reverse('meetings_times', kwargs={'meeting_id':meeting_id})
        return HttpResponseRedirect(url)
    
    TimeSlot.objects.filter(meeting=meeting,time=dtime).delete()
    
    messages.success(request, 'Timeslot deleted')
    url = reverse('meetings_times', kwargs={'meeting_id':meeting_id})
    return HttpResponseRedirect(url)
    
def view(request, meeting_id):
    '''
    View Meeting information.

    **Templates:**

    * ``meetings/view.html``

    **Template Variables:**

    * meeting , proceeding

    '''
    meeting = get_object_or_404(Meeting, number=meeting_id)
    
    return render_to_response('meetings/view.html', {
        'meeting': meeting},
        RequestContext(request, {}),
    )
