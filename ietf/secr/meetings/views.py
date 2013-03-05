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
from django.utils import simplejson

from ietf.utils.mail import send_mail
from ietf.meeting.models import Meeting, Session, Room, TimeSlot
from ietf.group.models import Group
from ietf.name.models import SessionStatusName, TimeSlotTypeName
from ietf.person.models import Person
from ietf.secr.meetings.blue_sheets import create_blue_sheets
from ietf.secr.proceedings.views import build_choices, handle_upload_file
from ietf.secr.sreq.forms import GroupSelectForm
from ietf.secr.sreq.views import get_initial_session, session_conflicts_as_string
from ietf.secr.utils.mail import get_cc_list
from ietf.secr.utils.meeting import get_upload_root

from forms import *

import os
import datetime

# --------------------------------------------------
# Helper Functions
# --------------------------------------------------
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
        # if we are just building timeslots for a new room, the room argument was passed,
        # then we need to use current meeting times as a template, not the last meeting times
        if room:
            source_meeting = meeting
        else:
            source_meeting = get_last_meeting(meeting)
            
        delta = meeting.date - source_meeting.date
        initial = []
        timeslots = []
        time_seen = set()
        for t in source_meeting.timeslot_set.filter(type='session'):
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

def build_nonsession(meeting):
    '''
    This function takes a meeting object and creates non-session records
    for a new meeting, based on the last meeting
    '''
    last_meeting = get_last_meeting(meeting)
    delta = meeting.date - last_meeting.date
    system = Person.objects.get(name='(system)')
    for slot in TimeSlot.objects.filter(meeting=last_meeting,type__in=('break','reg','other','plenary')):
        new_time = slot.time + delta
        session = None
        # create Session object for Tutorials to hold materials
        if slot.type.slug in ('other','plenary'):
            session = Session(meeting=meeting,
                              name=slot.name,
                              short=slot.session.short,
                              group=slot.session.group,
                              requested_by=system,
                              status_id='sched')
            session.save()
        
        TimeSlot.objects.create(type=slot.type,
                                meeting=meeting,
                                session=session,
                                name=slot.name,
                                time=new_time,
                                duration=slot.duration,
                                show_location=slot.show_location)
                                
def get_last_meeting(meeting):
    last_number = int(meeting.number) - 1
    return Meeting.objects.get(number=last_number)
    
def is_combined(session):
    '''
    Check to see if this session is using two combined timeslots
    '''
    if session.timeslot_set.count() > 1:
        return True
    else:
        return False
        
def make_directories(meeting):
    '''
    This function takes a meeting object and creates the appropriate materials directories
    '''
    path = get_upload_root(meeting)
    os.umask(0)
    if not os.path.exists(path):
        os.makedirs(path)
    for d in ('slides','agenda','minutes','id','rfc','bluesheets'):
        if not os.path.exists(os.path.join(path,d)):
            os.mkdir(os.path.join(path,d))

def send_notification(request, sessions):
    '''
    This view generates notifications for schedule sessions
    '''
    session_info_template = '''{0} Session {1} ({2})
    {3}, {4} {5}
    Room Name: {6}
    ---------------------------------------------
    '''
    group = sessions[0].group
    to_email = sessions[0].requested_by.role_email('chair').address
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

def sort_groups(meeting):
    '''
    Similar to sreq.views.sort_groups
    Takes a Django User object and a Meeting object
    Returns a tuple scheduled_groups, unscheduled groups.
    '''
    scheduled_groups = []
    unscheduled_groups = []
    #sessions = Session.objects.filter(meeting=meeting,status__in=('schedw','apprw','appr','sched','notmeet','canceled'))
    sessions = Session.objects.filter(meeting=meeting,status__in=('schedw','apprw','appr','sched','canceled'))
    groups_with_sessions = [ s.group for s in sessions ]
    gset = set(groups_with_sessions)
    sorted_groups_with_sessions = sorted(gset, key = lambda instance: instance.acronym)
    slots = TimeSlot.objects.filter(meeting=meeting,session__isnull=False)
    groups_with_timeslots = [ s.session.group for s in slots ]
    for group in sorted_groups_with_sessions:
            if group in groups_with_timeslots:
                scheduled_groups.append(group)
            else:
                unscheduled_groups.append(group)
            
    return scheduled_groups, unscheduled_groups
    
# -------------------------------------------------
# AJAX Functions
# -------------------------------------------------
def ajax_get_times(request, meeting_id, day):
    '''
    Ajax function to get timeslot times for a given day.
    returns JSON format response: [{id:start_time, value:start_time-end_time},...]
    '''
    # TODO strip duplicates if there are any  
    results=[]
    room = Room.objects.filter(meeting__number=meeting_id)[0]
    slots = TimeSlot.objects.filter(meeting__number=meeting_id,time__week_day=day,location=room).order_by('time')
    for slot in slots:
        d = {'id': slot.time.strftime('%H%M'), 'value': '%s-%s' % (slot.time.strftime('%H%M'), slot.end_time().strftime('%H%M'))}
        results.append(d)
        
    return HttpResponse(simplejson.dumps(results), mimetype='application/javascript')
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

def blue_sheet(request, meeting_id):
    '''
    Blue Sheet view.  The user can generate blue sheets or upload scanned bluesheets
    '''
    meeting = get_object_or_404(Meeting, number=meeting_id)
    
    url = settings.SECR_BLUE_SHEET_URL
    
    if request.method == 'POST':
        form = UploadBlueSheetForm(request.POST,request.FILES)
        if form.is_valid():
            file = request.FILES['file']
            handle_upload_file(file,file.name,meeting,'bluesheets')
            messages.success(request, 'File Uploaded')
            url = reverse('meetings_blue_sheet', kwargs={'meeting_id':meeting.number})
            return HttpResponseRedirect(url)
    
    else:
        form = UploadBlueSheetForm()
        
    return render_to_response('meetings/blue_sheet.html', {
        'meeting': meeting,
        'url': url,
        'form': form},
        RequestContext(request, {}),
    )
    
def blue_sheet_generate(request, meeting_id):
    '''
    Generate bluesheets
    '''
    meeting = get_object_or_404(Meeting, number=meeting_id)
    
    groups = Group.objects.filter(session__meeting=meeting).order_by('acronym')
    create_blue_sheets(meeting, groups)
    
    messages.success(request, 'Blue Sheets generated')
    url = reverse('meetings_blue_sheet', kwargs={'meeting_id':meeting.number})
    return HttpResponseRedirect(url)

def blue_sheet_redirect(request):
    '''
    This is the generic blue sheet URL.  It gets the next IETF meeting and redirects
    to the meeting specific URL.
    '''
    today = datetime.date.today()
    qs = Meeting.objects.filter(date__gt=today,type='ietf').order_by('date')
    if qs:
        meeting = qs[0]
    else:
        meeting = Meeting.objects.filter(type='ietf').order_by('-date')[0]
    url = reverse('meetings_blue_sheet', kwargs={'meeting_id':meeting.number})
    return HttpResponseRedirect(url)

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

def non_session(request, meeting_id):
    '''
    Display and add "non-session" time slots, ie. registration, beverage and snack breaks
    '''
    meeting = get_object_or_404(Meeting, number=meeting_id)
    
    # if the Break/Registration records don't exist yet (new meeting) create them
    if not TimeSlot.objects.filter(meeting=meeting,type__in=('break','reg','other')):
        build_nonsession(meeting)
    
    slots = TimeSlot.objects.filter(meeting=meeting,type__in=('break','reg','other','plenary')).order_by('-type__name','time')
    
    if request.method == 'POST':
        form = NonSessionForm(request.POST)
        if form.is_valid():
            day = form.cleaned_data['day']
            time = form.cleaned_data['time']
            name = form.cleaned_data['name']
            short = form.cleaned_data['short']
            type = form.cleaned_data['type']
            group = form.cleaned_data['group']
            duration = form.cleaned_data['duration']
            t = meeting.date + datetime.timedelta(days=int(day))
            new_time = datetime.datetime(t.year,t.month,t.day,time.hour,time.minute)
            
            # create a dummy Session object to hold materials
            # NOTE: we're setting group to none here, but the set_room page will force user 
            # to pick a legitimate group
            session = None
            if type.slug in ('other','plenary'):
                session = Session(meeting=meeting,
                                  name=name,
                                  short=short,
                                  group=group,
                                  requested_by=Person.objects.get(name='(system)'),
                                  status_id='sched')
                session.save()
            
            # create TimeSlot object
            TimeSlot.objects.create(type=form.cleaned_data['type'],
                                    meeting=meeting,
                                    session=session,
                                    name=name,
                                    time=new_time,
                                    duration=duration,
                                    show_location=form.cleaned_data['show_location'])
            
            messages.success(request, 'Non-Sessions updated successfully')
            url = reverse('meetings_non_session', kwargs={'meeting_id':meeting_id})
            return HttpResponseRedirect(url)
    else:       
        form = NonSessionForm(initial={'show_location':True})
    
    if TimeSlot.objects.filter(meeting=meeting,type='other',location__isnull=True):
        messages.warning(request, 'There are non-session items which do not have a room assigned')
        
    return render_to_response('meetings/non_session.html', {
        'slots': slots,
        'form': form,
        'meeting': meeting},
        RequestContext(request, {}),
    )

def non_session_delete(request, meeting_id, slot_id):
    '''
    This function deletes the non-session TimeSlot.  For "other" and "plenary" timeslot types
    we need to delete the corresponding Session object as well.  Check for uploaded material 
    first.
    '''
    slot = get_object_or_404(TimeSlot, id=slot_id)
    if slot.type_id in ('other','plenary'):
        if slot.session.materials.exclude(states__slug='deleted'):
            messages.error(request, 'Materials have already been uploaded for "%s".  You must delete those before deleting the timeslot.' % slot.name)
            url = reverse('meetings_non_session', kwargs={'meeting_id':meeting_id})
            return HttpResponseRedirect(url)
            
        else:
            slot.session.delete()
    slot.delete()
    
    messages.success(request, 'Non-Session timeslot deleted successfully')
    url = reverse('meetings_non_session', kwargs={'meeting_id':meeting_id})
    return HttpResponseRedirect(url)

def non_session_edit(request, meeting_id, slot_id):
    '''
    Allows the user to assign a location to this non-session timeslot
    '''
    meeting = get_object_or_404(Meeting, number=meeting_id)
    slot = get_object_or_404(TimeSlot, id=slot_id)

    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            url = reverse('meetings_non_session', kwargs={'meeting_id':meeting_id})
            return HttpResponseRedirect(url)
            
        form = NonSessionEditForm(request.POST,meeting=meeting, session=slot.session)
        if form.is_valid():
            location = form.cleaned_data['location']
            group = form.cleaned_data['group']
            name = form.cleaned_data['name']
            short = form.cleaned_data['short']
            slot.location = location
            slot.name = name
            slot.save()
            # save group to session object
            session = slot.session
            session.group = group
            session.name = name
            session.short = short
            session.save()
            
            messages.success(request, 'Location saved')
            url = reverse('meetings_non_session', kwargs={'meeting_id':meeting_id})
            return HttpResponseRedirect(url)
        
    else:
        # we need to pass the session to the form in order to disallow changing
        # of group after materials have been uploaded
        initial = {'location':slot.location,
                   'group':slot.session.group,
                   'name':slot.session.name,
                   'short':slot.session.short}
        form = NonSessionEditForm(meeting=meeting,session=slot.session,initial=initial)
            
    return render_to_response('meetings/non_session_edit.html', {
        'meeting': meeting,
        'form': form,
        'slot': slot},
        RequestContext(request, {}),
    )
    
def remove_session(request, meeting_id, acronym):
    '''
    Remove session from agenda.  Disassociate session from timeslot and set status.
    According to Wanda this option is used when people cancel, so the Session
    request should be deleted as well.
    '''
    meeting = get_object_or_404(Meeting, number=meeting_id)
    group = get_object_or_404(Group, acronym=acronym)
    sessions = Session.objects.filter(meeting=meeting,group=group)
    now = datetime.datetime.now()
    
    for session in sessions:
        timeslot = session.timeslot_set.all()[0]
        timeslot.session = None
        timeslot.modified = now
        timeslot.save()
        session.status_id = 'canceled'
        session.modified = now
        session.save()
    
    messages.success(request, '%s Session removed from agenda' % (group.acronym))
    url = reverse('meetings_select_group', kwargs={'meeting_id':meeting.number})
    return HttpResponseRedirect(url)

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

def schedule(request, meeting_id, acronym):
    '''
    This view handles scheduling session requests to TimeSlots
    '''
    meeting = get_object_or_404(Meeting, number=meeting_id)
    group = get_object_or_404(Group, acronym=acronym)
    sessions = Session.objects.filter(meeting=meeting,group=group,status__in=('schedw','apprw','appr','sched','canceled'))
    legacy_session = get_initial_session(sessions)
    session_conflicts = session_conflicts_as_string(group, meeting)
    now = datetime.datetime.now()
        
    # build initial
    initial = []
    for s in sessions:
        d = {'session':s.id,
             'note':s.agenda_note}
        qs = s.timeslot_set.all()
        if qs:
            d['room'] = qs[0].location.id
            d['day'] = qs[0].time.isoweekday() % 7 + 1     # adjust to django week_day
            d['time'] = qs[0].time.strftime('%H%M')
        else:
            d['day'] = 2
        if is_combined(s):
            d['combine'] = True
        initial.append(d)
    
    # need to use curry here to pass custom variable to form init
    NewSessionFormset = formset_factory(NewSessionForm, extra=0)
    NewSessionFormset.form = staticmethod(curry(NewSessionForm, meeting=meeting))
    
    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            url = reverse('meetings_select_group', kwargs={'meeting_id':meeting_id})
            return HttpResponseRedirect(url)

        formset = NewSessionFormset(request.POST,initial=initial)
        extra_form = ExtraSessionForm(request.POST)       
        
        if formset.is_valid() and extra_form.is_valid():
            # TODO formsets don't have has_changed until Django 1.3
            has_changed = False
            for form in formset.forms:
                if form.has_changed():
                    has_changed = True
                    id = form.cleaned_data['session']
                    note = form.cleaned_data['note']
                    room = form.cleaned_data['room']
                    time = form.cleaned_data['time']
                    day = form.cleaned_data['day']
                    combine = form.cleaned_data.get('combine',None)
                    session = Session.objects.get(id=id)
                    if session.timeslot_set.all():
                        initial_timeslot = session.timeslot_set.all()[0]
                    else:
                        initial_timeslot = None
                        
                    # find new timeslot
                    new_day = meeting.date + datetime.timedelta(days=int(day)-1)
                    hour = datetime.time(int(time[:2]),int(time[2:]))
                    new_time = datetime.datetime.combine(new_day,hour)
                    qs = TimeSlot.objects.filter(meeting=meeting,time=new_time,location=room)
                    if qs.filter(session=None):
                        timeslot = qs.filter(session=None)[0]
                    else:
                        # we need to create another, identical timeslot
                        timeslot = TimeSlot.objects.create(meeting=qs[0].meeting,
                                                           type=qs[0].type,
                                                           name=qs[0].name,
                                                           time=qs[0].time,
                                                           duration=qs[0].duration,
                                                           location=qs[0].location,
                                                           show_location=qs[0].show_location,
                                                           modified=now)
                        messages.warning(request, 'WARNING: There are now two sessions scheduled for the timeslot: %s' % timeslot)
                    
                    if any(x in form.changed_data for x in ('day','time','room')):
                        # clear the old timeslot
                        if initial_timeslot:
                            # if the initial timeslot is one of multiple we should delete it
                            tqs = TimeSlot.objects.filter(meeting=meeting,
                                                          type='session',
                                                          time=initial_timeslot.time,
                                                          location=initial_timeslot.location)
                            if tqs.count() > 1:
                                initial_timeslot.delete()
                            else:
                                initial_timeslot.session = None
                                initial_timeslot.modified = now
                                initial_timeslot.save()
                        if timeslot:
                            timeslot.session = session
                            timeslot.modified = now
                            timeslot.save()
                            session.status_id = 'sched'
                        else:
                            session.status_id = 'schedw'
                            
                        session.modified = now
                        session.save()
                    
                    if 'note' in form.changed_data:
                        session.agenda_note = note
                        session.modified = now
                        session.save()
                    
                    # COMBINE SECTION ----------------------
                    if 'combine' in form.changed_data:
                        next_slot = get_next_slot(timeslot)
                        if combine:
                            next_slot.session = session
                        else:
                            next_slot.session = None
                        next_slot.modified = now
                        next_slot.save()
                    # ---------------------------------------
            
            # notify.  dont send if Tutorial, BOF or indicated on form
            notification_message = "No notification has been sent to anyone for this session."
            if (has_changed 
                and not extra_form.cleaned_data.get('no_notify',False)
                and group.state.slug != 'bof'
                and session.timeslot_set.all()):       # and the session is scheduled, else skip
                
                send_notification(request, sessions)
                notification_message = "Notification sent."
                
            if has_changed:
                messages.success(request, 'Session(s) Scheduled for %s.  %s' %  (group.acronym, notification_message))
            
            url = reverse('meetings_select_group', kwargs={'meeting_id':meeting_id})
            return HttpResponseRedirect(url)

    else:
        formset = NewSessionFormset(initial=initial)
        extra_form = ExtraSessionForm()
        
    return render_to_response('meetings/schedule.html', {
        'extra_form': extra_form,
        'group': group,
        'meeting': meeting,
        'show_request': True,
        'session': legacy_session,
        'formset': formset},
        RequestContext(request, {}),
    )
    
def select_group(request, meeting_id):
    '''
    In this view the user can select the group to schedule.  Only those groups that have
    submitted session requests appear in the dropdowns.
    
    NOTE: BOF list includes Proposed Working Group type, per Wanda
    '''
    meeting = get_object_or_404(Meeting, number=meeting_id)
    
    if request.method == 'POST':
        group = request.POST.get('group',None)
        if group:
            redirect_url = reverse('meetings_schedule', kwargs={'meeting_id':meeting_id,'acronym':group})
        else:
            redirect_url = reverse('meetings_select_group',kwargs={'meeting_id':meeting_id})
            messages.error(request, 'No group selected')
            
        return HttpResponseRedirect(redirect_url)
            
    # split groups into scheduled / unscheduled
    scheduled_groups, unscheduled_groups = sort_groups(meeting)
    
    # prep group form
    wgs = filter(lambda a: a.type_id in ('wg','ag') and a.state_id=='active', unscheduled_groups)
    group_form = GroupSelectForm(choices=build_choices(wgs))
    
    # prep BOFs form
    bofs = filter(lambda a: a.type_id=='wg' and a.state_id in ('bof','proposed'), unscheduled_groups)
    bof_form = GroupSelectForm(choices=build_choices(bofs))
    
    # prep IRTF form
    irtfs = filter(lambda a: a.type_id=='rg' and a.state_id in ('active','proposed'), unscheduled_groups)
    irtf_form = GroupSelectForm(choices=build_choices(irtfs))
    
    return render_to_response('meetings/select_group.html', {
        'group_form': group_form,
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
                      'end_time':t.end_time()})
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
            
            # don't allow creation of timeslots with same start time as existing timeslots
            # assert False, (new_time, time_seen)
            if new_time in time_seen:
                messages.error(request, 'There is already a timeslot for %s.  To change you must delete the old one first.' % new_time.strftime('%a %H:%M'))
                url = reverse('meetings_times', kwargs={'meeting_id':meeting_id})
                return HttpResponseRedirect(url)
            
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
