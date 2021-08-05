# Copyright The IETF Trust 2007-2019, All Rights Reserved
# -*- coding: utf-8 -*-

import datetime
import os
import time

from django.conf import settings
from django.contrib import messages
from django.db.models import IntegerField
from django.db.models.functions import Cast
from django.forms.models import inlineformset_factory
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.text import slugify

import debug                            # pyflakes:ignore

from ietf.ietfauth.utils import role_required
from ietf.utils.mail import send_mail
from ietf.meeting.forms import duration_string
from ietf.meeting.helpers import get_meeting, make_materials_directories, populate_important_dates
from ietf.meeting.models import Meeting, Session, Room, TimeSlot, SchedTimeSessAssignment, Schedule, SchedulingEvent
from ietf.meeting.utils import add_event_info_to_session_qs
from ietf.name.models import SessionStatusName
from ietf.group.models import Group, GroupEvent
from ietf.secr.meetings.blue_sheets import create_blue_sheets
from ietf.secr.meetings.forms import ( BaseMeetingRoomFormSet, MeetingModelForm, MeetingSelectForm,
    MeetingRoomForm, MiscSessionForm, TimeSlotForm, RegularSessionEditForm,
    UploadBlueSheetForm )
from ietf.secr.proceedings.utils import handle_upload_file
from ietf.secr.sreq.views import get_initial_session
from ietf.secr.utils.meeting import get_session, get_timeslot
from ietf.mailtrigger.utils import gather_address_lists


# prep for agenda changes
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
    slots = meeting.timeslot_set.filter(type='regular')

    # Don't do anything if the room is not capable of handling sessions
    if room and not room.session_types.filter(slug='regular'):
        return

    if room:
        rooms = [room]
    else:
        rooms = meeting.room_set.filter(session_types__slug='regular')
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
        for t in source_meeting.timeslot_set.filter(type='regular'):
            if not t.time in time_seen:
                time_seen.add(t.time)
                timeslots.append(t)
        for t in timeslots:
            new_time = t.time + delta
            for room in rooms:
                TimeSlot.objects.create(type_id='regular',
                                        meeting=meeting,
                                        name=t.name,
                                        time=new_time,
                                        location=room,
                                        duration=t.duration)

def check_misc_sessions(meeting,schedule):
    '''
    Ensure misc session timeslots exist and have appropriate SchedTimeSessAssignment objects
    for the specified schedule.
    '''
    # FIXME: this is a legacy function: delete it once base schedules are rolled out

    if Schedule.objects.filter(meeting=meeting, base__isnull=False).exists():
        return

    slots = TimeSlot.objects.filter(meeting=meeting,type__in=('break','reg','other','plenary','lead','offagenda'))
    plenary = slots.filter(type='plenary').first()
    if plenary:
        assignments = plenary.sessionassignments.all()
        if not assignments.filter(schedule=schedule):
            source = assignments.first().schedule
            for ss in SchedTimeSessAssignment.objects.filter(schedule=source,timeslot__in=slots):
                SchedTimeSessAssignment.objects.create(schedule=schedule,session=ss.session,timeslot=ss.timeslot)

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
        schedule = meeting.schedule
    if session.timeslotassignments.filter(schedule=schedule).count() > 1:
        return True
    else:
        return False

def send_notifications(meeting, groups, person):
    '''
    Send session scheduled email notifications for each group in groups.  Person is the
    user who initiated this action, request.uesr.get_profile().
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
        items = [ {'session':s, 'timeslot':get_timeslot(s)} for s in sessions if get_timeslot(s) ]
        items.sort(key=lambda d: d['timeslot'].time)
        for i,d in enumerate(items):
            s = d['session']
            t = d['timeslot']
            dur = s.requested_duration.seconds/60
            items[i]['duration'] = "%d:%02d" % (dur//60, dur%60)
            items[i]['period'] = '%s-%s' % (t.time.strftime('%H%M'),(t.time + t.duration).strftime('%H%M'))

        # send email
        first_event = SchedulingEvent.objects.filter(session=sessions[0]).select_related('by').order_by('time', 'id').first()
        requested_by = None
        if first_event and first_event.status_id in ['appw', 'schedw']:
            requested_by = first_event.by
        
        context = {
            'items': items,
            'meeting': meeting,
            'baseurl': settings.IDTRACKER_BASE_URL,
        }
        context['to_name'] = str(requested_by) or "Requester"
        context['agenda_note'] = sessions[0].agenda_note
        context['session'] = get_initial_session(sessions)
        context['group'] = group
        context['login'] = requested_by

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


# -------------------------------------------------
# AJAX Functions
# -------------------------------------------------
# def ajax_get_times(request, meeting_id, day):
#     '''
#     Ajax function to get timeslot times for a given day.
#     returns JSON format response: [{id:start_time, value:start_time-end_time},...]
#     '''
#     # TODO strip duplicates if there are any
#     from ietf.utils import log
#     log.unreachable("2017-07-08")
#     results=[]
#     room = Room.objects.filter(meeting__number=meeting_id)[0]
#     slots = TimeSlot.objects.filter(meeting__number=meeting_id,time__week_day=day,location=room).order_by('time')
#     for slot in slots:
#         d = {'id': slot.time.strftime('%H%M'), 'value': '%s-%s' % (slot.time.strftime('%H%M'), slot.end_time().strftime('%H%M'))}
#         results.append(d)
# 
#     return HttpResponse(json.dumps(results), content_type='application/javascript')

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
            return redirect('ietf.secr.meetings.views.main')

        form = MeetingModelForm(request.POST)
        if form.is_valid():
            meeting = form.save()

            base_schedule = Schedule.objects.create(
                meeting=meeting,
                name='base',
                owner=request.user.person,
                visible=True,
                public=True
            )

            schedule = Schedule.objects.create(meeting = meeting,
                                               name    = "%s-1" % slugify(request.user.person.plain_name()),
                                               owner   = request.user.person,
                                               visible = True,
                                               public  = True,
                                               base    = base_schedule,
            )
            meeting.schedule = schedule

            # we want to carry session request lock status over from previous meeting
            previous_meeting = get_meeting( int(meeting.number) - 1 )
            meeting.session_request_lock_message = previous_meeting.session_request_lock_message
            meeting.save()

            populate_important_dates(meeting)
            
            # Create Physical new meeting directory and subdirectories
            make_materials_directories(meeting)

            messages.success(request, 'The Meeting was created successfully!')
            return redirect('ietf.secr.meetings.views.main')
    else:
        # display initial forms
        last_ietf_meeting = Meeting.objects.filter(
            type='ietf'
        ).annotate(
            number_as_int=Cast('number', output_field=IntegerField())
        ).order_by('-number_as_int').first()
        initial = dict()
        # fill in defaults if we can
        if last_ietf_meeting is not None:
            initial['number'] = last_ietf_meeting.number_as_int + 1
            initial['group_conflict_types'] = [cn.pk for cn in last_ietf_meeting.group_conflict_types.all()]
        form = MeetingModelForm(initial=initial)

    return render(request, 'meetings/add.html', {
        'form': form},
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
            save_error = handle_upload_file(file,file.name,meeting,'bluesheets')
            if save_error:
                form.add_error(None, save_error)
            else:
                messages.success(request, 'File Uploaded')
                return redirect('ietf.secr.meetings.views.blue_sheet', meeting_id=meeting.number)
    else:
        form = UploadBlueSheetForm()

    return render(request, 'meetings/blue_sheet.html', {
        'meeting': meeting,
        'url': url,
        'form': form,
        'last_run': last_run,
        'uploaded_files': uploaded_files},
    )

@role_required('Secretariat')
def blue_sheet_generate(request, meeting_id):
    '''
    Generate bluesheets
    '''
    meeting = get_object_or_404(Meeting, number=meeting_id)

    if request.method == "POST":
        groups = Group.objects.filter(
            type__in=['wg','rg','ag','rag','program'],
            session__timeslotassignments__schedule__in=[meeting.schedule, meeting.schedule.base if meeting.schedule else None]).order_by('acronym')
        create_blue_sheets(meeting, groups)

        messages.success(request, 'Blue Sheets generated')
    return redirect('ietf.secr.meetings.views.blue_sheet', meeting_id=meeting.number)

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
    return redirect('ietf.secr.meetings.views.blue_sheet', meeting_id=meeting.number)

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
            return redirect('ietf.secr.meetings.views.view', meeting_id=meeting_id)

        form = MeetingModelForm(request.POST, instance=meeting)
        if form.is_valid():
            form.save()
            messages.success(request,'The meeting entry was changed successfully')
            return redirect('ietf.secr.meetings.views.view', meeting_id=meeting_id)

    else:
        form = MeetingModelForm(instance=meeting)

    return render(request, 'meetings/edit_meeting.html', {
        'meeting': meeting,
        'form' : form, },
    )

@role_required('Secretariat')
def main(request):
    '''
    In this view the user can choose a meeting to manage or elect to create a new meeting.
    '''
    meetings = Meeting.objects.filter(type='ietf').order_by('-date')

    if request.method == 'POST':
        return redirect('ietf.secr.meetings.views.view', meeting_id=request.POST['meeting'])

    choices = [ (str(x.number),str(x.number)) for x in meetings ]
    form = MeetingSelectForm(choices=choices)

    return render(request, 'meetings/main.html', {
        'form': form,
        'meetings': meetings},
    )

@role_required('Secretariat')
def misc_sessions(request, meeting_id, schedule_name):
    '''
    Display and add misc session time slots, e.g. registration, beverage and snack breaks
    '''
    meeting = get_object_or_404(Meeting, number=meeting_id)
    schedule = get_object_or_404(Schedule, meeting=meeting, name=schedule_name)
    
    check_misc_sessions(meeting,schedule)

    misc_session_types = ['break','reg','other','plenary','lead']
    assignments = SchedTimeSessAssignment.objects.filter(schedule__in=[schedule, schedule.base], timeslot__type__in=misc_session_types)
    assignments = assignments.order_by('-timeslot__type__name','timeslot__time')
    
    if request.method == 'POST':
        form = MiscSessionForm(request.POST, meeting=meeting)
        if form.is_valid():
            time = get_timeslot_time(form, meeting)
            name = form.cleaned_data['name']
            short = form.cleaned_data['short']
            type = form.cleaned_data['type']
            group = form.cleaned_data['group']
            duration = form.cleaned_data['duration']
            location = form.cleaned_data['location']

            # create TimeSlot object
            timeslot = TimeSlot.objects.create(type=type,
                                               meeting=meeting,
                                               name=name,
                                               time=time,
                                               duration=duration,
                                               location=location,
                                               show_location=form.cleaned_data['show_location'])

            if timeslot.type.slug not in ('other','plenary','lead'):
                group = Group.objects.get(acronym='secretariat')
            
            # create associated Session object
            session = Session.objects.create(meeting=meeting,
                                             name=name,
                                             short=short,
                                             group=group,
                                             type=type)

            SchedulingEvent.objects.create(
                session=session,
                status=SessionStatusName.objects.get(slug='sched'),
                by=request.user.person,
            )

            # create association
            SchedTimeSessAssignment.objects.create(timeslot=timeslot,
                                            session=session,
                                            schedule=schedule)

            messages.success(request, 'Misc. sessions updated successfully')
            return redirect('ietf.secr.meetings.views.misc_sessions', meeting_id=meeting_id, schedule_name=schedule_name)
    else:
        form = MiscSessionForm(initial={'show_location':True}, meeting=meeting)

    no_room = TimeSlot.objects.filter(meeting=meeting,type='other',location__isnull=True)
    if no_room:
        messages.warning(request, 'There are misc. session time slots which do not have a room assigned')

    session_statuses = {
        e.session_id: e.status_id
        for e in SchedulingEvent.objects.filter(session__in=[a.session_id for a in assignments]).order_by('time', 'id')
    }

    for a in assignments:
        a.current_session_status = session_statuses.get(a.session_id)

    return render(request, 'meetings/misc_sessions.html', {
        'assignments': assignments,
        'form': form,
        'meeting': meeting,
        'schedule': schedule,
        'selected': 'misc-sessions'},
    )

@role_required('Secretariat')
def misc_session_cancel(request, meeting_id, schedule_name, slot_id):
    '''
    This function cancels the misc session TimeSlot.  Check for uploaded
    material first.  SchedTimeSessAssignment objects get cancelled as well.
    '''
    slot = get_object_or_404(TimeSlot, id=slot_id)
    meeting = get_object_or_404(Meeting, number=meeting_id)
    schedule = get_object_or_404(Schedule, meeting=meeting, name=schedule_name)

    if request.method == 'POST' and request.POST['post'] == 'yes':
        for session in Session.objects.filter(timeslotassignments__schedule=schedule, timeslotassignments__timeslot=slot):
            SchedulingEvent.objects.create(
                session=session,
                status=SessionStatusName.objects.get(slug='canceled'),
                by=request.user.person,
            )

        messages.success(request, 'The session was cancelled successfully')
        return redirect('ietf.secr.meetings.views.misc_sessions', meeting_id=meeting_id, schedule_name=schedule_name)

    return render(request, 'confirm_cancel.html', {'object': slot})

@role_required('Secretariat')
def misc_session_delete(request, meeting_id, schedule_name, slot_id):
    '''
    This function deletes the misc session TimeSlot.  Check for uploaded
    material first.  SchedTimeSessAssignment objects get deleted as well.
    '''
    slot = get_object_or_404(TimeSlot, id=slot_id)

    if request.method == 'POST' and request.POST['post'] == 'yes':
        assignments = slot.sessionassignments.all()
        session_objects = [ x.session for x in assignments ]
        
        for session in session_objects:
            if session.materials.exclude(states__slug='deleted'):
                messages.error(request, 'Materials have already been uploaded for "%s".  You must delete those before deleting the timeslot.' % slot.name)
                return redirect('ietf.secr.meetings.views.misc_sessions', meeting_id=meeting_id, schedule_name=schedule_name)
        
        # delete high order assignments, then sessions and slots
        assignments.delete()
        Session.objects.filter(pk__in=[ x.pk for x in session_objects ]).delete()
        slot.delete()

        messages.success(request, 'The entry was deleted successfully')
        return redirect('ietf.secr.meetings.views.misc_sessions', meeting_id=meeting_id, schedule_name=schedule_name)

    return render(request, 'confirm_delete.html', {'object': slot})

@role_required('Secretariat')
def misc_session_edit(request, meeting_id, schedule_name, slot_id):
    '''
    Allows the user to assign a location to this misc session timeslot
    '''
    meeting = get_object_or_404(Meeting, number=meeting_id)
    slot = get_object_or_404(TimeSlot, id=slot_id)
    schedule = get_object_or_404(Schedule, meeting=meeting, name=schedule_name)
    session = get_session(slot,schedule=schedule)

    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Back':
            return redirect('ietf.secr.meetings.views.misc_sessions', meeting_id=meeting_id, schedule_name=schedule_name)

        form = MiscSessionForm(request.POST,meeting=meeting,session=session)
        if form.is_valid():
            location = form.cleaned_data['location']
            group = form.cleaned_data['group']
            name = form.cleaned_data['name']
            short = form.cleaned_data['short']
            duration = form.cleaned_data['duration']
            slot_type = form.cleaned_data['type']
            show_location = form.cleaned_data['show_location']
            remote_instructions = form.cleaned_data['remote_instructions']
            time = get_timeslot_time(form, meeting)
            slot.location = location
            slot.name = name
            slot.time = time
            slot.duration = duration
            slot.type = slot_type
            slot.show_location = show_location
            slot.save()
            # save group to session object
            session.group = group
            session.name = name
            session.short = short
            session.remote_instructions = remote_instructions
            session.save()

            messages.success(request, 'Location saved')
            return redirect('ietf.secr.meetings.views.misc_sessions', meeting_id=meeting_id, schedule_name=schedule_name)

    else:
        # we need to pass the session to the form in order to disallow changing
        # of group after materials have been uploaded
        delta = slot.time.date() - meeting.date
        initial = {'location':slot.location,
                   'group':session.group,
                   'name':session.name,
                   'short':session.short,
                   'day':delta.days,
                   'time':slot.time.strftime('%H:%M'),
                   'duration':duration_string(slot.duration),
                   'show_location':slot.show_location,
                   'type':slot.type,
                   'remote_instructions': session.remote_instructions,
               }
        form = MiscSessionForm(initial=initial, meeting=meeting, session=session)

    return render(request, 'meetings/misc_session_edit.html', {
        'meeting': meeting,
        'form': form,
        'schedule': schedule,
        'slot': slot},
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
    for ss in SchedTimeSessAssignment.objects.filter(schedule__in=[meeting.schedule, meeting.schedule.base if meeting.schedule else None], timeslot__type='regular'):
        last_notice = ss.session.group.latest_event(type='sent_notification')
        if last_notice and ss.modified > last_notice.time:
            groups.add(ss.session.group)
        elif not last_notice:
            groups.add(ss.session.group)

    if request.method == "POST":
        # ensure session state is scheduled
        sessions = add_event_info_to_session_qs(Session.objects.filter(timeslotassignments__schedule=meeting.schedule_id)).filter(current_status__in=["schedw", "appr"])
        for session in sessions:
            SchedulingEvent.objects.create(
                session=session,
                status=SessionStatusName.objects.get(slug='sched'),
                by=request.user.person,
            )
        send_notifications(meeting,groups,request.user.person)

        messages.success(request, "Notifications Sent")
        return redirect('ietf.secr.meetings.views.view', meeting_id=meeting.number)

    return render(request, 'meetings/notifications.html', {
        'meeting': meeting,
        'groups': sorted(groups, key=lambda a: a.acronym),
        'last_notice': last_notice },
    )

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
            return redirect('ietf.secr.meetings.views.main', meeting_id=meeting_id,schedule_name=schedule_name)

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
            return redirect('ietf.secr.meetings.views.rooms', meeting_id=meeting_id, schedule_name=schedule_name)
    else:
        formset = RoomFormset(instance=meeting, prefix='room')

    return render(request, 'meetings/rooms.html', {
        'meeting': meeting,
        'schedule': schedule,
        'formset': formset,
        'selected': 'rooms'}
    )

@role_required('Secretariat')
def regular_sessions(request, meeting_id, schedule_name):
    '''
    Display and edit Session records for the specified meeting
    '''
    meeting = get_object_or_404(Meeting, number=meeting_id)
    schedule = get_object_or_404(Schedule, meeting=meeting, name=schedule_name)

    sessions = meeting.session_set.that_can_meet().order_by('group__acronym')

    if request.method == 'POST':
        if 'cancel' in request.POST:
            pk = request.POST.get('pk')
            session = get_object_or_404(sessions, pk=pk)
            if session.current_status not in ['canceled', 'resched']:
                SchedulingEvent.objects.create(
                    session=session,
                    status=SessionStatusName.objects.get(slug='canceled'),
                    by=request.user.person,
                )
                messages.success(request, 'Session cancelled')

        return redirect('ietf.secr.meetings.views.regular_sessions', meeting_id=meeting_id, schedule_name=schedule_name)

    status_names = {n.slug: n.name for n in SessionStatusName.objects.all()}

    for s in sessions:
        s.current_status_name = status_names.get(s.current_status, s.current_status)
        s.can_cancel = s.current_status not in ['canceled', 'resched']

    return render(request, 'meetings/sessions.html', {
        'meeting': meeting,
        'schedule': schedule,
        'sessions': sessions,
        'formset': None,
        'selected': 'regular-sessions',},
    )

@role_required('Secretariat')
def regular_session_edit(request, meeting_id, schedule_name, session_id):
    '''
    Edit session details
    '''
    meeting = get_object_or_404(Meeting, number=meeting_id)
    schedule = get_object_or_404(Schedule, meeting=meeting, name=schedule_name)
    session = get_object_or_404(Session, id=session_id)
    assignment = SchedTimeSessAssignment.objects.filter(schedule=schedule, session=session).first()

    if request.method == 'POST':
        form = RegularSessionEditForm(request.POST, instance=session)
        if form.is_valid():
            form.save()
            messages.success(request, 'Session saved')
            return redirect('ietf.secr.meetings.views.regular_sessions', meeting_id=meeting_id,schedule_name=schedule_name)

    else:
        form = RegularSessionEditForm(instance=session)

    current_status_name = None
    latest_event = SchedulingEvent.objects.filter(session=session).order_by('-time', '-id').first()
    if latest_event:
        current_status_name = latest_event.status.name

    return render(request, 'meetings/regular_session_edit.html', {
        'meeting': meeting,
        'schedule': schedule,
        'session': session,
        'timeslot': assignment.timeslot if assignment else None,
        'current_status_name': current_status_name,
        'form': form},
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
    for t in meeting.timeslot_set.filter(type='regular'):
        if not t.time in time_seen:
            time_seen.add(t.time)
            timeslots.append(t)
    for t in timeslots:
        slots.append({'name':t.name,
                      'time':t.time,
                      'end_time':t.end_time()})
    times = sorted(slots, key=lambda a: a['time'])

    if request.method == 'POST':
        form = TimeSlotForm(request.POST, meeting=meeting)
        if form.is_valid():
            time = get_timeslot_time(form, meeting)
            duration = form.cleaned_data['duration']
            name = form.cleaned_data['name']

            # don't allow creation of timeslots with same start time as existing timeslots
            # assert False, (new_time, time_seen)
            if time in time_seen:
                messages.error(request, 'There is already a timeslot for %s.  To change you must delete the old one first.' % time.strftime('%a %H:%M'))
                return redirect('ietf.secr.meetings.views.times', meeting_id=meeting_id,schedule_name=schedule_name)

            for room in meeting.room_set.all():
                TimeSlot.objects.create(type_id='regular',
                                        meeting=meeting,
                                        name=name,
                                        time=time,
                                        location=room,
                                        duration=duration)

            messages.success(request, 'Timeslots created')
            return redirect('ietf.secr.meetings.views.times', meeting_id=meeting_id,schedule_name=schedule_name)

    else:
        form = TimeSlotForm(meeting=meeting)

    return render(request, 'meetings/times.html', {
        'form': form,
        'meeting': meeting,
        'schedule': schedule,
        'times': times,
        'selected': 'times'},
    )

def get_timeslot_time(form, meeting):
    '''Returns datetime calculated from day and time form fields'''
    time = form.cleaned_data['time']
    day = form.cleaned_data['day']

    date = meeting.date + datetime.timedelta(days=int(day))
    return datetime.datetime(date.year,date.month,date.day,time.hour,time.minute)

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
            return redirect('ietf.secr.meetings.views.times', meeting_id=meeting_id,schedule_name=schedule_name)

        form = TimeSlotForm(request.POST, meeting=meeting)
        if form.is_valid():
            day = form.cleaned_data['day']
            time = get_timeslot_time(form, meeting)
            duration = form.cleaned_data['duration']
            name = form.cleaned_data['name']
            
            for timeslot in timeslots:
                timeslot.time = time
                timeslot.duration = duration
                timeslot.name = name
                timeslot.save()

            messages.success(request, 'TimeSlot saved')
            return redirect('ietf.secr.meetings.views.times', meeting_id=meeting_id,schedule_name=schedule_name)

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
        form = TimeSlotForm(initial=initial, meeting=meeting)

    return render(request, 'meetings/times_edit.html', {
        'meeting': meeting,
        'schedule': schedule,
        'form': form},
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
    status = SessionStatusName.objects.get(slug='schedw')

    if request.method == 'POST' and request.POST['post'] == 'yes':
        for slot in TimeSlot.objects.filter(meeting=meeting,time=dtime):
            for assignment in slot.sessionassignments.all():
                if assignment.session:
                    session = assignment.session
                    latest_event = SchedulingEvent.objects.filter(session=session).order_by('-time', '-id').first()
                    if not latest_event or latest_event.status_id != 'schedw':
                        SchedulingEvent.objects.create(
                            session=session,
                            status=status,
                            by=request.user.person,
                        )
                assignment.delete()
            slot.delete()
        messages.success(request, 'The entry was deleted successfully')
        return redirect('ietf.secr.meetings.views.times', meeting_id=meeting_id,schedule_name=schedule_name)

    return render(request, 'confirm_delete.html', {
        'object': '%s timeslots' % dtime.strftime("%A %H:%M"),
        'extra': 'Any sessions assigned to this timeslot will be unscheduled'
    })

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

    return render(request, 'meetings/view.html', {
        'meeting': meeting},
    )
