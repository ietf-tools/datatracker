import datetime
import json
import os
import time

from django.conf import settings
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.db.models import Max
from django.forms.formsets import formset_factory
from django.forms.models import inlineformset_factory
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response, get_object_or_404, redirect
from django.template import RequestContext
from django.utils.functional import curry

from ietf.dbtemplate.models import DBTemplate
from ietf.ietfauth.utils import role_required
from ietf.utils.mail import send_mail
from ietf.meeting.helpers import get_meeting, make_materials_directories
from ietf.meeting.models import Meeting, Session, Room, TimeSlot, SchedTimeSessAssignment, Schedule
from ietf.group.models import Group, GroupEvent
from ietf.person.models import Person
from ietf.secr.meetings.blue_sheets import create_blue_sheets
from ietf.secr.meetings.forms import ( BaseMeetingRoomFormSet, MeetingModelForm,
    MeetingRoomForm, NewSessionForm, NonSessionEditForm, NonSessionForm, TimeSlotForm,
    UploadBlueSheetForm, get_next_slot )
from ietf.secr.proceedings.views import build_choices, handle_upload_file
from ietf.secr.sreq.forms import GroupSelectForm
from ietf.secr.sreq.views import get_initial_session
from ietf.secr.utils.meeting import get_session, get_timeslot
from ietf.mailtrigger.utils import gather_address_lists


# prep for agenda changes
# --------------------------------------------------
# Helper Functions
# --------------------------------------------------
def assign(session,timeslot,meeting,schedule=None):
    '''
    Robust function to assign a session to a timeslot.  Much simplyfied 2014-03-26.
    '''
    if schedule == None:
        schedule = meeting.agenda
    SchedTimeSessAssignment.objects.create(schedule=schedule,
                                    session=session,
                                    timeslot=timeslot)
    session.status_id = 'sched'
    session.save()

def build_timeslots(meeting,room=None):
    '''
    This function takes a Meeting object and an optional room argument.  If room isn't passed we
    pre-create the full set of timeslot records using the last meeting as a template.
    If room is passed pre-create timeslots for the new room.  Call this after saving new rooms
    or adding a room.
    '''
    slots = meeting.timeslot_set.filter(type='session')

    # Don't do anything if the room is not capable of handling sessions
    if room and not room.session_types.filter(slug='session'):
        return

    if room:
        rooms = [room]
    else:
        rooms = meeting.room_set.filter(session_types__slug='session')
    if not slots or room:
        # if we are just building timeslots for a new room, the room argument was passed,
        # then we need to use current meeting times as a template, not the last meeting times
        if room:
            source_meeting = meeting
        else:
            source_meeting = get_last_meeting(meeting)

        delta = meeting.date - source_meeting.date
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

def build_nonsession(meeting,schedule):
    '''
    This function takes a meeting object and creates non-session records
    for a new meeting, based on the last meeting
    '''
    last_meeting = get_last_meeting(meeting)
    if not last_meeting:
        return None
    
    delta = meeting.date - last_meeting.date
    system = Person.objects.get(name='(system)')
    secretariat = Group.objects.get(acronym='secretariat')
    
    for slot in TimeSlot.objects.filter(meeting=last_meeting,type__in=('break','reg','other','plenary','lead')):
        new_time = slot.time + delta
        session = None
        # create Session object for Tutorials to hold materials
        if slot.type.slug in ('other','plenary'):
            session = Session(meeting=meeting,
                              name=slot.name,
                              short=get_session(slot).short,
                              group=get_session(slot).group,
                              requested_by=system,
                              status_id='sched',
                              type=slot.type,
                             )
        else:
            session, __ = Session.objects.get_or_create(meeting=meeting,
                              name=slot.name,
                              group=secretariat,
                              requested_by=system,
                              status_id='sched',
                              type=slot.type,
                             )
        session.save()

        ts = TimeSlot.objects.create(type=slot.type,
                                meeting=meeting,
                                name=slot.name,
                                time=new_time,
                                duration=slot.duration,
                                show_location=slot.show_location)
        if session:
            SchedTimeSessAssignment.objects.create(schedule=schedule,session=session,timeslot=ts)

def check_nonsession(meeting,schedule):
    '''
    Ensure non-session timeslots exist and have appropriate SchedTimeSessAssignment objects
    for the specified schedule.
    '''
    slots = TimeSlot.objects.filter(meeting=meeting,type__in=('break','reg','other','plenary','lead','offagenda'))
    if not slots:
        build_nonsession(meeting,schedule)
        return None

    plenary = slots.filter(type='plenary').first()
    if plenary:
        assignments = plenary.sessionassignments.all()
        if not assignments.filter(schedule=schedule):
            source = assignments.first().schedule
            copy_assignments(slots,source,schedule)

def copy_assignments(slots,source,target):
    '''
    Copy SchedTimeSessAssignment objects from source schedule to target schedule.  Slots is
    a queryset of slots
    '''
    for ss in SchedTimeSessAssignment.objects.filter(schedule=source,timeslot__in=slots):
        SchedTimeSessAssignment.objects.create(schedule=target,session=ss.session,timeslot=ss.timeslot)

def get_last_meeting(meeting):
    last_number = int(meeting.number) - 1
    try:
        return Meeting.objects.get(number=last_number)
    except Meeting.DoesNotExist:
        return None
        
def is_combined(session,meeting,schedule=None):
    '''
    Check to see if this session is using two combined timeslots
    '''
    if schedule == None:
        schedule = meeting.agenda
    if session.timeslotassignments.filter(schedule=schedule).count() > 1:
        return True
    else:
        return False

def send_notifications(meeting, groups, person):
    '''
    Send session scheduled email notifications for each group in groups.  Person is the
    user who initiated this action, request.uesr.get_profile().
    '''
    session_info_template = '''{0} Session {1} ({2})
    {3}, {4} {5}
    Room Name: {6}
    ---------------------------------------------
    '''
    now = datetime.datetime.now()
    for group in groups:
        sessions = group.session_set.filter(meeting=meeting)
        addrs = gather_address_lists('session_scheduled',group=group,session=sessions[0])
        from_email = ('"IETF Secretariat"','agenda@ietf.org')
        if len(sessions) == 1:
            subject = '%s - Requested session has been scheduled for IETF %s' % (group.acronym, meeting.number)
        else:
            subject = '%s - Requested sessions have been scheduled for IETF %s' % (group.acronym, meeting.number)
        template = 'meetings/session_schedule_notification.txt'

        # easier to populate template from timeslot perspective. assuming one-to-one timeslot-session
        count = 0
        session_info = ''
        data = [ (s,get_timeslot(s)) for s in sessions ]
        data = [ (s,t) for s,t in data if t ]
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
        context['group'] = group
        context['login'] = sessions[0].requested_by

        send_mail(None,
                  addrs.to,
                  from_email,
                  subject,
                  template,
                  context,
                  cc=addrs.cc)
        
        # create sent_notification event
        GroupEvent.objects.create(group=group,time=now,type='sent_notification',
                                  by=person,desc='sent scheduled notification for %s' % meeting)

def sort_groups(meeting,schedule=None):
    '''
    Similar to sreq.views.sort_groups
    Takes a Meeting object and returns a tuple scheduled_groups, unscheduled groups.
    '''
    if not schedule:
        schedule = meeting.agenda
    scheduled_groups = []
    unscheduled_groups = []
    #sessions = Session.objects.filter(meeting=meeting,status__in=('schedw','apprw','appr','sched','notmeet','canceled'))
    sessions = Session.objects.filter(meeting=meeting,status__in=('schedw','apprw','appr','sched','canceled'))
    groups_with_sessions = [ s.group for s in sessions ]
    gset = set(groups_with_sessions)
    sorted_groups_with_sessions = sorted(gset, key = lambda instance: instance.acronym)
    scheduled_sessions = SchedTimeSessAssignment.objects.filter(schedule=schedule,session__isnull=False)
    groups_with_timeslots = [ x.session.group for x in scheduled_sessions ]
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

    return HttpResponse(json.dumps(results), content_type='application/javascript')
# --------------------------------------------------
# STANDARD VIEW FUNCTIONS
# --------------------------------------------------
@role_required('Secretariat')
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
            return redirect('meetings')

        form = MeetingModelForm(request.POST)
        if form.is_valid():
            meeting = form.save()

            schedule = Schedule.objects.create(meeting = meeting,
                                               name    = 'Empty-Schedule',
                                               owner   = Person.objects.get(name='(System)'),
                                               visible = True,
                                               public  = True)
            meeting.agenda = schedule
            
            # we want to carry session request lock status over from previous meeting
            previous_meeting = get_meeting( int(meeting.number) - 1 )
            meeting.session_request_lock_message = previous_meeting.session_request_lock_message
            meeting.save()

            # Create Physical new meeting directory and subdirectories
            make_materials_directories(meeting)
            
            # Make copy of IETF Overview template
            template = DBTemplate.objects.get(path='/meeting/proceedings/defaults/overview.rst')
            template.id = None
            template.path = '/meeting/proceedings/%s/overview.rst' % (meeting.number)
            template.title = 'IETF %s Proceedings Overview' % (meeting.number)
            template.save()
            meeting.overview = template
            meeting.save()
            
            messages.success(request, 'The Meeting was created successfully!')
            return redirect('meetings')
    else:
        # display initial forms
        max_number = Meeting.objects.filter(type='ietf').aggregate(Max('number'))['number__max']
        form = MeetingModelForm(initial={'number':int(max_number) + 1})

    return render_to_response('meetings/add.html', {
        'form': form},
        RequestContext(request, {}),
    )

@role_required('Secretariat')
def blue_sheet(request, meeting_id):
    '''
    Blue Sheet view.  The user can generate blue sheets or upload scanned bluesheets
    '''
    meeting = get_object_or_404(Meeting, number=meeting_id)
    url = settings.SECR_BLUE_SHEET_URL
    blank_sheets_path = settings.SECR_BLUE_SHEET_PATH
    try:
        last_run = time.ctime(os.stat(blank_sheets_path).st_ctime)
    except OSError:
        last_run = None
    uploaded_sheets_path = os.path.join(settings.SECR_PROCEEDINGS_DIR,meeting.number,'bluesheets')
    uploaded_files = sorted(os.listdir(uploaded_sheets_path))
    
    if request.method == 'POST':
        form = UploadBlueSheetForm(request.POST,request.FILES)
        if form.is_valid():
            file = request.FILES['file']
            handle_upload_file(file,file.name,meeting,'bluesheets')
            messages.success(request, 'File Uploaded')
            return redirect('meetings_blue_sheet', meeting_id=meeting.number)
    else:
        form = UploadBlueSheetForm()

    return render_to_response('meetings/blue_sheet.html', {
        'meeting': meeting,
        'url': url,
        'form': form,
        'last_run': last_run,
        'uploaded_files': uploaded_files},
        RequestContext(request, {}),
    )

@role_required('Secretariat')
def blue_sheet_generate(request, meeting_id):
    '''
    Generate bluesheets
    '''
    meeting = get_object_or_404(Meeting, number=meeting_id)

    if request.method == "POST":
        groups = Group.objects.filter(
            type__in=['wg','rg'],
            session__timeslotassignments__schedule=meeting.agenda).order_by('acronym')
        create_blue_sheets(meeting, groups)

        messages.success(request, 'Blue Sheets generated')
    return redirect('meetings_blue_sheet', meeting_id=meeting.number)

@role_required('Secretariat')
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
    return redirect('meetings_blue_sheet', meeting_id=meeting.number)

@role_required('Secretariat')
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
        if button_text == 'Cancel':
            return redirect('meetings_view', meeting_id=meeting_id)

        form = MeetingModelForm(request.POST, instance=meeting)
        if form.is_valid():
            form.save()
            messages.success(request,'The meeting entry was changed successfully')
            return redirect('meetings_view', meeting_id=meeting_id)

    else:
        form = MeetingModelForm(instance=meeting)

    return render_to_response('meetings/edit_meeting.html', {
        'meeting': meeting,
        'form' : form, },
        RequestContext(request,{}),
    )

@role_required('Secretariat')
def main(request):
    '''
    In this view the user can choose a meeting to manage or elect to create a new meeting.
    '''
    meetings = Meeting.objects.filter(type='ietf').order_by('-number')

    if request.method == 'POST':
        return redirect('meetings_view', meeting_id=request.POST['group'])

    choices = [ (str(x.number),str(x.number)) for x in meetings ]
    form = GroupSelectForm(choices=choices)

    return render_to_response('meetings/main.html', {
        'form': form,
        'meetings': meetings},
        RequestContext(request, {}),
    )

@role_required('Secretariat')
def non_session(request, meeting_id, schedule_name):
    '''
    Display and add "non-session" time slots, ie. registration, beverage and snack breaks
    '''
    meeting = get_object_or_404(Meeting, number=meeting_id)
    schedule = get_object_or_404(Schedule, meeting=meeting, name=schedule_name)
    
    check_nonsession(meeting,schedule)

    slots = TimeSlot.objects.filter(meeting=meeting)
    slots = slots.filter(sessionassignments__schedule=schedule)
    slots = slots.filter(type__in=('break','reg','other','plenary','lead'))
    slots = slots.order_by('-type__name','time')
    
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

            # create TimeSlot object
            timeslot = TimeSlot.objects.create(type=type,
                                               meeting=meeting,
                                               name=name,
                                               time=new_time,
                                               duration=duration,
                                               show_location=form.cleaned_data['show_location'])

            if timeslot.type.slug not in ('other','plenary','lead'):
                group = Group.objects.get(acronym='secretariat')
            
            # create associated Session object
            session = Session(meeting=meeting,
                                  name=name,
                                  short=short,
                                  group=group,
                                  requested_by=Person.objects.get(name='(system)'),
                                  status_id='sched',
                                  type=type,
                             )
            session.save()
            
            # create association
            SchedTimeSessAssignment.objects.create(timeslot=timeslot,
                                            session=session,
                                            schedule=schedule)

            messages.success(request, 'Non-Sessions updated successfully')
            return redirect('meetings_non_session', meeting_id=meeting_id, schedule_name=schedule_name)
    else:
        form = NonSessionForm(initial={'show_location':True})

    if TimeSlot.objects.filter(meeting=meeting,type='other',location__isnull=True):
        messages.warning(request, 'There are non-session items which do not have a room assigned')

    return render_to_response('meetings/non_session.html', {
        'slots': slots,
        'form': form,
        'meeting': meeting,
        'schedule': schedule},
        RequestContext(request, {}),
    )

@role_required('Secretariat')
def non_session_delete(request, meeting_id, schedule_name, slot_id):
    '''
    This function deletes the non-session TimeSlot.  For "other" and "plenary" timeslot
    types we need to delete the corresponding Session object as well.  Check for uploaded
    material first.  SchedTimeSessAssignment objects get deleted as well.
    '''
    meeting = get_object_or_404(Meeting, number=meeting_id)
    # schedule = get_object_or_404(Schedule, meeting=meeting, name=schedule_name)
    slot = get_object_or_404(TimeSlot, id=slot_id)
    if slot.type_id in ('other','plenary','lead'):
        assignments = slot.sessionassignments.filter(schedule__meeting=meeting)
        session_objects = [ x.session for x in assignments ]
        for session in session_objects:
            if session.materials.exclude(states__slug='deleted'):
                messages.error(request, 'Materials have already been uploaded for "%s".  You must delete those before deleting the timeslot.' % slot.name)
                return redirect('meetings_non_session', meeting_id=meeting_id, schedule_name=schedule_name)
        else:
            Session.objects.filter(pk__in=[ x.pk for x in session_objects ]).delete()
    slot.delete()

    messages.success(request, 'Non-Session timeslot deleted successfully')
    return redirect('meetings_non_session', meeting_id=meeting_id, schedule_name=schedule_name)

@role_required('Secretariat')
def non_session_edit(request, meeting_id, schedule_name, slot_id):
    '''
    Allows the user to assign a location to this non-session timeslot
    '''
    meeting = get_object_or_404(Meeting, number=meeting_id)
    slot = get_object_or_404(TimeSlot, id=slot_id)
    schedule = get_object_or_404(Schedule, meeting=meeting, name=schedule_name)
    session = get_session(slot,schedule=schedule)

    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            return redirect('meetings_non_session', meeting_id=meeting_id, schedule_name=schedule_name)

        form = NonSessionEditForm(request.POST,meeting=meeting, session=session)
        if form.is_valid():
            location = form.cleaned_data['location']
            group = form.cleaned_data['group']
            name = form.cleaned_data['name']
            short = form.cleaned_data['short']
            slot.location = location
            slot.name = name
            slot.save()
            # save group to session object
            session.group = group
            session.name = name
            session.short = short
            session.save()

            messages.success(request, 'Location saved')
            return redirect('meetings_non_session', meeting_id=meeting_id, schedule_name=schedule_name)

    else:
        # we need to pass the session to the form in order to disallow changing
        # of group after materials have been uploaded
        initial = {'location':slot.location,
                   'group':session.group,
                   'name':session.name,
                   'short':session.short}
        form = NonSessionEditForm(meeting=meeting,session=session,initial=initial)

    return render_to_response('meetings/non_session_edit.html', {
        'meeting': meeting,
        'form': form,
        'schedule': schedule,
        'slot': slot},
        RequestContext(request, {}),
    )

@role_required('Secretariat')
def notifications(request, meeting_id):
    '''
    Send scheduled session email notifications.  Finds all groups with
    schedule changes since the last time notifications were sent.
    '''
    meeting = get_object_or_404(Meeting, number=meeting_id)
    last_notice = GroupEvent.objects.filter(type='sent_notification').first()
    groups = set()
    for ss in meeting.agenda.assignments.filter(timeslot__type='session'):
        last_notice = ss.session.group.latest_event(type='sent_notification')
        if last_notice and ss.modified > last_notice.time:
            groups.add(ss.session.group)
        elif not last_notice:
            groups.add(ss.session.group)

    if request.method == "POST":
        # ensure session state is scheduled
        for ss in meeting.agenda.assignments.all():
            session = ss.session
            if session.status.slug == "schedw":
                session.status_id = "sched"
                session.scheduled = datetime.datetime.now()
                session.save()
        send_notifications(meeting,groups,request.user.person)

        messages.success(request, "Notifications Sent")
        return redirect('meetings_view', meeting_id=meeting.number)

    return render_to_response('meetings/notifications.html', {
        'meeting': meeting,
        'groups': sorted(groups, key=lambda a: a.acronym),
        'last_notice': last_notice },
        RequestContext(request, {}),
    )

@role_required('Secretariat')
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
        ss = session.official_timeslotassignment()
        ss.session = None
        ss.modified = now
        ss.save()
        session.status_id = 'canceled'
        session.modified = now
        session.save()

    messages.success(request, '%s Session removed from agenda' % (group.acronym))
    return redirect('meetings_select_group', meeting_id=meeting.number)

@role_required('Secretariat')
def rooms(request, meeting_id, schedule_name):
    '''
    Display and edit MeetingRoom records for the specified meeting
    '''
    meeting = get_object_or_404(Meeting, number=meeting_id)
    schedule = get_object_or_404(Schedule, meeting=meeting, name=schedule_name)
    
    # if no rooms exist yet (new meeting) formset extra=10
    first_time = not bool(meeting.room_set.all())
    extra = 10 if first_time else 0
    RoomFormset = inlineformset_factory(Meeting, Room, form=MeetingRoomForm, formset=BaseMeetingRoomFormSet, can_delete=True, extra=extra)

    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            return redirect('meetings', meeting_id=meeting_id,schedule_name=schedule_name)

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
            return redirect('meetings_rooms', meeting_id=meeting_id, schedule_name=schedule_name)
    else:
        formset = RoomFormset(instance=meeting, prefix='room')

    return render_to_response('meetings/rooms.html', {
        'meeting': meeting,
        'schedule': schedule,
        'formset': formset},
        RequestContext(request, {}),
    )

@role_required('Secretariat')
def schedule(request, meeting_id, schedule_name, acronym):
    '''
    This view handles scheduling session requests to TimeSlots
    '''
    meeting = get_object_or_404(Meeting, number=meeting_id)
    schedule = get_object_or_404(Schedule, meeting=meeting, name=schedule_name)
    group = get_object_or_404(Group, acronym=acronym)
    
    sessions = Session.objects.filter(meeting=meeting,group=group,status__in=('schedw','apprw','appr','sched','canceled'))
    legacy_session = get_initial_session(sessions)
    now = datetime.datetime.now()

    # build initial
    initial = []
    for s in sessions:
        d = {'session':s.id,
             'note':s.agenda_note}
        timeslot = get_timeslot(s, schedule=schedule)

        if timeslot:
            d['room'] = timeslot.location.id
            d['day'] = timeslot.time.isoweekday() % 7 + 1     # adjust to django week_day
            d['time'] = timeslot.time.strftime('%H%M')
        else:
            d['day'] = 2    # default
        if is_combined(s,meeting,schedule=schedule):
            d['combine'] = True
        initial.append(d)

    # need to use curry here to pass custom variable to form init
    NewSessionFormset = formset_factory(NewSessionForm, extra=0)
    NewSessionFormset.form = staticmethod(curry(NewSessionForm, meeting=meeting))

    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            return redirect('meetings_select_group', meeting_id=meeting_id,schedule_name=schedule_name)

        formset = NewSessionFormset(request.POST,initial=initial)

        if formset.is_valid():
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
                    initial_timeslot = get_timeslot(session,schedule=schedule)

                    # find new timeslot
                    new_day = meeting.date + datetime.timedelta(days=int(day)-1)
                    hour = datetime.time(int(time[:2]),int(time[2:]))
                    new_time = datetime.datetime.combine(new_day,hour)
                    timeslot = TimeSlot.objects.filter(meeting=meeting,time=new_time,location=room)[0]

                    # COMBINE SECTION - BEFORE --------------
                    if 'combine' in form.changed_data and not combine:
                        next_slot = get_next_slot(initial_timeslot)
                        for ss in next_slot.sessionassignments.filter(schedule=schedule,session=session):
                            ss.session = None
                            ss.save()
                    # ---------------------------------------
                    if any(x in form.changed_data for x in ('day','time','room')):
                        # clear the old association
                        if initial_timeslot:
                            # delete schedtimesessassignment records to unschedule
                            session.timeslotassignments.filter(schedule=schedule).delete()

                        if timeslot:
                            assign(session,timeslot,meeting,schedule=schedule)
                            if timeslot.sessions.all().count() > 1:
                                messages.warning(request, 'WARNING: There are now multiple sessions scheduled for the timeslot: %s' % timeslot)
                        else:
                            session.status_id = 'schedw'

                        session.modified = now
                        session.save()

                    if 'note' in form.changed_data:
                        session.agenda_note = note
                        session.modified = now
                        session.save()

                    # COMBINE SECTION - AFTER ---------------
                    if 'combine' in form.changed_data and combine:
                        next_slot = get_next_slot(timeslot)
                        assign(session,next_slot,meeting,schedule=schedule)
                    # ---------------------------------------

            if has_changed:
                messages.success(request, 'Session(s) Scheduled for %s.' % group.acronym )

            return redirect('meetings_select_group', meeting_id=meeting_id,schedule_name=schedule_name)

    else:
        formset = NewSessionFormset(initial=initial)

    return render_to_response('meetings/schedule.html', {
        'group': group,
        'meeting': meeting,
        'schedule': schedule,
        'show_request': True,
        'session': legacy_session,
        'formset': formset},
        RequestContext(request, {}),
    )

@role_required('Secretariat')
def select(request, meeting_id, schedule_name):
    '''
    Options to edit Rooms & Times or schedule a session
    '''
    meeting = get_object_or_404(Meeting, number=meeting_id)
    schedule = get_object_or_404(Schedule, meeting=meeting, name=schedule_name)
    
    return render_to_response('meetings/select.html', {
        'meeting': meeting,
        'schedule': schedule},
        RequestContext(request, {}),
    )
    
@role_required('Secretariat')
def select_group(request, meeting_id, schedule_name):
    '''
    In this view the user can select the group to schedule.  Only those groups that have
    submitted session requests appear in the dropdowns.

    NOTE: BOF list includes Proposed Working Group type, per Wanda
    '''
    meeting = get_object_or_404(Meeting, number=meeting_id)
    schedule = get_object_or_404(Schedule, meeting=meeting, name=schedule_name)
    
    if request.method == 'POST':
        group = request.POST.get('group',None)
        if group:
            redirect_url = reverse('meetings_schedule', kwargs={'meeting_id':meeting_id,'acronym':group,'schedule_name':schedule_name})
        else:
            redirect_url = reverse('meetings_select_group',kwargs={'meeting_id':meeting_id,'schedule_name':schedule_name})
            messages.error(request, 'No group selected')

        return HttpResponseRedirect(redirect_url)

    # split groups into scheduled / unscheduled
    scheduled_groups, unscheduled_groups = sort_groups(meeting,schedule)

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
        'meeting': meeting,
        'schedule': schedule},
        RequestContext(request, {}),
    )

@role_required('Secretariat')
def times(request, meeting_id, schedule_name):
    '''
    Display and edit time slots (TimeSlots).  It doesn't display every TimeSlot
    object for the meeting because there is one timeslot per time per room,
    rather it displays all the unique times.
    The first time this view is called for a meeting it creates a form with times
    prepopulated from the last meeting
    '''
    meeting = get_object_or_404(Meeting, number=meeting_id)
    schedule = get_object_or_404(Schedule, meeting=meeting, name=schedule_name)

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
                return redirect('meetings_times', meeting_id=meeting_id,schedule_name=schedule_name)

            for room in meeting.room_set.all():
                TimeSlot.objects.create(type_id='session',
                                        meeting=meeting,
                                        name=name,
                                        time=new_time,
                                        location=room,
                                        duration=duration)

            messages.success(request, 'Timeslots created')
            return redirect('meetings_times', meeting_id=meeting_id,schedule_name=schedule_name)

    else:
        form = TimeSlotForm()

    return render_to_response('meetings/times.html', {
        'form': form,
        'meeting': meeting,
        'schedule': schedule,
        'times': times},
        RequestContext(request, {}),
    )

@role_required('Secretariat')
def times_edit(request, meeting_id, schedule_name, time):
    '''
    This view handles bulk edit of timeslot details.
    '''
    meeting = get_object_or_404(Meeting, number=meeting_id)
    schedule = get_object_or_404(Schedule, meeting=meeting, name=schedule_name)
    
    parts = [ int(x) for x in time.split(':') ]
    dtime = datetime.datetime(*parts)
    timeslots = TimeSlot.objects.filter(meeting=meeting,time=dtime)

    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            return redirect('meetings_times', meeting_id=meeting_id,schedule_name=schedule_name)

        form = TimeSlotForm(request.POST)
        if form.is_valid():
            day = form.cleaned_data['day']
            time = form.cleaned_data['time']
            duration = form.cleaned_data['duration']
            name = form.cleaned_data['name']
            
            t = meeting.date + datetime.timedelta(days=int(day))
            new_time = datetime.datetime(t.year,t.month,t.day,time.hour,time.minute)
            
            for timeslot in timeslots:
                timeslot.time = new_time
                timeslot.duration = duration
                timeslot.name = name
                timeslot.save()

            messages.success(request, 'TimeSlot saved')
            return redirect('meetings_times', meeting_id=meeting_id,schedule_name=schedule_name)

    else:
        # we need to pass the session to the form in order to disallow changing
        # of group after materials have been uploaded
        day = dtime.strftime('%w')
        if day == 6:
            day = -1
        initial = {'day':day,
                   'time':dtime.strftime('%H:%M'),
                   'duration':timeslots.first().duration,
                   'name':timeslots.first().name}
        form = TimeSlotForm(initial=initial)

    return render_to_response('meetings/times_edit.html', {
        'meeting': meeting,
        'schedule': schedule,
        'form': form},
        RequestContext(request, {}),
    )

@role_required('Secretariat')
def times_delete(request, meeting_id, schedule_name, time):
    '''
    This view handles bulk delete of all timeslots matching time (datetime) for the given
    meeting.  There is one timeslot for each room.
    '''
    meeting = get_object_or_404(Meeting, number=meeting_id)
    
    parts = [ int(x) for x in time.split(':') ]
    dtime = datetime.datetime(*parts)

    TimeSlot.objects.filter(meeting=meeting,time=dtime).delete()

    messages.success(request, 'Timeslot deleted')
    return redirect('meetings_times', meeting_id=meeting_id,schedule_name=schedule_name)

@role_required('Secretariat')
def unschedule(request, meeting_id, schedule_name, session_id):
    '''
    Unschedule given session object
    '''
    meeting = get_object_or_404(Meeting, number=meeting_id)
    session = get_object_or_404(Session, id=session_id)

    session.timeslotassignments.filter(schedule=meeting.agenda).delete()

    # TODO: change session state?

    messages.success(request, 'Session unscheduled')
    return redirect('meetings_select_group', meeting_id=meeting_id, schedule_name=schedule_name)

@role_required('Secretariat')
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
