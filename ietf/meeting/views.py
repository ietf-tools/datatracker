# Copyright The IETF Trust 2007-2024, All Rights Reserved
# -*- coding: utf-8 -*-


import csv
import datetime
import glob
import io
import itertools
import json
import math
import os
import pytz
import re
import tarfile
import tempfile
import shutil

from calendar import timegm
from collections import OrderedDict, Counter, deque, defaultdict, namedtuple
from functools import partialmethod
import jsonschema
from urllib.parse import parse_qs, unquote, urlencode, urlsplit, urlunsplit
from tempfile import mkstemp
from wsgiref.handlers import format_date_time

from django import forms
from django.shortcuts import render, redirect, get_object_or_404
from django.http import (HttpResponse, HttpResponseRedirect, HttpResponseForbidden,
                         HttpResponseNotFound, Http404, HttpResponseBadRequest,
                         JsonResponse, HttpResponseGone, HttpResponseNotAllowed)
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.validators import URLValidator
from django.urls import reverse,reverse_lazy
from django.db.models import F, Max, Q
from django.forms.models import modelform_factory, inlineformset_factory
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.text import slugify
from django.views.decorators.cache import cache_page
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.views.generic import RedirectView

import debug                            # pyflakes:ignore

from ietf.doc.fields import SearchableDocumentsField
from ietf.doc.models import Document, State, DocEvent, NewRevisionDocEvent
from ietf.group.models import Group
from ietf.group.utils import can_manage_session_materials, can_manage_some_groups, can_manage_group
from ietf.person.models import Person, User
from ietf.ietfauth.utils import role_required, has_role, user_is_person
from ietf.mailtrigger.utils import gather_address_lists
from ietf.meeting.models import Meeting, Session, Schedule, FloorPlan, SessionPresentation, TimeSlot, SlideSubmission, Attended
from ietf.meeting.models import SessionStatusName, SchedulingEvent, SchedTimeSessAssignment, Room, TimeSlotTypeName
from ietf.meeting.forms import ( CustomDurationField, SwapDaysForm, SwapTimeslotsForm, ImportMinutesForm,
                                 TimeSlotCreateForm, TimeSlotEditForm, SessionCancelForm, SessionEditForm )
from ietf.meeting.helpers import get_person_by_email, get_schedule_by_name
from ietf.meeting.helpers import get_meeting, get_ietf_meeting, get_current_ietf_meeting_num
from ietf.meeting.helpers import get_schedule, schedule_permissions
from ietf.meeting.helpers import preprocess_assignments_for_agenda, read_agenda_file
from ietf.meeting.helpers import AgendaFilterOrganizer, AgendaKeywordTagger
from ietf.meeting.helpers import convert_draft_to_pdf, get_earliest_session_date
from ietf.meeting.helpers import can_view_interim_request, can_approve_interim_request
from ietf.meeting.helpers import can_edit_interim_request
from ietf.meeting.helpers import can_request_interim_meeting, get_announcement_initial
from ietf.meeting.helpers import sessions_post_save, is_interim_meeting_approved
from ietf.meeting.helpers import send_interim_meeting_cancellation_notice, send_interim_session_cancellation_notice
from ietf.meeting.helpers import send_interim_approval
from ietf.meeting.helpers import send_interim_approval_request
from ietf.meeting.helpers import send_interim_announcement_request, sessions_post_cancel
from ietf.meeting.utils import finalize, sort_accept_tuple, condition_slide_order
from ietf.meeting.utils import add_event_info_to_session_qs
from ietf.meeting.utils import session_time_for_sorting
from ietf.meeting.utils import session_requested_by, SaveMaterialsError
from ietf.meeting.utils import current_session_status, get_meeting_sessions, SessionNotScheduledError
from ietf.meeting.utils import data_for_meetings_overview, handle_upload_file, save_session_minutes_revision
from ietf.meeting.utils import preprocess_constraints_for_meeting_schedule_editor
from ietf.meeting.utils import diff_meeting_schedules, prefetch_schedule_diff_objects
from ietf.meeting.utils import swap_meeting_schedule_timeslot_assignments, bulk_create_timeslots
from ietf.meeting.utils import preprocess_meeting_important_dates
from ietf.meeting.utils import new_doc_for_session, write_doc_for_session
from ietf.meeting.utils import get_activity_stats, post_process, create_recording
from ietf.meeting.utils import participants_for_meeting, generate_bluesheet, bluesheet_data, save_bluesheet
from ietf.message.utils import infer_message
from ietf.name.models import SlideSubmissionStatusName, ProceedingsMaterialTypeName, SessionPurposeName
from ietf.stats.models import MeetingRegistration
from ietf.utils import markdown
from ietf.utils.decorators import require_api_key
from ietf.utils.hedgedoc import Note, NoteError
from ietf.utils.meetecho import MeetechoAPIError, SlidesManager
from ietf.utils.log import assertion, log
from ietf.utils.mail import send_mail_message, send_mail_text
from ietf.utils.mime import get_mime_type
from ietf.utils.pipe import pipe
from ietf.utils.pdf import pdf_pages
from ietf.utils.response import permission_denied
from ietf.utils.text import xslugify
from ietf.utils.timezone import datetime_today, date_today

from .forms import (InterimMeetingModelForm, InterimAnnounceForm, InterimSessionModelForm,
    InterimCancelForm, InterimSessionInlineFormSet, RequestMinutesForm,
    UploadAgendaForm, UploadBlueSheetForm, UploadMinutesForm, UploadSlidesForm,
    UploadNarrativeMinutesForm)

request_summary_exclude_group_types = ['team']

    
def get_interim_menu_entries(request):
    '''Setup menu entries for interim meeting view tabs'''
    entries = []
    entries.append(("Upcoming", reverse("ietf.meeting.views.upcoming")))
    entries.append(("Pending", reverse("ietf.meeting.views.interim_pending")))
    entries.append(("Announce", reverse("ietf.meeting.views.interim_announce")))
    return entries

def send_interim_change_notice(request, meeting):
    """Sends an email notifying changes to a previously scheduled / announced meeting"""
    group = meeting.session_set.first().group
    form = InterimAnnounceForm(get_announcement_initial(meeting, is_change=True))
    message = form.save(user=request.user)
    message.related_groups.add(group)
    send_mail_message(request, message)

# -------------------------------------------------
# View Functions
# -------------------------------------------------

def materials(request, num=None):
    meeting = get_meeting(num)
    begin_date = meeting.get_submission_start_date()
    cut_off_date = meeting.get_submission_cut_off_date()
    cor_cut_off_date = meeting.get_submission_correction_date()
    today_utc = date_today(datetime.timezone.utc)
    old = timezone.now() - datetime.timedelta(days=1)
    if settings.SERVER_MODE != 'production' and '_testoverride' in request.GET:
        pass
    elif today_utc > cor_cut_off_date:
        if meeting.number.isdigit() and int(meeting.number) > 96:
            return redirect('ietf.meeting.views.proceedings', num=meeting.number)
        else:
            with timezone.override(meeting.tz()):
                return render(request, "meeting/materials_upload_closed.html", {
                    'meeting_num': meeting.number,
                    'begin_date': begin_date,
                    'cut_off_date': cut_off_date,
                    'cor_cut_off_date': cor_cut_off_date
                })

    past_cutoff_date = today_utc > meeting.get_submission_correction_date()

    schedule = get_schedule(meeting, None)

    sessions  = add_event_info_to_session_qs(Session.objects.filter(
        meeting__number=meeting.number,
        timeslotassignments__schedule__in=[schedule, schedule.base if schedule else None]
    ).distinct().select_related('meeting__schedule', 'group__state', 'group__parent')).order_by('group__acronym')

    plenaries = sessions.filter(name__icontains='plenary')
    ietf      = sessions.filter(group__parent__type__slug = 'area').exclude(group__acronym='edu').order_by('group__parent__acronym', 'group__acronym')
    irtf      = sessions.filter(group__parent__acronym = 'irtf')
    training  = sessions.filter(group__acronym__in=['edu','iaoc'], type_id__in=['regular', 'other', ])
    iab       = sessions.filter(group__parent__acronym = 'iab')
    editorial      = sessions.filter(group__acronym__in=['rsab','rswg'])

    session_pks = [s.pk for ss in [plenaries, ietf, irtf, training, iab, editorial] for s in ss]
    other     = sessions.filter(type__in=['regular'], group__type__features__has_meetings=True).exclude(pk__in=session_pks)

    for topic in [plenaries, ietf, training, irtf, iab, editorial]:
        for event in topic:
            date_list = []
            for slide_event in event.all_meeting_slides(): date_list.append(slide_event.time)
            for agenda_event in event.all_meeting_agendas(): date_list.append(agenda_event.time)
            if date_list: setattr(event, 'last_update', sorted(date_list, reverse=True)[0])

    for session_list in [plenaries, ietf, training, irtf, iab, editorial, other]:
        for session in session_list:
            session.past_cutoff_date = past_cutoff_date

    proceedings_materials = [
        (type_name, meeting.proceedings_materials.filter(type=type_name).first())
        for type_name in ProceedingsMaterialTypeName.objects.all()
    ]

    plenaries, _ = organize_proceedings_sessions(plenaries)
    irtf, _ = organize_proceedings_sessions(irtf)
    training, _ = organize_proceedings_sessions(training)
    iab, _ = organize_proceedings_sessions(iab)
    editorial, _ = organize_proceedings_sessions(editorial)
    other, _ = organize_proceedings_sessions(other)

    ietf_areas = []
    for area, area_sessions in itertools.groupby(
            ietf,
            key=lambda s: s.group.parent
    ):
        meeting_groups, not_meeting_groups = organize_proceedings_sessions(area_sessions)
        ietf_areas.append((area, meeting_groups, not_meeting_groups))

    with timezone.override(meeting.tz()):
        return render(request, "meeting/materials.html", {
            'meeting': meeting,
            'proceedings_materials': proceedings_materials,
            'plenaries': plenaries,
            'ietf_areas': ietf_areas,
            'training': training,
            'irtf': irtf,
            'iab': iab,
            'editorial': editorial,
            'other': other,
            'cut_off_date': cut_off_date,
            'cor_cut_off_date': cor_cut_off_date,
            'submission_started': today_utc > begin_date,
            'old': old,
        })

def current_materials(request):
    today = date_today()
    meetings = Meeting.objects.exclude(number__startswith='interim-').filter(date__lte=today).order_by('-date')
    if meetings:
        return redirect(materials, meetings[0].number)
    else:
        raise Http404('No such meeting')


def _get_materials_doc(meeting, name):
    """Get meeting materials document named by name

    Raises Document.DoesNotExist if a match cannot be found.
    """
    # try an exact match first
    doc = Document.objects.filter(name=name).first()
    if doc is not None and doc.get_related_meeting() == meeting:
        return doc, None
    # try parsing a rev number
    if "-" in name:
        docname, rev = name.rsplit("-", 1)
        if len(rev) == 2 and rev.isdigit():
            doc = Document.objects.get(name=docname)  # may raise Document.DoesNotExist
            if doc.get_related_meeting() == meeting and rev in doc.revisions_by_newrevisionevent():
                return doc, rev
    # give up
    raise Document.DoesNotExist


@cache_page(1 * 60)
def materials_document(request, document, num=None, ext=None):
    meeting=get_meeting(num,type_in=['ietf','interim'])
    num = meeting.number
    try:
        doc, rev = _get_materials_doc(meeting=meeting, name=document)
    except Document.DoesNotExist:
        raise Http404("No such document for meeting %s" % num)

    if not rev:
        filename = doc.get_file_name()
    else:
        filename = os.path.join(doc.get_file_path(), document)
    if ext:
        if not filename.endswith(ext):
            name, _ = os.path.splitext(filename)
            filename = name + ext
    else:
        filenames = glob.glob(filename+'.*')
        if filenames:
            filename = filenames[0]
    _, basename = os.path.split(filename)
    if not os.path.exists(filename):
        raise Http404("File not found: %s" % filename)

    old_proceedings_format = meeting.number.isdigit() and int(meeting.number) <= 96
    if settings.MEETING_MATERIALS_SERVE_LOCALLY or old_proceedings_format:
        with io.open(filename, 'rb') as file:
            bytes = file.read()
        
        mtype, chset = get_mime_type(bytes)
        content_type = "%s; charset=%s" % (mtype, chset)

        file_ext = os.path.splitext(filename)
        if len(file_ext) == 2 and file_ext[1] == '.md' and mtype == 'text/plain':
            sorted_accept = sort_accept_tuple(request.META.get('HTTP_ACCEPT'))
            for atype in sorted_accept:
                if atype[0] == "text/markdown":
                    content_type = content_type.replace("plain", "markdown", 1)
                    break
                elif atype[0] == "text/html":
                    bytes = render_to_string(
                        "minimal.html",
                        {
                            "content": markdown.markdown(bytes.decode(encoding=chset)),
                            "title": basename,
                        },
                    )
                    content_type = content_type.replace("plain", "html", 1)
                    break
                elif atype[0] == "text/plain":
                    break

        response = HttpResponse(bytes, content_type=content_type)
        response['Content-Disposition'] = 'inline; filename="%s"' % basename
        return response
    else:
        return HttpResponseRedirect(redirect_to=doc.get_href(meeting=meeting))

@login_required
def materials_editable_groups(request, num=None):
    meeting = get_meeting(num)
    return render(request, "meeting/materials_editable_groups.html", {
        'meeting_num': meeting.number})


@role_required('Secretariat')
def edit_timeslots(request, num=None):
    meeting = get_meeting(num)
    if 'sched' in request.GET:
        schedule = Schedule.objects.filter(pk=request.GET.get('sched', None)).first()
        schedule_edit_url = _schedule_edit_url(meeting, schedule)
    else:
        schedule_edit_url = None

    with timezone.override(meeting.tz()):
        if request.method == 'POST':
            # handle AJAX requests
            action = request.POST.get('action')
            if action == 'delete':
                # delete a timeslot
                # Parameters:
                #   slot_id: comma-separated list of TimeSlot PKs to delete
                slot_id = request.POST.get('slot_id')
                if slot_id is None:
                    return HttpResponseBadRequest('missing slot_id')
                slot_ids = [id.strip() for id in slot_id.split(',')]
                try:
                    timeslots = meeting.timeslot_set.filter(pk__in=slot_ids)
                except ValueError:
                    return HttpResponseBadRequest('invalid slot_id specification')
                missing_ids = set(slot_ids).difference(str(ts.pk) for ts in timeslots)
                if len(missing_ids) != 0:
                    return HttpResponseNotFound('TimeSlot ids not found in meeting {}: {}'.format(
                        meeting.number,
                        ', '.join(sorted(missing_ids))
                    ))
                timeslots.delete()
                return HttpResponse(content='; '.join('Deleted TimeSlot {}'.format(id) for id in slot_ids))
            else:
                return HttpResponseBadRequest('unknown action')

        # Labels here differ from those in the build_timeslices() method. The labels here are
        # relative to the table: time_slices are the row headings (ie, days), date_slices are
        # the column headings (i.e., time intervals), and slots are the per-day list of timeslots
        # (with only one timeslot per unique time/duration)
        time_slices, date_slices, slots = meeting.build_timeslices()

        ts_list = deque()
        rooms = meeting.room_set.order_by("capacity","name","id")
        for room in rooms:
            for day in time_slices:
                for slice in date_slices[day]:
                    ts_list.append(room.timeslot_set.filter(time=slice[0],duration=datetime.timedelta(seconds=slice[2])))

        # Grab these in one query each to identify sessions that are in use and should be handled with care
        ts_with_official_assignments = meeting.timeslot_set.filter(sessionassignments__schedule=meeting.schedule)
        ts_with_any_assignments = meeting.timeslot_set.filter(sessionassignments__isnull=False)

        return render(request, "meeting/timeslot_edit.html",
                                             {"rooms":rooms,
                                              "time_slices":time_slices,
                                              "slot_slices": slots,
                                              "date_slices":date_slices,
                                              "meeting":meeting,
                                              "schedule_edit_url": schedule_edit_url,
                                              "ts_list":ts_list,
                                              "ts_with_official_assignments": ts_with_official_assignments,
                                              "ts_with_any_assignments": ts_with_any_assignments,
                                          })


class NewScheduleForm(forms.ModelForm):
    class Meta:
        model = Schedule
        fields = ['name', 'visible', 'public', 'notes', 'base']

    def __init__(self, meeting, schedule, new_owner, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.meeting = meeting
        self.schedule = schedule
        self.new_owner = new_owner

        username = new_owner.user.username

        name_suggestion = username
        counter = 2

        existing_names = set(Schedule.objects.filter(meeting=meeting, owner=new_owner).values_list('name', flat=True))
        while name_suggestion in existing_names:
            name_suggestion = username + str(counter)
            counter += 1

        self.fields['name'].initial = name_suggestion
        self.fields['name'].label = "Name of new agenda"

        self.fields['base'].queryset = self.fields['base'].queryset.filter(meeting=meeting)

        if schedule:
            self.fields['visible'].initial = schedule.visible
            self.fields['public'].initial = schedule.public
            self.fields['base'].queryset = self.fields['base'].queryset.exclude(pk=schedule.pk)
            self.fields['base'].initial = schedule.base_id
        else:
            base = Schedule.objects.filter(meeting=meeting, name='base').first()
            if base:
                self.fields['base'].initial = base.pk

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name and Schedule.objects.filter(meeting=self.meeting, owner=self.new_owner, name=name):
            raise forms.ValidationError("Schedule with this name already exists.")
        return name

@role_required('Area Director','Secretariat')
def new_meeting_schedule(request, num, owner=None, name=None):
    meeting  = get_meeting(num)
    schedule = get_schedule_by_name(meeting, get_person_by_email(owner), name)

    if request.method == 'POST':
        form = NewScheduleForm(meeting, schedule, request.user.person, request.POST)

        if form.is_valid():
            new_schedule = form.save(commit=False)
            new_schedule.meeting = meeting
            new_schedule.owner = request.user.person
            new_schedule.origin = schedule
            new_schedule.save()

            if schedule:
                for assignment in schedule.assignments.all():
                    # clone by resetting primary key
                    assignment.pk = None
                    assignment.schedule = new_schedule
                    assignment.extendedfrom = None
                    assignment.save()

            # now redirect to this new schedule
            return redirect(edit_meeting_schedule, meeting.number, new_schedule.owner_email(), new_schedule.name)
            
    else:
        form = NewScheduleForm(meeting, schedule, request.user.person)

    return render(request, "meeting/new_meeting_schedule.html", {
        'meeting': meeting,
        'schedule': schedule,
        'form': form,
    })

@ensure_csrf_cookie
def edit_meeting_schedule(request, num=None, owner=None, name=None):
    """Schedule editor

    In addition to the URL parameters, accepts a query string parameter 'type'.
    If present, only sessions/timeslots with a TimeSlotTypeName with that slug
    will be included in the editor. More than one type can be enabled by passing
    multiple type parameters.

    ?type=regular  - shows only regular sessions/timeslots (i.e., old editor behavior)
    ?type=regular&type=other  - shows both regular and other sessions/timeslots
    """
    # Need to coordinate this list with types of session requests
    # that can be created (see, e.g., SessionQuerySet.requests())
    meeting = get_meeting(num)
    if name is None:
        schedule = meeting.schedule
    else:
        schedule = get_schedule_by_name(meeting, get_person_by_email(owner), name)

    if schedule is None:
        raise Http404("No meeting information for meeting %s owner %s schedule %s available" % (num, owner, name))

    can_see, can_edit, secretariat = schedule_permissions(meeting, schedule, request.user)

    lock_time = settings.MEETING_SESSION_LOCK_TIME
    def timeslot_locked(ts):
        meeting_now = timezone.now().astimezone(meeting.tz())
        return schedule.is_official and (ts.time - meeting_now < lock_time)

    if not can_see:
        if request.method == 'POST':
            permission_denied(request, "Can't view this schedule.")

        return render(request, "meeting/private_schedule.html", {
            "schedule":schedule,
            "meeting": meeting,
            "meeting_base_url": request.build_absolute_uri(meeting.base_url()),
            "hide_menu": True
        }, status=403, content_type="text/html")

    # See if we were given one or more 'type' query string parameters. If so, filter to that timeslot type.
    if 'type' in request.GET:
        include_timeslot_types = request.GET.getlist('type')
    else:
        include_timeslot_types = None  # disables filtering by type (other than IGNORE_TIMESLOT_TYPES)

    assignments = SchedTimeSessAssignment.objects.filter(
        schedule__in=[schedule, schedule.base],
        timeslot__location__isnull=False,
    )
    if include_timeslot_types is not None:
        assignments = assignments.filter(session__type__in=include_timeslot_types)
    assignments = assignments.order_by('timeslot__time','timeslot__name')

    assignments_by_session = defaultdict(list)
    for a in assignments:
        assignments_by_session[a.session_id].append(a)

    tombstone_states = ['canceled', 'canceledpa', 'resched']

    sessions = meeting.session_set.with_current_status()
    if include_timeslot_types is not None:
        sessions = sessions.filter(type__in=include_timeslot_types)
    sessions_to_schedule = sessions.that_can_be_scheduled()
    session_tombstones = sessions.filter(
        current_status__in=tombstone_states, pk__in={a.session_id for a in assignments}
    )
    sessions = sessions_to_schedule | session_tombstones
    sessions = add_event_info_to_session_qs(
        sessions.order_by('pk'),
        requested_time=True,
        requested_by=True,
    ).prefetch_related(
        'resources', 'group', 'group__parent', 'group__type', 'joint_with_groups', 'purpose',
    )

    timeslots_qs = TimeSlot.objects.filter(meeting=meeting)
    if include_timeslot_types is not None:
        timeslots_qs = timeslots_qs.filter(type__in=include_timeslot_types)
    timeslots_qs = timeslots_qs.that_can_be_scheduled().prefetch_related('type').order_by('location', 'time', 'name')

    if timeslots_qs.count() > 0:
        min_duration = min(t.duration for t in timeslots_qs)
        max_duration = max(t.duration for t in timeslots_qs)
    else:
        min_duration = datetime.timedelta(minutes=30)
        max_duration = datetime.timedelta(minutes=120)

    def timedelta_to_css_ems(timedelta):
        # we scale the session and slots a bit according to their
        # length for an added visual clue
        capped_min_d = max(min_duration, datetime.timedelta(minutes=30))
        capped_max_d = min(max_duration, datetime.timedelta(hours=4))
        capped_timedelta = min(max(capped_min_d, timedelta), capped_max_d)

        min_d_css_rems = 5
        max_d_css_rems = 7
        # interpolate
        scale = (capped_timedelta - capped_min_d) / (capped_max_d - capped_min_d) if capped_min_d != capped_max_d else 1
        return min_d_css_rems + (max_d_css_rems - min_d_css_rems) * scale

    def prepare_sessions_for_display(sessions):
        # requesters
        requested_by_lookup = {p.pk: p for p in Person.objects.filter(pk__in=set(s.requested_by for s in sessions if s.requested_by))}

        # constraints
        constraints_for_sessions, formatted_constraints_for_sessions, constraint_names = preprocess_constraints_for_meeting_schedule_editor(meeting, sessions)

        sessions_for_group = defaultdict(list)
        for s in sessions:
            sessions_for_group[s.group_id].append(s)

        for s in sessions:
            s.requested_by_person = requested_by_lookup.get(s.requested_by)

            s.purpose_label = None
            if s.group:
                if (s.purpose.slug in ('none', 'regular')):
                    s.scheduling_label = s.group.acronym
                    s.purpose_label = 'BoF' if s.group.is_bof() else s.group.type.name
                else:
                    s.scheduling_label = s.name if s.name else f'??? [{s.group.acronym}]'
                    s.purpose_label = s.purpose.name
            else:
                s.scheduling_label = s.name if s.name else '???'
                s.purpose_label = s.purpose.name

            s.requested_duration_in_hours = round(s.requested_duration.seconds / 60.0 / 60.0, 1)

            session_layout_margin = 0.2
            s.layout_width = timedelta_to_css_ems(s.requested_duration) - 2 * session_layout_margin
            s.parent_acronym = s.group.parent.acronym if s.group and s.group.parent else ""

            # compress the constraints, so similar constraint labels are
            # shared between the conflicting sessions they cover - the JS
            # then simply has to detect violations and show the
            # preprocessed labels
            ConstraintHint = namedtuple('ConstraintHint', 'constraint_name count')
            constraint_hints = defaultdict(set)
            for name_id, ts in itertools.groupby(sorted(constraints_for_sessions.get(s.pk, [])), key=lambda t: t[0]):  # name_id same for each set of ts
                ts = list(ts)
                session_pks = (t[1] for t in ts)
                for session_pk, grouped_session_pks in itertools.groupby(session_pks):
                    # count is the number of instances of session_pk - should only have multiple in the
                    # case of bethere constraints, where there will be one per person.pk
                    count = len(list(grouped_session_pks))  # list() needed because iterator has no len()
                    constraint_hints[ConstraintHint(constraint_names[name_id], count)].add(session_pk)

            # The constraint hint key is a tuple (ConstraintName, count). Value is the set of sessions pks that
            # should trigger that hint.
            s.constraint_hints = list(constraint_hints.items())
            s.formatted_constraints = formatted_constraints_for_sessions.get(s.pk, {})

            s.other_sessions = [s_other for s_other in sessions_for_group.get(s.group_id) if s != s_other]

            s.readonly = s.current_status in tombstone_states or any(a.schedule_id != schedule.pk for a in assignments_by_session.get(s.pk, []))

    def prepare_timeslots_for_display(timeslots, rooms):
        """Prepare timeslot data for template

        Prepares timeslots for display by sorting into groups in a structure
        that can be rendered by the template and by adding some data to the timeslot
        instances. Currently adds a 'layout_width' property to each timeslot instance.
        The layout_width is the width, in em, that should be used to style the timeslot's
        width.

        Rooms are partitioned into groups that have identical sets of timeslots
        for the entire meeting.

        The result of this method is an OrderedDict, days, keyed by the Date
        of each day that has at least one timeslot. The value of days[day] is a
        list with one entry for each group of rooms. Each entry is a list of
        dicts with keys 'room' and 'timeslots'. The 'room' value is the room
        instance and 'timeslots' is a list of timeslot instances for that room.

        The format is more easily illustrated than explained:

        days = OrderedDict(
          Date(2021, 5, 27): [
            [  # room group 1
              {'room': <room1>, 'timeslots': [<room1 timeslot1>, <room1 timeslot2>]},
              {'room': <room2>, 'timeslots': [<room2 timeslot1>, <room2 timeslot2>]},
              {'room': <room3>, 'timeslots': [<room3 timeslot1>, <room3 timeslot2>]},
            ],
            [  # room group 2
              {'room': <room4>, 'timeslots': [<room4 timeslot1>]},
            ],
          ],
          Date(2021, 5, 28): [
            [ # room group 1
              {'room': <room1>, 'timeslots': [<room1 timeslot3>]},
              {'room': <room2>, 'timeslots': [<room2 timeslot3>]},
              {'room': <room3>, 'timeslots': [<room3 timeslot3>]},
            ],
            [ # room group 2
              {'room': <room4>, 'timeslots': []},
            ],
          ],
        )
        """

        # Populate room_data. This collects the timeslots for each room binned by
        # day, plus data needed for sorting the rooms for display.
        room_data = dict()
        all_days = set()
        # timeslots_qs is already sorted by location, name, and time
        for t in timeslots:
            if t.location not in rooms:
                continue

            t.layout_width = timedelta_to_css_ems(t.duration)
            if t.location_id not in room_data:
                room_data[t.location_id] = dict(
                    timeslots_by_day=dict(),
                    timeslot_count=0,
                    start_and_duration=[],
                    first_timeslot = t,
                )
            rd = room_data[t.location_id]
            rd['timeslot_count'] += 1
            rd['start_and_duration'].append((t.time, t.duration))
            ttd = t.local_start_time().date()  # date in meeting timezone
            all_days.add(ttd)
            if ttd not in rd['timeslots_by_day']:
                rd['timeslots_by_day'][ttd] = []
            rd['timeslots_by_day'][ttd].append(t)

        all_days = sorted(all_days)  # changes set to a list
        # Note the maximum timeslot count for any room
        if len(room_data) > 0:
            max_timeslots = max(rd['timeslot_count'] for rd in room_data.values())
        else:
            max_timeslots = 0

        # Partition rooms into groups with identical timeslot arrangements.
        # Start by discarding any roos that have no timeslots.
        rooms_with_timeslots = [r for r in rooms if r.pk in room_data]
        # Then sort the remaining rooms.
        sorted_rooms = sorted(
            rooms_with_timeslots,
            key=lambda room: (
                # Sort lower capacity rooms first.
                room.capacity if room.capacity is not None else math.inf,  # sort rooms with capacity = None at end
                # Sort regular session rooms ahead of others - these will usually
                # have more timeslots than other room types.
                0 if room_data[room.pk]['timeslot_count'] == max_timeslots else 1,
                # Sort rooms with earlier timeslots ahead of later
                room_data[room.pk]['first_timeslot'].time,
                # Sort rooms with more sessions ahead of rooms with fewer
                0 - room_data[room.pk]['timeslot_count'],
                # Sort by list of starting time and duration so that groups with identical
                # timeslot structure will be neighbors. The grouping algorithm relies on this!
                room_data[room.pk]['start_and_duration'],
                # Finally, sort alphabetically by name
                room.name
            )
        )

        # Rooms are now ordered so rooms with identical timeslot arrangements are neighbors.
        # Walk the list, splitting these into groups.
        room_groups = []
        last_start_and_duration = None  # Used to watch for changes in start_and_duration
        for room in sorted_rooms:
            if last_start_and_duration != room_data[room.pk]['start_and_duration']:
                room_groups.append([])  # start a new room_group
                last_start_and_duration = room_data[room.pk]['start_and_duration']
            room_groups[-1].append(room)

        # Next, build the structure that will hold the data for the view. This makes it
        # easier to arrange that every room has an entry for every day, even if there is
        # no timeslot for that day. This makes the HTML template much easier to write.
        # Use OrderedDicts instead of lists so that we can easily put timeslot data in the
        # right place.
        days = OrderedDict(
            (
                day,  # key in the Ordered Dict
                [
                    # each value is an OrderedDict of room group data
                    OrderedDict(
                        (room.pk, dict(room=room, timeslots=[]))
                        for room in rg
                    ) for rg in room_groups
                ]
            ) for day in all_days
        )

        # With the structure's skeleton built, now fill in the data. The loops must
        # preserve the order of room groups and rooms within each group.
        for rg_num, rgroup in enumerate(room_groups):
            for room in rgroup:
                for day, ts_for_day in room_data[room.pk]['timeslots_by_day'].items():
                    days[day][rg_num][room.pk]['timeslots'] = ts_for_day

        # Now convert the OrderedDict entries into lists since we don't need to
        # do lookup by pk any more.
        for day in days.keys():
            days[day] = [list(rg.values()) for rg in days[day]]

        return days

    def _json_response(success, status=None, **extra_data):
        if status is None:
            status = 200 if success else 400
        data = dict(success=success, **extra_data)
        return JsonResponse(data, status=status)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'updateview':
            # allow updateview action even if can_edit is false, it affects only the user's session
            sess_data = request.session.setdefault('edit_meeting_schedule', {})
            enabled_types = [ts_type.slug for ts_type in TimeSlotTypeName.objects.filter(
                used=True,
                slug__in=request.POST.getlist('enabled_timeslot_types[]', [])
            )]
            sess_data['enabled_timeslot_types'] = enabled_types
            return _json_response(True)
        elif not can_edit:
            permission_denied(request, "Can't edit this schedule.")

        # Handle ajax requests. Most of these return JSON responses with at least a 'success' key.
        # For the swapdays and swaptimeslots actions, the response is either a redirect to the
        # updated page or a simple BadRequest error page. The latter should not normally be seen
        # by the user, because the front end should be preventing most invalid requests.
        if action == 'assign' and request.POST.get('session', '').isdigit() and request.POST.get('timeslot', '').isdigit():
            session = get_object_or_404(sessions, pk=request.POST['session'])
            timeslot = get_object_or_404(timeslots_qs, pk=request.POST['timeslot'])
            if timeslot_locked(timeslot):
                return _json_response(False, error="Can't assign to this timeslot.")

            tombstone_session = None

            existing_assignments = SchedTimeSessAssignment.objects.filter(session=session, schedule=schedule)

            if existing_assignments:
                assertion('len(existing_assignments) <= 1',
                          note='Multiple assignments for {} in schedule {}'.format(session, schedule))

                if timeslot_locked(existing_assignments[0].timeslot):
                    return _json_response(False, error="Can't reassign this session.")

                if schedule.pk == meeting.schedule_id and session.current_status == 'sched':
                    old_timeslot = existing_assignments[0].timeslot
                    # clone session and leave it as a tombstone
                    tombstone_session = session
                    tombstone_session.tombstone_for_id = session.pk
                    tombstone_session.pk = None
                    tombstone_session.save()

                    session = None

                    SchedulingEvent.objects.create(
                        session=tombstone_session,
                        status=SessionStatusName.objects.get(slug='resched'),
                        by=request.user.person,
                    )

                    tombstone_session.current_status = 'resched' # rematerialize status for the rendering

                    SchedTimeSessAssignment.objects.create(
                        session=tombstone_session,
                        schedule=schedule,
                        timeslot=old_timeslot,
                    )

                existing_assignments.update(timeslot=timeslot, modified=timezone.now())
            else:
                SchedTimeSessAssignment.objects.create(
                    session=session,
                    schedule=schedule,
                    timeslot=timeslot,
                )

            if tombstone_session:
                prepare_sessions_for_display([tombstone_session])
                return _json_response(
                    True,
                    tombstone=render_to_string("meeting/edit_meeting_schedule_session.html",
                                               {'session': tombstone_session})
                )
            else:
                return _json_response(True)

        elif action == 'unassign' and request.POST.get('session', '').isdigit():
            session = get_object_or_404(sessions, pk=request.POST['session'])
            existing_assignments = SchedTimeSessAssignment.objects.filter(session=session, schedule=schedule)
            assertion('len(existing_assignments) <= 1',
                      note='Multiple assignments for {} in schedule {}'.format(session, schedule))
            if not any(timeslot_locked(ea.timeslot) for ea in existing_assignments):
                existing_assignments.delete()
            else:
                return _json_response(False, error="Can't unassign this session.")

            return _json_response(True)

        elif action == 'swapdays':
            # updating the client side is a bit complicated, so just
            # do a full refresh

            swap_days_form = SwapDaysForm(request.POST)
            if not swap_days_form.is_valid():
                return HttpResponseBadRequest("Invalid swap: {}".format(swap_days_form.errors))

            source_day = swap_days_form.cleaned_data['source_day']
            target_day = swap_days_form.cleaned_data['target_day']

            source_timeslots = [ts for ts in timeslots_qs if ts.local_start_time().date() == source_day]
            target_timeslots = [ts for ts in timeslots_qs if ts.local_start_time().date() == target_day]
            if any(timeslot_locked(ts) for ts in source_timeslots + target_timeslots):
                return HttpResponseBadRequest("Can't swap these days.")

            swap_meeting_schedule_timeslot_assignments(schedule, source_timeslots, target_timeslots, target_day - source_day)

            return HttpResponseRedirect(request.get_full_path())

        elif action == 'swaptimeslots':
            # Swap sets of timeslots with equal start/end time for a given set of rooms.
            # Gets start and end times from TimeSlot instances for the origin and target,
            # then swaps all timeslots for the requested rooms whose start/end match those.
            # The origin/target timeslots do not need to be the same duration.
            swap_timeslots_form = SwapTimeslotsForm(meeting, request.POST)
            if not swap_timeslots_form.is_valid():
                return HttpResponseBadRequest("Invalid swap: {}".format(swap_timeslots_form.errors))

            affected_rooms = swap_timeslots_form.cleaned_data['rooms']
            origin_timeslot = swap_timeslots_form.cleaned_data['origin_timeslot']
            target_timeslot = swap_timeslots_form.cleaned_data['target_timeslot']

            origin_timeslots = meeting.timeslot_set.filter(
                location__in=affected_rooms,
                time=origin_timeslot.time,
                duration=origin_timeslot.duration,
            )
            target_timeslots = meeting.timeslot_set.filter(
                location__in=affected_rooms,
                time=target_timeslot.time,
                duration=target_timeslot.duration,
            )
            if (any(timeslot_locked(ts) for ts in origin_timeslots)
                    or any(timeslot_locked(ts) for ts in target_timeslots)):
                return HttpResponseBadRequest("Can't swap these timeslots.")

            swap_meeting_schedule_timeslot_assignments(
                schedule,
                list(origin_timeslots),
                list(target_timeslots),
                target_timeslot.time - origin_timeslot.time,
            )
            return HttpResponseRedirect(request.get_full_path())

        return _json_response(False, error="Invalid parameters")

    # Show only rooms that have regular sessions
    if include_timeslot_types is None:
        rooms = meeting.room_set.all()
    else:
        rooms = meeting.room_set.filter(session_types__slug__in=include_timeslot_types)

    # Construct timeslot data for the template to render
    days = prepare_timeslots_for_display(timeslots_qs, rooms)

    # possible timeslot start/ends
    timeslot_groups = defaultdict(set)
    for ts in timeslots_qs:
        ts.start_end_group = "ts-group-{}-{}".format(ts.local_start_time().strftime("%Y%m%d-%H%M"), int(ts.duration.total_seconds() / 60))
        timeslot_groups[ts.local_start_time().date()].add((ts.local_start_time(), ts.local_end_time(), ts.start_end_group))

    # prepare sessions
    prepare_sessions_for_display(sessions)

    for ts in timeslots_qs:
        ts.session_assignments = []
    timeslots_by_pk = {ts.pk: ts for ts in timeslots_qs}

    unassigned_sessions = []
    for s in sessions:
        assigned = False
        for a in assignments_by_session.get(s.pk, []):
            timeslot = timeslots_by_pk.get(a.timeslot_id)
            if timeslot:
                timeslot.session_assignments.append((a, s))
                assigned = True

        if not assigned:
            unassigned_sessions.append(s)

    # group parent colors
    def cubehelix(i, total, hue=1.2, start_angle=0.5):
        # theory in https://arxiv.org/pdf/1108.5083.pdf
        rotations = total // 4
        x = float(i + 1) / (total + 1)
        phi = 2 * math.pi * (start_angle / 3 + rotations * x)
        a = hue * x * (1 - x) / 2.0

        return (
            max(0, min(x + a * (-0.14861 * math.cos(phi) + 1.78277 * math.sin(phi)), 1)),
            max(0, min(x + a * (-0.29227 * math.cos(phi) + -0.90649 * math.sin(phi)), 1)),
            max(0, min(x + a * (1.97294 * math.cos(phi)), 1)),
        )

    session_parents = sorted(set(
        s.group.parent for s in sessions
        if s.group and s.group.parent and (s.group.parent.type_id == 'area' or s.group.parent.acronym in ('irtf','iab'))
    ), key=lambda p: p.acronym)

    liz_preferred_colors = {
        'art' : { 'dark' : (204, 121, 167) , 'light' : (234, 232, 230) },
        'gen' : { 'dark' : (29, 78, 17) , 'light' : (232, 237, 231) },
        'iab' : { 'dark' : (255, 165, 0) , 'light' : (255, 246, 230) },
        'int' : { 'dark' : (132, 240, 240) , 'light' : (232, 240, 241) },
        'irtf' : { 'dark' : (154, 119, 230) , 'light' : (243, 239, 248) },
        'ops' : { 'dark' : (199, 133, 129) , 'light' : (250, 240, 242) },
        'rtg' : { 'dark' : (222, 219, 124) , 'light' : (247, 247, 233) },
        'sec' : { 'dark' : (0, 114, 178) , 'light' : (245, 252, 248) },
        'tsv' : { 'dark' : (117,201,119) , 'light' : (251, 252, 255) },
        'wit' : { 'dark' : (117,201,119) , 'light' : (251, 252, 255) }, # intentionally the same as tsv
    }    
    for i, p in enumerate(session_parents):
        if p.acronym in liz_preferred_colors:
            colors = liz_preferred_colors[p.acronym]
            p.scheduling_color = "rgb({}, {}, {})".format(*colors['dark'])
            p.light_scheduling_color = "rgb({}, {}, {})".format(*colors['light'])
        else:
            rgb_color = cubehelix(i, len(session_parents))
            p.scheduling_color = "rgb({}, {}, {})".format(*tuple(int(round(x * 255)) for x in rgb_color))
            p.light_scheduling_color = "rgb({}, {}, {})".format(*tuple(int(round((0.9 + 0.1 * x) * 255)) for x in rgb_color))

    session_purposes = sorted(set(s.purpose for s in sessions if s.purpose), key=lambda p: p.name)
    timeslot_types = sorted(
        set(
            s.type for s in sessions if s.type
        ).union(
            t.type for t in timeslots_qs.all()
        ),
        key=lambda tstype: tstype.name,
    )

    # extract view configuration from session store
    session_data = request.session.get('edit_meeting_schedule', None)
    if session_data is None:
        enabled_timeslot_types = ['regular']
    else:
        enabled_timeslot_types = [
            ts_type.slug for ts_type in timeslot_types
            if ts_type.slug in session_data.get('enabled_timeslot_types', [])
        ]

    with timezone.override(meeting.tz()):
        return render(request, "meeting/edit_meeting_schedule.html", {
            'meeting': meeting,
            'schedule': schedule,
            'can_edit': can_edit,
            'can_edit_properties': can_edit or secretariat,
            'secretariat': secretariat,
            'days': days,
            'timeslot_groups': sorted((d, list(sorted(t_groups))) for d, t_groups in timeslot_groups.items()),
            'unassigned_sessions': unassigned_sessions,
            'session_parents': session_parents,
            'session_purposes': session_purposes,
            'timeslot_types': timeslot_types,
            'hide_menu': True,
            'lock_time': lock_time,
            'enabled_timeslot_types': enabled_timeslot_types,
        })


class RoomNameModelChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.name

class TimeSlotForm(forms.Form):
    day = forms.TypedChoiceField(coerce=lambda t: datetime.datetime.strptime(t, "%Y-%m-%d").date())  # all dates, no tz
    time = forms.TimeField()
    duration = CustomDurationField() # this is just to make 1:30 turn into 1.5 hours instead of 1.5 minutes
    location = RoomNameModelChoiceField(queryset=Room.objects.all(), required=False, empty_label="(No location)")
    show_location = forms.BooleanField(initial=True, required=False)
    type = forms.ModelChoiceField(queryset=TimeSlotTypeName.objects.filter(used=True), empty_label=None, required=False)
    purpose = forms.ModelChoiceField(queryset=SessionPurposeName.objects.filter(used=True), required=False, widget=forms.HiddenInput)
    name = forms.CharField(help_text='Name that appears on the agenda', required=False)
    short = forms.CharField(max_length=32,label='Short name', help_text='Abbreviated session name used for material file names', required=False)
    group = forms.ModelChoiceField(queryset=Group.objects.filter(type__in=['ietf', 'team'], state='active'),
        help_text='''Select a group to associate with this session.<br>For example: Tutorials = Education, Code Sprint = Tools Team''',
        required=False)
    agenda_note = forms.CharField(required=False)

    def __init__(self, meeting, schedule, *args, timeslot=None, **kwargs):
        super().__init__(*args,**kwargs)

        self.fields["time"].widget.attrs["placeholder"] = "HH:MM"
        self.fields["duration"].widget.attrs["placeholder"] = "HH:MM"
        self.fields["duration"].initial = ""

        self.fields["day"].choices = [
            ((meeting.date + datetime.timedelta(days=i)).isoformat(), (meeting.date + datetime.timedelta(days=i)).strftime("%a %b %d"))
            for i in range(meeting.days)
        ]

        self.fields['location'].queryset = self.fields['location'].queryset.filter(meeting=meeting)

        self.fields['group'].widget.attrs['data-ietf'] = Group.objects.get(acronym='ietf').pk

        self.active_assignment = None

        # only allow timeslots with at least one purpose
        timeslot_types_with_purpose = set()
        for spn in SessionPurposeName.objects.filter(used=True):
            timeslot_types_with_purpose.update(spn.timeslot_types)
        self.fields['type'].queryset = self.fields['type'].queryset.filter(pk__in=timeslot_types_with_purpose)

        if timeslot:
            self.initial = {
                'day': timeslot.local_start_time().date(),
                'time': timeslot.local_start_time().time(),
                'duration': timeslot.duration,
                'location': timeslot.location_id,
                'show_location': timeslot.show_location,
                'type': timeslot.type_id,
                'name': timeslot.name,
            }

            assignments = sorted(SchedTimeSessAssignment.objects.filter(
                timeslot=timeslot,
                schedule__in=[schedule, schedule.base if schedule else None]
            ).select_related('session', 'session__group'), key=lambda a: 0 if a.schedule_id == schedule.pk else 1)

            if assignments:
                self.active_assignment = assignments[0]

                self.initial['short'] = self.active_assignment.session.short
                self.initial['group'] = self.active_assignment.session.group_id

        if not self.active_assignment or timeslot.type_id != 'regular':
            del self.fields['agenda_note'] # at the moment, the UI only shows this field for regular sessions

        self.timeslot = timeslot

    def clean(self):
        group = self.cleaned_data.get('group')
        ts_type = self.cleaned_data.get('type')
        short = self.cleaned_data.get('short')

        if not ts_type:
            # assign a generic purpose if no type has been set
            self.cleaned_data['purpose'] = SessionPurposeName.objects.get(slug='open_meeting')
        else:
            if ts_type.slug in ['break', 'reg', 'reserved', 'unavail', 'regular']:
                if ts_type.slug != 'regular':
                    self.cleaned_data['group'] = self.fields['group'].queryset.get(acronym='secretariat')
            else:
                if not group:
                    self.add_error('group', 'When scheduling this type of timeslot, a group must be associated')
                if not short:
                    self.add_error('short', 'When scheduling this type of timeslot, a short name is required')

            if self.timeslot and self.timeslot.type.slug == 'regular' and self.active_assignment and ts_type.slug != self.timeslot.type.slug:
                self.add_error('type', "Can't change type on timeslots for regular sessions when a session has been assigned")

            # find an allowed session purpose (guaranteed by TimeSlotForm)
            for purpose in SessionPurposeName.objects.filter(used=True):
                if ts_type.pk in purpose.timeslot_types:
                    self.cleaned_data['purpose'] = purpose
                    break
            if self.cleaned_data['purpose'] is None:
                self.add_error('type', f'{ts_type} has no allowed purposes')


        if (self.active_assignment
            and self.active_assignment.session.group != self.cleaned_data.get('group')
            and self.active_assignment.session.materials.exists()
            and self.timeslot.type.slug != 'regular'):
            self.add_error('group', "Can't change group after materials have been uploaded")


@role_required('Area Director', 'Secretariat')
def edit_meeting_timeslots_and_misc_sessions(request, num=None, owner=None, name=None):
    meeting = get_meeting(num)
    if name is None:
        schedule = meeting.schedule
    else:
        schedule = get_schedule_by_name(meeting, get_person_by_email(owner), name)

    if schedule is None:
        raise Http404("No meeting information for meeting %s owner %s schedule %s available" % (num, owner, name))

    rooms = list(Room.objects.filter(meeting=meeting).prefetch_related('session_types').order_by('-capacity', 'name'))
    rooms.append(Room(name="(No location)"))

    timeslot_qs = TimeSlot.objects.filter(meeting=meeting).prefetch_related('type').order_by('time')

    can_edit = has_role(request.user, 'Secretariat')

    with timezone.override(meeting.tz()):
        if request.method == 'GET' and request.GET.get('action') == "edit-timeslot":
            timeslot_pk = request.GET.get('timeslot')
            if not timeslot_pk or not timeslot_pk.isdecimal():
                raise Http404
            timeslot = get_object_or_404(timeslot_qs, pk=timeslot_pk)

            assigned_session = add_event_info_to_session_qs(Session.objects.filter(
                timeslotassignments__schedule__in=[schedule, schedule.base],
                timeslotassignments__timeslot=timeslot,
            )).first()

            timeslot.can_cancel = not assigned_session or assigned_session.current_status not in ['canceled', 'canceled', 'resched']

            return JsonResponse({
                'form': render_to_string("meeting/edit_timeslot_form.html", {
                    'timeslot_form_action': 'edit',
                    'timeslot_form': TimeSlotForm(meeting, schedule, timeslot=timeslot),
                    'timeslot': timeslot,
                    'schedule': schedule,
                    'meeting': meeting,
                    'can_edit': can_edit,
                }, request=request)
            })

        scroll = request.POST.get('scroll')

        def redirect_with_scroll():
            url = request.get_full_path()
            if scroll and scroll.isdecimal():
                url += "#scroll={}".format(scroll)
            return HttpResponseRedirect(url)

        add_timeslot_form = None
        if request.method == 'POST' and request.POST.get('action') == 'add-timeslot' and can_edit:
            add_timeslot_form = TimeSlotForm(meeting, schedule, request.POST)
            if add_timeslot_form.is_valid():
                c = add_timeslot_form.cleaned_data

                timeslot, created = TimeSlot.objects.get_or_create(
                    meeting=meeting,
                    type=c['type'],
                    name=c['name'],
                    time=meeting.tz().localize(datetime.datetime.combine(c['day'], c['time'])),
                    duration=c['duration'],
                    location=c['location'],
                    show_location=c['show_location'],
                )

                if timeslot.type_id != 'regular':
                    if not created:
                        Session.objects.filter(timeslotassignments__timeslot=timeslot).delete()

                    session = Session.objects.create(
                        meeting=meeting,
                        name=c['name'],
                        short=c['short'],
                        group=c['group'],
                        type=c['type'],
                        purpose=c['purpose'],
                        agenda_note=c.get('agenda_note') or "",
                    )

                    SchedulingEvent.objects.create(
                        session=session,
                        status=SessionStatusName.objects.get(slug='sched'),
                        by=request.user.person,
                    )

                    SchedTimeSessAssignment.objects.create(
                        timeslot=timeslot,
                        session=session,
                        schedule=schedule
                    )

                return redirect_with_scroll()

        edit_timeslot_form = None
        if request.method == 'POST' and request.POST.get('action') == 'edit-timeslot' and can_edit:
            timeslot_pk = request.POST.get('timeslot')
            if not timeslot_pk or not timeslot_pk.isdecimal():
                raise Http404

            timeslot = get_object_or_404(TimeSlot, pk=timeslot_pk)

            edit_timeslot_form = TimeSlotForm(meeting, schedule, request.POST, timeslot=timeslot)
            if edit_timeslot_form.is_valid() and edit_timeslot_form.active_assignment.schedule_id == schedule.pk:

                c = edit_timeslot_form.cleaned_data

                timeslot.type = c['type']
                timeslot.name = c['name']
                timeslot.time = meeting.tz().localize(datetime.datetime.combine(c['day'], c['time']))
                timeslot.duration = c['duration']
                timeslot.location = c['location']
                timeslot.show_location = c['show_location']
                timeslot.save()

                session = Session.objects.filter(
                    timeslotassignments__schedule__in=[schedule, schedule.base if schedule else None],
                    timeslotassignments__timeslot=timeslot,
                ).select_related('group').first()

                if session:
                    if timeslot.type_id != 'regular':
                        session.name = c['name']
                        session.short = c['short']
                        session.group = c['group']
                        session.type = c['type']
                    session.agenda_note = c.get('agenda_note') or ""
                    session.save()

                return redirect_with_scroll()

        if request.method == 'POST' and request.POST.get('action') == 'cancel-timeslot' and can_edit:
            timeslot_pk = request.POST.get('timeslot')
            if not timeslot_pk or not timeslot_pk.isdecimal():
                raise Http404

            timeslot = get_object_or_404(TimeSlot, pk=timeslot_pk)
            if timeslot.type_id != 'break':
                sessions = add_event_info_to_session_qs(
                    Session.objects.filter(timeslotassignments__schedule=schedule, timeslotassignments__timeslot=timeslot),
                ).exclude(current_status__in=['canceled', 'resched'])
                for session in sessions:
                    SchedulingEvent.objects.create(
                        session=session,
                        status=SessionStatusName.objects.get(slug='canceled'),
                        by=request.user.person,
                    )

            return redirect_with_scroll()

        if request.method == 'POST' and request.POST.get('action') == 'delete-timeslot' and can_edit:
            timeslot_pk = request.POST.get('timeslot')
            if not timeslot_pk or not timeslot_pk.isdecimal():
                raise Http404

            timeslot = get_object_or_404(TimeSlot, pk=timeslot_pk)

            if timeslot.type_id != 'regular':
                for session in Session.objects.filter(timeslotassignments__schedule=schedule, timeslotassignments__timeslot=timeslot):
                    for doc in session.materials.all():
                        doc.set_state(State.objects.get(type=doc.type_id, slug='deleted'))
                        e = DocEvent(doc=doc, rev=doc.rev, by=request.user.person, type='deleted')
                        e.desc = "Deleted meeting session"
                        e.save()

                    session.delete()

            timeslot.delete()

            return redirect_with_scroll()

        sessions_by_pk = {
            s.pk: s for s in
            add_event_info_to_session_qs(
                Session.objects.filter(
                    meeting=meeting,
                ).order_by('pk'),
                requested_time=True,
                requested_by=True,
            ).filter(
                current_status__in=['appr', 'schedw', 'scheda', 'sched', 'canceled', 'canceledpa', 'resched']
            ).prefetch_related(
                'group', 'group', 'group__type',
            )
        }

        assignments_by_timeslot = defaultdict(list)
        for a in SchedTimeSessAssignment.objects.filter(schedule__in=[schedule, schedule.base]):
            assignments_by_timeslot[a.timeslot_id].append(a)

        days = [meeting.date + datetime.timedelta(days=i) for i in range(meeting.days)]

        timeslots_by_day_and_room = defaultdict(list)
        for t in timeslot_qs:
            timeslots_by_day_and_room[(t.time.date(), t.location_id)].append(t)

        # Calculate full time range for display in meeting-local time, always showing at least 8am to 10pm
        min_time = min([t.local_start_time().time() for t in timeslot_qs] + [datetime.time(8)])
        max_time = max([t.local_end_time().time() for t in timeslot_qs] + [datetime.time(22)])
        min_max_delta = datetime.datetime.combine(meeting.date, max_time) - datetime.datetime.combine(meeting.date, min_time)

        day_grid = []
        for d in days:
            room_timeslots = []
            for r in rooms:
                ts = []
                for t in timeslots_by_day_and_room.get((d, r.pk), []):
                    # FIXME: the database (as of 2020) contains spurious
                    # regular timeslots in rooms not intended for regular
                    # sessions - once those are gone, this filter can go
                    # away
                    if t.type_id == 'regular' and not any(t.slug == 'regular' for t in r.session_types.all()):
                        continue

                    t.assigned_sessions = []
                    for a in assignments_by_timeslot.get(t.pk, []):
                        s = sessions_by_pk.get(a.session_id)
                        if s:
                            t.assigned_sessions.append(s)

                    local_start_dt = t.local_start_time()
                    local_min_dt = local_start_dt.replace(
                        hour=min_time.hour,
                        minute=min_time.minute,
                        second=min_time.second,
                        microsecond=min_time.microsecond,
                    )
                    t.left_offset = 100.0 * (local_start_dt - local_min_dt) / min_max_delta
                    t.layout_width = min(100.0 * t.duration / min_max_delta, 100 - t.left_offset)
                    ts.append(t)

                room_timeslots.append((r, ts))

            day_grid.append({
                'day': d,
                'room_timeslots': room_timeslots
            })

        return render(request, "meeting/edit_meeting_timeslots_and_misc_sessions.html", {
            'meeting': meeting,
            'schedule': schedule,
            'can_edit': can_edit,
            'day_grid': day_grid,
            'empty_timeslot_form': TimeSlotForm(meeting, schedule),
            'add_timeslot_form': add_timeslot_form,
            'edit_timeslot_form': edit_timeslot_form,
            'scroll': scroll,
            'hide_menu': True,
        })


class SchedulePropertiesForm(forms.ModelForm):
    class Meta:
        model = Schedule
        fields = ['name', 'notes', 'visible', 'public', 'base']

    def __init__(self, meeting, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['base'].queryset = self.fields['base'].queryset.filter(meeting=meeting)
        if self.instance.pk is not None:
            self.fields['base'].queryset = self.fields['base'].queryset.exclude(pk=self.instance.pk)

@role_required('Area Director','Secretariat')
def edit_schedule_properties(request, num, owner, name):
    meeting  = get_meeting(num)
    person   = get_person_by_email(owner)
    schedule = get_schedule_by_name(meeting, person, name)
    if schedule is None:
        raise Http404("No agenda information for meeting %s owner %s schedule %s available" % (num, owner, name))

    can_see, can_edit, secretariat = schedule_permissions(meeting, schedule, request.user)

    can_edit_properties = can_edit or secretariat

    if not can_edit_properties:
        permission_denied(request, "You may not edit this schedule.")

    if request.method == 'POST':
        # use a new copy of the Schedule instance for the form so the template isn't fouled if validation fails
        form = SchedulePropertiesForm(meeting, instance=Schedule.objects.get(pk=schedule.pk), data=request.POST)
        if form.is_valid():
            form.save()
            if request.GET.get('next'):
                return HttpResponseRedirect(request.GET.get('next'))
            return redirect('ietf.meeting.views.edit_meeting_schedule', num=num, owner=owner, name=form.instance.name)
    else:
        form = SchedulePropertiesForm(meeting, instance=schedule)

    return render(request, "meeting/properties_edit.html", {
        "schedule": schedule,
        "form": form,
        "meeting": meeting,
    })


nat_sort_re = re.compile('([0-9]+)')
def natural_sort_key(s): # from https://stackoverflow.com/questions/4836710/is-there-a-built-in-function-for-string-natural-sort
    return [int(text) if text.isdecimal() else text.lower() for text in nat_sort_re.split(s)]

@role_required('Area Director','Secretariat')
def list_schedules(request, num):
    meeting = get_meeting(num)

    schedules = Schedule.objects.filter(
        meeting=meeting
    ).prefetch_related('owner', 'assignments', 'origin', 'origin__assignments', 'base').order_by('owner', '-name', '-public').distinct()
    if not has_role(request.user, 'Secretariat'):
        schedules = schedules.filter(Q(visible=True) | Q(owner=request.user.person))

    official_schedules = []
    own_schedules = []
    other_public_schedules = []
    other_private_schedules = []

    is_secretariat = has_role(request.user, 'Secretariat')

    for s in schedules:
        s.can_edit_properties = is_secretariat or user_is_person(request.user, s.owner)

        if s.origin:
            s.changes_from_origin = len(diff_meeting_schedules(s.origin, s))

        if s in [meeting.schedule, meeting.schedule.base if meeting.schedule else None]:
            official_schedules.append(s)
        elif user_is_person(request.user, s.owner):
            own_schedules.append(s)
        elif s.public:
            other_public_schedules.append(s)
        else:
            other_private_schedules.append(s)

    schedule_groups = [
        (official_schedules, False, "Official Agenda"),
        (own_schedules, True, "Own Draft Agendas"),
        (other_public_schedules, False, "Other Draft Agendas"),
        (other_private_schedules, False, "Other Private Draft Agendas"),
    ]

    schedule_groups = [(sorted(l, reverse=True, key=lambda s: natural_sort_key(s.name)), own, *t) for l, own, *t in schedule_groups if l or own]

    return render(request, "meeting/schedule_list.html", {
        'meeting': meeting,
        'schedule_groups': schedule_groups,
        'can_edit_timeslots': is_secretariat,
    })

class DiffSchedulesForm(forms.Form):
    from_schedule = forms.ChoiceField()
    to_schedule = forms.ChoiceField()

    def __init__(self, meeting, user, *args, **kwargs):
        super().__init__(*args, **kwargs)

        qs = Schedule.objects.filter(meeting=meeting).prefetch_related('owner').order_by('-public').distinct()

        if not has_role(user, 'Secretariat'):
            qs = qs.filter(Q(visible=True) | Q(owner__user=user))

        sorted_schedules = sorted(qs, reverse=True, key=lambda s: natural_sort_key(s.name))

        schedule_choices = [(schedule.name, "{} ({})".format(schedule.name, schedule.owner)) for schedule in sorted_schedules]

        self.fields['from_schedule'].choices = schedule_choices
        self.fields['to_schedule'].choices = schedule_choices

@role_required('Area Director','Secretariat')
def diff_schedules(request, num):
    meeting = get_meeting(num)

    diffs = None
    from_schedule = None
    to_schedule = None

    if 'from_schedule' in request.GET:
        form = DiffSchedulesForm(meeting, request.user, request.GET)
        if form.is_valid():
            from_schedule = get_object_or_404(Schedule, name=form.cleaned_data['from_schedule'], meeting=meeting)
            to_schedule = get_object_or_404(Schedule, name=form.cleaned_data['to_schedule'], meeting=meeting)
            raw_diffs = diff_meeting_schedules(from_schedule, to_schedule)

            diffs = prefetch_schedule_diff_objects(raw_diffs)
            for d in diffs:
                s = d['session']
                s.session_label = s.short_name
                if s.requested_duration:
                    s.session_label = "{} ({}h)".format(s.session_label, round(s.requested_duration.seconds / 60.0 / 60.0, 1))
    else:
        form = DiffSchedulesForm(meeting, request.user)

    return render(request, "meeting/diff_schedules.html", {
        'meeting': meeting,
        'form': form,
        'diffs': diffs,
        'from_schedule': from_schedule,
        'to_schedule': to_schedule,
    })

@ensure_csrf_cookie
def session_materials(request, session_id):
    """Session details for agenda page pop-up"""
    session = get_object_or_404(Session, id=session_id)
    assignments = SchedTimeSessAssignment.objects.filter(session=session)
    if len(assignments) == 0:
        raise Http404('No such scheduled session')
    assignments = preprocess_assignments_for_agenda(assignments, session.meeting)
    assignment = assignments[0]
    return render(request, 'meeting/session_materials.html', dict(item=assignment))


def get_assignments_for_agenda(schedule):
    """Get queryset containing assignments to show on the agenda"""
    return SchedTimeSessAssignment.objects.filter(
        schedule__in=[schedule, schedule.base],
        session__on_agenda=True,
    )


@ensure_csrf_cookie
def agenda_plain(request, num=None, name=None, base=None, ext=None, owner=None, utc=None):
    base = base if base else 'agenda'
    ext = ext if ext else '.txt'
    mimetype = {
        ".txt": "text/plain; charset=%s"%settings.DEFAULT_CHARSET,
        ".csv": "text/csv; charset=%s"%settings.DEFAULT_CHARSET,
    }
    if ext not in mimetype:
        raise Http404('Extension not allowed')

    # We do not have the appropriate data in the datatracker for IETF 64 and earlier.
    # So that we're not producing misleading pages, redirect to their proceedings.
    # The datatracker DB does include a Meeting instance for every IETF meeting, though,
    # so we can use that to validate that num is a valid meeting number.
    meeting = get_ietf_meeting(num)
    if meeting is None:
        raise Http404("No such full IETF meeting")
    elif int(meeting.number) <= 64:
        return HttpResponseRedirect(f'{settings.PROCEEDINGS_V1_BASE_URL.format(meeting=meeting)}')
    else:
        pass

    # Select the schedule to show
    if name is None:
        schedule = get_schedule(meeting, name)
    else:
        person   = get_person_by_email(owner)
        schedule = get_schedule_by_name(meeting, person, name)

    if schedule is None:
        base = base.replace("-utc", "")
        return render(request, "meeting/no-"+base+ext, {'meeting':meeting }, content_type=mimetype[ext])

    updated = meeting.updated()

    # Select and prepare sessions that should be included
    filtered_assignments = preprocess_assignments_for_agenda(
        get_assignments_for_agenda(schedule),
        meeting
    )
    AgendaKeywordTagger(assignments=filtered_assignments).apply()

    # Done processing for CSV output
    if ext == ".csv":
        return agenda_csv(schedule, filtered_assignments, utc=utc is not None)

    filter_organizer = AgendaFilterOrganizer(assignments=filtered_assignments)

    is_current_meeting = (num is None) or (num == get_current_ietf_meeting_num())

    display_timezone = meeting.time_zone if utc is None else 'UTC'
    with timezone.override(display_timezone):
        rendered_page = render(
            request,
            "meeting/" + base + ext,
            {
                "personalize": False,
                "schedule": schedule,
                "filtered_assignments": filtered_assignments,
                "updated": updated,
                "filter_categories": filter_organizer.get_filter_categories(),
                "non_area_keywords": filter_organizer.get_non_area_keywords(),
                "now": timezone.now().astimezone(meeting.tz()),
                "display_timezone": display_timezone,
                "is_current_meeting": is_current_meeting,
                "cache_time": 150 if is_current_meeting else 3600,
            },
            content_type=mimetype[ext],
        )

    return rendered_page

@ensure_csrf_cookie
def agenda(request, num=None, name=None, base=None, ext=None, owner=None, utc=""):
    # Get current meeting if not specified
    if num is None:
        num = get_current_ietf_meeting_num()

    # We do not have the appropriate data in the datatracker for IETF 64 and earlier.
    # So that we're not producing misleading pages, redirect to their proceedings.
    # The datatracker DB does include a Meeting instance for every IETF meeting, though,
    # so we can use that to validate that num is a valid meeting number.
    if int(num) <= 64:
        meeting = get_ietf_meeting(num)
        if meeting is None:
            raise Http404("No such full IETF meeting")
        else:
            return HttpResponseRedirect(f'{settings.PROCEEDINGS_V1_BASE_URL.format(meeting=meeting)}')

    return render(request, "meeting/agenda.html", {
        "meetingData": {
            "meetingNumber": num
        }
    })

@cache_page(5 * 60)
def api_get_agenda_data (request, num=None):
    meeting = get_ietf_meeting(num)
    if meeting is None:
        raise Http404("No such full IETF meeting")
    elif int(meeting.number) <= 64:
        return Http404("Pre-IETF 64 meetings are not available through this API")
    else:
        pass

    # Select the schedule to show
    schedule = get_schedule(meeting, None)

    updated = meeting.updated()

    # Select and prepare sessions that should be included
    filtered_assignments = preprocess_assignments_for_agenda(
        get_assignments_for_agenda(schedule),
        meeting
    )
    AgendaKeywordTagger(assignments=filtered_assignments).apply()

    filter_organizer = AgendaFilterOrganizer(assignments=filtered_assignments)

    is_current_meeting = (num is None) or (num == get_current_ietf_meeting_num())

    # Get Floor Plans
    floors = FloorPlan.objects.filter(meeting=meeting).order_by('order')

    #debug.show('all([(item.acronym,item.session.order_number,item.session.order_in_meeting()) for item in filtered_assignments])')

    return JsonResponse({
        "meeting": {
            "number": schedule.meeting.number,
            "city": schedule.meeting.city,
            "startDate": schedule.meeting.date.isoformat(),
            "endDate": schedule.meeting.end_date().isoformat(),
            "updated": updated,
            "timezone": meeting.time_zone,
            "infoNote": schedule.meeting.agenda_info_note,
            "warningNote": schedule.meeting.agenda_warning_note
        },
        "categories": filter_organizer.get_filter_categories(),
        "isCurrentMeeting": is_current_meeting,
        "usesNotes": meeting.uses_notes(),
        "schedule": list(map(agenda_extract_schedule, filtered_assignments)),
        "floors": list(map(agenda_extract_floorplan, floors))
    })


def api_get_session_materials(request, session_id=None):
    session = get_object_or_404(Session, pk=session_id)

    minutes = session.minutes()
    slides_actions = []
    if can_manage_session_materials(request.user, session.group, session) or not session.is_material_submission_cutoff():
        slides_actions.append(
            {
                "label": "Upload slides",
                "url": reverse(
                    "ietf.meeting.views.upload_session_slides",
                    kwargs={"num": session.meeting.number, "session_id": session.pk},
                ),
            }
        )
    else:
        pass  # no action available if it's past cutoff

    agenda = session.agenda()
    agenda_url = agenda.get_href() if agenda is not None else None
    return JsonResponse(
        {
            "url": agenda_url,
            "slides": {
                "decks": [
                    agenda_extract_slide(slide) | {"order": order}  # add "order" field
                    for order, slide in enumerate(session.slides())
                ],
                "actions": slides_actions,
            },
            "minutes": {
                "id": minutes.id,
                "title": minutes.title,
                "url": minutes.get_href(),
                "ext": minutes.file_extension(),
            }
            if minutes is not None
            else None,
        }
    )


def agenda_extract_schedule (item):
    return {
        "id": item.id,
        "sessionId": item.session.id,
        "room": item.room_name if item.timeslot.show_location else None,
        "location": {
            "short": item.timeslot.location.floorplan.short,
            "name": item.timeslot.location.floorplan.name,
        } if (item.timeslot.show_location and item.timeslot.location and item.timeslot.location.floorplan) else {},
        "acronym": item.acronym,
        "duration": item.timeslot.duration.seconds,
        "name": item.session.name,
        "slotName": item.timeslot.name,
        "startDateTime": item.timeslot.time.isoformat(),
        "status": item.session.current_status,
        "type": item.session.type.slug,
        "purpose": item.session.purpose.slug,
        "isBoF": item.session.group_at_the_time().state_id == "bof",
        "filterKeywords": item.filter_keywords,
        "groupAcronym": item.session.group_at_the_time().acronym,
        "groupName": item.session.group_at_the_time().name,
        "groupParent": ({
            "acronym": item.session.group_parent_at_the_time().acronym
        } if item.session.group_parent_at_the_time() else {}),
        "note": item.session.agenda_note,
        "remoteInstructions": item.session.remote_instructions,
        "flags": {
            "agenda": True if item.session.agenda() is not None else False,
            "showAgenda": True if (item.session.agenda() is not None or item.session.remote_instructions) else False
        },
        "agenda": {
            "url": item.session.agenda().get_href()
        } if item.session.agenda() is not None else {
            "url": None
        },
        "orderInMeeting": item.session.order_number,
        "short": item.session.short if item.session.short else item.session.short_name,
        "sessionToken": item.session.docname_token_only_for_multiple(),
        "links": {
            "chat" : item.session.chat_room_url(),
            "chatArchive" : item.session.chat_archive_url(),
            "recordings": list(map(agenda_extract_recording, item.session.recordings())),
            "videoStream": item.session.video_stream_url() or "",
            "audioStream": item.session.audio_stream_url() or "",
            "webex": item.timeslot.location.webex_url() if item.timeslot.location else "",
            "onsiteTool": item.session.onsite_tool_url() or "",
            "calendar": reverse(
                'ietf.meeting.views.agenda_ical',
                kwargs={'num': item.schedule.meeting.number, 'session_id': item.session.id},
            ),
        }
        # "slotType": {
        #     "slug": item.slot_type.slug
        # }
    }


def agenda_extract_floorplan(item):
    try:
        item.image.width
    except FileNotFoundError:
        return {}

    return {
        "id": item.id,
        "image": item.image.url,
        "name": item.name,
        "short": item.short,
        "width": item.image.width,
        "height": item.image.height,
        "rooms": list(map(agenda_extract_room, item.room_set.all())),
    }


def agenda_extract_room(item):
    return {
        "id": item.id,
        "name": item.name,
        "functionalName": item.functional_name,
        "slug": xslugify(item.name),
        "left": item.left(),
        "right": item.right(),
        "top": item.top(),
        "bottom": item.bottom()
    }


def agenda_extract_recording(item):
    return {
        "id": item.id,
        "name": item.name,
        "title": item.title,
        "url": item.external_url
    }


def agenda_extract_slide(item):
    return {
        "id": item.id,
        "title": item.title,
        "rev": item.rev,
        "url": item.get_href(),
        "ext": item.file_extension(),
    }


def agenda_csv(schedule, filtered_assignments, utc=False):
    encoding = 'utf-8'
    response = HttpResponse(content_type=f"text/csv; charset={encoding}")
    writer = csv.writer(response, delimiter=str(','), quoting=csv.QUOTE_ALL)

    headings = ["Date", "Start", "End", "Session", "Room", "Area", "Acronym", "Type", "Description", "Session ID", "Agenda", "Slides"]

    def write_row(row):
        if len(row) < len(headings):
            padding = [None] * (len(headings) - len(row))  # produce empty entries at the end as necessary
        else:
            padding = []
        writer.writerow(row + padding)

    def agenda_field(item):
        agenda_doc = item.session.agenda()
        if agenda_doc:
            return "http://www.ietf.org/proceedings/{schedule.meeting.number}/agenda/{agenda.uploaded_filename}".format(schedule=schedule, agenda=agenda_doc)
        else:
            return ""

    def slides_field(item):
        return "|".join("http://www.ietf.org/proceedings/{schedule.meeting.number}/slides/{slide.uploaded_filename}".format(schedule=schedule, slide=slide) for slide in item.session.slides())

    write_row(headings)

    tz = datetime.timezone.utc if utc else schedule.meeting.tz()
    for item in filtered_assignments:
        row = []
        row.append(item.timeslot.time.astimezone(tz).strftime("%Y-%m-%d"))
        row.append(item.timeslot.time.astimezone(tz).strftime("%H%M"))
        row.append(item.timeslot.end_time().astimezone(tz).strftime("%H%M"))

        if item.slot_type().slug == "break":
            row.append(item.slot_type().name)
            row.append(schedule.meeting.break_area)
            row.append("")
            row.append("")
            row.append("")
            row.append(item.timeslot.name)
            row.append("b{}".format(item.timeslot.pk))
        elif item.slot_type().slug == "reg":
            row.append(item.slot_type().name)
            row.append(schedule.meeting.reg_area)
            row.append("")
            row.append("")
            row.append("")
            row.append(item.timeslot.name)
            row.append("r{}".format(item.timeslot.pk))
        elif item.slot_type().slug == "other":
            row.append("None")
            row.append(item.timeslot.location.name if item.timeslot.location else "")
            row.append("")
            row.append(item.session.group_at_the_time().acronym)
            row.append(item.session.group_parent_at_the_time().acronym.upper() if item.session.group_parent_at_the_time() else "")
            row.append(item.session.name)
            row.append(item.session.pk)
        elif item.slot_type().slug == "plenary":
            row.append(item.session.name)
            row.append(item.timeslot.location.name if item.timeslot.location else "")
            row.append("")
            row.append(item.session.group_at_the_time().acronym)
            row.append("")
            row.append(item.session.name)
            row.append(item.session.pk)
            row.append(agenda_field(item))
            row.append(slides_field(item))
        elif item.slot_type().slug == 'regular':
            row.append(item.timeslot.name)
            row.append(item.timeslot.location.name if item.timeslot.location else "")
            row.append(item.session.group_parent_at_the_time().acronym.upper() if item.session.group_parent_at_the_time() else "")
            row.append(item.session.group_at_the_time().acronym)
            row.append("BOF" if item.session.group_at_the_time().state_id in ("bof", "bof-conc") else item.session.group_at_the_time().type.name)
            row.append(item.session.group_at_the_time().name)
            row.append(item.session.pk)
            row.append(agenda_field(item))
            row.append(slides_field(item))

        if len(row) > 3:
            write_row(row)

    return response

@role_required('Area Director','Secretariat','IAB')
def agenda_by_type_ics(request,num=None,type=None):
    meeting = get_meeting(num) 
    schedule = get_schedule(meeting)
    assignments = SchedTimeSessAssignment.objects.filter(
        schedule__in=[schedule, schedule.base if schedule else None]
    ).prefetch_related(
        'timeslot', 'timeslot__location', 'session', 'session__group', 'session__group__parent'
    ).order_by('session__type__slug','timeslot__time')
    if type:
        assignments = assignments.filter(session__type__slug=type)
    updated = meeting.updated()
    return render(request,"meeting/agenda.ics",{"schedule":schedule,"updated":updated,"assignments":assignments},content_type="text/calendar")

def session_draft_list(num, acronym):
    try:
        agendas = Document.objects.filter(type="agenda",
                                         session__meeting__number=num,
                                         session__group__acronym=acronym,
                                         states=State.objects.get(type="agenda", slug="active")).distinct()
    except Document.DoesNotExist:
        raise Http404

    drafts = set()
    for agenda in agendas:
        content, _ = read_agenda_file(num, agenda)
        if content:
            drafts.update(re.findall(b'(draft-[-a-z0-9]*)', content))

    result = []
    for draft in drafts:
        draft = force_str(draft)
        try:
            if re.search('-[0-9]{2}$', draft):
                doc_name = draft
            else:
                doc = Document.objects.get(name=draft)
                doc_name = draft + "-" + doc.rev

            if doc_name not in result:
                result.append(doc_name)
        except Document.DoesNotExist:
            pass

    for sp in SessionPresentation.objects.filter(session__meeting__number=num, session__group__acronym=acronym, document__type='draft'):
        doc_name = sp.document.name + "-" + sp.document.rev
        if doc_name not in result:
            result.append(doc_name)

    return sorted(result)

def session_draft_tarfile(request, num, acronym):
    drafts = session_draft_list(num, acronym);

    response = HttpResponse(content_type='application/octet-stream')
    response['Content-Disposition'] = 'attachment; filename=%s-drafts.tgz'%(acronym)
    tarstream = tarfile.open('','w:gz',response)
    mfh, mfn = mkstemp()
    os.close(mfh)
    manifest = io.open(mfn, "w")

    for doc_name in drafts:
        pdf_path = os.path.join(settings.INTERNET_DRAFT_PDF_PATH, doc_name + ".pdf")

        if not os.path.exists(pdf_path):
            convert_draft_to_pdf(doc_name)

        if os.path.exists(pdf_path):
            try:
                tarstream.add(pdf_path, str(doc_name + ".pdf"))
                manifest.write("Included:  "+pdf_path+"\n")
            except Exception as e:
                manifest.write(("Failed (%s): "%e)+pdf_path+"\n")
        else:
            manifest.write("Not found: "+pdf_path+"\n")

    manifest.close()
    tarstream.add(mfn, "manifest.txt")
    tarstream.close()
    os.unlink(mfn)
    return response

def session_draft_pdf(request, num, acronym):
    drafts = session_draft_list(num, acronym);
    curr_page = 1
    pmh, pmn = mkstemp()
    os.close(pmh)
    pdfmarks = io.open(pmn, "w")
    pdf_list = ""

    for draft in drafts:
        pdf_path = os.path.join(settings.INTERNET_DRAFT_PDF_PATH, draft + ".pdf")
        if not os.path.exists(pdf_path):
            convert_draft_to_pdf(draft)

        if os.path.exists(pdf_path):
            pages = pdf_pages(pdf_path)
            pdfmarks.write("[/Page "+str(curr_page)+" /View [/XYZ 0 792 1.0] /Title (" + draft + ") /OUT pdfmark\n")
            pdf_list = pdf_list + " " + pdf_path
            curr_page = curr_page + pages

    pdfmarks.close()
    pdfh, pdfn = mkstemp()
    os.close(pdfh)
    gs = settings.GHOSTSCRIPT_COMMAND
    code, out, err = pipe(gs + " -dBATCH -dNOPAUSE -q -sDEVICE=pdfwrite -sOutputFile=" + pdfn + " " + pdf_list + " " + pmn)
    assertion('code == 0')

    pdf = io.open(pdfn,"rb")
    pdf_contents = pdf.read()
    pdf.close()

    os.unlink(pmn)
    os.unlink(pdfn)
    return HttpResponse(pdf_contents, content_type="application/pdf")

def ical_session_status(assignment):
    if assignment.session.current_status == 'canceled':
        return "CANCELLED"
    elif assignment.session.current_status == 'resched':
        t = "RESCHEDULED"
        if assignment.session.tombstone_for_id is not None:
            other_assignment = SchedTimeSessAssignment.objects.filter(schedule=assignment.schedule_id, session=assignment.session.tombstone_for_id).first()
            if other_assignment:
                t = "RESCHEDULED TO {}-{}".format(
                    other_assignment.timeslot.time.strftime("%A %H:%M").upper(),
                    other_assignment.timeslot.end_time().strftime("%H:%M")
                )
        return t
    else:
        return "CONFIRMED"

def parse_agenda_filter_params(querydict):
    """Parse agenda filter parameters from a request"""
    if len(querydict) == 0:
        return None

    # Parse group filters from GET parameters. Other params are ignored.
    filt_params = {'show': set(), 'hide': set(), 'showtypes': set(), 'hidetypes': set()}

    for key, value in querydict.items():
        if key in filt_params:
            vals = unquote(value).lower().split(',')
            vals = [v.strip() for v in vals]
            filt_params[key] = set([v for v in vals if len(v) > 0])  # remove empty strings

    return filt_params


def should_include_assignment(filter_params, assignment):
    """Decide whether to include an assignment"""
    shown = len(set(filter_params['show']).intersection(assignment.filter_keywords)) > 0
    hidden = len(set(filter_params['hide']).intersection(assignment.filter_keywords)) > 0
    return shown and not hidden

def agenda_ical(request, num=None, acronym=None, session_id=None):
    """Agenda ical view

    If num is None, looks for the next IETF meeting. Otherwise, uses the requested meeting
    regardless of its type.

    By default, all agenda items will be shown. A filter can be specified in
    the querystring. It has the format
    
      ?show=...&hide=...&showtypes=...&hidetypes=...

    where any of the parameters can be omitted. The right-hand side of each
    '=' is a comma separated list, which can be empty. If none of the filter
    parameters are specified, no filtering will be applied, even if the query
    string is not empty.

    The show and hide parameters each take a list of working group (wg) acronyms.    
    The showtypes and hidetypes parameters take a list of session types. 

    Hiding (by wg or type) takes priority over showing.
    """
    if num is None:
        meeting = get_ietf_meeting()
        if meeting is None:
            raise Http404
    else:
        meeting = get_meeting(num, type_in=None)  # get requested meeting, whatever its type
    schedule = get_schedule(meeting)
    updated = meeting.updated()

    if schedule is None and acronym is None and session_id is None:
        raise Http404

    assignments = SchedTimeSessAssignment.objects.filter(
        schedule__in=[schedule, schedule.base],
        session__on_agenda=True,
    )
    assignments = preprocess_assignments_for_agenda(assignments, meeting)
    AgendaKeywordTagger(assignments=assignments).apply()

    try:
        filt_params = parse_agenda_filter_params(request.GET)
    except ValueError as e:
        return HttpResponseBadRequest(str(e))

    if filt_params is not None:
        # Apply the filter
        assignments = [a for a in assignments if should_include_assignment(filt_params, a)]

    if acronym:
        assignments = [ a for a in assignments if a.session.group_at_the_time().acronym == acronym ]
    elif session_id:
        assignments = [ a for a in assignments if a.session_id == int(session_id) ]

    for a in assignments:
        if a.session:
            a.session.ical_status = ical_session_status(a)

    return render(request, "meeting/agenda.ics", {
        "schedule": schedule,
        "assignments": assignments,
        "updated": updated
    }, content_type="text/calendar")

@cache_page(15 * 60)
def agenda_json(request, num=None):
    if num is None:
        meeting = get_ietf_meeting()
        if meeting is None:
            raise Http404
    else:
        meeting = get_meeting(num, type_in=None)  # get requested meeting, whatever its type

    sessions = []
    locations = set()
    parent_acronyms = set()
    assignments = SchedTimeSessAssignment.objects.filter(
        schedule__in=[meeting.schedule, meeting.schedule.base if meeting.schedule else None],
        session__on_agenda=True,
    ).exclude(
        session__type__in=['break', 'reg']
    )
    # Update the assignments with historic information, i.e., valid at the
    # time of the meeting
    assignments = preprocess_assignments_for_agenda(assignments, meeting, extra_prefetches=[
        "session__materials__docevent_set",
        "session__presentations",
        "timeslot__meeting"
    ])
    for asgn in assignments:
        sessdict = dict()
        sessdict['objtype'] = 'session'
        sessdict['id'] = asgn.pk
        sessdict['is_bof'] = False
        if asgn.session.group_at_the_time():
            sessdict['group'] = {
                    "acronym": asgn.session.group_at_the_time().acronym,
                    "name": asgn.session.group_at_the_time().name,
                    "type": asgn.session.group_at_the_time().type_id,
                    "state": asgn.session.group_at_the_time().state_id,
                }
            if asgn.session.group_at_the_time().is_bof():
                sessdict['is_bof'] = True
            if asgn.session.group_at_the_time().type_id in ['wg','rg', 'ag', 'rag'] or asgn.session.group_at_the_time().acronym in ['iesg',]: # TODO: should that first list be groupfeatures driven?
                if asgn.session.group_parent_at_the_time():
                    sessdict['group']['parent'] = asgn.session.group_parent_at_the_time().acronym
                    parent_acronyms.add(asgn.session.group_parent_at_the_time().acronym)
        if asgn.session.name:
            sessdict['name'] = asgn.session.name
        else:
            sessdict['name'] = asgn.session.group_at_the_time().name
        if asgn.session.short:
            sessdict['short'] = asgn.session.short
        if asgn.session.agenda_note:
            sessdict['agenda_note'] = asgn.session.agenda_note
        if asgn.session.remote_instructions:
            sessdict['remote_instructions'] = asgn.session.remote_instructions
        utc_start = asgn.timeslot.utc_start_time()
        if utc_start:
            sessdict['start'] = utc_start.strftime("%Y-%m-%dT%H:%M:%SZ")
        sessdict['duration'] = str(asgn.timeslot.duration)
        sessdict['location'] = asgn.room_name
        if asgn.timeslot.location:      # Some socials have an assignment but no location
            locations.add(asgn.timeslot.location)
        if asgn.session.agenda():
            sessdict['agenda'] = asgn.session.agenda().get_href()

        if asgn.session.minutes():
            sessdict['minutes'] = asgn.session.minutes().get_href()
        if asgn.session.slides():
            sessdict['presentations'] = []
            presentations = SessionPresentation.objects.filter(session=asgn.session, document__type__slug='slides')
            for pres in presentations:
                sessdict['presentations'].append(
                    {
                        'name':     pres.document.name,
                        'title':    pres.document.title,
                        'order':    pres.order,
                        'rev':      pres.rev,
                        'resource_uri': '/api/v1/meeting/sessionpresentation/%s/'%pres.id,
                    })
        sessdict['session_res_uri'] = '/api/v1/meeting/session/%s/'%asgn.session.id
        sessdict['session_id'] = asgn.session.id
        modified = asgn.session.modified
        for doc in asgn.session.materials.all():
            rev_docevent = doc.latest_event(NewRevisionDocEvent,'new_revision')
            modified = max(modified, (rev_docevent and rev_docevent.time) or modified)
        sessdict['modified'] = modified
        sessdict['status'] = asgn.session.current_status
        sessions.append(sessdict)

    rooms = []
    for room in locations:
        roomdict = dict()
        roomdict['id'] = room.pk
        roomdict['objtype'] = 'location'
        roomdict['name'] = room.name
        if room.floorplan:
            roomdict['level_name'] = room.floorplan.name
            roomdict['level_sort'] = room.floorplan.order
        if room.x1 is not None:
            roomdict['x'] = (room.x1+room.x2)/2.0
            roomdict['y'] = (room.y1+room.y2)/2.0
        roomdict['modified'] = room.modified
        if room.floorplan and room.floorplan.image:
            roomdict['map'] = room.floorplan.image.url
            roomdict['modified'] = max(room.modified, room.floorplan.modified)
        rooms.append(roomdict)

    parents = []
    for parent in Group.objects.filter(acronym__in=parent_acronyms):
        parentdict = dict()
        parentdict['id'] = parent.pk
        parentdict['objtype'] = 'parent'
        parentdict['name'] = parent.acronym
        parentdict['description'] = parent.name
        parentdict['modified'] = parent.time
        parents.append(parentdict)

    meetinfo = []
    meetinfo.extend(sessions)
    meetinfo.extend(rooms)
    meetinfo.extend(parents)
    meetinfo.sort(key=lambda x: x['modified'],reverse=True)
    last_modified = meetinfo and meetinfo[0]['modified']

    for obj in meetinfo:
        obj['modified'] = obj['modified'].astimezone(pytz.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    data = {"%s"%num: meetinfo}

    response = HttpResponse(json.dumps(data, indent=2, sort_keys=True), content_type='application/json;charset=%s'%settings.DEFAULT_CHARSET)
    if last_modified:
        last_modified = last_modified.astimezone(pytz.utc)
        response['Last-Modified'] = format_date_time(timegm(last_modified.timetuple()))
    return response

def request_summary_filter(session):
    if (session.group.area is None
            or session.group.type.slug in request_summary_exclude_group_types
            or session.current_status == 'notmeet'):
        return False
    return True

def get_area_column(area):
    if area is None:
        return ''
    if area.type.slug in ['rfcedtyp']:
        name = 'OTHER'
    else:
        name = area.acronym.upper()
    return name

def get_summary_by_area(sessions):
    """Returns summary by area for list of session requests.
    Summary is a two dimensional array[row=session duration][col=session area count]
    It also includes row and column headers as well as a totals row.
    """

    # first build a dictionary of counts, key=(duration,area)
    durations = set()
    areas = set()
    duration_totals = defaultdict(int)
    data = defaultdict(int)
    for session in sessions:
        area_column = get_area_column(session.group.area)
        duration = session.requested_duration.seconds / 3600
        key = (duration, area_column)
        data[key] = data[key] + 1
        durations.add(duration)
        areas.add(area_column)
        duration_totals[duration] = duration_totals[duration] + 1

    # build two dimensional array for use in template
    rows = []
    sorted_areas = sorted(areas)
    # move "other" to end
    if 'OTHER' in sorted_areas:
        sorted_areas.remove('OTHER')
        sorted_areas.append('OTHER')
    # add header row
    rows.append(['Duration'] + sorted_areas + ['TOTAL SLOTS', 'TOTAL HOURS'])
    for duration in sorted(durations):
        rows.append([duration] + [data[(duration, a)] for a in sorted_areas] + [duration_totals[duration]] + [duration_totals[duration] * duration])
    # add total row
    rows.append(['Total Slots'] + [sum([rows[r][c] for r in range(1, len(rows))]) for c in range(1, len(rows[0]))])
    rows.append(['Total Hours'] + [sum([d * data[(d, area)] for d in durations]) for area in sorted_areas])
    return rows

def get_summary_by_type(sessions):
    counter = Counter([s.group.type.name for s in sessions])
    data = counter.most_common()
    data.insert(0, ('Group Type', 'Count'))
    return data

def get_summary_by_purpose(sessions):
    counter = Counter([s.purpose.name for s in sessions])
    data = counter.most_common()
    data.insert(0, ('Purpose', 'Count'))
    return data

def meeting_requests(request, num=None):
    meeting = get_meeting(num)
    groups_to_show = Group.objects.filter(
        state_id__in=('active', 'bof', 'proposed'),
        type__features__has_meetings=True,
    )
    sessions = list(
        Session.objects.requests().filter(
            meeting__number=meeting.number,
            group__in=groups_to_show,
        ).exclude(
            purpose__in=('admin', 'social'),
        ).with_current_status().with_requested_by().exclude(
            requested_by=0
        ).prefetch_related(
            "group", "group__ad_role__person", "group__type"
        )
    )

    status_names = {n.slug: n.name for n in SessionStatusName.objects.all()}
    session_requesters = {p.pk: p for p in Person.objects.filter(pk__in=[s.requested_by for s in sessions if s.requested_by is not None])}

    for s in sessions:
        s.current_status_name = status_names.get(s.current_status, s.current_status)
        s.requested_by_person = session_requesters.get(s.requested_by)
        if s.group.parent and s.group.parent.type.slug in ('area', 'irtf'):
            s.display_area = s.group.parent
        else:
            s.display_area = None
    sessions.sort(
        key=lambda s: (
            s.display_area.acronym if s.display_area is not None else 'zzzz',
            s.current_status,
            s.group.acronym,
        ),
    )

    groups_not_meeting = groups_to_show.exclude(
        acronym__in=[session.group.acronym for session in sessions]
    ).order_by(
        "parent__acronym",
        "acronym",
    ).prefetch_related("parent")

    summary_sessions = list(filter(request_summary_filter, sessions))

    return render(
        request,
        "meeting/requests.html",
        {
            "meeting": meeting,
            "sessions": sessions,
            "groups_not_meeting": groups_not_meeting,
            "summary_by_area": get_summary_by_area(summary_sessions),
            "summary_by_group_type": get_summary_by_type(summary_sessions),
            "summary_by_purpose": get_summary_by_purpose(summary_sessions),
        },
    )


def get_sessions(num, acronym):
    return sorted(
        get_meeting_sessions(num, acronym).with_current_status(),
        key=lambda s: session_time_for_sorting(s, use_meeting_date=False)
    )


def session_details(request, num, acronym):
    meeting = get_meeting(num=num,type_in=None)
    sessions = get_sessions(num, acronym)

    if not sessions:
        raise Http404

    status_names = {n.slug: n.name for n in SessionStatusName.objects.all()}
    for session in sessions:

        session.type_counter = Counter()
        ss = session.timeslotassignments.filter(schedule__in=[meeting.schedule, meeting.schedule.base if meeting.schedule else None]).order_by('timeslot__time')
        if ss:
            if meeting.type_id == 'interim' and not (meeting.city or meeting.country):
                session.times = [ x.timeslot.utc_start_time() for x in ss ]                
            else:
                session.times = [ x.timeslot.local_start_time() for x in ss ]
            session.cancelled = session.current_status in Session.CANCELED_STATUSES
            session.status = ''
        elif meeting.type_id=='interim':
            session.times = [ meeting.date ]
            session.cancelled = session.current_status in Session.CANCELED_STATUSES
            session.status = ''
        else:
            session.times = []
            session.cancelled = session.current_status in Session.CANCELED_STATUSES
            session.status = status_names.get(session.current_status, session.current_status)

        if session.meeting.type_id == 'ietf' and not session.meeting.proceedings_final:
            artifact_types = ['agenda','minutes','narrativeminutes']
            if Attended.objects.filter(session=session).exists():
                session.type_counter.update(['bluesheets'])
                ota = session.official_timeslotassignment()
                sess_time = ota and ota.timeslot.time
                session.bluesheet_title = 'Attendance IETF%s: %s : %s' % (session.meeting.number, 
                                                                          session.group.acronym, 
                                                                          sess_time.strftime("%a %H:%M"))
        else:
            artifact_types = ['agenda','minutes','narrativeminutes','bluesheets']
        session.filtered_artifacts = list(session.presentations.filter(document__type__slug__in=artifact_types))
        session.filtered_artifacts.sort(key=lambda d:artifact_types.index(d.document.type.slug))
        session.filtered_slides    = session.presentations.filter(document__type__slug='slides').order_by('order')
        session.filtered_drafts    = session.presentations.filter(document__type__slug='draft')
        session.filtered_chatlog_and_polls = session.presentations.filter(document__type__slug__in=('chatlog', 'polls')).order_by('document__type__slug')
        # TODO FIXME Deleted materials shouldn't be in the presentations
        for qs in [session.filtered_artifacts,session.filtered_slides,session.filtered_drafts]:
            qs = [p for p in qs if p.document.get_state_slug(p.document.type_id)!='deleted']
            session.type_counter.update([p.document.type.slug for p in qs])

        session.order_number = session.order_in_meeting()

    # we somewhat arbitrarily use the group of the last session we get from
    # get_sessions() above when checking can_manage_session_materials()
    group = session.group
    can_manage = can_manage_session_materials(request.user, group, session)
    can_view_request = can_view_interim_request(meeting, request.user)

    scheduled_sessions = [s for s in sessions if s.current_status == 'sched']
    unscheduled_sessions = [s for s in sessions if s.current_status != 'sched']

    pending_suggestions = None
    if request.user.is_authenticated:
        if can_manage:
            pending_suggestions = session.slidesubmission_set.filter(status__slug='pending')
        else:
            pending_suggestions = session.slidesubmission_set.filter(status__slug='pending', submitter=request.user.person)

    return render(request, "meeting/session_details.html",
                  { 'scheduled_sessions':scheduled_sessions ,
                    'unscheduled_sessions':unscheduled_sessions , 
                    'pending_suggestions' : pending_suggestions,
                    'meeting' :meeting ,
                    'group': group,
                    'is_materials_manager' : session.group.has_role(request.user, session.group.features.matman_roles),
                    'can_manage_materials' : can_manage,
                    'can_view_request': can_view_request,
                    'thisweek': datetime_today()-datetime.timedelta(days=7),
                  })

class SessionDraftsForm(forms.Form):
    drafts = SearchableDocumentsField(required=False)

    def __init__(self, *args, **kwargs):
        self.already_linked = kwargs.pop('already_linked')
        super(self.__class__, self).__init__(*args, **kwargs)

    def clean(self):
        selected = self.cleaned_data['drafts']
        problems = set(selected).intersection(set(self.already_linked)) 
        if problems:
           raise forms.ValidationError("Already linked: %s" % ', '.join([d.name for d in problems]))
        return self.cleaned_data

def add_session_drafts(request, session_id, num):
    # num is redundant, but we're dragging it along an artifact of where we are in the current URL structure
    session = get_object_or_404(Session,pk=session_id)
    if not session.can_manage_materials(request.user):
        raise Http404
    if session.is_material_submission_cutoff() and not has_role(request.user, "Secretariat"):
        raise Http404

    already_linked = [sp.document for sp in session.presentations.filter(document__type_id='draft')]

    session_number = None
    sessions = get_sessions(session.meeting.number,session.group.acronym)
    if len(sessions) > 1:
       session_number = 1 + sessions.index(session)

    if request.method == 'POST':
        form = SessionDraftsForm(request.POST,already_linked=already_linked)
        if form.is_valid():
            for draft in form.cleaned_data['drafts']:
                session.presentations.create(document=draft,rev=None)
                c = DocEvent(type="added_comment", doc=draft, rev=draft.rev, by=request.user.person)
                c.desc = "Added to session: %s" % session
                c.save()
            return redirect('ietf.meeting.views.session_details', num=session.meeting.number, acronym=session.group.acronym)
    else:
        form = SessionDraftsForm(already_linked=already_linked)

    return render(request, "meeting/add_session_drafts.html",
                  { 'session': session,
                    'session_number': session_number,
                    'already_linked': session.presentations.filter(document__type_id='draft'),
                    'form': form,
                  })


def session_attendance(request, session_id, num):
    """Session attendance view

    GET - retrieve the current session attendance or redirect to the published bluesheet if finalized

    POST - self-attest attendance for logged-in user; falls through to GET for AnonymousUser or invalid request
    """
    # num is redundant, but we're dragging it along as an artifact of where we are in the current URL structure
    session = get_object_or_404(Session, pk=session_id)
    if session.meeting.type_id != "ietf" or session.meeting.proceedings_final:
        bluesheets = session.presentations.filter(
            document__type_id="bluesheets"
        )
        if bluesheets:
            bluesheet = bluesheets[0].document
            return redirect(bluesheet.get_href(session.meeting))
        else:
            raise Http404("Bluesheets not found")

    cor_cut_off_date = session.meeting.get_submission_correction_date()
    today_utc = date_today(datetime.timezone.utc)
    was_there = False
    can_add = False
    if request.user.is_authenticated:
        # use getattr() instead of request.user.person because it's a reverse OneToOne field
        person = getattr(request.user, "person", None)
        # Consider allowing self-declared attendance if we have a person and at least one Attended instance exists.
        # The latter condition will be satisfied when Meetecho pushes their attendee records - assuming that at least
        # one person will have accessed the meeting tool. This prevents people from self-declaring before they are
        # marked as attending if they did log in to the meeting tool (except for a tiny window while records are
        # being processed).
        if person is not None and Attended.objects.filter(session=session).exists():
            was_there = Attended.objects.filter(session=session, person=person).exists()
            can_add = (
                today_utc <= cor_cut_off_date
                and MeetingRegistration.objects.filter(
                    meeting=session.meeting, person=person
                ).exists()
                and not was_there
            )
            if can_add and request.method == "POST":
                session.attended_set.get_or_create(
                    person=person, defaults={"origin": "self declared"}
                )
                can_add = False
                was_there = True

    data = bluesheet_data(session)
    return render(
        request,
        "meeting/attendance.html",
        {
            "session": session,
            "data": data,
            "can_add": can_add,
            "was_there": was_there,
        },
    )


def upload_session_bluesheets(request, session_id, num):
    # num is redundant, but we're dragging it along an artifact of where we are in the current URL structure
    session = get_object_or_404(Session,pk=session_id)

    if not session.can_manage_materials(request.user):
        permission_denied(request, "You don't have permission to upload bluesheets for this session.")
    if session.is_material_submission_cutoff() and not has_role(request.user, "Secretariat"):
        permission_denied(request, "The materials cutoff for this session has passed. Contact the secretariat for further action.")

    if session.meeting.type.slug == 'ietf' and not has_role(request.user, 'Secretariat'):
        permission_denied(request, 'Restricted to role Secretariat')
        
    session_number = None
    sessions = get_sessions(session.meeting.number,session.group.acronym)
    if len(sessions) > 1:
       session_number = 1 + sessions.index(session)

    if request.method == 'POST':
        form = UploadBlueSheetForm(request.POST,request.FILES)
        if form.is_valid():
            file = request.FILES['file']

            ota = session.official_timeslotassignment()
            sess_time = ota and ota.timeslot.time
            if not sess_time:
                return HttpResponseGone("Cannot receive uploads for an unscheduled session.  Please check the session ID.", content_type="text/plain")


            save_error = save_bluesheet(request, session, file, encoding=form.file_encoding[file.name])
            if save_error:
                form.add_error(None, save_error)
            else:
                messages.success(request, 'Successfully uploaded bluesheets.')
                return redirect('ietf.meeting.views.session_details',num=num,acronym=session.group.acronym)
    else: 
        form = UploadBlueSheetForm()

    bluesheet_sp = session.presentations.filter(document__type='bluesheets').first()

    return render(request, "meeting/upload_session_bluesheets.html", 
                  {'session': session,
                   'session_number': session_number,
                   'bluesheet_sp' : bluesheet_sp,
                   'form': form,
                  })


def upload_session_minutes(request, session_id, num):
    # num is redundant, but we're dragging it along an artifact of where we are in the current URL structure
    session = get_object_or_404(Session,pk=session_id)

    if not session.can_manage_materials(request.user):
        permission_denied(request, "You don't have permission to upload minutes for this session.")
    if session.is_material_submission_cutoff() and not has_role(request.user, "Secretariat"):
        permission_denied(request, "The materials cutoff for this session has passed. Contact the secretariat for further action.")

    session_number = None
    sessions = get_sessions(session.meeting.number,session.group.acronym)
    show_apply_to_all_checkbox = len(sessions) > 1 if session.type_id == 'regular' else False
    if len(sessions) > 1:
       session_number = 1 + sessions.index(session)

    minutes_sp = session.presentations.filter(document__type='minutes').first()
    
    if request.method == 'POST':
        form = UploadMinutesForm(show_apply_to_all_checkbox,request.POST,request.FILES)
        if form.is_valid():
            file = request.FILES['file']
            _, ext = os.path.splitext(file.name)
            apply_to_all = session.type_id == 'regular'
            if show_apply_to_all_checkbox:
                apply_to_all = form.cleaned_data['apply_to_all']

            # Set up the new revision
            try:
                save_session_minutes_revision(
                    session=session,
                    apply_to_all=apply_to_all,
                    file=file,
                    ext=ext,
                    encoding=form.file_encoding[file.name],
                    request=request,
                )
            except SessionNotScheduledError:
                return HttpResponseGone(
                    "Cannot receive uploads for an unscheduled session. Please check the session ID.",
                    content_type="text/plain",
                )
            except SaveMaterialsError as err:
                form.add_error(None, str(err))
            else:
                # no exception -- success!
                messages.success(request, f'Successfully uploaded minutes as revision {session.minutes().rev}.')
                return redirect('ietf.meeting.views.session_details', num=num, acronym=session.group.acronym)
    else:
        form = UploadMinutesForm(show_apply_to_all_checkbox)

    return render(request, "meeting/upload_session_minutes.html", 
                  {'session': session,
                   'session_number': session_number,
                   'minutes_sp' : minutes_sp,
                   'form': form,
                  })

@role_required("Secretariat")
def upload_session_narrativeminutes(request, session_id, num):
    # num is redundant, but we're dragging it along an artifact of where we are in the current URL structure
    session = get_object_or_404(Session,pk=session_id)
    if session.group.acronym != "iesg":
        raise Http404()
    
    session_number = None
    sessions = get_sessions(session.meeting.number,session.group.acronym)
    show_apply_to_all_checkbox = len(sessions) > 1 if session.type_id == 'regular' else False
    if len(sessions) > 1:
       session_number = 1 + sessions.index(session)

    narrativeminutes_sp = session.presentations.filter(document__type='narrativeminutes').first()
    
    if request.method == 'POST':
        form = UploadNarrativeMinutesForm(show_apply_to_all_checkbox,request.POST,request.FILES)
        if form.is_valid():
            file = request.FILES['file']
            _, ext = os.path.splitext(file.name)
            apply_to_all = session.type_id == 'regular'
            if show_apply_to_all_checkbox:
                apply_to_all = form.cleaned_data['apply_to_all']

            # Set up the new revision
            try:
                save_session_minutes_revision(
                    session=session,
                    apply_to_all=apply_to_all,
                    file=file,
                    ext=ext,
                    encoding=form.file_encoding[file.name],
                    request=request,
                    narrative=True
                )
            except SessionNotScheduledError:
                return HttpResponseGone(
                    "Cannot receive uploads for an unscheduled session. Please check the session ID.",
                    content_type="text/plain",
                )
            except SaveMaterialsError as err:
                form.add_error(None, str(err))
            else:
                # no exception -- success!
                messages.success(request, f'Successfully uploaded narrative minutes as revision {session.narrative_minutes().rev}.')
                return redirect('ietf.meeting.views.session_details', num=num, acronym=session.group.acronym)
    else:
        form = UploadMinutesForm(show_apply_to_all_checkbox)

    return render(request, "meeting/upload_session_narrativeminutes.html", 
                  {'session': session,
                   'session_number': session_number,
                   'minutes_sp' : narrativeminutes_sp,
                   'form': form,
                  })

class UploadOrEnterAgendaForm(UploadAgendaForm):
    ACTIONS = [
        ("upload", "Upload agenda"),
        ("enter", "Enter agenda"),
    ]
    submission_method = forms.ChoiceField(choices=ACTIONS, widget=forms.RadioSelect)

    content = forms.CharField(widget=forms.Textarea, required=False, strip=False, label="Agenda text")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["file"].required=False
        self.order_fields(["submission_method", "file", "content"])

    def clean_content(self):
        return self.cleaned_data["content"].replace("\r", "")

    def clean_file(self):
        submission_method = self.cleaned_data.get("submission_method")
        if submission_method == "upload":
            if self.cleaned_data.get("file", None) is not None:
                return super().clean_file()
        return None

    def clean(self):
        def require_field(f):
            if not self.cleaned_data.get(f):
                self.add_error(f, ValidationError("You must fill in this field."))

        submission_method = self.cleaned_data.get("submission_method")
        if submission_method == "upload":
            require_field("file")
        elif submission_method == "enter":
            require_field("content")

    def get_file(self):
        """Get content as a file-like object"""
        if self.cleaned_data.get("submission_method") == "upload":
            return self.cleaned_data["file"]
        else:
            return SimpleUploadedFile(
                name="uploaded.md",
                content=self.cleaned_data["content"].encode("utf-8"),
                content_type="text/markdown;charset=utf-8",
            )

def upload_session_agenda(request, session_id, num):
    # num is redundant, but we're dragging it along an artifact of where we are in the current URL structure
    session = get_object_or_404(Session,pk=session_id)

    if not session.can_manage_materials(request.user):
        permission_denied(request, "You don't have permission to upload an agenda for this session.")
    if session.is_material_submission_cutoff() and not has_role(request.user, "Secretariat"):
        permission_denied(request, "The materials cutoff for this session has passed. Contact the secretariat for further action.")

    session_number = None
    sessions = get_sessions(session.meeting.number,session.group.acronym)
    show_apply_to_all_checkbox = len(sessions) > 1 if session.type.slug == 'regular' else False
    if len(sessions) > 1:
       session_number = 1 + sessions.index(session)

    agenda_sp = session.presentations.filter(document__type='agenda').first()
    
    if request.method == 'POST':
        form = UploadOrEnterAgendaForm(show_apply_to_all_checkbox,request.POST,request.FILES)
        if form.is_valid():
            file = form.get_file()
            _, ext = os.path.splitext(file.name)
            apply_to_all = session.type.slug == 'regular'
            if show_apply_to_all_checkbox:
                apply_to_all = form.cleaned_data['apply_to_all']
            if agenda_sp:
                doc = agenda_sp.document
                doc.rev = '%02d' % (int(doc.rev)+1)
                agenda_sp.rev = doc.rev
                agenda_sp.save()
            else:
                ota = session.official_timeslotassignment()
                sess_time = ota and ota.timeslot.time
                if not sess_time:
                    return HttpResponseGone("Cannot receive uploads for an unscheduled session.  Please check the session ID.", content_type="text/plain")
                if session.meeting.type_id=='ietf':
                    name = 'agenda-%s-%s' % (session.meeting.number, 
                                                 session.group.acronym) 
                    title = 'Agenda IETF%s: %s' % (session.meeting.number, 
                                                         session.group.acronym) 
                    if not apply_to_all:
                        name += '-%s' % (session.docname_token(),)
                        if sess_time:
                            title += ': %s' % (sess_time.strftime("%a %H:%M"),)
                else:
                    name = 'agenda-%s-%s' % (session.meeting.number, session.docname_token())
                    title = 'Agenda %s' % (session.meeting.number, )
                    if sess_time:
                        title += ': %s' % (sess_time.strftime("%a %H:%M"),)
                if Document.objects.filter(name=name).exists():
                    doc = Document.objects.get(name=name)
                    doc.rev = '%02d' % (int(doc.rev)+1)
                else:
                    doc = Document.objects.create(
                              name = name,
                              type_id = 'agenda',
                              title = title,
                              group = session.group,
                              rev = '00',
                          )
                doc.states.add(State.objects.get(type_id='agenda',slug='active'))
            if session.presentations.filter(document=doc).exists():
                sp = session.presentations.get(document=doc)
                sp.rev = doc.rev
                sp.save()
            else:
                session.presentations.create(document=doc,rev=doc.rev)
            if apply_to_all:
                for other_session in sessions:
                    if other_session != session:
                        other_session.presentations.filter(document__type='agenda').delete()
                        other_session.presentations.create(document=doc,rev=doc.rev)
            filename = '%s-%s%s'% ( doc.name, doc.rev, ext)
            doc.uploaded_filename = filename
            e = NewRevisionDocEvent.objects.create(doc=doc,by=request.user.person,type='new_revision',desc='New revision available: %s'%doc.rev,rev=doc.rev)
            # The way this function builds the filename it will never trigger the file delete in handle_file_upload.
            try:
                encoding=form.file_encoding[file.name]
            except AttributeError:
                encoding=None
            save_error = handle_upload_file(file, filename, session.meeting, 'agenda', request=request, encoding=encoding)
            if save_error:
                form.add_error(None, save_error)
            else:
                doc.save_with_history([e])
                messages.success(request, f'Successfully uploaded agenda as revision {doc.rev}.')
                return redirect('ietf.meeting.views.session_details',num=num,acronym=session.group.acronym)
    else: 
        initial={'apply_to_all':session.type_id=='regular', 'submission_method':'upload'}
        if agenda_sp:
            doc = agenda_sp.document
            initial['content'] = doc.text()
        form = UploadOrEnterAgendaForm(show_apply_to_all_checkbox, initial=initial)

    return render(request, "meeting/upload_session_agenda.html", 
                  {'session': session,
                   'session_number': session_number,
                   'agenda_sp' : agenda_sp,
                   'form': form,
                  })


@login_required
def upload_session_slides(request, session_id, num, name=None):
    """Upload new or replacement slides for a session
    
    If name is None or "", expects a new set of slides. Otherwise, replaces the named slides with a new rev.
    """
    # num is redundant, but we're dragging it along an artifact of where we are in the current URL structure
    session = get_object_or_404(Session, pk=session_id)
    can_manage = session.can_manage_materials(request.user)
    if session.is_material_submission_cutoff() and not has_role(
        request.user, "Secretariat"
    ):
        permission_denied(
            request,
            "The materials cutoff for this session has passed. Contact the secretariat for further action.",
        )

    session_number = None
    sessions = get_sessions(session.meeting.number, session.group.acronym)
    show_apply_to_all_checkbox = (
        len(sessions) > 1 if session.type_id == "regular" else False
    )
    if len(sessions) > 1:
        session_number = 1 + sessions.index(session)

    doc = None
    if name:
        doc = get_object_or_404(
            session.presentations, document__name=name, document__type_id="slides"
        ).document

    if request.method == "POST":
        form = UploadSlidesForm(
            session, show_apply_to_all_checkbox, can_manage, request.POST, request.FILES
        )
        if form.is_valid():
            file = request.FILES["file"]
            _, ext = os.path.splitext(file.name)
            apply_to_all = session.type_id == "regular"
            if show_apply_to_all_checkbox:
                apply_to_all = form.cleaned_data["apply_to_all"]
            if can_manage:
                approved = form.cleaned_data["approved"]
            else:
                approved = False

            # Propose slides if not auto-approved
            if not approved:
                title = form.cleaned_data['title']
                submission = SlideSubmission.objects.create(session = session, title = title, filename = '', apply_to_all = apply_to_all, submitter=request.user.person)

                if session.meeting.type_id=='ietf':
                    name = 'slides-%s-%s' % (session.meeting.number, 
                                         session.group.acronym) 
                    if not apply_to_all:
                        name += '-%s' % (session.docname_token(),)
                else:
                    name = 'slides-%s-%s' % (session.meeting.number, session.docname_token())
                name = name + '-' + slugify(title).replace('_', '-')[:128]
                filename = '%s-ss%d%s'% (name, submission.id, ext)
                destination = io.open(os.path.join(settings.SLIDE_STAGING_PATH, filename),'wb+')
                for chunk in file.chunks():
                    destination.write(chunk)
                destination.close()

                submission.filename = filename
                submission.save()

                (to, cc) = gather_address_lists('slides_proposed', group=session.group, proposer=request.user.person).as_strings()
                msg_txt = render_to_string("meeting/slides_proposed.txt", {
                        "to": to,
                        "cc": cc,
                        "submission": submission,
                        "settings": settings,
                     })
                msg = infer_message(msg_txt)
                msg.by = request.user.person
                msg.save()
                send_mail_message(request, msg)
                messages.success(request, 'Successfully submitted proposed slides.')
                return redirect('ietf.meeting.views.session_details',num=num,acronym=session.group.acronym)

            # Handle creation / update of the Document (but do not save yet)
            if doc is not None:
                # This is a revision - bump the version and update the title.
                doc.rev = "%02d" % (int(doc.rev) + 1)
                doc.title = form.cleaned_data["title"]
            else:
                # This is a new slide deck - create a new doc unless one exists with that name
                title = form.cleaned_data["title"]
                if session.meeting.type_id == "ietf":
                    name = "slides-%s-%s" % (
                        session.meeting.number,
                        session.group.acronym,
                    )
                    if not apply_to_all:
                        name += "-%s" % (session.docname_token(),)
                else:
                    name = "slides-%s-%s" % (
                        session.meeting.number,
                        session.docname_token(),
                    )
                name = name + "-" + slugify(title).replace("_", "-")[:128]
                if Document.objects.filter(name=name).exists():
                    doc = Document.objects.get(name=name)
                    doc.rev = "%02d" % (int(doc.rev) + 1)
                    doc.title = form.cleaned_data["title"]
                else:
                    doc = Document.objects.create(
                        name=name,
                        type_id="slides",
                        title=title,
                        group=session.group,
                        rev="00",
                    )
                doc.states.add(State.objects.get(type_id="slides", slug="active"))
                doc.states.add(State.objects.get(type_id="reuse_policy", slug="single"))

            # Now handle creation / update of the SessionPresentation(s)
            sessions_to_apply = sessions if apply_to_all else [session]
            added_presentations = []
            revised_presentations = []
            for sess in sessions_to_apply:
                sp = sess.presentations.filter(document=doc).first()
                if sp is not None:
                    sp.rev = doc.rev
                    sp.save()
                    revised_presentations.append(sp)
                else:
                    max_order = (
                        sess.presentations.filter(document__type="slides").aggregate(
                            Max("order")
                        )["order__max"]
                        or 0
                    )
                    sp = sess.presentations.create(
                        document=doc, rev=doc.rev, order=max_order + 1
                    )
                    added_presentations.append(sp)

            # Now handle the uploaded file
            filename = "%s-%s%s" % (doc.name, doc.rev, ext)
            doc.uploaded_filename = filename
            e = NewRevisionDocEvent.objects.create(
                doc=doc,
                by=request.user.person,
                type="new_revision",
                desc="New revision available: %s" % doc.rev,
                rev=doc.rev,
            )
            # The way this function builds the filename it will never trigger the file delete in handle_file_upload.
            save_error = handle_upload_file(
                file,
                filename,
                session.meeting,
                "slides",
                request=request,
                encoding=form.file_encoding[file.name],
            )
            if save_error:
                form.add_error(None, save_error)
            else:
                doc.save_with_history([e])
                post_process(doc)

            # Send MeetEcho updates even if we had a problem saving - that will keep it in sync with the
            # SessionPresentation, which was already saved regardless of problems saving the file.
            if hasattr(settings, "MEETECHO_API_CONFIG"):
                sm = SlidesManager(api_config=settings.MEETECHO_API_CONFIG)
                for sp in added_presentations:
                    try:
                        sm.add(session=sp.session, slides=doc, order=sp.order)
                    except MeetechoAPIError as err:
                        log(f"Error in SlidesManager.add(): {err}")
                for sp in revised_presentations:
                    try:
                        sm.revise(session=sp.session, slides=doc)
                    except MeetechoAPIError as err:
                        log(f"Error in SlidesManager.revise(): {err}")

            if not save_error:
                messages.success(
                    request,
                    f"Successfully uploaded slides as revision {doc.rev} of {doc.name}.",
                )
                return redirect(
                    "ietf.meeting.views.session_details",
                    num=num,
                    acronym=session.group.acronym,
                )
    else:
        initial = {}
        if doc is not None:
            initial = {"title": doc.title}
        form = UploadSlidesForm(session, show_apply_to_all_checkbox, can_manage, initial=initial)

    return render(
        request,
        "meeting/upload_session_slides.html",
        {
            "session": session,
            "session_number": session_number,
            "slides_sp": session.presentations.filter(document=doc).first() if doc else None,
            "manage": session.can_manage_materials(request.user),
            "form": form,
        },
    )


def remove_sessionpresentation(request, session_id, num, name):
    sp = get_object_or_404(
        SessionPresentation, session_id=session_id, document__name=name
    )
    session = sp.session
    if not session.can_manage_materials(request.user):
        permission_denied(
            request, "You don't have permission to manage materials for this session."
        )
    if session.is_material_submission_cutoff() and not has_role(
        request.user, "Secretariat"
    ):
        permission_denied(
            request,
            "The materials cutoff for this session has passed. Contact the secretariat for further action.",
        )
    if request.method == "POST":
        session.presentations.filter(pk=sp.pk).delete()
        c = DocEvent(
            type="added_comment",
            doc=sp.document,
            rev=sp.document.rev,
            by=request.user.person,
        )
        c.desc = "Removed from session: %s" % (session)
        c.save()
        messages.success(request, f"Successfully removed {name}.")
        if sp.document.type_id == "slides" and hasattr(settings, "MEETECHO_API_CONFIG"):
            sm = SlidesManager(api_config=settings.MEETECHO_API_CONFIG)
            try:
                sm.delete(session=session, slides=sp.document)
            except MeetechoAPIError as err:
                log(f"Error in SlidesManager.delete(): {err}")

        return redirect(
            "ietf.meeting.views.session_details",
            num=session.meeting.number,
            acronym=session.group.acronym,
        )

    return render(request, "meeting/remove_sessionpresentation.html", {"sp": sp})


def ajax_add_slides_to_session(request, session_id, num):
    session = get_object_or_404(Session, pk=session_id)

    if not session.can_manage_materials(request.user):
        permission_denied(
            request, "You don't have permission to upload slides for this session."
        )
    if session.is_material_submission_cutoff() and not has_role(
        request.user, "Secretariat"
    ):
        permission_denied(
            request,
            "The materials cutoff for this session has passed. Contact the secretariat for further action.",
        )

    if request.method != "POST" or not request.POST:
        return HttpResponse(
            json.dumps({"success": False, "error": "No data submitted or not POST"}),
            content_type="application/json",
        )

    order_str = request.POST.get("order", None)
    try:
        order = int(order_str)
    except (ValueError, TypeError):
        return HttpResponse(
            json.dumps({"success": False, "error": "Supplied order is not valid"}),
            content_type="application/json",
        )
    if (
        order < 1
        or order > session.presentations.filter(document__type_id="slides").count() + 1
    ):
        return HttpResponse(
            json.dumps({"success": False, "error": "Supplied order is not valid"}),
            content_type="application/json",
        )

    name = request.POST.get("name", None)
    doc = Document.objects.filter(name=name).first()
    if not doc:
        return HttpResponse(
            json.dumps({"success": False, "error": "Supplied name is not valid"}),
            content_type="application/json",
        )

    if not session.presentations.filter(document=doc).exists():
        condition_slide_order(session)
        session.presentations.filter(
            document__type_id="slides", order__gte=order
        ).update(order=F("order") + 1)
        session.presentations.create(document=doc, rev=doc.rev, order=order)
        DocEvent.objects.create(
            type="added_comment",
            doc=doc,
            rev=doc.rev,
            by=request.user.person,
            desc="Added to session: %s" % session,
        )

        # Notify Meetecho of new slides if the API is configured
        if hasattr(settings, "MEETECHO_API_CONFIG"):
            sm = SlidesManager(api_config=settings.MEETECHO_API_CONFIG)
            try:
                sm.add(session=session, slides=doc, order=order)
            except MeetechoAPIError as err:
                log(f"Error in SlidesManager.add(): {err}")

    return HttpResponse(json.dumps({"success": True}), content_type="application/json")


def ajax_remove_slides_from_session(request, session_id, num):
    session = get_object_or_404(Session, pk=session_id)

    if not session.can_manage_materials(request.user):
        permission_denied(
            request, "You don't have permission to upload slides for this session."
        )
    if session.is_material_submission_cutoff() and not has_role(
        request.user, "Secretariat"
    ):
        permission_denied(
            request,
            "The materials cutoff for this session has passed. Contact the secretariat for further action.",
        )

    if request.method != "POST" or not request.POST:
        return HttpResponse(
            json.dumps({"success": False, "error": "No data submitted or not POST"}),
            content_type="application/json",
        )

    oldIndex_str = request.POST.get("oldIndex", None)
    try:
        oldIndex = int(oldIndex_str)
    except (ValueError, TypeError):
        return HttpResponse(
            json.dumps({"success": False, "error": "Supplied index is not valid"}),
            content_type="application/json",
        )
    if (
        oldIndex < 1
        or oldIndex > session.presentations.filter(document__type_id="slides").count()
    ):
        return HttpResponse(
            json.dumps({"success": False, "error": "Supplied index is not valid"}),
            content_type="application/json",
        )

    name = request.POST.get("name", None)
    doc = Document.objects.filter(name=name).first()
    if not doc:
        return HttpResponse(
            json.dumps({"success": False, "error": "Supplied name is not valid"}),
            content_type="application/json",
        )

    condition_slide_order(session)
    affected_presentations = session.presentations.filter(document=doc).first()
    if affected_presentations:
        if affected_presentations.order == oldIndex:
            affected_presentations.delete()
            session.presentations.filter(
                document__type_id="slides", order__gt=oldIndex
            ).update(order=F("order") - 1)
            DocEvent.objects.create(
                type="added_comment",
                doc=doc,
                rev=doc.rev,
                by=request.user.person,
                desc="Removed from session: %s" % session,
            )
            # Notify Meetecho of removed slides if the API is configured
            if hasattr(settings, "MEETECHO_API_CONFIG"):
                sm = SlidesManager(api_config=settings.MEETECHO_API_CONFIG)
                try:
                    sm.delete(session=session, slides=doc)
                except MeetechoAPIError as err:
                    log(f"Error in SlidesManager.delete(): {err}")
            # Report success
            return HttpResponse(
                json.dumps({"success": True}), content_type="application/json"
            )
        else:
            return HttpResponse(
                json.dumps({"success": False, "error": "Name does not match index"}),
                content_type="application/json",
            )
    else:
        return HttpResponse(
            json.dumps({"success": False, "error": "SessionPresentation not found"}),
            content_type="application/json",
        )


def ajax_reorder_slides_in_session(request, session_id, num):
    session = get_object_or_404(Session, pk=session_id)

    if not session.can_manage_materials(request.user):
        permission_denied(
            request, "You don't have permission to upload slides for this session."
        )
    if session.is_material_submission_cutoff() and not has_role(
        request.user, "Secretariat"
    ):
        permission_denied(
            request,
            "The materials cutoff for this session has passed. Contact the secretariat for further action.",
        )

    if request.method != "POST" or not request.POST:
        return HttpResponse(
            json.dumps({"success": False, "error": "No data submitted or not POST"}),
            content_type="application/json",
        )

    session_slides = session.presentations.filter(document__type_id="slides")
    num_slides_in_session = session_slides.count()
    oldIndex_str = request.POST.get("oldIndex", None)
    try:
        oldIndex = int(oldIndex_str)
    except (ValueError, TypeError):
        return HttpResponse(
            json.dumps({"success": False, "error": "Supplied index is not valid"}),
            content_type="application/json",
        )
    if oldIndex < 1 or oldIndex > num_slides_in_session:
        return HttpResponse(
            json.dumps({"success": False, "error": "Supplied index is not valid"}),
            content_type="application/json",
        )

    newIndex_str = request.POST.get("newIndex", None)
    try:
        newIndex = int(newIndex_str)
    except (ValueError, TypeError):
        return HttpResponse(
            json.dumps({"success": False, "error": "Supplied index is not valid"}),
            content_type="application/json",
        )
    if newIndex < 1 or newIndex > num_slides_in_session:
        return HttpResponse(
            json.dumps({"success": False, "error": "Supplied index is not valid"}),
            content_type="application/json",
        )

    if newIndex == oldIndex:
        return HttpResponse(
            json.dumps({"success": False, "error": "Supplied index is not valid"}),
            content_type="application/json",
        )

    condition_slide_order(session)
    sp = session_slides.get(order=oldIndex)
    if oldIndex < newIndex:
        session_slides.filter(order__gt=oldIndex, order__lte=newIndex).update(
            order=F("order") - 1
        )
    else:
        session_slides.filter(order__gte=newIndex, order__lt=oldIndex).update(
            order=F("order") + 1
        )
    sp.order = newIndex
    sp.save()

    # Update slide order with Meetecho if the API is configured
    if hasattr(settings, "MEETECHO_API_CONFIG"):
        sm = SlidesManager(api_config=settings.MEETECHO_API_CONFIG)
        try:
            sm.send_update(session)
        except MeetechoAPIError as err:
            log(f"Error in SlidesManager.send_update(): {err}")

    return HttpResponse(json.dumps({"success": True}), content_type="application/json")


@role_required('Secretariat')
def make_schedule_official(request, num, owner, name):

    meeting  = get_meeting(num)
    person   = get_person_by_email(owner)
    schedule = get_schedule_by_name(meeting, person, name)

    if schedule is None:
        raise Http404

    if request.method == 'POST':
        if not (schedule.public and schedule.visible):
            schedule.public = True
            schedule.visible = True
            schedule.save()
        if schedule.base and not (schedule.base.public and schedule.base.visible):
            schedule.base.public = True
            schedule.base.visible = True
            schedule.base.save()
        meeting.schedule = schedule
        meeting.save()
        return HttpResponseRedirect(reverse('ietf.meeting.views.list_schedules',kwargs={'num':num}))

    if not schedule.public:
        messages.warning(request,"This schedule will be made public as it is made official.")
    if not schedule.visible:
        messages.warning(request,"This schedule will be made visible as it is made official.")
    if schedule.base:
        if not schedule.base.public:
            messages.warning(request,"The base schedule will be made public as it is made official.")
        if not schedule.base.visible:
            messages.warning(request,"The base schedule will be made visible as it is made official.")

    return render(request, "meeting/make_schedule_official.html",
                  { 'schedule' : schedule,
                    'meeting' : meeting,
                  }
                 )
    

@role_required('Secretariat','Area Director')
def delete_schedule(request, num, owner, name):

    meeting  = get_meeting(num)
    person   = get_person_by_email(owner)
    schedule = get_schedule_by_name(meeting, person, name)

    # FIXME: we ought to put these checks in a function and only show
    # the delete button if the checks pass
    if schedule == meeting.schedule:
        permission_denied(request, 'You may not delete the official schedule for %s'%meeting)

    if Schedule.objects.filter(base=schedule).exists():
        return HttpResponseForbidden('You may not delete a schedule serving as the base for other schedules')

    if not ( has_role(request.user, 'Secretariat') or person.user == request.user ):
        permission_denied(request, "You may not delete other user's schedules")

    if request.method == 'POST':
        # remove schedule from origin tree
        replacement_origin = schedule.origin
        Schedule.objects.filter(origin=schedule).update(origin=replacement_origin)

        schedule.delete()
        return HttpResponseRedirect(reverse('ietf.meeting.views.list_schedules',kwargs={'num':num}))

    return render(request, "meeting/delete_schedule.html",
                  { 'schedule' : schedule,
                    'meeting' : meeting,
                  }
                 )
  
# -------------------------------------------------
# Interim Views
# -------------------------------------------------
def interim_announce(request):
    '''View which shows interim meeting requests awaiting announcement'''
    meetings = data_for_meetings_overview(Meeting.objects.filter(type='interim').order_by('date'), interim_status='scheda')
    menu_entries = get_interim_menu_entries(request)
    selected_menu_entry = 'announce'

    return render(request, "meeting/interim_announce.html", {
        'menu_entries': menu_entries,
        'selected_menu_entry': selected_menu_entry,
        'meetings': meetings})


@role_required('Secretariat',)
def interim_send_announcement(request, number):
    '''View for sending the announcement of a new interim meeting'''
    meeting = get_object_or_404(Meeting, number=number)
    group = meeting.session_set.first().group

    if request.method == 'POST':
        form = InterimAnnounceForm(request.POST,
                                   initial=get_announcement_initial(meeting))
        if form.is_valid():
            message = form.save(user=request.user)
            message.related_groups.add(group)
            for session in meeting.session_set.not_canceled():
                
                SchedulingEvent.objects.create(
                    session=session,
                    status=SessionStatusName.objects.get(slug='sched'),
                    by=request.user.person,
                )
            send_mail_message(request, message)
            messages.success(request, 'Interim meeting announcement sent')
            return redirect(interim_announce)

    form = InterimAnnounceForm(initial=get_announcement_initial(meeting))

    return render(request, "meeting/interim_send_announcement.html", {
        'meeting': meeting,
        'form': form})


@role_required('Secretariat',)
def interim_skip_announcement(request, number):
    '''View to change status of interim meeting to Scheduled without
    first announcing.  Only applicable to IRTF groups.
    '''
    meeting = get_object_or_404(Meeting, number=number)

    if request.method == 'POST':
        for session in meeting.session_set.not_canceled():
            SchedulingEvent.objects.create(
                session=session,
                status=SessionStatusName.objects.get(slug='sched'),
                by=request.user.person,
            )
        messages.success(request, 'Interim meeting scheduled.  No announcement sent.')
        return redirect(interim_announce)

    return render(request, "meeting/interim_skip_announce.html", {
        'meeting': meeting})


def interim_pending(request):

    '''View which shows interim meeting requests pending approval'''
    meetings = data_for_meetings_overview(Meeting.objects.filter(type='interim').order_by('date'), interim_status='apprw')

    menu_entries = get_interim_menu_entries(request)
    selected_menu_entry = 'pending'

    for meeting in meetings:
        if can_approve_interim_request(meeting, request.user):
            meeting.can_approve = True

    return render(request, "meeting/interim_pending.html", {
        'menu_entries': menu_entries,
        'selected_menu_entry': selected_menu_entry,
        'meetings': meetings})


@login_required
def interim_request(request):

    if not can_manage_some_groups(request.user):
        permission_denied(request, "You don't have permission to request any interims")

    '''View for requesting an interim meeting'''
    SessionFormset = inlineformset_factory(
        Meeting,
        Session,
        form=InterimSessionModelForm,
        formset=InterimSessionInlineFormSet,
        can_delete=False, extra=2)

    if request.method == 'POST':
        form = InterimMeetingModelForm(request, data=request.POST)
        formset = SessionFormset(instance=Meeting(), data=request.POST)
        if form.is_valid() and formset.is_valid():
            group = form.cleaned_data.get('group')
            is_approved = form.cleaned_data.get('approved', False)
            is_virtual = form.is_virtual()
            meeting_type = form.cleaned_data.get('meeting_type')

            requires_approval = not ( is_approved or ( is_virtual and not settings.VIRTUAL_INTERIMS_REQUIRE_APPROVAL ))

            # pre create meeting
            if meeting_type in ('single', 'multi-day'):
                meeting = form.save(date=get_earliest_session_date(formset))

                # need to use partialmethod here to pass custom variable to form init
                SessionFormset.form.__init__ = partialmethod(
                    InterimSessionModelForm.__init__,
                    user=request.user,
                    group=group,
                    requires_approval=requires_approval)
                formset = SessionFormset(instance=meeting, data=request.POST)
                formset.is_valid()
                formset.save()
                sessions_post_save(request, formset)

                if requires_approval:
                    send_interim_approval_request(meetings=[meeting])
                else:
                    send_interim_approval(request.user, meeting=meeting)
                    if not has_role(request.user, 'Secretariat'):
                        send_interim_announcement_request(meeting=meeting)

            # series require special handling, each session gets it's own
            # meeting object we won't see this on edit because series are
            # subsequently dealt with individually
            elif meeting_type == 'series':
                series = []
                SessionFormset.form.__init__ = partialmethod(
                    InterimSessionModelForm.__init__,
                    user=request.user,
                    group=group,
                    requires_approval=requires_approval)
                formset = SessionFormset(instance=Meeting(), data=request.POST)
                formset.is_valid()  # re-validate
                for session_form in formset.forms:
                    if not session_form.has_changed():
                        continue
                    # create meeting
                    form = InterimMeetingModelForm(request, data=request.POST)
                    form.is_valid()
                    meeting = form.save(date=session_form.cleaned_data['date'])
                    # create save session
                    session = session_form.save(commit=False)
                    session.meeting = meeting
                    session.save()
                    series.append(meeting)
                    sessions_post_save(request, [session_form])

                if requires_approval:
                    send_interim_approval_request(meetings=series)
                else:
                    send_interim_approval(request.user, meeting=meeting)
                    if not has_role(request.user, 'Secretariat'):
                        send_interim_announcement_request(meeting=meeting)

            messages.success(request, 'Interim meeting request submitted')
            return redirect(upcoming)

    else:
        initial = {'meeting_type': 'single', 'group': request.GET.get('group', '')}
        form = InterimMeetingModelForm(request=request, 
                                       initial=initial)
        formset = SessionFormset()

    return render(request, "meeting/interim_request.html", {
        "form": form,
        "formset": formset})


@login_required
def interim_request_cancel(request, number):
    '''View for cancelling an interim meeting request'''
    meeting = get_object_or_404(Meeting, number=number)
    first_session = meeting.session_set.first()
    group = first_session.group
    if not can_manage_group(request.user, group):
        permission_denied(request, "You do not have permissions to cancel this meeting request")
    session_status = current_session_status(first_session)

    if request.method == 'POST':
        form = InterimCancelForm(request.POST)
        if form.is_valid():
            if 'comments' in form.changed_data:
                meeting.session_set.update(agenda_note=form.cleaned_data.get('comments'))

            was_scheduled = session_status.slug == 'sched'

            result_status = SessionStatusName.objects.get(slug='canceled' if was_scheduled else 'canceledpa')
            sessions_to_cancel = meeting.session_set.not_canceled()
            for session in sessions_to_cancel:

                SchedulingEvent.objects.create(
                    session=session,
                    status=result_status,
                    by=request.user.person,
                )

            if was_scheduled:
                send_interim_meeting_cancellation_notice(meeting)

            sessions_post_cancel(request, sessions_to_cancel)

            messages.success(request, 'Interim meeting cancelled')
            return redirect(upcoming)
    else:
        form = InterimCancelForm(initial={'group': group.acronym, 'date': meeting.date})

    return render(request, "meeting/interim_request_cancel.html", {
        "form": form,
        "meeting": meeting,
        "session_status": session_status,
    })


@login_required
def interim_request_session_cancel(request, sessionid):
    '''View for cancelling an interim meeting request'''
    session = get_object_or_404(Session, pk=sessionid)
    group = session.group
    if not can_manage_group(request.user, group):
        permission_denied(request, "You do not have permissions to cancel this session")
    session_status = current_session_status(session)

    if request.method == 'POST':
        form = InterimCancelForm(request.POST)
        if form.is_valid():
            remaining_sessions = session.meeting.session_set.with_current_status().exclude(
                current_status__in=['canceled', 'canceledpa']
            )
            if remaining_sessions.count() <= 1:
                return HttpResponse('Cannot cancel only remaining session. Cancel the request instead.',
                                    status=409)

            if 'comments' in form.changed_data:
                session.agenda_note=form.cleaned_data.get('comments')
                session.save()

            was_scheduled = session_status.slug == 'sched'

            result_status = SessionStatusName.objects.get(slug='canceled' if was_scheduled else 'canceledpa')
            SchedulingEvent.objects.create(
                session=session,
                status=result_status,
                by=request.user.person,
            )

            if was_scheduled:
                send_interim_session_cancellation_notice(session)

            sessions_post_cancel(request, [session])

            messages.success(request, 'Interim meeting session cancelled')
            return redirect(interim_request_details, number=session.meeting.number)
    else:
        session_time = session.official_timeslotassignment().timeslot.time
        form = InterimCancelForm(initial={'group': group.acronym, 'date': session_time.date()})

    return render(request, "meeting/interim_request_cancel.html", {
        "form": form,
        "session": session,
        "session_status": session_status,
    })


@login_required
def interim_request_details(request, number):
    '''View details of an interim meeting request'''
    meeting = get_object_or_404(Meeting, number=number)
    sessions_not_canceled = meeting.session_set.not_canceled()
    first_session = meeting.session_set.first()  # first, whether or not canceled
    group = first_session.group

    if not can_manage_group(request.user, group):
        permission_denied(request, "You do not have permissions to manage this meeting request")
    can_edit = can_edit_interim_request(meeting, request.user)
    can_approve = can_approve_interim_request(meeting, request.user)

    if request.method == 'POST':
        if request.POST.get('approve') and can_approve_interim_request(meeting, request.user):
            for session in sessions_not_canceled:
                SchedulingEvent.objects.create(
                    session=session,
                    status=SessionStatusName.objects.get(slug='scheda'),
                    by=request.user.person,
                )
            messages.success(request, 'Interim meeting approved')
            if has_role(request.user, 'Secretariat'):
                return redirect(interim_send_announcement, number=number)
            else:
                send_interim_announcement_request(meeting)
                return redirect(interim_pending)
        if request.POST.get('disapprove') and can_approve_interim_request(meeting, request.user):
            for session in sessions_not_canceled:
                SchedulingEvent.objects.create(
                    session=session,
                    status=SessionStatusName.objects.get(slug='disappr'),
                    by=request.user.person,
                )
            messages.success(request, 'Interim meeting disapproved')
            return redirect(interim_pending)

    # Determine meeting status from non-canceled sessions, if any.
    # N.b., meeting_status may be None after either of these code paths,
    # though I am not sure what circumstances would cause this.
    if sessions_not_canceled.count() > 0:
        meeting_status = current_session_status(sessions_not_canceled.first())
    else:
        meeting_status = current_session_status(first_session)

    meeting_assignments = SchedTimeSessAssignment.objects.filter(
        schedule__in=[meeting.schedule, meeting.schedule.base if meeting.schedule else None]
    ).select_related(
        'session', 'timeslot'
    )
    for ma in meeting_assignments:
        ma.status = current_session_status(ma.session)
        ma.can_be_canceled = ma.status.slug in ('sched', 'scheda', 'apprw')

    return render(request, "meeting/interim_request_details.html", {
        "meeting": meeting,
        "meeting_assignments": meeting_assignments,
        "group": group,
        "requester": session_requested_by(first_session),
        "meeting_status": meeting_status or SessionStatusName.objects.get(slug='canceled'),
        "can_edit": can_edit,
        "can_approve": can_approve})

@login_required
def interim_request_edit(request, number):
    '''Edit details of an interim meeting reqeust'''
    meeting = get_object_or_404(Meeting, number=number)
    if not can_edit_interim_request(meeting, request.user):
        permission_denied(request, "You do not have permissions to edit this meeting request")

    SessionFormset = inlineformset_factory(
        Meeting,
        Session,
        form=InterimSessionModelForm,
        can_delete=False,
        extra=1)

    if request.method == 'POST':
        form = InterimMeetingModelForm(request=request, instance=meeting,
                                       data=request.POST)
        group = Group.objects.get(pk=form.data['group'])
        is_approved = is_interim_meeting_approved(meeting)

        SessionFormset.form.__init__ = partialmethod(
            InterimSessionModelForm.__init__,
            user=request.user,
            group=group,
            requires_approval= not is_approved)

        formset = SessionFormset(instance=meeting, data=request.POST)

        if form.is_valid() and formset.is_valid():
            meeting = form.save(date=get_earliest_session_date(formset))
            formset.save()
            sessions_post_save(request, formset)

            message = 'Interim meeting request saved'
            meeting_is_scheduled = add_event_info_to_session_qs(meeting.session_set).filter(current_status='sched').exists()
            if (form.has_changed() or formset.has_changed()) and meeting_is_scheduled:
                send_interim_change_notice(request, meeting)
                message = message + ' and change announcement sent'
            messages.success(request, message)
            return redirect(interim_request_details, number=number)

    else:
        form = InterimMeetingModelForm(request=request, instance=meeting)
        formset = SessionFormset(instance=meeting)

    return render(request, "meeting/interim_request_edit.html", {
        "meeting": meeting,
        "form": form,
        "formset": formset})

def past(request):
    '''List of past meetings'''
    today = timezone.now()

    meetings = data_for_meetings_overview(Meeting.objects.filter(date__lte=today).order_by('-date'))

    return render(request, 'meeting/past.html', {
                  'meetings': meetings,
                  })

def upcoming(request):
    '''List of upcoming meetings'''
    today = datetime_today()

    # Get ietf meetings starting 7 days ago, and interim meetings starting today
    ietf_meetings = Meeting.objects.filter(type_id='ietf', date__gte=today-datetime.timedelta(days=7))

    interim_sessions = add_event_info_to_session_qs(
        Session.objects.filter(
            meeting__type_id='interim', 
            timeslotassignments__schedule=F('meeting__schedule'),
            timeslotassignments__timeslot__time__gte=today
        )
    ).filter(current_status__in=('sched','canceled'))

    # Set up for agenda filtering - only one filter_category here
    AgendaKeywordTagger(sessions=interim_sessions).apply()
    filter_organizer = AgendaFilterOrganizer(sessions=interim_sessions, single_category=True)
    # Allow filtering to show only IETF Meetings. This adds a button labeled "IETF Meetings" to the
    # "Other" column of the filter UI. When enabled, this adds the keyword "ietf-meetings" to the "show"
    # filter list. The IETF meetings are explicitly labeled with this keyword in upcoming.html.
    filter_organizer.add_extra_filter('IETF Meetings')

    entries = list(ietf_meetings)
    entries.extend(list(interim_sessions))
    entries.sort(
        key=lambda o: (
            pytz.utc.localize(datetime.datetime.combine(o.date, datetime.datetime.min.time())) if isinstance(o, Meeting) else o.official_timeslotassignment().timeslot.utc_start_time(),
            o.number if isinstance(o, Meeting) else o.meeting.number,
        )
    )
    for o in entries:
        if isinstance(o, Meeting):
            o.start_timestamp = int(pytz.utc.localize(datetime.datetime.combine(o.date, datetime.time.min)).timestamp())
            o.end_timestamp = int(pytz.utc.localize(datetime.datetime.combine(o.end_date(), datetime.time.max)).timestamp())
        else:
            o.start_timestamp = int(o.official_timeslotassignment().timeslot.utc_start_time().timestamp())
            o.end_timestamp = int(o.official_timeslotassignment().timeslot.utc_end_time().timestamp())

    # add menu entries
    menu_entries = get_interim_menu_entries(request)
    selected_menu_entry = 'upcoming'

    # add menu actions
    actions = []
    if can_request_interim_meeting(request.user):
        actions.append(dict(
            label='Request new interim meeting',
            url=reverse('ietf.meeting.views.interim_request'),
            append_filter=False)
        )
    actions.append(dict(
        label='Download as .ics',
        url=reverse('ietf.meeting.views.upcoming_ical'),
        append_filter=True)
    )
    actions.append(dict(
        label='Subscribe with webcal',
        url='webcal://'+request.get_host()+reverse('ietf.meeting.views.upcoming_ical'),
        append_filter=True)
    )

    return render(request, 'meeting/upcoming.html', {
                  'entries': entries,
                  'filter_categories': filter_organizer.get_filter_categories(),
                  'menu_actions': actions,
                  'menu_entries': menu_entries,
                  'selected_menu_entry': selected_menu_entry,
                  'now': timezone.now(),
                  })


def upcoming_ical(request):
    """Return Upcoming meetings in iCalendar file

    Filters by wg name and session type.
    """
    try:
        filter_params = parse_agenda_filter_params(request.GET)
    except ValueError as e:
        return HttpResponseBadRequest(str(e))
        
    today = datetime_today()

    # get meetings starting 7 days ago -- we'll filter out sessions in the past further down
    meetings = data_for_meetings_overview(Meeting.objects.filter(date__gte=today-datetime.timedelta(days=7)).prefetch_related('schedule').order_by('date'))

    assignments = list(SchedTimeSessAssignment.objects.filter(
        schedule__in=[m.schedule_id for m in meetings] + [m.schedule.base_id for m in meetings if m.schedule],
        session__in=[s.pk for m in meetings for s in m.sessions if m.type_id != 'ietf'],
        timeslot__time__gte=today,
    ).order_by(
        'schedule__meeting__date', 'session__type', 'timeslot__time', 'schedule__meeting__number',
    ).select_related(
        'session__group', 'session__group__parent', 'timeslot', 'schedule', 'schedule__meeting'
    ).distinct())

    AgendaKeywordTagger(assignments=assignments).apply()

    # apply filters
    if filter_params is not None:
        assignments = [a for a in assignments if should_include_assignment(filter_params, a)]

    # we already collected sessions with current_status, so reuse those
    sessions = {s.pk: s for m in meetings for s in m.sessions}
    for a in assignments:
        if a.session_id is not None:
            a.session = sessions.get(a.session_id) or a.session
            a.session.ical_status = ical_session_status(a)

    # Handle IETFs separately. Manually apply the 'ietf-meetings' filter.
    if filter_params is None or (
            'ietf-meetings' in filter_params['show'] and 'ietf-meetings' not in filter_params['hide']
    ):
        ietfs = [m for m in meetings if m.type_id == 'ietf']
        preprocess_meeting_important_dates(ietfs)
    else:
        ietfs = []

    meeting_vtz = {meeting.vtimezone() for meeting in meetings}
    meeting_vtz.discard(None)

    # icalendar response file should have '\r\n' line endings per RFC5545
    response = render_to_string('meeting/upcoming.ics', {
        'vtimezones': ''.join(sorted(meeting_vtz)),
        'assignments': assignments,
        'ietfs': ietfs,
    }, request=request)
    response = re.sub("\r(?!\n)|(?<!\r)\n", "\r\n", response)

    response = HttpResponse(response, content_type='text/calendar')
    response['Content-Disposition'] = 'attachment; filename="upcoming.ics"'
    return response
    

def upcoming_json(request):
    '''Return Upcoming meetings in json format'''
    today = date_today()

    # get meetings starting 7 days ago -- we'll filter out sessions in the past further down
    meetings = data_for_meetings_overview(Meeting.objects.filter(date__gte=today-datetime.timedelta(days=7)).order_by('date'))

    data = {}
    for m in meetings:
        data[m.number] = {
            'date':  m.date.strftime("%Y-%m-%d"),
        }

    response = HttpResponse(json.dumps(data, indent=2, sort_keys=False), content_type='application/json;charset=%s'%settings.DEFAULT_CHARSET)
    return response

def organize_proceedings_sessions(sessions):
    # Collect sessions by Group, then bin by session name (including sessions with blank names).
    # If all of a group's sessions are 'notmeet', the processed data goes in not_meeting_sessions.
    # Otherwise, the data goes in meeting_sessions.
    meeting_groups = []
    not_meeting_groups = []
    for group_acronym, group_sessions in itertools.groupby(sessions, key=lambda s: s.group.acronym):
        by_name = {}
        is_meeting = False
        all_canceled = True
        group = None
        for s in sorted(
                group_sessions,
                key=lambda gs: (
                        gs.official_timeslotassignment().timeslot.time
                        if gs.official_timeslotassignment() else datetime.datetime(datetime.MAXYEAR, 1, 1)
                ),
        ):
            group = s.group
            if s.current_status != 'notmeet':
                is_meeting = True
            if s.current_status != 'canceled':
                all_canceled = False
            by_name.setdefault(s.name, [])
            if s.current_status != 'notmeet' or s.presentations.exists():
                by_name[s.name].append(s)  # for notmeet, only include sessions with materials
        for sess_name, ss in by_name.items():
            session = ss[0] if ss else None
            def _format_materials(items):
                """Format session/material for template

                Input is a list of (session, materials) pairs. The materials value can be a single value or a list.
                """
                material_times = {}  # key is material, value is first timestamp it appeared
                for s, mats in items:
                    tsa = s.official_timeslotassignment()
                    timestamp = tsa.timeslot.time if tsa else None
                    if not isinstance(mats, list):
                        mats = [mats]
                    for mat in mats:
                        if mat and mat not in material_times:
                            material_times[mat] = timestamp
                n_mats = len(material_times)
                result = []
                if n_mats == 1:
                    result.append({'material': list(material_times)[0]})  # no 'time' when only a single material
                elif n_mats > 1:
                    for mat, timestamp in material_times.items():
                        result.append({'material': mat, 'time': timestamp})
                return result

            entry = {
                'group': group,
                'name': sess_name,
                'session': session,
                'canceled': all_canceled,
                'has_materials': s.presentations.exists(),
                'agendas': _format_materials((s, s.agenda()) for s in ss),
                'minutes': _format_materials((s, s.minutes()) for s in ss),
                'bluesheets': _format_materials((s, s.bluesheets()) for s in ss),
                'recordings': _format_materials((s, s.recordings()) for s in ss),
                'chatlogs': _format_materials((s, s.chatlogs()) for s in ss),
                'slides': _format_materials((s, s.slides()) for s in ss),
                'drafts': _format_materials((s, s.drafts()) for s in ss),
                'last_update': session.last_update if hasattr(session, 'last_update') else None
            }
            if session and session.meeting.type_id == 'ietf' and not session.meeting.proceedings_final:
                entry['attendances'] = _format_materials((s, s) for s in ss if Attended.objects.filter(session=s).exists())
            if is_meeting:
                meeting_groups.append(entry)
            else:
                not_meeting_groups.append(entry)
    return meeting_groups, not_meeting_groups


def proceedings(request, num=None):

    def area_and_group_acronyms_from_session(s):
        area = s.group_parent_at_the_time()
        if area == None:
            area = s.group.parent
        group = s.group_at_the_time()
        return (area.acronym, group.acronym)

    meeting = get_meeting(num)

    # Early proceedings were hosted on www.ietf.org rather than the datatracker
    if meeting.proceedings_format_version == 1:
        return HttpResponseRedirect(settings.PROCEEDINGS_V1_BASE_URL.format(meeting=meeting))

    if not meeting.schedule or not meeting.schedule.assignments.exists():
        kwargs = dict()
        if num:
            kwargs['num'] = num
        return redirect('ietf.meeting.views.materials', **kwargs)

    begin_date = meeting.get_submission_start_date()
    cut_off_date = meeting.get_submission_cut_off_date()
    cor_cut_off_date = meeting.get_submission_correction_date()
    today_utc = date_today(datetime.timezone.utc)

    schedule = get_schedule(meeting, None)
    sessions  = (
        meeting.session_set.with_current_status()
        .filter(Q(timeslotassignments__schedule__in=[schedule, schedule.base if schedule else None])
                | Q(current_status='notmeet'))
        .select_related()
        .order_by('-current_status')
    )

    plenaries, _ = organize_proceedings_sessions(
        sessions.filter(name__icontains='plenary')
        .exclude(current_status='notmeet')
    )
    irtf_meeting, irtf_not_meeting = organize_proceedings_sessions(
        sessions.filter(group__parent__acronym = 'irtf').order_by('group__acronym')
    )
    # per Colin (datatracker #5010) - don't report not meeting rags
    irtf_not_meeting = [item for item in irtf_not_meeting if item["group"].type_id != "rag"]
    irtf = {"meeting_groups":irtf_meeting, "not_meeting_groups":irtf_not_meeting}

    training, _ = organize_proceedings_sessions(
        sessions.filter(group__acronym__in=['edu','iaoc'], type_id__in=['regular', 'other',])
        .exclude(current_status='notmeet')
    )
    iab, _ = organize_proceedings_sessions(
        sessions.filter(group__parent__acronym = 'iab')
        .exclude(current_status='notmeet')
    )
    editorial, _ = organize_proceedings_sessions(
        sessions.filter(group__acronym__in=['rsab','rswg'])
        .exclude(current_status='notmeet')
    )

    ietf = sessions.filter(group__parent__type__slug = 'area').exclude(group__acronym__in=['edu','iepg','tools'])
    ietf = list(ietf)
    ietf.sort(key=lambda s: area_and_group_acronyms_from_session(s))
    ietf_areas = []
    for area, area_sessions in itertools.groupby(ietf, key=lambda s: s.group_parent_at_the_time()):
        meeting_groups, not_meeting_groups = organize_proceedings_sessions(area_sessions)
        ietf_areas.append((area, meeting_groups, not_meeting_groups))

    cache_version = Document.objects.filter(session__meeting__number=meeting.number).aggregate(Max('time'))["time__max"]

    with timezone.override(meeting.tz()):
        return render(request, "meeting/proceedings.html", {
            'meeting': meeting,
            'plenaries': plenaries,
            'training': training,
            'irtf': irtf,
            'iab': iab,
            'editorial': editorial,
            'ietf_areas': ietf_areas,
            'cut_off_date': cut_off_date,
            'cor_cut_off_date': cor_cut_off_date,
            'submission_started': today_utc > begin_date,
            'cache_version': cache_version,
            'attendance': meeting.get_attendance(),
            'meetinghost_logo': {
                'max_height': settings.MEETINGHOST_LOGO_MAX_DISPLAY_HEIGHT,
                'max_width': settings.MEETINGHOST_LOGO_MAX_DISPLAY_WIDTH,
            }
        })

@role_required('Secretariat')
def finalize_proceedings(request, num=None):

    meeting = get_meeting(num)
    if (meeting.number.isdigit() and int(meeting.number) <= 64) or not meeting.schedule or not meeting.schedule.assignments.exists() or meeting.proceedings_final:
        raise Http404

    if request.method=='POST':
        finalize(request, meeting)
        return HttpResponseRedirect(reverse('ietf.meeting.views.proceedings',kwargs={'num':meeting.number}))
    
    return render(request, "meeting/finalize.html", {'meeting':meeting,})

def proceedings_acknowledgements(request, num=None):
    '''Display Acknowledgements for meeting'''
    if not (num and num.isdigit()):
        raise Http404
    meeting = get_meeting(num)
    if meeting.proceedings_format_version == 1:
        return HttpResponseRedirect( f'{settings.PROCEEDINGS_V1_BASE_URL.format(meeting=meeting)}/acknowledgement.html')
    return render(request, "meeting/proceedings_acknowledgements.html", {
        'meeting': meeting,
    })

def proceedings_attendees(request, num=None):
    '''Display list of meeting attendees'''
    if not (num and num.isdigit()):
        raise Http404
    meeting = get_meeting(num)
    if meeting.proceedings_format_version == 1:
        return HttpResponseRedirect(f'{settings.PROCEEDINGS_V1_BASE_URL.format(meeting=meeting)}/attendee.html')

    template = None
    meeting_registrations = None

    if int(meeting.number) >= 118:
        checked_in, attended = participants_for_meeting(meeting)
        regs = list(MeetingRegistration.objects.filter(meeting__number=num, reg_type='onsite', checkedin=True))

        for mr in MeetingRegistration.objects.filter(meeting__number=num, reg_type='remote').select_related('person'):
            if mr.person.pk in attended and mr.person.pk not in checked_in:
                regs.append(mr)

        meeting_registrations = sorted(regs, key=lambda x: (x.last_name, x.first_name))
    else:
        overview_template = "/meeting/proceedings/%s/attendees.html" % meeting.number
        try:
            template = render_to_string(overview_template, {})
        except TemplateDoesNotExist:
            raise Http404

    return render(request, "meeting/proceedings_attendees.html", {
        'meeting': meeting,
        'meeting_registrations': meeting_registrations,
        'template': template,
    })

def proceedings_overview(request, num=None):
    '''Display Overview for given meeting'''
    if not (num and num.isdigit()):
        raise Http404
    meeting = get_meeting(num)
    if meeting.proceedings_format_version == 1:
        return HttpResponseRedirect(f'{settings.PROCEEDINGS_V1_BASE_URL.format(meeting=meeting)}/overview.html')
    overview_template = '/meeting/proceedings/%s/overview.rst' % meeting.number
    try:
        template = render_to_string(overview_template, {})
    except TemplateDoesNotExist:
        raise Http404
    return render(request, "meeting/proceedings_overview.html", {
        'meeting': meeting,
        'template': template,
    })

def proceedings_activity_report(request, num=None):
    '''Display Activity Report (stats since last meeting)'''
    if not (num and num.isdigit()):
        raise Http404
    meeting = get_meeting(num)
    if meeting.proceedings_format_version == 1:
        return HttpResponseRedirect(f'{settings.PROCEEDINGS_V1_BASE_URL.format(meeting=meeting)}/progress-report.html')
    sdate = meeting.previous_meeting().date
    edate = meeting.date
    context = get_activity_stats(sdate,edate)
    context['meeting'] = meeting
    context['is_meeting_report'] = True
    return render(request, "meeting/proceedings_activity_report.html", context)
    
class OldUploadRedirect(RedirectView):
    def get_redirect_url(self, **kwargs):
        return reverse_lazy('ietf.meeting.views.session_details',kwargs=self.kwargs)


@require_api_key
@role_required("Recording Manager")
@csrf_exempt
def api_set_meetecho_recording_name(request):
    """Set name for meetecho recording

    parameters:
        apikey: the poster's personal API key
        session_id: id of the session to update
        name: the name to use for the recording at meetecho player
    """
    def err(code, text):
        return HttpResponse(text, status=code, content_type='text/plain')

    if request.method != "POST":
        return HttpResponseNotAllowed(
            content="Method not allowed", content_type="text/plain", permitted_methods=('POST',)
        )

    session_id = request.POST.get('session_id', None)
    if session_id is None:
        return err(400, 'Missing session_id parameter')
    name = request.POST.get('name', None)
    if name is None:
        return err(400, 'Missing name parameter')

    try:
        session = Session.objects.get(pk=session_id)
    except Session.DoesNotExist:
        return err(400, f"Session not found with session_id '{session_id}'")
    except ValueError:
        return err(400, "Invalid session_id: {session_id}")

    session.meetecho_recording_name = name
    session.save()

    return HttpResponse("Done", status=200, content_type='text/plain')

@require_api_key
@role_required('Recording Manager')
@csrf_exempt
def api_set_session_video_url(request):
    """Set video URL for session

    parameters:
      apikey: the poster's personal API key
      session_id: id of session to update
      url: The recording url (on YouTube, or whatever)
    """
    def err(code, text):
        return HttpResponse(text, status=code, content_type='text/plain')

    if request.method != 'POST':
        return HttpResponseNotAllowed(
            content="Method not allowed", content_type="text/plain", permitted_methods=('POST',)
        )

    # Temporary: fall back to deprecated interface if we have old-style parameters.
    # Do away with this once meetecho is using the new pk-based interface.
    if any(k in request.POST for k in ['meeting', 'group', 'item']):
        return deprecated_api_set_session_video_url(request)

    session_id = request.POST.get('session_id', None)
    if session_id is None:
        return err(400, 'Missing session_id parameter')
    incoming_url = request.POST.get('url', None)
    if incoming_url is None:
        return err(400, 'Missing url parameter')

    try:
        session = Session.objects.get(pk=session_id)
    except Session.DoesNotExist:
        return err(400, f"Session not found with session_id '{session_id}'")
    except ValueError:
        return err(400, "Invalid session_id: {session_id}")

    try:
        URLValidator()(incoming_url)
    except ValidationError:
        return err(400, f"Invalid url value: '{incoming_url}'")

    recordings = [(r.name, r.title, r) for r in session.recordings() if 'video' in r.title.lower()]
    if recordings:
        r = recordings[-1][-1]
        if r.external_url != incoming_url:
            e = DocEvent.objects.create(doc=r, rev=r.rev, type="added_comment", by=request.user.person,
                                        desc="External url changed from %s to %s" % (r.external_url, incoming_url))
            r.external_url = incoming_url
            r.save_with_history([e])
    else:
        time = session.official_timeslotassignment().timeslot.time
        title = 'Video recording for %s on %s at %s' % (session.group.acronym, time.date(), time.time())
        create_recording(session, incoming_url, title=title, user=request.user.person)
    return HttpResponse("Done", status=200, content_type='text/plain')


def deprecated_api_set_session_video_url(request):
    """Set video URL for session (deprecated)

    Uses meeting/group/item to identify session.
    """
    def err(code, text):
        return HttpResponse(text, status=code, content_type='text/plain')
    if request.method == 'POST':
        # parameters:
        #   apikey: the poster's personal API key
        #   meeting: '101', or 'interim-2018-quic-02'
        #   group: 'quic' or 'plenary'
        #   item: '1', '2', '3' (the group's first, second, third etc.
        #                           session during the week)
        #   url: The recording url (on YouTube, or whatever)
        user = request.user.person
        for item in ['meeting', 'group', 'item', 'url',]:
            value = request.POST.get(item)
            if not value:
                return err(400, "Missing %s parameter" % item)
        number = request.POST.get('meeting')
        sessions = Session.objects.filter(meeting__number=number)
        if not sessions.exists():
            return err(400, "No sessions found for meeting '%s'" % (number, ))
        acronym = request.POST.get('group')
        sessions = sessions.filter(group__acronym=acronym)
        if not sessions.exists():
            return err(400, "No sessions found in meeting '%s' for group '%s'" % (number, acronym))
        session_times = [ (s.official_timeslotassignment().timeslot.time, s.id, s) for s in sessions if s.official_timeslotassignment() ]
        session_times.sort()
        item = request.POST.get('item')
        if not item.isdigit():
            return err(400, "Expected a numeric value for 'item', found '%s'" % (item, ))
        n = int(item)-1              # change 1-based to 0-based
        try:
            time, __, session = session_times[n]
        except IndexError:
            return err(400, "No item '%s' found in list of sessions for group" % (item, ))
        url = request.POST.get('url')
        try:
            URLValidator()(url)
        except ValidationError:
            return err(400, "Invalid url value: '%s'" % (url, ))
        recordings = [ (r.name, r.title, r) for r in session.recordings() if 'video' in r.title.lower() ]
        if recordings:
            r = recordings[-1][-1]
            if r.external_url != url:
                e = DocEvent.objects.create(doc=r, rev=r.rev, type="added_comment", by=request.user.person,
                    desc="External url changed from %s to %s" % (r.external_url, url))
                r.external_url = url
                r.save_with_history([e])
            else:
                return err(400, "URL is the same")
        else:
            time = session.official_timeslotassignment().timeslot.time
            title = 'Video recording for %s on %s at %s' % (acronym, time.date(), time.time())
            create_recording(session, url, title=title, user=user)
    else:
        return err(405, "Method not allowed")

    return HttpResponse("Done", status=200, content_type='text/plain')


@require_api_key
@role_required('Recording Manager') # TODO : Rework how Meetecho interacts via APIs. There may be better paths to pursue than Personal API keys as they are currently defined.
@csrf_exempt
def api_add_session_attendees(request):
    """Upload attendees for one or more sessions

    parameters:
        apikey: the poster's personal API key
        attended: json blob with
            {
                "session_id": session pk,
                "attendees": [
                    {"user_id": user-pk-1, "join_time": "2024-02-21T18:00:00Z"},
                    {"user_id": user-pk-2, "join_time": "2024-02-21T18:00:01Z"},
                    {"user_id": user-pk-3, "join_time": "2024-02-21T18:00:02Z"},
                    ...
                ]
            }
    """
    json_validator = jsonschema.Draft202012Validator(
        schema={
            "type": "object",
            "properties": {
                "session_id": {"type": "integer"},
                "attendees": {
                    # Allow either old or new format until after IETF 119
                    "anyOf": [
                        {"type": "array", "items": {"type": "integer"}},  # old: array of user PKs
                        {
                            # new: array of user_id / join_time objects
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "user_id": {"type": "integer", },
                                    "join_time": {"type": "string", "format": "date-time"}
                                },
                                "required": ["user_id", "join_time"],
                            },
                        },
                    ],
                }
            },
            "required": ["session_id", "attendees"],
        },
        format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER,  # format-checks disabled by default
    )

    def err(code, text):
        return HttpResponse(text, status=code, content_type="text/plain")

    if request.method != "POST":
        return err(405, "Method not allowed")
    attended_post = request.POST.get("attended")
    if not attended_post:
        return err(400, "Missing attended parameter")

    # Validate the request payload
    try:
        payload = json.loads(attended_post)
        json_validator.validate(payload)
    except (json.decoder.JSONDecodeError, jsonschema.exceptions.ValidationError):
        return err(400, "Malformed post")

    session_id = payload["session_id"]
    session = Session.objects.filter(pk=session_id).first()
    if not session:
        return err(400, "Invalid session")

    attendees = payload["attendees"]
    if len(attendees) > 0:
        # Check whether we have old or new format
        if type(attendees[0]) == int:
            # it's the old format
            users = User.objects.filter(pk__in=attendees)
            if users.count() != len(payload["attendees"]):
                return err(400, "Invalid attendee")
            for user in users:
                session.attended_set.get_or_create(person=user.person)
        else:
            # it's the new format
            join_time_by_pk = {
                att["user_id"]: datetime.datetime.fromisoformat(
                    att["join_time"].replace("Z", "+00:00")  # Z not understood until py311
                )
                for att in attendees
            }
            persons = list(Person.objects.filter(user__pk__in=join_time_by_pk))
            if len(persons) != len(join_time_by_pk):
                return err(400, "Invalid attendee")
            to_create = [
                Attended(session=session, person=person, time=join_time_by_pk[person.user_id])
                for person in persons
            ]
            # Create in bulk, ignoring any that already exist
            Attended.objects.bulk_create(to_create, ignore_conflicts=True)

    if session.meeting.type_id == "interim":
        save_error = generate_bluesheet(request, session)
        if save_error:
            return err(400, save_error)

    return HttpResponse("Done", status=200, content_type="text/plain")


@require_api_key
@role_required('Recording Manager')
@csrf_exempt
def api_upload_chatlog(request):
    def err(code, text):
        return HttpResponse(text, status=code, content_type='text/plain')
    if request.method != 'POST':
        return err(405, "Method not allowed")
    apidata_post = request.POST.get('apidata')
    if not apidata_post:
        return err(400, "Missing apidata parameter")
    try:
        apidata = json.loads(apidata_post)
    except json.decoder.JSONDecodeError:
        return err(400, "Malformed post")
    if not ( 'session_id' in apidata and type(apidata['session_id']) is int ):
        return err(400, "Malformed post")
    session_id = apidata['session_id']
    if not ( 'chatlog' in apidata and type(apidata['chatlog']) is list and all([type(el) is dict for el in apidata['chatlog']]) ):
        return err(400, "Malformed post")
    session = Session.objects.filter(pk=session_id).first()
    if not session:
        return err(400, "Invalid session")
    chatlog_sp = session.presentations.filter(document__type='chatlog').first()
    if chatlog_sp:
        doc = chatlog_sp.document
        doc.rev = f"{(int(doc.rev)+1):02d}"
        chatlog_sp.rev = doc.rev
        chatlog_sp.save()
    else:
        doc = new_doc_for_session('chatlog', session)
        if doc is None:
            return err(400, "Could not find official timeslot for session")
    filename = f"{doc.name}-{doc.rev}.json"
    doc.uploaded_filename = filename
    write_doc_for_session(session, 'chatlog', filename, json.dumps(apidata['chatlog']))
    e = NewRevisionDocEvent.objects.create(doc=doc, rev=doc.rev, by=request.user.person, type='new_revision', desc='New revision available: %s'%doc.rev)
    doc.save_with_history([e])
    return HttpResponse("Done", status=200, content_type='text/plain')

@require_api_key
@role_required('Recording Manager')
@csrf_exempt
def api_upload_polls(request):
    def err(code, text):
        return HttpResponse(text, status=code, content_type='text/plain')
    if request.method != 'POST':
        return err(405, "Method not allowed")
    apidata_post = request.POST.get('apidata')
    if not apidata_post:
        return err(400, "Missing apidata parameter")
    try:
        apidata = json.loads(apidata_post)
    except json.decoder.JSONDecodeError:
        return err(400, "Malformed post")
    if not ( 'session_id' in apidata and type(apidata['session_id']) is int ):
        return err(400, "Malformed post")
    session_id = apidata['session_id']
    if not ( 'polls' in apidata and type(apidata['polls']) is list and all([type(el) is dict for el in apidata['polls']]) ):
        return err(400, "Malformed post")
    session = Session.objects.filter(pk=session_id).first()
    if not session:
        return err(400, "Invalid session")
    polls_sp = session.presentations.filter(document__type='polls').first()
    if polls_sp:
        doc = polls_sp.document
        doc.rev = f"{(int(doc.rev)+1):02d}"
        polls_sp.rev = doc.rev
        polls_sp.save()
    else:
        doc = new_doc_for_session('polls', session)
        if doc is None:
            return err(400, "Could not find official timeslot for session")
    filename = f"{doc.name}-{doc.rev}.json"
    doc.uploaded_filename = filename
    write_doc_for_session(session, 'polls', filename, json.dumps(apidata['polls']))
    e = NewRevisionDocEvent.objects.create(doc=doc, rev=doc.rev, by=request.user.person, type='new_revision', desc='New revision available: %s'%doc.rev)
    doc.save_with_history([e])
    return HttpResponse("Done", status=200, content_type='text/plain')

@require_api_key
@role_required('Recording Manager', 'Secretariat')
@csrf_exempt
def api_upload_bluesheet(request):
    """Upload bluesheet for a session

    parameters:
      apikey: the poster's personal API key
      session_id: id of session to update
      bluesheet: json blob with
          [{'name': 'Name', 'affiliation': 'Organization', }, ...]
    """
    def err(code, text):
        return HttpResponse(text, status=code, content_type='text/plain')

    if request.method != 'POST':
        return HttpResponseNotAllowed(
            content="Method not allowed", content_type="text/plain", permitted_methods=('POST',)
        )

    # Temporary: fall back to deprecated interface if we have old-style parameters.
    # Do away with this once meetecho is using the new pk-based interface.
    if any(k in request.POST for k in ['meeting', 'group', 'item']):
        return deprecated_api_upload_bluesheet(request)

    session_id = request.POST.get('session_id', None)
    if session_id is None:
        return err(400, 'Missing session_id parameter')
    bjson = request.POST.get('bluesheet', None)
    if bjson is None:
        return err(400, 'Missing bluesheet parameter')

    try:
        session = Session.objects.get(pk=session_id)
    except Session.DoesNotExist:
        return err(400, f"Session not found with session_id '{session_id}'")
    except ValueError:
        return err(400, f"Invalid session_id '{session_id}'")

    try:
        data = json.loads(bjson)
    except json.decoder.JSONDecodeError:
        return err(400, f"Invalid json value: '{bjson}'")

    text = render_to_string('meeting/bluesheet.txt', {
            'data': data,
            'session': session,
        })

    fd, name = tempfile.mkstemp(suffix=".txt", text=True)
    os.close(fd)
    with open(name, "w") as file:
        file.write(text)
    with open(name, "br") as file:
        save_err = save_bluesheet(request, session, file)
    if save_err:
        return err(400, save_err)

    return HttpResponse("Done", status=200, content_type='text/plain')


def deprecated_api_upload_bluesheet(request):
    def err(code, text):
        return HttpResponse(text, status=code, content_type='text/plain')
    if request.method == 'POST':
        # parameters:
        #   apikey: the poster's personal API key
        #   meeting: number as string, i.e., '101', or 'interim-2018-quic-02'
        #   group: acronym or special, i.e., 'quic' or 'plenary'
        #   item: '1', '2', '3' (the group's first, second, third etc.
        #                           session during the week)
        #   bluesheet: json blob with
        #       [{'name': 'Name', 'affiliation': 'Organization', }, ...]
        for item in ['meeting', 'group', 'item', 'bluesheet',]:
            value = request.POST.get(item)
            if not value:
                return err(400, "Missing %s parameter" % item)
        number = request.POST.get('meeting')
        sessions = Session.objects.filter(meeting__number=number)
        if not sessions.exists():
            return err(400, "No sessions found for meeting '%s'" % (number, ))
        acronym = request.POST.get('group')
        sessions = sessions.filter(group__acronym=acronym)
        if not sessions.exists():
            return err(400, "No sessions found in meeting '%s' for group '%s'" % (number, acronym))
        session_times = [ (s.official_timeslotassignment().timeslot.time, s.id, s) for s in sessions if s.official_timeslotassignment() ]
        session_times.sort()
        item = request.POST.get('item')
        if not item.isdigit():
            return err(400, "Expected a numeric value for 'item', found '%s'" % (item, ))
        n = int(item)-1              # change 1-based to 0-based
        try:
            time, __, session = session_times[n]
        except IndexError:
            return err(400, "No item '%s' found in list of sessions for group" % (item, ))
        bjson = request.POST.get('bluesheet')
        try:
            data = json.loads(bjson)
        except json.decoder.JSONDecodeError:
            return err(400, "Invalid json value: '%s'" % (bjson, ))

        text = render_to_string('meeting/bluesheet.txt', {
                'data': data,
                'session': session,
            })

        fd, name = tempfile.mkstemp(suffix=".txt", text=True)
        os.close(fd)
        with open(name, "w") as file:
            file.write(text)
        with open(name, "br") as file:
            save_err = save_bluesheet(request, session, file)
        if save_err:
            return err(400, save_err)
    else:
        return err(405, "Method not allowed")

    return HttpResponse("Done", status=200, content_type='text/plain')


def important_dates(request, num=None, output_format=None):
    assert num is None or num.isdigit()
    preview_roles = ['Area Director', 'Secretariat', 'IETF Chair', 'IAD', ]

    meeting = get_ietf_meeting(num)
    if not meeting:
        raise Http404
    base_num = int(meeting.number)

    user = request.user
    today = date_today()
    meetings = []
    if meeting.show_important_dates or meeting.date < today:
        meetings.append(meeting)
    for i in range(1,3):
        future_meeting = get_ietf_meeting(base_num+i)
        if future_meeting and ( future_meeting.show_important_dates
            or (user and user.is_authenticated and has_role(user, preview_roles))):
            meetings.append(future_meeting)

    if output_format == 'ics':
        preprocess_meeting_important_dates(meetings)

        ics = render_to_string('meeting/important_dates.ics', {
            'meetings': meetings,
        }, request=request)
        # icalendar response file should have '\r\n' line endings per RFC5545
        response = HttpResponse(re.sub("\r(?!\n)|(?<!\r)\n", "\r\n", ics), content_type='text/calendar')
        response['Content-Disposition'] = 'attachment; filename="important-dates.ics"'
        return response

    return render(request, 'meeting/important-dates.html', {
        'meetings': meetings
    })

TimeSlotTypeForm = modelform_factory(TimeSlot, fields=('type',))

@role_required('Secretariat')
def edit_timeslot_type(request, num, slot_id):
    timeslot = get_object_or_404(TimeSlot,id=slot_id)
    meeting = get_object_or_404(Meeting,number=num)
    if timeslot.meeting!=meeting:
        raise Http404()
    if request.method=='POST':
        form = TimeSlotTypeForm(instance=timeslot,data=request.POST)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(reverse('ietf.meeting.views.edit_timeslots',kwargs={'num':num}))

    else:
        form = TimeSlotTypeForm(instance=timeslot)

    sessions = timeslot.sessions.filter(timeslotassignments__schedule__in=[meeting.schedule, meeting.schedule.base if meeting.schedule else None])

    return render(request, 'meeting/edit_timeslot_type.html', {'timeslot':timeslot,'form':form,'sessions':sessions})

@role_required('Secretariat')
def edit_timeslot(request, num, slot_id):
    timeslot = get_object_or_404(TimeSlot, id=slot_id)
    meeting = get_object_or_404(Meeting, number=num)
    if timeslot.meeting != meeting:
        raise Http404()
    with timezone.override(meeting.tz()):  # specifies current_timezone used for rendering and form handling
        if request.method == 'POST':
            form = TimeSlotEditForm(instance=timeslot, data=request.POST)
            if form.is_valid():
                form.save()
                redirect_to = reverse('ietf.meeting.views.edit_timeslots', kwargs={'num': num})
                if 'sched' in request.GET:
                    # Preserve 'sched' as a query parameter
                    urlparts = list(urlsplit(redirect_to))
                    query = parse_qs(urlparts[3])
                    query['sched'] = request.GET['sched']
                    urlparts[3] = urlencode(query)
                    redirect_to = urlunsplit(urlparts)
                return HttpResponseRedirect(redirect_to)
        else:
            form = TimeSlotEditForm(instance=timeslot)

        sessions = timeslot.sessions.filter(
            timeslotassignments__schedule__in=[meeting.schedule, meeting.schedule.base if meeting.schedule else None])

        return render(
            request,
            'meeting/edit_timeslot.html',
            {'timeslot': timeslot, 'form': form, 'sessions': sessions},
            status=400 if form.errors else 200,
        )


@role_required('Secretariat')
def create_timeslot(request, num):
    meeting = get_object_or_404(Meeting, number=num)
    if request.method == 'POST':
        form = TimeSlotCreateForm(meeting, data=request.POST)
        if form.is_valid():
            bulk_create_timeslots(
                meeting,
                [meeting.tz().localize(datetime.datetime.combine(day, form.cleaned_data['time']))
                 for day in form.cleaned_data.get('days', [])],
                form.cleaned_data['locations'],
                dict(
                    name=form.cleaned_data['name'],
                    type=form.cleaned_data['type'],
                    duration=form.cleaned_data['duration'],
                    show_location=form.cleaned_data['show_location'],
                )
            )
            redirect_to = reverse('ietf.meeting.views.edit_timeslots',kwargs={'num':num})
            if 'sched' in request.GET:
                # Preserve 'sched' as a query parameter
                urlparts = list(urlsplit(redirect_to))
                query = parse_qs(urlparts[3])
                query['sched'] = request.GET['sched']
                urlparts[3] = urlencode(query)
                redirect_to = urlunsplit(urlparts)
            return HttpResponseRedirect(redirect_to)
    else:
        form = TimeSlotCreateForm(meeting)

    return render(
        request,
        'meeting/create_timeslot.html',
        dict(meeting=meeting, form=form),
        status=400 if form.errors else 200,
    )


@role_required('Secretariat')
def edit_session(request, session_id):
    session = get_object_or_404(Session, pk=session_id)
    schedule = Schedule.objects.filter(pk=request.GET.get('sched', None)).first()
    editor_url = _schedule_edit_url(session.meeting, schedule)
    if request.method == 'POST':
        form = SessionEditForm(instance=session, data=request.POST)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(editor_url)
    else:
        form = SessionEditForm(instance=session)
    return render(
        request,
        'meeting/edit_session.html',
        {'session': session, 'form': form, 'editor_url': editor_url},
    )

def _schedule_edit_url(meeting, schedule):
    """Get the preferred URL to edit a schedule

    Returns a link to the official schedule if schedule is None
    """
    url_args = {'num': meeting.number}
    if schedule and not schedule.is_official:
        url_args.update({
            'name': schedule.name if schedule and not schedule.is_official else None,
            'owner': schedule.owner_email() if schedule and not schedule.is_official else None,
        })
    return reverse('ietf.meeting.views.edit_meeting_schedule', kwargs=url_args)

@role_required('Secretariat')
def cancel_session(request, session_id):
    session = get_object_or_404(Session.objects.with_current_status(), pk=session_id)
    schedule = Schedule.objects.filter(pk=request.GET.get('sched', None)).first()
    editor_url = _schedule_edit_url(session.meeting, schedule)
    if session.current_status in Session.CANCELED_STATUSES:
        messages.info(request, 'Session is already canceled.')
        return HttpResponseRedirect(editor_url)
    if request.method == 'POST':
        form = SessionCancelForm(data=request.POST)
        if form.is_valid():
            SchedulingEvent.objects.create(
                session=session,
                status_id='canceled',
                by=request.user.person,
            )
            messages.success(request, 'Session canceled.')
            return HttpResponseRedirect(editor_url)
    else:
        form = SessionCancelForm()
    return render(
        request,
        'meeting/cancel_session.html',
        {'session': session, 'form': form, 'editor_url': editor_url},
    )


@role_required('Secretariat')
def request_minutes(request, num=None):
    meeting = get_ietf_meeting(num)
    if request.method=='POST':
        form = RequestMinutesForm(data=request.POST)
        if form.is_valid():
            send_mail_text(request,
                           to=form.cleaned_data.get('to'),
                           frm=request.user.person.email_address(),
                           subject=form.cleaned_data.get('subject'),
                           txt=form.cleaned_data.get('body'),
                           cc=form.cleaned_data.get('cc'),
                          )
            return HttpResponseRedirect(reverse('ietf.meeting.views.materials',kwargs={'num':num}))
    else:
        needs_minutes = set()
        session_qs = add_event_info_to_session_qs(
            Session.objects.filter(
                timeslotassignments__schedule__meeting=meeting,
                timeslotassignments__schedule__meeting__schedule=F('timeslotassignments__schedule'),
                group__type__in=['wg','rg','ag','rag','program'],
            )
        ).filter(~Q(current_status='canceled')).select_related('group', 'group__parent')
        for session in session_qs:
            if not session.all_meeting_minutes():
                group = session.group
                if group.parent and group.parent.type_id in ('area','irtf'):
                    needs_minutes.add(group)
        needs_minutes = list(needs_minutes)
        needs_minutes.sort(key=lambda g: ('zzz' if g.parent.acronym == 'irtf' else g.parent.acronym)+":"+g.acronym)
        body_context = {'meeting':meeting, 
                        'needs_minutes':needs_minutes,
                        'settings':settings,
                       }
        body = render_to_string('meeting/request_minutes.txt', body_context)
        initial = {'to': 'wgchairs@ietf.org',
                   'cc': 'irsg@irtf.org',
                   'subject': 'Request for IETF WG and BOF Session Minutes',
                   'body': body,
                  }
        form = RequestMinutesForm(initial=initial)
    context = {'meeting':meeting, 'form': form}
    return render(request, 'meeting/request_minutes.html', context)

class ApproveSlidesForm(forms.Form):
    title = forms.CharField(max_length=255)
    apply_to_all = forms.BooleanField(label='Apply to all group sessions at this meeting',initial=False,required=False)

    def __init__(self, show_apply_to_all_checkbox, *args, **kwargs):
        super(ApproveSlidesForm, self).__init__(*args, **kwargs )
        if not show_apply_to_all_checkbox:
            self.fields.pop('apply_to_all')
            
@login_required
def approve_proposed_slides(request, slidesubmission_id, num):
    submission = get_object_or_404(SlideSubmission,pk=slidesubmission_id)
    if not submission.session.can_manage_materials(request.user):
        permission_denied(request, "You don't have permission to manage slides for this session.")
    if submission.session.is_material_submission_cutoff() and not has_role(request.user, "Secretariat"):
        permission_denied(request, "The materials cutoff for this session has passed. Contact the secretariat for further action.")   
    
    session_number = None
    sessions = get_sessions(submission.session.meeting.number,submission.session.group.acronym)
    show_apply_to_all_checkbox = len(sessions) > 1 if submission.session.type_id == 'regular' else False
    if len(sessions) > 1:
       session_number = 1 + sessions.index(submission.session)
    name, _ = os.path.splitext(submission.filename)
    name = name[:name.rfind('-ss')]
    existing_doc = Document.objects.filter(name=name).first()
    if request.method == 'POST' and submission.status.slug == 'pending':
        form = ApproveSlidesForm(show_apply_to_all_checkbox, request.POST)
        if form.is_valid():
            apply_to_all = submission.session.type_id == 'regular'
            if show_apply_to_all_checkbox:
                apply_to_all = form.cleaned_data['apply_to_all']
            if request.POST.get('approve'):
                # Ensure that we have a file to approve.  The system gets cranky otherwise.
                if submission.filename is None or submission.filename == '' or not os.path.isfile(submission.staged_filepath()):
                    return HttpResponseNotFound("The slides you attempted to approve could not be found.  Please disapprove and delete them instead.")
                title = form.cleaned_data['title']
                if existing_doc:
                   doc = Document.objects.get(name=name)
                   doc.rev = '%02d' % (int(doc.rev)+1)
                   doc.title = form.cleaned_data['title']
                else:
                    doc = Document.objects.create(
                              name = name,
                              type_id = 'slides',
                              title = title,
                              group = submission.session.group,
                              rev = '00',
                          )
                doc.states.add(State.objects.get(type_id='slides',slug='active'))
                doc.states.add(State.objects.get(type_id='reuse_policy',slug='single'))
                added_presentations = []
                revised_presentations = []
                if submission.session.presentations.filter(document=doc).exists():
                    sp = submission.session.presentations.get(document=doc)
                    sp.rev = doc.rev
                    sp.save()
                    revised_presentations.append(sp)
                else:
                    max_order = submission.session.presentations.filter(document__type='slides').aggregate(Max('order'))['order__max'] or 0
                    added_presentations.append(
                        submission.session.presentations.create(document=doc,rev=doc.rev,order=max_order+1)
                    )
                if apply_to_all:
                    for other_session in sessions:
                        if other_session != submission.session and not other_session.presentations.filter(document=doc).exists():
                            max_order = other_session.presentations.filter(document__type='slides').aggregate(Max('order'))['order__max'] or 0
                            added_presentations.append(
                                other_session.presentations.create(document=doc,rev=doc.rev,order=max_order+1)
                            )
                sub_name, sub_ext = os.path.splitext(submission.filename)
                target_filename = '%s-%s%s' % (sub_name[:sub_name.rfind('-ss')],doc.rev,sub_ext)
                doc.uploaded_filename = target_filename
                e = NewRevisionDocEvent.objects.create(doc=doc,by=submission.submitter,type='new_revision',desc='New revision available: %s'%doc.rev,rev=doc.rev)
                doc.save_with_history([e])
                path = os.path.join(submission.session.meeting.get_materials_path(),'slides')
                if not os.path.exists(path):
                    os.makedirs(path)
                shutil.move(submission.staged_filepath(), os.path.join(path, target_filename))
                post_process(doc)
                DocEvent.objects.create(type="approved_slides", doc=doc, rev=doc.rev, by=request.user.person, desc="Slides approved")

                # update meetecho slide info if configured
                if hasattr(settings, "MEETECHO_API_CONFIG"):
                    sm = SlidesManager(api_config=settings.MEETECHO_API_CONFIG)
                    for sp in added_presentations:
                        try:
                            sm.add(session=sp.session, slides=doc, order=sp.order)
                        except MeetechoAPIError as err:
                            log(f"Error in SlidesManager.add(): {err}")
                    for sp in revised_presentations:
                        try:
                            sm.revise(session=sp.session, slides=doc)
                        except MeetechoAPIError as err:
                            log(f"Error in SlidesManager.revise(): {err}")

                acronym = submission.session.group.acronym
                submission.status = SlideSubmissionStatusName.objects.get(slug='approved')
                submission.doc = doc
                submission.save()
                (to, cc) = gather_address_lists('slides_approved', group=submission.session.group, proposer=submission.submitter).as_strings()
                subject = f"Slides approved for {submission.session.meeting} : {submission.session.group.acronym}{' : '+submission.session.name if submission.session.name else ''}"
                body = render_to_string("meeting/slides_approved.txt", {
                    "to": to,
                    "cc": cc,
                    "submission": submission,
                    "settings": settings,
                    "approver": request.user.person
                })
                send_mail_text(request, to, None, subject, body, cc=cc)
                return redirect('ietf.meeting.views.session_details',num=num,acronym=acronym)
            elif request.POST.get('disapprove'):
                # Errors in processing a submit request sometimes result
                # in a SlideSubmission object without a file.  Handle
                # this case and keep processing the 'disapprove' even if
                # the filename doesn't exist.
                try:
                    if submission.filename != None and submission.filename != '':
                        os.unlink(submission.staged_filepath())
                except (FileNotFoundError, IsADirectoryError):
                    pass
                acronym = submission.session.group.acronym
                submission.status = SlideSubmissionStatusName.objects.get(slug='rejected')
                submission.save()
                return redirect('ietf.meeting.views.session_details',num=num,acronym=acronym)
            else:
                pass
    elif not submission.status.slug == 'pending':
        return render(request, "meeting/previously_approved_slides.html",
                      {'submission': submission })
    else:
        initial = {
            'title': submission.title,
            'apply_to_all' : submission.apply_to_all,
        }
        form = ApproveSlidesForm(show_apply_to_all_checkbox, initial=initial )

    return render(request, "meeting/approve_proposed_slides.html",
                  {'submission': submission,
                   'session_number': session_number,
                   'existing_doc' : existing_doc,
                   'form': form,
                  })


def import_session_minutes(request, session_id, num):
    """Import session minutes from the ietf.notes.org site

    A GET pulls in the markdown for a session's notes using the HedgeDoc API. An HTML preview of how
    the datatracker will render the result is sent back. The confirmation form presented to the user
    contains a hidden copy of the markdown source that will be submitted back if approved.

    A POST accepts the hidden source and creates a new revision of the notes. This step does *not*
    retrieve the note from the HedgeDoc API again - it posts the hidden source from the form. Any
    changes to the HedgeDoc site after the preview was retrieved will be ignored. We could also pull
    the source again and re-display the updated preview with an explanatory message, but there will
    always be a race condition. Rather than add that complication, we assume that the user previewing
    the imported minutes will be aware of anyone else changing the notes and coordinate with them.

    A consequence is that the user could tamper with the hidden form and it would be accepted. This is
    ok, though, because they could more simply upload whatever they want through the upload form with
    the same effect so no exploit is introduced.
    """
    session = get_object_or_404(Session, pk=session_id)
    note = Note(session.notes_id())

    if not session.can_manage_materials(request.user):
        permission_denied(request, "You don't have permission to import minutes for this session.")
    if session.is_material_submission_cutoff() and not has_role(request.user, "Secretariat"):
        permission_denied(request, "The materials cutoff for this session has passed. Contact the secretariat for further action.")

    if request.method == 'POST':
        form = ImportMinutesForm(request.POST)
        if not form.is_valid():
            import_contents = form.data['markdown_text']
        else:
            import_contents = form.cleaned_data['markdown_text']
            try:
                save_session_minutes_revision(
                    session=session,
                    file=io.BytesIO(import_contents.encode('utf8')),
                    ext='.md',
                    request=request,
                )
            except SessionNotScheduledError:
                return HttpResponseGone(
                    "Cannot import minutes for an unscheduled session. Please check the session ID.",
                    content_type="text/plain",
                )
            except SaveMaterialsError as err:
                form.add_error(None, str(err))
            else:
                messages.success(request, f'Successfully imported minutes as revision {session.minutes().rev}.')
                return redirect('ietf.meeting.views.session_details', num=num, acronym=session.group.acronym)
    else:
        try:
            import_contents = note.get_source()
        except NoteError as err:
            messages.error(request, f'Could not import notes with id {note.id}: {err}.')
            return redirect('ietf.meeting.views.session_details', num=num, acronym=session.group.acronym)
        form = ImportMinutesForm(initial={'markdown_text': import_contents})

    # Try to prevent pointless revision creation. Note that we do not block replacing
    # a document with an identical copy in the validation above. We cannot entirely
    # avoid a race condition and the likelihood/amount of damage is very low so no
    # need to complicate things further.
    current_minutes = session.minutes()
    contents_changed = True
    if current_minutes:
        try:
            with open(current_minutes.get_file_name()) as f:
                if import_contents == f.read():
                    contents_changed = False
                    messages.warning(request, 'This document is identical to the current revision, no need to import.')
        except Exception:
            pass  # Do not let a failure here prevent minutes from being updated.

    return render(
        request,
        'meeting/import_minutes.html',
        {
            'form': form,
            'note': note,
            'session': session,
            'contents_unchanged': not contents_changed,
        },
    )
