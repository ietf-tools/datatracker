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

#from sec.proceedings.views import build_choices
#from sec.core.forms import GroupSelectForm
#from sec.core.models import Acronym, WGType
#from sec.utils.sessions import add_session_activity
#from sec.utils.shortcuts import get_group_or_404
#from sec.utils.ams_mail import get_cc_list
#from sec.core.models import Acronym, IETFWG, IRTF, MeetingHour, SessionConflict, Switches, WgMeetingSession,  WGType
#from sec.proceedings.models import Proceeding, SessionName

from ietf.utils.mail import send_mail
from ietf.meeting.models import Meeting, Session, Room, TimeSlot
from ietf.group.models import Group
from ietf.name.models import SessionStatusName, TimeSlotTypeName
from sec.proceedings.views import build_choices
from sec.sreq.forms import GroupSelectForm
from sec.sreq.views import get_initial_session, session_conflicts_as_string
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
    pre-creates the full set of timeslot records using the last meeting as a template.  
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
        initial = []
        timeslots = []
        time_seen = set()
        for t in last_meeting.timeslot_set.filter(type='session'):
            if not t.time in time_seen:
                time_seen.add(t.time)
                timeslots.append(t)
        for t in timeslots:
            new_time = t.time
            for room in rooms:
                TimeSlot.objects.create(type_id='session',
                                        meeting=meeting,
                                        name=t.name,
                                        time=new_time,
                                        location=room,
                                        duration=t.duration)

def init_timeslot_records(meeting):
    '''
    This function gets called when a new meeting is created.  It creates empty timeslot records
    to represent the schedule for the meeting (based on the schedule for the last meeting).  
    These records are used as metadata for scheduling actual sessions.
    '''
    
    # do nothing if there are already timeslots (something is wrong)
    if meeting.timeslot_set.filter(type='session'):
        return None
        
    last_meeting = get_last_meeting(meeting)
    timeslots = []
    time_seen = set()
    for t in last_meeting.timeslot_set.filter(type='session'):
        if not t.time in time_seen:
            time_seen.add(t.time)
            timeslots.append(t)
    for t in timeslots:
        new_time = t.time
        TimeSlot.objects.create(meeting=meeting,
                                type_id='session',
                                name=t.name,
                                time=new_time,
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
"""    
def send_notification(request, session):
    '''
    This view generates email notifications for schedule sessions
    '''
    session_info_template = '''{0} Session {1} ({2})
    {3}, {4} {5}
    Room Name: {6}
    ---------------------------------------------
    '''
    group = get_group_or_404(session.group_acronym_id)
    group_name = group.acronym
    try:
        to_email = session.requested_by.email()
    except ObjectDoesNotExist:
        to_email = '[requested_by not found]'
    cc_list = get_cc_list(group, request.person)
    from_email = ('"IETF Secretariat"','agenda@ietf.org')
    subject = '%s - Requested session has been scheduled for IETF %s' % (group_name, session.meeting.meeting_num)
    template = 'meetings/session_schedule_notification.txt'
    
    session_info = session_info_template.format(group_name, 
                                                1, 
                                                session.length_session1,
                                                MeetingTime.DAYS[session.sched_time_id1.day_id],
                                                session.sched_time_id1.session_name,
                                                session.sched_time_id1.time_desc,
                                                session.sched_room_id1.room_name)
    if session.num_session > 1:
        subject = '%s - Requested sessions have been scheduled for IETF %s' % (group_name, session.meeting.meeting_num)
        session_info += session_info_template.format(group_name, 
                                                     2, 
                                                     session.length_session2,
                                                     MeetingTime.DAYS[session.sched_time_id2.day_id],
                                                     session.sched_time_id2.session_name,
                                                     session.sched_time_id2.time_desc,
                                                     session.sched_room_id2.room_name)
    if session.length_session3 and session.ts_status_id == 4:
        session_info += session_info_template.format(group_name, 
                                                     3, 
                                                     session.length_session3,
                                                     MeetingTime.DAYS[session.sched_time_id3.day_id],
                                                     session.sched_time_id3.session_name,
                                                     session.sched_time_id3.time_desc,
                                                     session.sched_room_id3.room_name)
                                                     
    # send email
    context = {}
    context['to_name'] = str(session.requested_by)
    context['session'] = session
    context['session_info'] = session_info

    send_mail(request,
              to_email,
              from_email,
              subject,
              template,
              context,
              cc=cc_list)
              
def update_switches():
    '''
    Updates the "switches" table.  This just stores the date and time that the meeting agenda
    was last updated.  This funtion should be called if a session is scheduled or edited.
    '''
    rec = Switches.objects.get(name='agenda_updated')
    rec.updated_date = datetime.date.today()
    rec.updated_time = datetime.datetime.now().strftime("%H:%M:%S")
    rec.save()
    
# --------------------------------------------------
# STANDARD VIEW FUNCTIONS
# --------------------------------------------------
"""
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
    # get meeting or return HTTP 404 if record not found
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

def edit_session(request, session_id):
    '''
    Edit session scheduling details
    '''
    pass
    """
    session = get_object_or_404(WgMeetingSession, session_id=session_id)
    meeting = get_object_or_404(Meeting, meeting_num=session.meeting.meeting_num)
    group = session.group
    
    # NOTE special cases for Tutorials / BOFs
    if ( isinstance(group, IETFWG) and group.group_type.pk == 3 ) or group.pk < 0:
        show_request = False
        num_session = 1
    else:
        show_request = True
        num_session = session.real_num_session
    
    # need to use curry here to pass custom variable to form init
    NewSessionFormset = formset_factory(NewSessionForm, extra=0)
    NewSessionFormset.form = staticmethod(curry(NewSessionForm, meeting=meeting))
    
    if request.method == 'POST':
        formset = NewSessionFormset(request.POST)
        extra_form = ExtraSessionForm(request.POST)
        if formset.is_valid() and extra_form.is_valid():
            # do save
            count = 1
            for form in formset.forms:
                time_attr = 'sched_time_id' + str(count)
                room_attr = 'sched_room_id' + str(count)
                time = MeetingTime.objects.get(id=form.cleaned_data['time'])
                room = MeetingRoom.objects.get(id=form.cleaned_data['room'])
                setattr(session, time_attr, time)
                setattr(session, room_attr, room)
                
                # handle "combine" option
                if form.cleaned_data.get('combine',None):
                    # there must be a next slot or validation would have failed
                    next_slot = get_next_slot(time.id)
                    if count != 3:
                        comb_time = 'combined_time_id' + str(count)
                        comb_room = 'combined_room_id' + str(count)
                        setattr(session, comb_time, next_slot)
                        setattr(session, comb_room, room)
                else:
                    if count != 3:
                        comb_time = 'combined_time_id' + str(count)
                        comb_room = 'combined_room_id' + str(count)
                        setattr(session, comb_time, None)
                        setattr(session, comb_room, None)
                    
                if count == 3 and session.ts_status_id == 3:
                    session.ts_status_id = 4
                
                '''
                if isinstance(group, IRTF):
                    one_hour = MeetingHour.objects.get(hour_id=1)
                    session.irtf = 1
                    session.num_session = 1
                    session.length_session1 = one_hour
                    session.requested_by = request.person
                '''
                count = count + 1
                
            session.status_id = 4
            session.scheduled_date = datetime.datetime.now()
            session.special_agenda_note = extra_form.cleaned_data['note']
            session.save()
            
            update_switches()
            
            # update session activity
            add_session_activity(group.pk,'Session was scheduled',meeting,request.person)
            
            # notify.  dont send if Tutorial, BOF or indicated on form
            notification_message = "No notification has been sent to anyone for this session."
            if not extra_form.cleaned_data.get('no_notify',False):
                if group.pk > 0:
                    group = get_group_or_404(group.pk)
                    bof_type = WGType.objects.get(group_type_id=3)
                    if hasattr(group,'group_type') and group.group_type == bof_type:
                        pass
                    else:
                        send_notification(request, session)
                        notification_message = "Notification sent."
                            
            messages.success(request, 'Session(s) Scheduled for %s.  %s' %  (group.acronym, notification_message))
            url = reverse('meetings_select_group', kwargs={'meeting_id':meeting.pk})
            return HttpResponseRedirect(url)
            
    else:
        # intitialize forms
        initial = []
        if session.sched_time_id1:
            values = {'time':str(session.sched_time_id1.pk),
                      'room':str(session.sched_room_id1.pk)}
            if session.combined_room_id1:
                values['combined'] = True
            initial.append(values)
        if session.sched_time_id2:
            values = {'time':str(session.sched_time_id2.pk),
                      'room':str(session.sched_room_id2.pk)}
            if session.combined_room_id2:
                values['combined'] = True
            initial.append(values)
        if session.sched_time_id3:
            values = {'time':str(session.sched_time_id3.pk),
                      'room':str(session.sched_room_id3.pk)}
            initial.append(values)
        #assert False, initial
        formset = NewSessionFormset(initial=initial)
        extra_form = ExtraSessionForm(initial={'note':session.special_agenda_note})
        
    return render_to_response('meetings/edit_session.html', {
        'extra_form': extra_form,
        'show_request': show_request,
        'session': session,
        'formset': formset},
        RequestContext(request, {}),
    )

"""
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
    NewSessionFormset = formset_factory(NewSessionForm, extra=num_session)
    NewSessionFormset.form = staticmethod(curry(NewSessionForm, meeting=meeting))

    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            url = reverse('meetings_select_group', kwargs={'meeting_id':meeting_id})
            return HttpResponseRedirect(url)

        formset = NewSessionFormset(request.POST)
        extra_form = ExtraSessionForm(request.POST)
        
        
        if formset.is_valid() and extra_form.is_valid():
            # create session now if it doesn't exist (tutorials, BOFs)
            if not sessions:
                sess_stat = SessionStatusName.objects.get(slug='schedw')
                session = Session(meeting=meeting,group=group,status=sess_stat)
                session.save()
                    
            count = 1
            for form in formset.forms:
                time_attr = 'sched_time_id' + str(count)
                room_attr = 'sched_room_id' + str(count)
                time = TimeSlot.objects.get(id=form.cleaned_data['time'])
                room = Room.objects.get(id=form.cleaned_data['room'])
                setattr(session, time_attr, time)
                setattr(session, room_attr, room)
                
                # handle "combine" option
                if form.cleaned_data.get('combine',None):
                    # there must be a next slot or validation would have failed
                    next_slot = get_next_slot(time.id)
                    if count != 3:
                        comb_time = 'combined_time_id' + str(count)
                        comb_room = 'combined_room_id' + str(count)
                        setattr(session, comb_time, next_slot)
                        setattr(session, comb_room, room)
                    
                if count == 3 and session.ts_status_id == 3:
                    session.ts_status_id = 4
                
                '''
                if isinstance(group, IRTF):
                    one_hour = MeetingHour.objects.get(hour_id=1)
                    session.irtf = 1
                    session.num_session = 1
                    session.length_session1 = one_hour
                    session.requested_by = request.person
                '''
                count = count + 1
                
            session.status_id = 4
            session.scheduled_date = datetime.datetime.now()
            session.special_agenda_note = extra_form.cleaned_data['note']
            session.save()
            update_switches()
            
            # update session activity
            add_session_activity(group.id,'Session was scheduled',meeting,request.person)
            
            # notify.  dont send if Tutorial, BOF or indicated on form
            notification_message = "No notification has been sent to anyone for this session."
            if not extra_form.cleaned_data.get('no_notify',False):
                if int(group_id) > 0:
                    group = get_group_or_404(group_id)
                    bof_type = WGType.objects.get(group_type_id=3)
                    if hasattr(group,'group_type') and group.group_type == bof_type:
                        pass
                    else:
                        send_notification(request, session)
                        notification_message = "Notification sent."
                
            messages.success(request, 'Session(s) Scheduled for %s.  %s' %  (group.acronym, notification_message))
            url = reverse('meetings_select_group', kwargs={'meeting_id':meeting_id})
            return HttpResponseRedirect(url)
    else:
        formset = NewSessionFormset()
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
    # TODO rewrite these queries more efficiently
    meeting = get_object_or_404(Meeting, number=meeting_id)
    
    if request.method == 'POST':
        redirect_url = reverse('meetings_new_session', kwargs={'meeting_id':meeting.number,'acronym':request.POST['group']})
        return HttpResponseRedirect(redirect_url)
            
    scheduled_sessions = Session.objects.filter(meeting=meeting,status='sched')
    scheduled_groups = [ s.group for s in scheduled_sessions ]
    sorted_scheduled_sessions = sorted(scheduled_sessions, key=lambda scheduled_sessions: scheduled_sessions.group.acronym.lower())
    #scheduled_group_ids = [ s.group_acronym_id for s in scheduled_sessions ]
    
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
        'scheduled_sessions': sorted_scheduled_sessions,
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
    TimeSlotFormset = formset_factory(TimeSlotForm, extra=0)
    #TimeSlotFormset = inlineformset_factory(Meeting, TimeSlot, form=TimeSlotModelForm, can_delete=True)
    
    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            url = reverse('meetings', kwargs={'meeting_id':meeting_id})
            return HttpResponseRedirect(url)
    else:
        initial = []
        timeslots = []
        time_seen = set()
        for t in last_meeting.timeslot_set.filter(type='session'):
            if not t.time in time_seen:
                time_seen.add(t.time)
                timeslots.append(t)
        for t in timeslots:
            new_time = t.time
            initial.append({'name':t.name,
                            'time':new_time,
                            'duration':t.duration})
        formset=TimeSlotFormset(initial=initial)
        if meeting.room_set.all():
            times = 'some times'
        else:
            times = None
        
            
    return render_to_response('meetings/times.html', {
        'meeting': meeting,
        'formset': formset,
        'times': times,
        'initial':initial},
        RequestContext(request, {}),
    )
    
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
