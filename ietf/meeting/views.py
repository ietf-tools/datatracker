# Copyright The IETF Trust 2007-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import csv
import datetime
import glob
import io
import itertools
import json
import os
import pytz
import re
import tarfile
import markdown2


from calendar import timegm
from collections import OrderedDict, Counter, deque
from urllib.parse import unquote
from tempfile import mkstemp
from wsgiref.handlers import format_date_time

import debug                            # pyflakes:ignore

from django import forms
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseForbidden, Http404
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.urls import reverse,reverse_lazy
from django.db.models import F, Min, Max, Prefetch, Q
from django.forms.models import modelform_factory, inlineformset_factory
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string
from django.utils.encoding import force_str
from django.utils.functional import curry
from django.utils.text import slugify
from django.views.decorators.cache import cache_page
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.views.generic import RedirectView


from ietf.doc.fields import SearchableDocumentsField
from ietf.doc.models import Document, State, DocEvent, NewRevisionDocEvent, DocAlias
from ietf.group.models import Group
from ietf.group.utils import can_manage_session_materials
from ietf.person.models import Person
from ietf.ietfauth.utils import role_required, has_role
from ietf.mailtrigger.utils import gather_address_lists
from ietf.meeting.models import Meeting, Session, Schedule, FloorPlan, SessionPresentation, TimeSlot, SlideSubmission, SessionStatusName, SchedulingEvent, SchedTimeSessAssignment
from ietf.meeting.helpers import get_areas, get_person_by_email, get_schedule_by_name
from ietf.meeting.helpers import build_all_agenda_slices, get_wg_name_list
from ietf.meeting.helpers import get_all_assignments_from_schedule
from ietf.meeting.helpers import get_modified_from_assignments
from ietf.meeting.helpers import get_wg_list, find_ads_for_meeting
from ietf.meeting.helpers import get_meeting, get_schedule, schedule_permissions, get_ietf_meeting
from ietf.meeting.helpers import preprocess_assignments_for_agenda, read_agenda_file
from ietf.meeting.helpers import convert_draft_to_pdf, get_earliest_session_date
from ietf.meeting.helpers import can_view_interim_request, can_approve_interim_request
from ietf.meeting.helpers import can_edit_interim_request
from ietf.meeting.helpers import can_request_interim_meeting, get_announcement_initial
from ietf.meeting.helpers import sessions_post_save, is_interim_meeting_approved
from ietf.meeting.helpers import send_interim_cancellation_notice
from ietf.meeting.helpers import send_interim_approval_request
from ietf.meeting.helpers import send_interim_announcement_request
from ietf.meeting.utils import finalize, sort_accept_tuple, condition_slide_order
from ietf.meeting.utils import add_event_info_to_session_qs
from ietf.meeting.utils import session_time_for_sorting
from ietf.meeting.utils import session_requested_by
from ietf.meeting.utils import current_session_status
from ietf.meeting.utils import data_for_meetings_overview
from ietf.message.utils import infer_message
from ietf.secr.proceedings.utils import handle_upload_file
from ietf.secr.proceedings.proc_utils import (get_progress_stats, post_process, import_audio_files,
    create_recording)
from ietf.utils.decorators import require_api_key
from ietf.utils.log import assertion
from ietf.utils.mail import send_mail_message, send_mail_text
from ietf.utils.pipe import pipe
from ietf.utils.pdf import pdf_pages
from ietf.utils.text import xslugify
from ietf.utils.mime import get_mime_type

from .forms import (InterimMeetingModelForm, InterimAnnounceForm, InterimSessionModelForm,
    InterimCancelForm, InterimSessionInlineFormSet, FileUploadForm, RequestMinutesForm,)


def get_interim_menu_entries(request):
    '''Setup menu entries for interim meeting view tabs'''
    entries = []
    if has_role(request.user, ('Area Director','Secretariat','IRTF Chair','WG Chair', 'RG Chair')):
        entries.append(("Upcoming", reverse("ietf.meeting.views.upcoming")))
        entries.append(("Pending", reverse("ietf.meeting.views.interim_pending")))
        if has_role(request.user, "Secretariat"):
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
    now = datetime.date.today()
    old = datetime.datetime.now() - datetime.timedelta(days=1)
    if settings.SERVER_MODE != 'production' and '_testoverride' in request.GET:
        pass
    elif now > cor_cut_off_date:
        if meeting.number.isdigit() and int(meeting.number) > 96:
            return redirect('ietf.meeting.views.proceedings', num=meeting.number)
        else:
            return render(request, "meeting/materials_upload_closed.html", {
                'meeting_num': meeting.number,
                'begin_date': begin_date,
                'cut_off_date': cut_off_date,
                'cor_cut_off_date': cor_cut_off_date
            })

    past_cutoff_date = datetime.date.today() > meeting.get_submission_correction_date()

    schedule = get_schedule(meeting, None)

    sessions  = add_event_info_to_session_qs(Session.objects.filter(
        meeting__number=meeting.number,
        timeslotassignments__schedule=schedule
    ).distinct().select_related('meeting__schedule', 'group__state', 'group__parent'))

    plenaries = sessions.filter(name__icontains='plenary')
    ietf      = sessions.filter(group__parent__type__slug = 'area').exclude(group__acronym='edu')
    irtf      = sessions.filter(group__parent__acronym = 'irtf')
    training  = sessions.filter(group__acronym__in=['edu','iaoc'], type_id__in=['regular', 'other', ])
    iab       = sessions.filter(group__parent__acronym = 'iab')

    session_pks = [s.pk for ss in [plenaries, ietf, irtf, training, iab] for s in ss]
    other     = sessions.filter(type__in=['regular'], group__type__features__has_meetings=True).exclude(pk__in=session_pks)

    for topic in [plenaries, ietf, training, irtf, iab]:
        for event in topic:
            date_list = []
            for slide_event in event.all_meeting_slides(): date_list.append(slide_event.time)
            for agenda_event in event.all_meeting_agendas(): date_list.append(agenda_event.time)
            if date_list: setattr(event, 'last_update', sorted(date_list, reverse=True)[0])

    for session_list in [plenaries, ietf, training, irtf, iab, other]:
        for session in session_list:
            session.past_cutoff_date = past_cutoff_date
            
    return render(request, "meeting/materials.html", {
        'meeting': meeting,
        'plenaries': plenaries,
        'ietf': ietf,
        'training': training,
        'irtf': irtf,
        'iab': iab,
        'other': other,
        'cut_off_date': cut_off_date,
        'cor_cut_off_date': cor_cut_off_date,
        'submission_started': now > begin_date,
        'old': old,
    })

def current_materials(request):
    today = datetime.date.today()
    meetings = Meeting.objects.exclude(number__startswith='interim-').filter(date__lte=today).order_by('-date')
    if meetings:
        return redirect(materials, meetings[0].number)
    else:
        raise Http404('No such meeting')

@cache_page(1 * 60)
def materials_document(request, document, num=None, ext=None):
    if num is None:
        num = get_meeting(num).number
    if (re.search(r'^\w+-\d+-.+-\d\d$', document) or
        re.search(r'^\w+-interim-\d+-.+-\d\d-\d\d$', document) or
        re.search(r'^\w+-interim-\d+-.+-sess[a-z]-\d\d$', document) or
        re.search(r'^minutes-interim-\d+-.+-\d\d$', document) or
        re.search(r'^slides-interim-\d+-.+-\d\d$', document)):
        name, rev = document.rsplit('-', 1)
    else:
        name, rev = document, None
    doc = get_object_or_404(Document, name=name)
    if not doc.meeting_related():
        raise Http404("Not a meeting related document")
    if not doc.session_set.filter(meeting__number=num).exists():
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
    with io.open(filename, 'rb') as file:
        bytes = file.read()
    
    mtype, chset = get_mime_type(bytes)
    content_type = "%s; charset=%s" % (mtype, chset)

    file_ext = os.path.splitext(filename)
    if len(file_ext) == 2 and file_ext[1] == '.md' and mtype == 'text/plain':
        sorted_accept = sort_accept_tuple(request.META.get('HTTP_ACCEPT'))
        for atype in sorted_accept:
            if atype[0] == 'text/markdown':
                content_type = content_type.replace('plain', 'markdown', 1)
                break;
            elif atype[0] == 'text/html':
                bytes = "<html>\n<head></head>\n<body>\n%s\n</body>\n</html>\n" % markdown2.markdown(bytes)
                content_type = content_type.replace('plain', 'html', 1)
                break;
            elif atype[0] == 'text/plain':
                break;

    response = HttpResponse(bytes, content_type=content_type)
    response['Content-Disposition'] = 'inline; filename="%s"' % basename
    return response

@login_required
def materials_editable_groups(request, num=None):
    meeting = get_meeting(num)
    return render(request, "meeting/materials_editable_groups.html", {
        'meeting_num': meeting.number})

def ascii_alphanumeric(string):
    return re.match(r'^[a-zA-Z0-9]*$', string)

class SaveAsForm(forms.Form):
    savename = forms.CharField(max_length=16)

@role_required('Area Director','Secretariat')
def schedule_create(request, num=None, owner=None, name=None):
    meeting  = get_meeting(num)
    person   = get_person_by_email(owner)
    schedule = get_schedule_by_name(meeting, person, name)

    if schedule is None:
        # here we have to return some ajax to display an error.
        messages.error("Error: No meeting information for meeting %s owner %s schedule %s available" % (num, owner, name)) # pylint: disable=no-value-for-parameter
        return redirect(edit_schedule, num=num, owner=owner, name=name)

    # authorization was enforced by the @group_require decorator above.

    saveasform = SaveAsForm(request.POST)
    if not saveasform.is_valid():
        messages.info(request, "This name is not valid. Please choose another one.")
        return redirect(edit_schedule, num=num, owner=owner, name=name)

    savedname = saveasform.cleaned_data['savename']

    if not ascii_alphanumeric(savedname):
        messages.info(request, "This name contains illegal characters. Please choose another one.")
        return redirect(edit_schedule, num=num, owner=owner, name=name)

    # create the new schedule, and copy the assignments
    try:
        sched = meeting.schedule_set.get(name=savedname, owner=request.user.person)
        if sched:
            return redirect(edit_schedule, num=meeting.number, owner=sched.owner_email(), name=sched.name)
        else:
            messages.info(request, "Schedule creation failed. Please try again.")
            return redirect(edit_schedule, num=num, owner=owner, name=name)

    except Schedule.DoesNotExist:
        pass

    # must be done
    newschedule = Schedule(name=savedname,
                           owner=request.user.person,
                           meeting=meeting,
                           visible=False,
                           public=False)

    newschedule.save()
    if newschedule is None:
        return HttpResponse(status=500)

    # keep a mapping so that extendedfrom references can be chased.
    mapping = {};
    for ss in schedule.assignments.all():
        # hack to copy the object, creating a new one
        # just reset the key, and save it again.
        oldid = ss.pk
        ss.pk = None
        ss.schedule=newschedule
        ss.save()
        mapping[oldid] = ss.pk
        #print "Copying %u to %u" % (oldid, ss.pk)

    # now fix up any extendedfrom references to new set.
    for ss in newschedule.assignments.all():
        if ss.extendedfrom is not None:
            oldid = ss.extendedfrom.id
            newid = mapping[oldid]
            #print "Fixing %u to %u" % (oldid, newid)
            ss.extendedfrom = newschedule.assignments.get(pk = newid)
            ss.save()


    # now redirect to this new schedule.
    return redirect(edit_schedule, meeting.number, newschedule.owner_email(), newschedule.name)


@role_required('Secretariat')
def edit_timeslots(request, num=None):

    meeting = get_meeting(num)

    time_slices,date_slices,slots = meeting.build_timeslices()

    ts_list = deque()
    rooms = meeting.room_set.order_by("capacity","name","id")
    for room in rooms:
        for day in time_slices:
            for slice in date_slices[day]:
                ts_list.append(room.timeslot_set.filter(time=slice[0],duration=datetime.timedelta(seconds=slice[2])).first())
            

    return render(request, "meeting/timeslot_edit.html",
                                         {"rooms":rooms,
                                          "time_slices":time_slices,
                                          "slot_slices": slots,
                                          "date_slices":date_slices,
                                          "meeting":meeting,
                                          "ts_list":ts_list,
                                      })

##############################################################################
#@role_required('Area Director','Secretariat')
# disable the above security for now, check it below.
@ensure_csrf_cookie
def edit_schedule(request, num=None, owner=None, name=None):

    if request.method == 'POST':
        return schedule_create(request, num, owner, name)

    user     = request.user
    meeting  = get_meeting(num)
    person   = get_person_by_email(owner)
    if name is None:
        schedule = meeting.schedule
    else:
        schedule = get_schedule_by_name(meeting, person, name)
    if schedule is None:
        raise Http404("No meeting information for meeting %s owner %s schedule %s available" % (num, owner, name))

    meeting_base_url = request.build_absolute_uri(meeting.base_url())
    site_base_url = request.build_absolute_uri('/')[:-1] # skip the trailing slash

    rooms = meeting.room_set.filter(session_types__slug='regular').distinct().order_by("capacity")
    saveas = SaveAsForm()
    saveasurl=reverse(edit_schedule,
                      args=[meeting.number, schedule.owner_email(), schedule.name])

    can_see, can_edit,secretariat = schedule_permissions(meeting, schedule, user)

    if not can_see:
        return render(request, "meeting/private_schedule.html",
                                             {"schedule":schedule,
                                              "meeting": meeting,
                                              "meeting_base_url":meeting_base_url,
                                              "hide_menu": True
                                          }, status=403, content_type="text/html")

    assignments = get_all_assignments_from_schedule(schedule)

    # get_modified_from needs the query set, not the list
    modified = get_modified_from_assignments(assignments)

    area_list = get_areas()
    wg_name_list = get_wg_name_list(assignments)
    wg_list = get_wg_list(wg_name_list)
    ads = find_ads_for_meeting(meeting)
    for ad in ads:
        # set the default to avoid needing extra arguments in templates
        # django 1.3+
        ad.default_hostscheme = site_base_url

    time_slices,date_slices = build_all_agenda_slices(meeting)

    return render(request, "meeting/landscape_edit.html",
                                         {"schedule":schedule,
                                          "saveas": saveas,
                                          "saveasurl": saveasurl,
                                          "meeting_base_url": meeting_base_url,
                                          "site_base_url": site_base_url,
                                          "rooms":rooms,
                                          "time_slices":time_slices,
                                          "date_slices":date_slices,
                                          "modified": modified,
                                          "meeting":meeting,
                                          "area_list": area_list,
                                          "area_directors" : ads,
                                          "wg_list": wg_list ,
                                          "assignments": assignments,
                                          "show_inline": set(["txt","htm","html"]),
                                          "hide_menu": True,
                                      })

##############################################################################
#  show the properties associated with a schedule (visible, public)
#
SchedulePropertiesForm = modelform_factory(Schedule, fields=('name','visible', 'public'))

# The meeing urls.py won't allow empy num, owmer, or name values

@role_required('Area Director','Secretariat')
def edit_schedule_properties(request, num=None, owner=None, name=None):
    meeting  = get_meeting(num)
    person   = get_person_by_email(owner)
    schedule = get_schedule_by_name(meeting, person, name)
    if schedule is None:
        raise Http404("No meeting information for meeting %s owner %s schedule %s available" % (num, owner, name))

    cansee, canedit, secretariat = schedule_permissions(meeting, schedule, request.user)

    if not (canedit or has_role(request.user,'Secretariat')):
        return HttpResponseForbidden("You may not edit this schedule")
    else:
        if request.method == 'POST':
            form = SchedulePropertiesForm(instance=schedule,data=request.POST)
            if form.is_valid():
               form.save()
               return HttpResponseRedirect(reverse('ietf.meeting.views.list_schedules',kwargs={'num': num}))
        else: 
            form = SchedulePropertiesForm(instance=schedule)
        return render(request, "meeting/properties_edit.html",
                                             {"schedule":schedule,
                                              "form":form,
                                              "meeting":meeting,
                                          })

##############################################################################
# show list of schedules.
#

@role_required('Area Director','Secretariat')
def list_schedules(request, num=None ):

    meeting = get_meeting(num)
    user = request.user

    schedules = meeting.schedule_set
    if not has_role(user, 'Secretariat'):
        schedules = schedules.filter(visible = True) | schedules.filter(owner = user.person)

    schedules = schedules.order_by('owner', 'name')

    schedules = sorted(list(schedules),key=lambda x:not x.is_official)

    return render(request, "meeting/schedule_list.html",
                                         {"meeting":   meeting,
                                          "schedules": schedules,
                                          })

@ensure_csrf_cookie
def agenda(request, num=None, name=None, base=None, ext=None, owner=None, utc=""):
    base = base if base else 'agenda'
    ext = ext if ext else '.html'
    mimetype = {
        ".html":"text/html; charset=%s"%settings.DEFAULT_CHARSET,
        ".txt": "text/plain; charset=%s"%settings.DEFAULT_CHARSET,
        ".csv": "text/csv; charset=%s"%settings.DEFAULT_CHARSET,
    }

    # We do not have the appropriate data in the datatracker for IETF 64 and earlier.
    # So that we're not producing misleading pages...
    
    assert num is None or num.isdigit()

    meeting = get_ietf_meeting(num)
    if not meeting or (meeting.number.isdigit() and int(meeting.number) <= 64 and (not meeting.schedule or not meeting.schedule.assignments.exists())):
        if ext == '.html' or (meeting and meeting.number.isdigit() and 0 < int(meeting.number) <= 64):
            return HttpResponseRedirect( 'https://www.ietf.org/proceedings/%s' % num )
        else:
            raise Http404("No such meeting")

    if name is None:
        schedule = get_schedule(meeting, name)
    else:
        person   = get_person_by_email(owner)
        schedule = get_schedule_by_name(meeting, person, name)

    if schedule == None:
        base = base.replace("-utc", "")
        return render(request, "meeting/no-"+base+ext, {'meeting':meeting }, content_type=mimetype[ext])

    updated = meeting.updated()
    filtered_assignments = schedule.assignments.exclude(timeslot__type__in=['lead','offagenda'])
    filtered_assignments = preprocess_assignments_for_agenda(filtered_assignments, meeting)

    if ext == ".csv":
        return agenda_csv(schedule, filtered_assignments)

    # extract groups hierarchy, it's a little bit complicated because
    # we can be dealing with historic groups
    seen = set()
    groups = [a.session.historic_group for a in filtered_assignments
              if a.session
              and a.session.historic_group
              and a.session.historic_group.type_id in ('wg', 'rg', 'ag', 'iab')
              and a.session.historic_group.historic_parent]
    group_parents = []
    for g in groups:
        if g.historic_parent.acronym not in seen:
            group_parents.append(g.historic_parent)
            seen.add(g.historic_parent.acronym)

    seen = set()
    for p in group_parents:
        p.group_list = []
        for g in groups:
            if g.acronym not in seen and g.historic_parent.acronym == p.acronym:
                p.group_list.append(g)
                seen.add(g.acronym)

        p.group_list.sort(key=lambda g: g.acronym)

    return render(request, "meeting/"+base+ext, {
        "schedule": schedule,
        "filtered_assignments": filtered_assignments,
        "updated": updated,
        "group_parents": group_parents,
        "now": datetime.datetime.now(),
    }, content_type=mimetype[ext])

def agenda_csv(schedule, filtered_assignments):
    response = HttpResponse(content_type="text/csv; charset=%s"%settings.DEFAULT_CHARSET)
    writer = csv.writer(response, delimiter=str(','), quoting=csv.QUOTE_ALL)

    headings = ["Date", "Start", "End", "Session", "Room", "Area", "Acronym", "Type", "Description", "Session ID", "Agenda", "Slides"]

    def write_row(row):
        encoded_row = [v.encode('utf-8') if isinstance(v, str) else v for v in row]

        while len(encoded_row) < len(headings):
            encoded_row.append(None) # produce empty entries at the end as necessary

        writer.writerow(encoded_row)

    def agenda_field(item):
        agenda_doc = item.session.agenda()
        if agenda_doc:
            return "http://www.ietf.org/proceedings/{schedule.meeting.number}/agenda/{agenda.uploaded_filename}".format(schedule=schedule, agenda=agenda_doc)
        else:
            return ""

    def slides_field(item):
        return "|".join("http://www.ietf.org/proceedings/{schedule.meeting.number}/slides/{slide.uploaded_filename}".format(schedule=schedule, slide=slide) for slide in item.session.slides())

    write_row(headings)

    for item in filtered_assignments:
        row = []
        row.append(item.timeslot.time.strftime("%Y-%m-%d"))
        row.append(item.timeslot.time.strftime("%H%M"))
        row.append(item.timeslot.end_time().strftime("%H%M"))

        if item.timeslot.type_id == "break":
            row.append(item.timeslot.type.name)
            row.append(schedule.meeting.break_area)
            row.append("")
            row.append("")
            row.append("")
            row.append(item.timeslot.name)
            row.append("b{}".format(item.timeslot.pk))
        elif item.timeslot.type_id == "reg":
            row.append(item.timeslot.type.name)
            row.append(schedule.meeting.reg_area)
            row.append("")
            row.append("")
            row.append("")
            row.append(item.timeslot.name)
            row.append("r{}".format(item.timeslot.pk))
        elif item.timeslot.type_id == "other":
            row.append("None")
            row.append(item.timeslot.location.name if item.timeslot.location else "")
            row.append("")
            row.append(item.session.historic_group.acronym)
            row.append(item.session.historic_group.historic_parent.acronym.upper() if item.session.historic_group.historic_parent else "")
            row.append(item.session.name)
            row.append(item.session.pk)
        elif item.timeslot.type_id == "plenary":
            row.append(item.session.name)
            row.append(item.timeslot.location.name if item.timeslot.location else "")
            row.append("")
            row.append(item.session.historic_group.acronym if item.session.historic_group else "")
            row.append("")
            row.append(item.session.name)
            row.append(item.session.pk)
            row.append(agenda_field(item))
            row.append(slides_field(item))
        elif item.timeslot.type_id == 'regular':
            row.append(item.timeslot.name)
            row.append(item.timeslot.location.name if item.timeslot.location else "")
            row.append(item.session.historic_group.historic_parent.acronym.upper() if item.session.historic_group.historic_parent else "")
            row.append(item.session.historic_group.acronym if item.session.historic_group else "")
            row.append("BOF" if item.session.historic_group.state_id in ("bof", "bof-conc") else item.session.historic_group.type.name)
            row.append(item.session.historic_group.name if item.session.historic_group else "")
            row.append(item.session.pk)
            row.append(agenda_field(item))
            row.append(slides_field(item))

        if len(row) > 3:
            write_row(row)

    return response

@role_required('Area Director','Secretariat','IAB')
def agenda_by_room(request, num=None, name=None, owner=None):
    meeting = get_meeting(num) 
    if name is None:
        schedule = get_schedule(meeting)
    else:
        person   = get_person_by_email(owner)
        schedule = get_schedule_by_name(meeting, person, name)
    ss_by_day = OrderedDict()
    for day in schedule.assignments.dates('timeslot__time','day'):
        ss_by_day[day]=[]
    for ss in schedule.assignments.order_by('timeslot__location__functional_name','timeslot__location__name','timeslot__time'):
        day = ss.timeslot.time.date()
        ss_by_day[day].append(ss)
    return render(request,"meeting/agenda_by_room.html",{"meeting":meeting,"schedule":schedule,"ss_by_day":ss_by_day})

@role_required('Area Director','Secretariat','IAB')
def agenda_by_type(request, num=None, type=None, name=None, owner=None):
    meeting = get_meeting(num) 
    if name is None:
        schedule = get_schedule(meeting)
    else:
        person   = get_person_by_email(owner)
        schedule = get_schedule_by_name(meeting, person, name)
    assignments = schedule.assignments.order_by('session__type__slug','timeslot__time','session__group__acronym')
    if type:
        assignments = assignments.filter(session__type__slug=type)
    return render(request,"meeting/agenda_by_type.html",{"meeting":meeting,"schedule":schedule,"assignments":assignments})

@role_required('Area Director','Secretariat','IAB')
def agenda_by_type_ics(request,num=None,type=None):
    meeting = get_meeting(num) 
    schedule = get_schedule(meeting)
    assignments = schedule.assignments.order_by('session__type__slug','timeslot__time')
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

def week_view(request, num=None, name=None, owner=None):
    meeting = get_meeting(num)

    if name is None:
        schedule = get_schedule(meeting)
    else:
        person   = get_person_by_email(owner)
        schedule = get_schedule_by_name(meeting, person, name)

    if not schedule:
        raise Http404

    filtered_assignments = schedule.assignments.exclude(timeslot__type__in=['lead','offagenda'])
    filtered_assignments = preprocess_assignments_for_agenda(filtered_assignments, meeting)
    
    items = []
    for a in filtered_assignments:
        # we don't HTML escape any of these as the week-view code is using createTextNode
        item = {
            "key": str(a.timeslot.pk),
            "day": a.timeslot.time.strftime("%w"),
            "time": a.timeslot.time.strftime("%H%M") + "-" + a.timeslot.end_time().strftime("%H%M"),
            "duration": a.timeslot.duration.seconds,
            "time_id": a.timeslot.time.strftime("%m%d%H%M"),
            "dayname": "{weekday}, {month} {day_of_month}, {year}".format(
                weekday=a.timeslot.time.strftime("%A").upper(),
                month=a.timeslot.time.strftime("%B"),
                day_of_month=a.timeslot.time.strftime("%d").lstrip("0"),
                year=a.timeslot.time.strftime("%Y"),
            ),
            "type": a.timeslot.type.name
        }

        if a.session:
            if a.session.historic_group:
                item["group"] = a.session.historic_group.acronym

            if a.session.name:
                item["name"] = a.session.name
            elif a.timeslot.type_id == "break":
                item["name"] = a.timeslot.name
                item["area"] = a.timeslot.type_id
                item["group"] = a.timeslot.type_id
            elif a.session.historic_group:
                item["name"] = a.session.historic_group.name
                if a.session.historic_group.state_id == "bof":
                    item["name"] += " BOF"

                item["state"] = a.session.historic_group.state.name
                if a.session.historic_group.historic_parent:
                    item["area"] = a.session.historic_group.historic_parent.acronym

            if a.timeslot.show_location:
                item["room"] = a.timeslot.get_location()

            if a.session and a.session.agenda():
                item["agenda"] = a.session.agenda().get_href()

            if a.session.current_status == 'canceled':
                item["name"] = "CANCELLED - " + item["name"]

        items.append(item)

    return render(request, "meeting/week-view.html", {
        "items": json.dumps(items),
    })

@role_required('Area Director','Secretariat','IAB')
def room_view(request, num=None, name=None, owner=None):
    meeting = get_meeting(num)

    rooms = meeting.room_set.order_by('functional_name','name')
    if not rooms.exists():
        return HttpResponse("No rooms defined yet")

    if name is None:
        schedule = get_schedule(meeting)
    else:
        person   = get_person_by_email(owner)
        schedule = get_schedule_by_name(meeting, person, name)

    assignments = schedule.assignments.all()
    unavailable = meeting.timeslot_set.filter(type__slug='unavail')
    if not (assignments.exists() or unavailable.exists()):
        return HttpResponse("No sessions/timeslots available yet")

    earliest = None
    latest = None

    if assignments:
        earliest = assignments.aggregate(Min('timeslot__time'))['timeslot__time__min']
        latest =  assignments.aggregate(Max('timeslot__time'))['timeslot__time__max']
        
    if unavailable:
        earliest_unavailable = unavailable.aggregate(Min('time'))['time__min']
        if not earliest or ( earliest_unavailable and earliest_unavailable < earliest ):
            earliest = earliest_unavailable
        latest_unavailable = unavailable.aggregate(Max('time'))['time__max']
        if not latest or ( latest_unavailable and latest_unavailable > latest ):
            latest = latest_unavailable

    if not (earliest and latest):
        raise Http404

    base_time = earliest
    base_day = datetime.datetime(base_time.year,base_time.month,base_time.day)

    day = base_day
    days = []
    while day <= latest :
        days.append(day)
        day += datetime.timedelta(days=1)

    unavailable = list(unavailable)
    for t in unavailable:
        t.delta_from_beginning = (t.time - base_time).total_seconds()
        t.day = (t.time-base_day).days

    assignments = list(assignments)
    for ss in assignments:
        ss.delta_from_beginning = (ss.timeslot.time - base_time).total_seconds()
        ss.day = (ss.timeslot.time-base_day).days

    template = "meeting/room-view.html"
    return render(request, template,{"meeting":meeting,"schedule":schedule,"unavailable":unavailable,"assignments":assignments,"rooms":rooms,"days":days})

def ical_session_status(session_with_current_status):
    if session_with_current_status == 'canceled':
        return "CANCELLED"
    else:
        return "CONFIRMED"

def ical_agenda(request, num=None, name=None, acronym=None, session_id=None):
    meeting = get_meeting(num, type_in=None)
    schedule = get_schedule(meeting, name)
    updated = meeting.updated()

    if schedule is None and acronym is None and session_id is None:
        raise Http404

    q = request.META.get('QUERY_STRING','') or ""
    filter = set(unquote(q).lower().split(','))
    include = [ i for i in filter if not (i.startswith('-') or i.startswith('~')) ]
    include_types = set(["plenary","other"])
    exclude = []

    # Process the special flags.
    #   "-wgname" will remove a working group from the output.
    #   "~Type" will add that type to the output.
    #   "-~Type" will remove that type from the output
    # Current types are:
    #   Session, Other (default on), Break, Plenary (default on)
    # Non-Working Group "wg names" include:
    #   edu, ietf, tools, iesg, iab

    for item in filter:
        if len(item) > 2 and item[0] == '-' and item[1] == '~':
            include_types -= set([item[2:]])
        elif len(item) > 1 and item[0] == '-':
            exclude.append(item[1:])
        elif len(item) > 1 and item[0] == '~':
            include_types |= set([item[1:]])

    assignments = schedule.assignments.exclude(timeslot__type__in=['lead','offagenda'])
    assignments = preprocess_assignments_for_agenda(assignments, meeting)

    if q:
        assignments = [a for a in assignments if
                   (a.timeslot.type_id in include_types
                    or (a.session.historic_group and a.session.historic_group.acronym in include)
                    or (a.session.historic_group and a.session.historic_group.historic_parent and a.session.historic_group.historic_parent.acronym in include))
                   and (not a.session.historic_group or a.session.historic_group.acronym not in exclude)]

    if acronym:
        assignments = [ a for a in assignments if a.session.historic_group and a.session.historic_group.acronym == acronym ]
    elif session_id:
        assignments = [ a for a in assignments if a.session_id == int(session_id) ]

    for a in assignments:
        if a.session:
            a.session.ical_status = ical_session_status(a.session.current_status)

    return render(request, "meeting/agenda.ics", {
        "schedule": schedule,
        "assignments": assignments,
        "updated": updated
    }, content_type="text/calendar")

@cache_page(15 * 60)
def json_agenda(request, num=None ):
    meeting = get_meeting(num, type_in=['ietf','interim'])

    sessions = []
    locations = set()
    parent_acronyms = set()
    assignments = meeting.schedule.assignments.exclude(session__type__in=['lead','offagenda','break','reg'])
    # Update the assignments with historic information, i.e., valid at the
    # time of the meeting
    assignments = preprocess_assignments_for_agenda(assignments, meeting, extra_prefetches=[
        # sadly, these prefetches aren't enough to get rid of all implicit queries below
        Prefetch("session__materials",
                 queryset=Document.objects.exclude(states__type=F("type"),states__slug='deleted').select_related("group").order_by("sessionpresentation__order"),
                 to_attr="prefetched_active_materials",
        ),
        "session__materials__docevent_set",
        "session__sessionpresentation_set",
        "timeslot__meeting"
    ])
    for asgn in assignments:
        sessdict = dict()
        sessdict['objtype'] = 'session'
        sessdict['id'] = asgn.pk
        sessdict['is_bof'] = False
        if asgn.session.historic_group:
            sessdict['group'] = {
                    "acronym": asgn.session.historic_group.acronym,
                    "name": asgn.session.historic_group.name,
                    "type": asgn.session.historic_group.type_id,
                    "state": asgn.session.historic_group.state_id,
                }
            if asgn.session.historic_group.is_bof():
                sessdict['is_bof'] = True
            if asgn.session.historic_group.type_id in ['wg','rg', 'ag',] or asgn.session.historic_group.acronym in ['iesg',]:
                sessdict['group']['parent'] = asgn.session.historic_group.historic_parent.acronym
                parent_acronyms.add(asgn.session.historic_group.historic_parent.acronym)
        if asgn.session.name:
            sessdict['name'] = asgn.session.name
        else:
            sessdict['name'] = asgn.session.historic_group.name
        if asgn.session.short:
            sessdict['short'] = asgn.session.short
        sessdict['start'] = asgn.timeslot.utc_start_time().strftime("%Y-%m-%dT%H:%M:%SZ")
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

    tz = pytz.timezone(settings.PRODUCTION_TIMEZONE)

    for obj in meetinfo:
        obj['modified'] = tz.localize(obj['modified']).astimezone(pytz.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    data = {"%s"%num: meetinfo}

    response = HttpResponse(json.dumps(data, indent=2, sort_keys=True), content_type='application/json;charset=%s'%settings.DEFAULT_CHARSET)
    if last_modified:
        last_modified = tz.localize(last_modified).astimezone(pytz.utc)
        response['Last-Modified'] = format_date_time(timegm(last_modified.timetuple()))
    return response

def meeting_requests(request, num=None):
    meeting = get_meeting(num)
    sessions = add_event_info_to_session_qs(
        Session.objects.filter(
            meeting__number=meeting.number,
            type__slug='regular',
            group__parent__isnull=False
        ),
        requested_by=True,
    ).exclude(
        requested_by=0
    ).order_by(
        "group__parent__acronym", "current_status", "group__acronym"
    ).prefetch_related(
        "group","group__ad_role__person"
    )

    status_names = {n.slug: n.name for n in SessionStatusName.objects.all()}
    session_requesters = {p.pk: p for p in Person.objects.filter(pk__in=[s.requested_by for s in sessions if s.requested_by is not None])}

    for s in sessions:
        s.current_status_name = status_names.get(s.current_status, s.current_status)
        s.requested_by_person = session_requesters.get(s.requested_by)

    groups_not_meeting = Group.objects.filter(state='Active',type__in=['wg','rg','ag','bof']).exclude(acronym__in = [session.group.acronym for session in sessions]).order_by("parent__acronym","acronym").prefetch_related("parent")

    return render(request, "meeting/requests.html",
        {"meeting": meeting, "sessions":sessions,
         "groups_not_meeting": groups_not_meeting})

def get_sessions(num, acronym):
    meeting = get_meeting(num=num,type_in=None)
    sessions = Session.objects.filter(meeting=meeting,group__acronym=acronym,type__in=['regular','plenary','other'])

    if not sessions:
        sessions = Session.objects.filter(meeting=meeting,short=acronym,type__in=['regular','plenary','other']) 

    sessions = add_event_info_to_session_qs(sessions)

    return sorted(sessions, key=lambda s: session_time_for_sorting(s, use_meeting_date=False))

def session_details(request, num, acronym):
    meeting = get_meeting(num=num,type_in=None)
    sessions = get_sessions(num, acronym)

    if not sessions:
        raise Http404

    status_names = {n.slug: n.name for n in SessionStatusName.objects.all()}
    for session in sessions:

        session.type_counter = Counter()
        ss = session.timeslotassignments.filter(schedule=meeting.schedule).order_by('timeslot__time')
        if ss:
            if meeting.type_id == 'interim' and not (meeting.city or meeting.country):
                session.times = [ x.timeslot.utc_start_time() for x in ss ]                
            else:
                session.times = [ x.timeslot.local_start_time() for x in ss ]
            session.cancelled = session.current_status == 'canceled'
            session.status = ''
        elif meeting.type_id=='interim':
            session.times = [ meeting.date ]
            session.cancelled = session.current_status == 'canceled'
            session.status = ''
        else:
            session.times = []
            session.cancelled = session.current_status == 'canceled'
            session.status = status_names.get(session.current_status, session.current_status)

        session.filtered_artifacts = list(session.sessionpresentation_set.filter(document__type__slug__in=['agenda','minutes','bluesheets']))
        session.filtered_artifacts.sort(key=lambda d:['agenda','minutes','bluesheets'].index(d.document.type.slug))
        session.filtered_slides    = session.sessionpresentation_set.filter(document__type__slug='slides').order_by('order')
        session.filtered_drafts    = session.sessionpresentation_set.filter(document__type__slug='draft')
        # TODO FIXME Deleted materials shouldn't be in the sessionpresentation_set
        for qs in [session.filtered_artifacts,session.filtered_slides,session.filtered_drafts]:
            qs = [p for p in qs if p.document.get_state_slug(p.document.type_id)!='deleted']
            session.type_counter.update([p.document.type.slug for p in qs])

    # we somewhat arbitrarily use the group of the last session we get from
    # get_sessions() above when checking can_manage_session_materials()
    can_manage = can_manage_session_materials(request.user, session.group, session)
    can_view_request = can_view_interim_request(meeting, request.user)

    scheduled_sessions = [s for s in sessions if s.current_status == 'sched']
    unscheduled_sessions = [s for s in sessions if s.current_status != 'sched']

    pending_suggestions = None
    if request.user.is_authenticated:
        if can_manage:
            pending_suggestions = session.slidesubmission_set.all()
        else:
            pending_suggestions = session.slidesubmission_set.filter(submitter=request.user.person)

    return render(request, "meeting/session_details.html",
                  { 'scheduled_sessions':scheduled_sessions ,
                    'unscheduled_sessions':unscheduled_sessions , 
                    'pending_suggestions' : pending_suggestions,
                    'meeting' :meeting ,
                    'acronym' :acronym,
                    'is_materials_manager' : session.group.has_role(request.user, session.group.features.matman_roles),
                    'can_manage_materials' : can_manage,
                    'can_view_request': can_view_request,
                    'thisweek': datetime.date.today()-datetime.timedelta(days=7),
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

    already_linked = [sp.document for sp in session.sessionpresentation_set.filter(document__type_id='draft')]

    session_number = None
    sessions = get_sessions(session.meeting.number,session.group.acronym)
    if len(sessions) > 1:
       session_number = 1 + sessions.index(session)

    if request.method == 'POST':
        form = SessionDraftsForm(request.POST,already_linked=already_linked)
        if form.is_valid():
            for draft in form.cleaned_data['drafts']:
                session.sessionpresentation_set.create(document=draft,rev=None)
                c = DocEvent(type="added_comment", doc=draft, rev=draft.rev, by=request.user.person)
                c.desc = "Added to session: %s" % session
                c.save()
            return redirect('ietf.meeting.views.session_details', num=session.meeting.number, acronym=session.group.acronym)
    else:
        form = SessionDraftsForm(already_linked=already_linked)

    return render(request, "meeting/add_session_drafts.html",
                  { 'session': session,
                    'session_number': session_number,
                    'already_linked': session.sessionpresentation_set.filter(document__type_id='draft'),
                    'form': form,
                  })


class UploadBlueSheetForm(FileUploadForm):

    def __init__(self, *args, **kwargs):
        kwargs['doc_type'] = 'bluesheets'
        super(UploadBlueSheetForm, self).__init__(*args, **kwargs )


@role_required('Area Director', 'Secretariat', 'IRTF Chair', 'WG Chair', 'RG Chair')
def upload_session_bluesheets(request, session_id, num):
    # num is redundant, but we're dragging it along an artifact of where we are in the current URL structure
    session = get_object_or_404(Session,pk=session_id)

    if session.meeting.type.slug == 'ietf' and not has_role(request.user, 'Secretariat'):
        return HttpResponseForbidden('Restricted to role Secretariat')
        
    session_number = None
    sessions = get_sessions(session.meeting.number,session.group.acronym)
    if len(sessions) > 1:
       session_number = 1 + sessions.index(session)

    bluesheet_sp = session.sessionpresentation_set.filter(document__type='bluesheets').first()
    
    if request.method == 'POST':
        form = UploadBlueSheetForm(request.POST,request.FILES)
        if form.is_valid():
            file = request.FILES['file']
            _, ext = os.path.splitext(file.name)
            if bluesheet_sp:
                doc = bluesheet_sp.document
                doc.rev = '%02d' % (int(doc.rev)+1)
                bluesheet_sp.rev = doc.rev
                bluesheet_sp.save()
            else:
                ota = session.official_timeslotassignment()
                sess_time = ota and ota.timeslot.time
                if not sess_time:
                    return HttpResponse("Cannot receive uploads for an unscheduled session.  Please check the session ID.", status=410, content_type="text/plain")
                if session.meeting.type_id=='ietf':
                    name = 'bluesheets-%s-%s-%s' % (session.meeting.number, 
                                                    session.group.acronym, 
                                                    sess_time.strftime("%Y%m%d%H%M"))
                    title = 'Bluesheets IETF%s: %s : %s' % (session.meeting.number, 
                                                            session.group.acronym, 
                                                            sess_time.strftime("%a %H:%M"))
                else:
                    name = 'bluesheets-%s-%s' % (session.meeting.number, sess_time.strftime("%Y%m%d%H%M"))
                    title = 'Bluesheets %s: %s' % (session.meeting.number, sess_time.strftime("%a %H:%M"))
                doc = Document.objects.create(
                          name = name,
                          type_id = 'bluesheets',
                          title = title,
                          group = session.group,
                          rev = '00',
                      )
                doc.states.add(State.objects.get(type_id='bluesheets',slug='active'))
                DocAlias.objects.create(name=doc.name).docs.add(doc)
                session.sessionpresentation_set.create(document=doc,rev='00')
            filename = '%s-%s%s'% ( doc.name, doc.rev, ext)
            doc.uploaded_filename = filename
            e = NewRevisionDocEvent.objects.create(doc=doc, rev=doc.rev, by=request.user.person, type='new_revision', desc='New revision available: %s'%doc.rev)
            save_error = handle_upload_file(file, filename, session.meeting, 'bluesheets', request=request, encoding=form.file_encoding[file.name])
            if save_error:
                form.add_error(None, save_error)
            else:
                doc.save_with_history([e])
                return redirect('ietf.meeting.views.session_details',num=num,acronym=session.group.acronym)
    else: 
        form = UploadBlueSheetForm()

    return render(request, "meeting/upload_session_bluesheets.html", 
                  {'session': session,
                   'session_number': session_number,
                   'bluesheet_sp' : bluesheet_sp,
                   'form': form,
                  })


class UploadMinutesForm(FileUploadForm):
    apply_to_all = forms.BooleanField(label='Apply to all group sessions at this meeting',initial=True,required=False)

    def __init__(self, show_apply_to_all_checkbox, *args, **kwargs):
        kwargs['doc_type'] = 'minutes'
        super(UploadMinutesForm, self).__init__(*args, **kwargs )
        if not show_apply_to_all_checkbox:
            self.fields.pop('apply_to_all')


def upload_session_minutes(request, session_id, num):
    # num is redundant, but we're dragging it along an artifact of where we are in the current URL structure
    session = get_object_or_404(Session,pk=session_id)

    if not session.can_manage_materials(request.user):
        return HttpResponseForbidden("You don't have permission to upload minutes for this session.")
    if session.is_material_submission_cutoff() and not has_role(request.user, "Secretariat"):
        return HttpResponseForbidden("The materials cutoff for this session has passed. Contact the secretariat for further action.")

    session_number = None
    sessions = get_sessions(session.meeting.number,session.group.acronym)
    show_apply_to_all_checkbox = len(sessions) > 1 if session.type_id == 'regular' else False
    if len(sessions) > 1:
       session_number = 1 + sessions.index(session)

    minutes_sp = session.sessionpresentation_set.filter(document__type='minutes').first()
    
    if request.method == 'POST':
        form = UploadMinutesForm(show_apply_to_all_checkbox,request.POST,request.FILES)
        if form.is_valid():
            file = request.FILES['file']
            _, ext = os.path.splitext(file.name)
            apply_to_all = session.type_id == 'regular'
            if show_apply_to_all_checkbox:
                apply_to_all = form.cleaned_data['apply_to_all']
            if minutes_sp:
                doc = minutes_sp.document
                doc.rev = '%02d' % (int(doc.rev)+1)
                minutes_sp.rev = doc.rev
                minutes_sp.save()
            else:
                ota = session.official_timeslotassignment()
                sess_time = ota and ota.timeslot.time
                if not sess_time:
                    return HttpResponse("Cannot receive uploads for an unscheduled session.  Please check the session ID.", status=410, content_type="text/plain")
                if session.meeting.type_id=='ietf':
                    name = 'minutes-%s-%s' % (session.meeting.number, 
                                                 session.group.acronym) 
                    title = 'Minutes IETF%s: %s' % (session.meeting.number, 
                                                         session.group.acronym) 
                    if not apply_to_all:
                        name += '-%s' % (sess_time.strftime("%Y%m%d%H%M"),)
                        title += ': %s' % (sess_time.strftime("%a %H:%M"),)
                else:
                    name = 'minutes-%s-%s' % (session.meeting.number, sess_time.strftime("%Y%m%d%H%M"))
                    title = 'Minutes %s: %s' % (session.meeting.number, sess_time.strftime("%a %H:%M"))
                if Document.objects.filter(name=name).exists():
                    doc = Document.objects.get(name=name)
                    doc.rev = '%02d' % (int(doc.rev)+1)
                else:
                    doc = Document.objects.create(
                              name = name,
                              type_id = 'minutes',
                              title = title,
                              group = session.group,
                              rev = '00',
                          )
                    DocAlias.objects.create(name=doc.name).docs.add(doc)
                doc.states.add(State.objects.get(type_id='minutes',slug='active'))
                if session.sessionpresentation_set.filter(document=doc).exists():
                    sp = session.sessionpresentation_set.get(document=doc)
                    sp.rev = doc.rev
                    sp.save()
                else:
                    session.sessionpresentation_set.create(document=doc,rev=doc.rev)
            if apply_to_all:
                for other_session in sessions:
                    if other_session != session:
                        other_session.sessionpresentation_set.filter(document__type='minutes').delete()
                        other_session.sessionpresentation_set.create(document=doc,rev=doc.rev)
            filename = '%s-%s%s'% ( doc.name, doc.rev, ext)
            doc.uploaded_filename = filename
            e = NewRevisionDocEvent.objects.create(doc=doc, by=request.user.person, type='new_revision', desc='New revision available: %s'%doc.rev, rev=doc.rev)
            # The way this function builds the filename it will never trigger the file delete in handle_file_upload.
            save_error = handle_upload_file(file, filename, session.meeting, 'minutes', request=request, encoding=form.file_encoding[file.name])
            if save_error:
                form.add_error(None, save_error)
            else:
                doc.save_with_history([e])
                return redirect('ietf.meeting.views.session_details',num=num,acronym=session.group.acronym)
    else: 
        form = UploadMinutesForm(show_apply_to_all_checkbox)

    return render(request, "meeting/upload_session_minutes.html", 
                  {'session': session,
                   'session_number': session_number,
                   'minutes_sp' : minutes_sp,
                   'form': form,
                  })


class UploadAgendaForm(FileUploadForm):
    apply_to_all = forms.BooleanField(label='Apply to all group sessions at this meeting',initial=True,required=False)

    def __init__(self, show_apply_to_all_checkbox, *args, **kwargs):
        kwargs['doc_type'] = 'agenda'
        super(UploadAgendaForm, self).__init__(*args, **kwargs )
        if not show_apply_to_all_checkbox:
            self.fields.pop('apply_to_all')

def upload_session_agenda(request, session_id, num):
    # num is redundant, but we're dragging it along an artifact of where we are in the current URL structure
    session = get_object_or_404(Session,pk=session_id)

    if not session.can_manage_materials(request.user):
        return HttpResponseForbidden("You don't have permission to upload an agenda for this session.")
    if session.is_material_submission_cutoff() and not has_role(request.user, "Secretariat"):
        return HttpResponseForbidden("The materials cutoff for this session has passed. Contact the secretariat for further action.")

    session_number = None
    sessions = get_sessions(session.meeting.number,session.group.acronym)
    show_apply_to_all_checkbox = len(sessions) > 1 if session.type_id == 'regular' else False
    if len(sessions) > 1:
       session_number = 1 + sessions.index(session)

    agenda_sp = session.sessionpresentation_set.filter(document__type='agenda').first()
    
    if request.method == 'POST':
        form = UploadAgendaForm(show_apply_to_all_checkbox,request.POST,request.FILES)
        if form.is_valid():
            file = request.FILES['file']
            _, ext = os.path.splitext(file.name)
            apply_to_all = session.type_id == 'regular'
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
                    return HttpResponse("Cannot receive uploads for an unscheduled session.  Please check the session ID.", status=410, content_type="text/plain")
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
                    DocAlias.objects.create(name=doc.name).docs.add(doc)
                doc.states.add(State.objects.get(type_id='agenda',slug='active'))
            if session.sessionpresentation_set.filter(document=doc).exists():
                sp = session.sessionpresentation_set.get(document=doc)
                sp.rev = doc.rev
                sp.save()
            else:
                session.sessionpresentation_set.create(document=doc,rev=doc.rev)
            if apply_to_all:
                for other_session in sessions:
                    if other_session != session:
                        other_session.sessionpresentation_set.filter(document__type='agenda').delete()
                        other_session.sessionpresentation_set.create(document=doc,rev=doc.rev)
            filename = '%s-%s%s'% ( doc.name, doc.rev, ext)
            doc.uploaded_filename = filename
            e = NewRevisionDocEvent.objects.create(doc=doc,by=request.user.person,type='new_revision',desc='New revision available: %s'%doc.rev,rev=doc.rev)
            # The way this function builds the filename it will never trigger the file delete in handle_file_upload.
            save_error = handle_upload_file(file, filename, session.meeting, 'agenda', request=request, encoding=form.file_encoding[file.name])
            if save_error:
                form.add_error(None, save_error)
            else:
                doc.save_with_history([e])
                return redirect('ietf.meeting.views.session_details',num=num,acronym=session.group.acronym)
    else: 
        form = UploadAgendaForm(show_apply_to_all_checkbox, initial={'apply_to_all':session.type_id=='regular'})

    return render(request, "meeting/upload_session_agenda.html", 
                  {'session': session,
                   'session_number': session_number,
                   'agenda_sp' : agenda_sp,
                   'form': form,
                  })


class UploadSlidesForm(FileUploadForm):
    title = forms.CharField(max_length=255)
    apply_to_all = forms.BooleanField(label='Apply to all group sessions at this meeting',initial=False,required=False)

    def __init__(self, session, show_apply_to_all_checkbox, *args, **kwargs):
        self.session = session
        kwargs['doc_type'] = 'slides'
        super(UploadSlidesForm, self).__init__(*args, **kwargs )
        if not show_apply_to_all_checkbox:
            self.fields.pop('apply_to_all')

    def clean_title(self):
        title = self.cleaned_data['title']
        if self.session.meeting.type_id=='interim':
            if re.search(r'-\d{2}$', title):
                raise forms.ValidationError("Interim slides currently may not have a title that ends with something that looks like a revision number (-nn)")
        return title

def upload_session_slides(request, session_id, num, name):
    # num is redundant, but we're dragging it along an artifact of where we are in the current URL structure
    session = get_object_or_404(Session,pk=session_id)
    if not session.can_manage_materials(request.user):
        return HttpResponseForbidden("You don't have permission to upload slides for this session.")
    if session.is_material_submission_cutoff() and not has_role(request.user, "Secretariat"):
        return HttpResponseForbidden("The materials cutoff for this session has passed. Contact the secretariat for further action.")

    session_number = None
    sessions = get_sessions(session.meeting.number,session.group.acronym)
    show_apply_to_all_checkbox = len(sessions) > 1 if session.type_id == 'regular' else False
    if len(sessions) > 1:
       session_number = 1 + sessions.index(session)

    slides = None
    slides_sp = None
    if name:
        slides = Document.objects.filter(name=name).first()
        if not (slides and slides.type_id=='slides'):
            raise Http404
        slides_sp = session.sessionpresentation_set.filter(document=slides).first()
    
    if request.method == 'POST':
        form = UploadSlidesForm(session, show_apply_to_all_checkbox,request.POST,request.FILES)
        if form.is_valid():
            file = request.FILES['file']
            _, ext = os.path.splitext(file.name)
            apply_to_all = session.type_id == 'regular'
            if show_apply_to_all_checkbox:
                apply_to_all = form.cleaned_data['apply_to_all']
            if slides_sp:
                doc = slides_sp.document
                doc.rev = '%02d' % (int(doc.rev)+1)
                doc.title = form.cleaned_data['title']
                slides_sp.rev = doc.rev
                slides_sp.save()
            else:
                title = form.cleaned_data['title']
                if session.meeting.type_id=='ietf':
                    name = 'slides-%s-%s' % (session.meeting.number, 
                                             session.group.acronym) 
                    if not apply_to_all:
                        name += '-%s' % (session.docname_token(),)
                else:
                    name = 'slides-%s-%s' % (session.meeting.number, session.docname_token())
                name = name + '-' + slugify(title).replace('_', '-')[:128]
                if Document.objects.filter(name=name).exists():
                   doc = Document.objects.get(name=name)
                   doc.rev = '%02d' % (int(doc.rev)+1)
                   doc.title = form.cleaned_data['title']
                else:
                    doc = Document.objects.create(
                              name = name,
                              type_id = 'slides',
                              title = title,
                              group = session.group,
                              rev = '00',
                          )
                    DocAlias.objects.create(name=doc.name).docs.add(doc)
                doc.states.add(State.objects.get(type_id='slides',slug='active'))
                doc.states.add(State.objects.get(type_id='reuse_policy',slug='single'))
            if session.sessionpresentation_set.filter(document=doc).exists():
                sp = session.sessionpresentation_set.get(document=doc)
                sp.rev = doc.rev
                sp.save()
            else:
                max_order = session.sessionpresentation_set.filter(document__type='slides').aggregate(Max('order'))['order__max'] or 0
                session.sessionpresentation_set.create(document=doc,rev=doc.rev,order=max_order+1)
            if apply_to_all:
                for other_session in sessions:
                    if other_session != session and not other_session.sessionpresentation_set.filter(document=doc).exists():
                        max_order = other_session.sessionpresentation_set.filter(document__type='slides').aggregate(Max('order'))['order__max'] or 0
                        other_session.sessionpresentation_set.create(document=doc,rev=doc.rev,order=max_order+1)
            filename = '%s-%s%s'% ( doc.name, doc.rev, ext)
            doc.uploaded_filename = filename
            e = NewRevisionDocEvent.objects.create(doc=doc,by=request.user.person,type='new_revision',desc='New revision available: %s'%doc.rev,rev=doc.rev)
            # The way this function builds the filename it will never trigger the file delete in handle_file_upload.
            save_error = handle_upload_file(file, filename, session.meeting, 'slides', request=request, encoding=form.file_encoding[file.name])
            if save_error:
                form.add_error(None, save_error)
            else:
                doc.save_with_history([e])
                post_process(doc)
                return redirect('ietf.meeting.views.session_details',num=num,acronym=session.group.acronym)
    else: 
        initial = {}
        if slides:
            initial = {'title':slides.title}
        form = UploadSlidesForm(session, show_apply_to_all_checkbox, initial=initial)

    return render(request, "meeting/upload_session_slides.html", 
                  {'session': session,
                   'session_number': session_number,
                   'slides_sp' : slides_sp,
                   'form': form,
                  })
@login_required
def propose_session_slides(request, session_id, num):
    session = get_object_or_404(Session,pk=session_id)
    if session.is_material_submission_cutoff() and not has_role(request.user, "Secretariat"):
        return HttpResponseForbidden("The materials cutoff for this session has passed. Contact the secretariat for further action.")

    session_number = None
    sessions = get_sessions(session.meeting.number,session.group.acronym)
    show_apply_to_all_checkbox = len(sessions) > 1 if session.type_id == 'regular' else False
    if len(sessions) > 1:
       session_number = 1 + sessions.index(session)

    
    if request.method == 'POST':
        form = UploadSlidesForm(session, show_apply_to_all_checkbox,request.POST,request.FILES)
        if form.is_valid():
            file = request.FILES['file']
            _, ext = os.path.splitext(file.name)
            apply_to_all = session.type_id == 'regular'
            if show_apply_to_all_checkbox:
                apply_to_all = form.cleaned_data['apply_to_all']
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

            (to, cc) = gather_address_lists('slides_proposed', group=session.group).as_strings() 
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
            return redirect('ietf.meeting.views.session_details',num=num,acronym=session.group.acronym)
    else: 
        initial = {}
        form = UploadSlidesForm(session, show_apply_to_all_checkbox, initial=initial)

    return render(request, "meeting/propose_session_slides.html", 
                  {'session': session,
                   'session_number': session_number,
                   'form': form,
                  })

def remove_sessionpresentation(request, session_id, num, name):
    sp = get_object_or_404(SessionPresentation,session_id=session_id,document__name=name)
    session = sp.session
    if not session.can_manage_materials(request.user):
        return HttpResponseForbidden("You don't have permission to manage materials for this session.")
    if session.is_material_submission_cutoff() and not has_role(request.user, "Secretariat"):
        return HttpResponseForbidden("The materials cutoff for this session has passed. Contact the secretariat for further action.")
    if request.method == 'POST':
        session.sessionpresentation_set.filter(pk=sp.pk).delete()
        c = DocEvent(type="added_comment", doc=sp.document, rev=sp.document.rev, by=request.user.person)
        c.desc = "Removed from session: %s" % (session)
        c.save()
        return redirect('ietf.meeting.views.session_details', num=session.meeting.number, acronym=session.group.acronym)

    return render(request,'meeting/remove_sessionpresentation.html', {'sp': sp })

def ajax_add_slides_to_session(request, session_id, num):
    session = get_object_or_404(Session,pk=session_id)

    if not session.can_manage_materials(request.user):
        return HttpResponseForbidden("You don't have permission to upload slides for this session.")
    if session.is_material_submission_cutoff() and not has_role(request.user, "Secretariat"):
        return HttpResponseForbidden("The materials cutoff for this session has passed. Contact the secretariat for further action.")

    if request.method != 'POST' or not request.POST:
        return HttpResponse(json.dumps({ 'success' : False, 'error' : 'No data submitted or not POST' }),content_type='application/json')

    order_str = request.POST.get('order', None)    
    try:
        order = int(order_str)
    except (ValueError, TypeError):
        return HttpResponse(json.dumps({ 'success' : False, 'error' : 'Supplied order is not valid' }),content_type='application/json')
    if order < 1 or order > session.sessionpresentation_set.filter(document__type_id='slides').count() + 1 :
        return HttpResponse(json.dumps({ 'success' : False, 'error' : 'Supplied order is not valid' }),content_type='application/json')

    name = request.POST.get('name', None)
    doc = Document.objects.filter(name=name).first()
    if not doc:
        return HttpResponse(json.dumps({ 'success' : False, 'error' : 'Supplied name is not valid' }),content_type='application/json')

    if not session.sessionpresentation_set.filter(document=doc).exists():
        condition_slide_order(session)
        session.sessionpresentation_set.filter(document__type_id='slides', order__gte=order).update(order=F('order')+1)
        session.sessionpresentation_set.create(document=doc,rev=doc.rev,order=order)
        DocEvent.objects.create(type="added_comment", doc=doc, rev=doc.rev, by=request.user.person, desc="Added to session: %s" % session)

    return HttpResponse(json.dumps({'success':True}), content_type='application/json')


def ajax_remove_slides_from_session(request, session_id, num):
    session = get_object_or_404(Session,pk=session_id)

    if not session.can_manage_materials(request.user):
        return HttpResponseForbidden("You don't have permission to upload slides for this session.")
    if session.is_material_submission_cutoff() and not has_role(request.user, "Secretariat"):
        return HttpResponseForbidden("The materials cutoff for this session has passed. Contact the secretariat for further action.")

    if request.method != 'POST' or not request.POST:
        return HttpResponse(json.dumps({ 'success' : False, 'error' : 'No data submitted or not POST' }),content_type='application/json')  

    oldIndex_str = request.POST.get('oldIndex', None)
    try:
        oldIndex = int(oldIndex_str)
    except (ValueError, TypeError):
        return HttpResponse(json.dumps({ 'success' : False, 'error' : 'Supplied index is not valid' }),content_type='application/json')
    if oldIndex < 1 or oldIndex > session.sessionpresentation_set.filter(document__type_id='slides').count() :
        return HttpResponse(json.dumps({ 'success' : False, 'error' : 'Supplied index is not valid' }),content_type='application/json')

    name = request.POST.get('name', None)
    doc = Document.objects.filter(name=name).first()
    if not doc:
        return HttpResponse(json.dumps({ 'success' : False, 'error' : 'Supplied name is not valid' }),content_type='application/json')

    condition_slide_order(session)
    affected_presentations = session.sessionpresentation_set.filter(document=doc).first()
    if affected_presentations:
        if affected_presentations.order == oldIndex:
            affected_presentations.delete()
            session.sessionpresentation_set.filter(document__type_id='slides', order__gt=oldIndex).update(order=F('order')-1)    
            DocEvent.objects.create(type="added_comment", doc=doc, rev=doc.rev, by=request.user.person, desc="Removed from session: %s" % session)
            return HttpResponse(json.dumps({'success':True}), content_type='application/json')
        else:
            return HttpResponse(json.dumps({ 'success' : False, 'error' : 'Name does not match index' }),content_type='application/json')
    else:
        return HttpResponse(json.dumps({ 'success' : False, 'error' : 'SessionPresentation not found' }),content_type='application/json')


def ajax_reorder_slides_in_session(request, session_id, num):
    session = get_object_or_404(Session,pk=session_id)

    if not session.can_manage_materials(request.user):
        return HttpResponseForbidden("You don't have permission to upload slides for this session.")
    if session.is_material_submission_cutoff() and not has_role(request.user, "Secretariat"):
        return HttpResponseForbidden("The materials cutoff for this session has passed. Contact the secretariat for further action.")

    if request.method != 'POST' or not request.POST:
        return HttpResponse(json.dumps({ 'success' : False, 'error' : 'No data submitted or not POST' }),content_type='application/json')  

    num_slides_in_session = session.sessionpresentation_set.filter(document__type_id='slides').count()
    oldIndex_str = request.POST.get('oldIndex', None)
    try:
        oldIndex = int(oldIndex_str)
    except (ValueError, TypeError):
        return HttpResponse(json.dumps({ 'success' : False, 'error' : 'Supplied index is not valid' }),content_type='application/json')
    if oldIndex < 1 or oldIndex > num_slides_in_session :
        return HttpResponse(json.dumps({ 'success' : False, 'error' : 'Supplied index is not valid' }),content_type='application/json')

    newIndex_str = request.POST.get('newIndex', None)
    try:
        newIndex = int(newIndex_str)
    except (ValueError, TypeError):
        return HttpResponse(json.dumps({ 'success' : False, 'error' : 'Supplied index is not valid' }),content_type='application/json')
    if newIndex < 1 or newIndex > num_slides_in_session :
        return HttpResponse(json.dumps({ 'success' : False, 'error' : 'Supplied index is not valid' }),content_type='application/json')

    if newIndex == oldIndex:
        return HttpResponse(json.dumps({ 'success' : False, 'error' : 'Supplied index is not valid' }),content_type='application/json')

    condition_slide_order(session)
    sp = session.sessionpresentation_set.get(order=oldIndex)
    if oldIndex < newIndex:
        session.sessionpresentation_set.filter(order__gt=oldIndex, order__lte=newIndex).update(order=F('order')-1)
    else:
        session.sessionpresentation_set.filter(order__gte=newIndex, order__lt=oldIndex).update(order=F('order')+1)
    sp.order = newIndex
    sp.save()

    return HttpResponse(json.dumps({'success':True}), content_type='application/json')


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
        meeting.schedule = schedule
        meeting.save()
        return HttpResponseRedirect(reverse('ietf.meeting.views.list_schedules',kwargs={'num':num}))

    if not schedule.public:
        messages.warning(request,"This schedule will be made public as it is made official.")

    if not schedule.visible:
        messages.warning(request,"This schedule will be made visible as it is made official.")

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

    if schedule.name=='Empty-Schedule':
        return HttpResponseForbidden('You may not delete the default empty schedule')

    if schedule == meeting.schedule:
        return HttpResponseForbidden('You may not delete the official schedule for %s'%meeting)

    if not ( has_role(request.user, 'Secretariat') or person.user == request.user ):
        return HttpResponseForbidden("You may not delete other user's schedules")

    if request.method == 'POST':
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


def ajax_get_utc(request):
    '''Ajax view that takes arguments time, timezone, date and returns UTC data'''
    time = request.GET.get('time')
    timezone = request.GET.get('timezone')
    date = request.GET.get('date')
    time_re = re.compile(r'^\d{2}:\d{2}$')
    # validate input
    if not time_re.match(time) or not date:
        return HttpResponse(json.dumps({'error': True}),
                            content_type='application/json')
    hour, minute = time.split(':')
    if not (int(hour) <= 23 and int(minute) <= 59):
        return HttpResponse(json.dumps({'error': True}),
                            content_type='application/json')
    year, month, day = date.split('-')
    dt = datetime.datetime(int(year), int(month), int(day), int(hour), int(minute))
    tz = pytz.timezone(timezone)
    aware_dt = tz.localize(dt, is_dst=None)
    utc_dt = aware_dt.astimezone(pytz.utc)
    utc = utc_dt.strftime('%H:%M')
    # calculate utc day offset
    naive_utc_dt = utc_dt.replace(tzinfo=None)
    utc_day_offset = (naive_utc_dt.date() - dt.date()).days
    html = "<span>{utc} UTC</span>".format(utc=utc)
    if utc_day_offset != 0:
        html = html + "<span class='day-offset'> {0:+d} Day</span>".format(utc_day_offset)
    context_data = {'timezone': timezone, 
                    'time': time, 
                    'utc': utc, 
                    'utc_day_offset': utc_day_offset,
                    'html': html}
    return HttpResponse(json.dumps(context_data),
                        content_type='application/json')


@role_required('Secretariat',)
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
            for session in meeting.session_set.all():
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
        for session in meeting.session_set.all():
            SchedulingEvent.objects.create(
                session=session,
                status=SessionStatusName.objects.get(slug='sched'),
                by=request.user.person,
            )
        messages.success(request, 'Interim meeting scheduled.  No announcement sent.')
        return redirect(interim_announce)

    return render(request, "meeting/interim_skip_announce.html", {
        'meeting': meeting})


@role_required('Area Director', 'Secretariat', 'IRTF Chair', 'WG Chair', 'RG Chair')
def interim_pending(request):
    '''View which shows interim meeting requests pending approval'''
    meetings = data_for_meetings_overview(Meeting.objects.filter(type='interim').order_by('date'), interim_status='apprw')

    menu_entries = get_interim_menu_entries(request)
    selected_menu_entry = 'pending'

    meetings = [m for m in meetings if can_view_interim_request(m, request.user)]
    for meeting in meetings:
        if can_approve_interim_request(meeting, request.user):
            meeting.can_approve = True

    return render(request, "meeting/interim_pending.html", {
        'menu_entries': menu_entries,
        'selected_menu_entry': selected_menu_entry,
        'meetings': meetings})


@role_required('Area Director', 'Secretariat', 'IRTF Chair', 'WG Chair', 'RG Chair')
def interim_request(request):
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

                # need to use curry here to pass custom variable to form init
                SessionFormset.form.__init__ = curry(
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
                elif not has_role(request.user, 'Secretariat'):
                    send_interim_announcement_request(meeting=meeting)

            # series require special handling, each session gets it's own
            # meeting object we won't see this on edit because series are
            # subsequently dealt with individually
            elif meeting_type == 'series':
                series = []
                SessionFormset.form.__init__ = curry(
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
                elif not has_role(request.user, 'Secretariat'):
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


@role_required('Area Director', 'Secretariat', 'IRTF Chair', 'WG Chair', 'RG Chair')
def interim_request_cancel(request, number):
    '''View for cancelling an interim meeting request'''
    meeting = get_object_or_404(Meeting, number=number)
    first_session = meeting.session_set.first()
    session_status = current_session_status(first_session)
    group = first_session.group
    if not can_view_interim_request(meeting, request.user):
        return HttpResponseForbidden("You do not have permissions to cancel this meeting request")

    if request.method == 'POST':
        form = InterimCancelForm(request.POST)
        if form.is_valid():
            if 'comments' in form.changed_data:
                meeting.session_set.update(agenda_note=form.cleaned_data.get('comments'))

            was_scheduled = session_status.slug == 'sched'

            result_status = SessionStatusName.objects.get(slug='canceled' if was_scheduled else 'canceledpa')
            for session in meeting.session_set.all():
                SchedulingEvent.objects.create(
                    session=first_session,
                    status=result_status,
                    by=request.user.person,
                )

            if was_scheduled:
                send_interim_cancellation_notice(meeting)

            messages.success(request, 'Interim meeting cancelled')
            return redirect(upcoming)
    else:
        form = InterimCancelForm(initial={'group': group.acronym, 'date': meeting.date})

    return render(request, "meeting/interim_request_cancel.html", {
        "form": form,
        "meeting": meeting,
        "session_status": session_status,
    })


@role_required('Area Director', 'Secretariat', 'IRTF Chair', 'WG Chair', 'RG Chair')
def interim_request_details(request, number):
    '''View details of an interim meeting reqeust'''
    meeting = get_object_or_404(Meeting, number=number)
    sessions = meeting.session_set.all()
    can_edit = can_edit_interim_request(meeting, request.user)
    can_approve = can_approve_interim_request(meeting, request.user)

    if request.method == 'POST':
        if request.POST.get('approve') and can_approve_interim_request(meeting, request.user):
            for session in meeting.session_set.all():
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
            for session in meeting.session_set.all():
                SchedulingEvent.objects.create(
                    session=session,
                    status=SessionStatusName.objects.get(slug='disappr'),
                    by=request.user.person,
                )
            messages.success(request, 'Interim meeting disapproved')
            return redirect(interim_pending)

    first_session = sessions.first()

    return render(request, "meeting/interim_request_details.html", {
        "meeting": meeting,
        "sessions": sessions,
        "group": first_session.group,
        "requester": session_requested_by(first_session),
        "session_status": current_session_status(first_session),
        "can_edit": can_edit,
        "can_approve": can_approve})


@role_required('Area Director', 'Secretariat', 'IRTF Chair', 'WG Chair', 'RG Chair')
def interim_request_edit(request, number):
    '''Edit details of an interim meeting reqeust'''
    meeting = get_object_or_404(Meeting, number=number)
    if not can_edit_interim_request(meeting, request.user):
        return HttpResponseForbidden("You do not have permissions to edit this meeting request")

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

        SessionFormset.form.__init__ = curry(
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

@cache_page(60*60)
def past(request):
    '''List of past meetings'''
    today = datetime.datetime.today()

    meetings = data_for_meetings_overview(Meeting.objects.filter(date__lte=today).order_by('-date'))

    return render(request, 'meeting/past.html', {
                  'meetings': meetings,
                  })

def upcoming(request):
    '''List of upcoming meetings'''
    today = datetime.date.today()

    # Get ietf meetings starting 7 days ago, and interim meetings starting today
    ietf_meetings = Meeting.objects.filter(type_id='ietf', date__gte=today-datetime.timedelta(days=7))
    for m in ietf_meetings:
        m.end = m.date+datetime.timedelta(days=m.days)
    interim_sessions = add_event_info_to_session_qs(
        Session.objects.filter(
            meeting__type_id='interim', 
            timeslotassignments__schedule=F('meeting__schedule'),
            timeslotassignments__timeslot__time__gte=today
        )
    ).filter(current_status__in=('sched','canceled'))
    for session in interim_sessions:
        session.historic_group = session.group

    entries = list(ietf_meetings)
    entries.extend(list(interim_sessions))
    entries.sort(key = lambda o: pytz.utc.localize(datetime.datetime.combine(o.date, datetime.datetime.min.time())) if isinstance(o,Meeting) else o.official_timeslotassignment().timeslot.utc_start_time())

    # add menu entries
    menu_entries = get_interim_menu_entries(request)
    selected_menu_entry = 'upcoming'

    # add menu actions
    actions = []
    if can_request_interim_meeting(request.user):
        actions.append(('Request new interim meeting',
                        reverse('ietf.meeting.views.interim_request')))
    actions.append(('Download as .ics',
                    reverse('ietf.meeting.views.upcoming_ical')))

    return render(request, 'meeting/upcoming.html', {
                  'entries': entries,
                  'menu_actions': actions,
                  'menu_entries': menu_entries,
                  'selected_menu_entry': selected_menu_entry,
                  })


def upcoming_ical(request):
    '''Return Upcoming meetings in iCalendar file'''
    filters = request.GET.getlist('filters')
    today = datetime.date.today()

    # get meetings starting 7 days ago -- we'll filter out sessions in the past further down
    meetings = data_for_meetings_overview(Meeting.objects.filter(date__gte=today-datetime.timedelta(days=7)).order_by('date'))

    assignments = list(SchedTimeSessAssignment.objects.filter(
        schedule__meeting__schedule=F('schedule'),
        session__in=[s.pk for m in meetings for s in m.sessions],
        timeslot__time__gte=today,
    ).order_by(
        'schedule__meeting__date', 'session__type', 'timeslot__time'
    ).select_related(
        'session__group', 'session__group__parent', 'timeslot', 'schedule', 'schedule__meeting'
    ).distinct())

    # apply filters
    if filters:
        assignments = [a for a in assignments if
                       a.session.group and (
                           a.session.group.acronym in filters or (
                               a.session.group.parent and a.session.group.parent.acronym in filters
                           )
                       ) ]

    # we already collected sessions with current_status, so reuse those
    sessions = {s.pk: s for m in meetings for s in m.sessions}
    for a in assignments:
        if a.session_id is not None:
            a.session = sessions.get(a.session_id) or a.session
            a.session.ical_status = ical_session_status(a.session.current_status)

    # gather vtimezones
    vtimezones = set()
    for meeting in meetings:
        if meeting.vtimezone():
            vtimezones.add(meeting.vtimezone())
    vtimezones = ''.join(vtimezones)

    # icalendar response file should have '\r\n' line endings per RFC5545
    response = render_to_string('meeting/upcoming.ics', {
        'vtimezones': vtimezones,
        'assignments': assignments})
    response = re.sub("\r(?!\n)|(?<!\r)\n", "\r\n", response)

    response = HttpResponse(response, content_type='text/calendar')
    response['Content-Disposition'] = 'attachment; filename="upcoming.ics"'
    return response
    

def floor_plan(request, num=None, floor=None, ):
    meeting = get_meeting(num)
    schedule = meeting.schedule
    floors = FloorPlan.objects.filter(meeting=meeting).order_by('order')
    if floor:
        floors = [ f for f in floors if xslugify(f.name) == floor ]
    return render(request, 'meeting/floor-plan.html', {
            "schedule": schedule,
            "number": num,
            "floors": floors,
        })

def proceedings(request, num=None):

    meeting = get_meeting(num)

    if (meeting.number.isdigit() and int(meeting.number) <= 64) or not meeting.schedule or not meeting.schedule.assignments.exists():
            return HttpResponseRedirect( 'https://www.ietf.org/proceedings/%s' % num )

    begin_date = meeting.get_submission_start_date()
    cut_off_date = meeting.get_submission_cut_off_date()
    cor_cut_off_date = meeting.get_submission_correction_date()
    now = datetime.date.today()

    schedule = get_schedule(meeting, None)
    sessions  = add_event_info_to_session_qs(
        Session.objects.filter(meeting__number=meeting.number)
    ).filter(
        Q(timeslotassignments__schedule=schedule) | Q(current_status='notmeet')
    ).select_related().order_by('-current_status')
    plenaries = sessions.filter(name__icontains='plenary').exclude(current_status='notmeet')
    ietf      = sessions.filter(group__parent__type__slug = 'area').exclude(group__acronym='edu')
    irtf      = sessions.filter(group__parent__acronym = 'irtf')
    training  = sessions.filter(group__acronym__in=['edu','iaoc'], type_id__in=['regular', 'other', ]).exclude(current_status='notmeet')
    iab       = sessions.filter(group__parent__acronym = 'iab').exclude(current_status='notmeet')

    cache_version = Document.objects.filter(session__meeting__number=meeting.number).aggregate(Max('time'))["time__max"]

    ietf_areas = []
    for area, sessions in itertools.groupby(sorted(ietf, key=lambda s: (s.group.parent.acronym, s.group.acronym)), key=lambda s: s.group.parent):
        sessions = list(sessions)
        meeting_groups = set(s.group_id for s in sessions if s.current_status != 'notmeet')
        meeting_sessions = []
        not_meeting_sessions = []
        for s in sessions:
            if s.current_status == 'notmeet' and s.group_id not in meeting_groups:
                not_meeting_sessions.append(s)
            else:
                meeting_sessions.append(s)
        ietf_areas.append((area, meeting_sessions, not_meeting_sessions))

    return render(request, "meeting/proceedings.html", {
        'meeting': meeting,
        'plenaries': plenaries, 'ietf': ietf, 'training': training, 'irtf': irtf, 'iab': iab,
        'ietf_areas': ietf_areas,
        'cut_off_date': cut_off_date,
        'cor_cut_off_date': cor_cut_off_date,
        'submission_started': now > begin_date,
        'cache_version': cache_version,
    })

@role_required('Secretariat')
def finalize_proceedings(request, num=None):

    meeting = get_meeting(num)

    if (meeting.number.isdigit() and int(meeting.number) <= 64) or not meeting.schedule or not meeting.schedule.assignments.exists() or meeting.proceedings_final:
        raise Http404

    if request.method=='POST':
        finalize(meeting)
        return HttpResponseRedirect(reverse('ietf.meeting.views.proceedings',kwargs={'num':meeting.number}))
    
    return render(request, "meeting/finalize.html", {'meeting':meeting,})

def proceedings_acknowledgements(request, num=None):
    '''Display Acknowledgements for meeting'''
    if not (num and num.isdigit()):
        raise Http404
    meeting = get_meeting(num)
    if int(meeting.number) < settings.NEW_PROCEEDINGS_START:
        return HttpResponseRedirect( 'https://www.ietf.org/proceedings/%s/acknowledgement.html' % num )
    return render(request, "meeting/proceedings_acknowledgements.html", {
        'meeting': meeting,
    })

def proceedings_attendees(request, num=None):
    '''Display list of meeting attendees'''
    if not (num and num.isdigit()):
        raise Http404
    meeting = get_meeting(num)
    if int(meeting.number) < settings.NEW_PROCEEDINGS_START:
        return HttpResponseRedirect( 'https://www.ietf.org/proceedings/%s/attendees.html' % num )
    overview_template = '/meeting/proceedings/%s/attendees.html' % meeting.number
    try:
        template = render_to_string(overview_template, {})
    except TemplateDoesNotExist:
        raise Http404
    return render(request, "meeting/proceedings_attendees.html", {
        'meeting': meeting,
        'template': template,
    })

def proceedings_overview(request, num=None):
    '''Display Overview for given meeting'''
    if not (num and num.isdigit()):
        raise Http404
    meeting = get_meeting(num)
    if int(meeting.number) < settings.NEW_PROCEEDINGS_START:
        return HttpResponseRedirect( 'https://www.ietf.org/proceedings/%s/overview.html' % num )
    overview_template = '/meeting/proceedings/%s/overview.rst' % meeting.number
    try:
        template = render_to_string(overview_template, {})
    except TemplateDoesNotExist:
        raise Http404
    return render(request, "meeting/proceedings_overview.html", {
        'meeting': meeting,
        'template': template,
    })

@cache_page( 60 * 60 )
def proceedings_progress_report(request, num=None):
    '''Display Progress Report (stats since last meeting)'''
    if not (num and num.isdigit()):
        raise Http404
    meeting = get_meeting(num)
    if int(meeting.number) < settings.NEW_PROCEEDINGS_START:
        return HttpResponseRedirect( 'https://www.ietf.org/proceedings/%s/progress-report.html' % num )
    sdate = meeting.previous_meeting().date
    edate = meeting.date
    context = get_progress_stats(sdate,edate)
    context['meeting'] = meeting
    return render(request, "meeting/proceedings_progress_report.html", context)
    
class OldUploadRedirect(RedirectView):
    def get_redirect_url(self, **kwargs):
        return reverse_lazy('ietf.meeting.views.session_details',kwargs=self.kwargs)

@csrf_exempt
def api_import_recordings(request, number):
    '''REST API to check for recording files and import'''
    if request.method == 'POST':
        meeting = get_meeting(number)
        import_audio_files(meeting)
        return HttpResponse(status=201)
    else:
        return HttpResponse(status=405)

@require_api_key
@role_required('Recording Manager')
@csrf_exempt
def api_set_session_video_url(request):
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
        session_times = [ (s.official_timeslotassignment().timeslot.time, s) for s in sessions if s.official_timeslotassignment() ]
        session_times.sort()
        item = request.POST.get('item')
        if not item.isdigit():
            return err(400, "Expected a numeric value for 'item', found '%s'" % (item, ))
        n = int(item)-1              # change 1-based to 0-based
        try:
            time, session = session_times[n]
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


def important_dates(request, num=None):
    assert num is None or num.isdigit()
    preview_roles = ['Area Director', 'Secretariat', 'IETF Chair', 'IAD', ]

    meeting = get_ietf_meeting(num)
    if not meeting:
        raise Http404
    base_num = int(meeting.number)

    user = request.user
    today = datetime.date.today()
    meetings = []
    if meeting.show_important_dates or meeting.date < today:
        meetings.append(meeting)
    for i in range(1,3):
        future_meeting = get_ietf_meeting(base_num+i)
        if future_meeting and ( future_meeting.show_important_dates
            or (user and user.is_authenticated and has_role(user, preview_roles))):
            meetings.append(future_meeting)

    context={'meetings':meetings}
    return render(request, 'meeting/important-dates.html', context)

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
        
    sessions = timeslot.sessions.filter(timeslotassignments__schedule=meeting.schedule)

    return render(request, 'meeting/edit_timeslot_type.html', {'timeslot':timeslot,'form':form,'sessions':sessions})


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
                group__type__in=['wg','rg','ag'],
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
                   'subject': 'Request for IETF WG and Bof Session Minutes',
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
        return HttpResponseForbidden("You don't have permission to manage slides for this session.")
    if submission.session.is_material_submission_cutoff() and not has_role(request.user, "Secretariat"):
        return HttpResponseForbidden("The materials cutoff for this session has passed. Contact the secretariat for further action.")   
    
    session_number = None
    sessions = get_sessions(submission.session.meeting.number,submission.session.group.acronym)
    show_apply_to_all_checkbox = len(sessions) > 1 if submission.session.type_id == 'regular' else False
    if len(sessions) > 1:
       session_number = 1 + sessions.index(submission.session)
    name, _ = os.path.splitext(submission.filename)
    name = name[:name.rfind('-ss')]
    existing_doc = Document.objects.filter(name=name).first()
    if request.method == 'POST':
        form = ApproveSlidesForm(show_apply_to_all_checkbox, request.POST)
        if form.is_valid():
            apply_to_all = submission.session.type_id == 'regular'
            if show_apply_to_all_checkbox:
                apply_to_all = form.cleaned_data['apply_to_all']
            if request.POST.get('approve'):
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
                    DocAlias.objects.create(name=doc.name).docs.add(doc)
                doc.states.add(State.objects.get(type_id='slides',slug='active'))
                doc.states.add(State.objects.get(type_id='reuse_policy',slug='single'))
                if submission.session.sessionpresentation_set.filter(document=doc).exists():
                    sp = submission.session.sessionpresentation_set.get(document=doc)
                    sp.rev = doc.rev
                    sp.save()
                else:
                    max_order = submission.session.sessionpresentation_set.filter(document__type='slides').aggregate(Max('order'))['order__max'] or 0
                    submission.session.sessionpresentation_set.create(document=doc,rev=doc.rev,order=max_order+1)
                if apply_to_all:
                    for other_session in sessions:
                        if other_session != submission.session and not other_session.sessionpresentation_set.filter(document=doc).exists():
                            max_order = other_session.sessionpresentation_set.filter(document__type='slides').aggregate(Max('order'))['order__max'] or 0
                            other_session.sessionpresentation_set.create(document=doc,rev=doc.rev,order=max_order+1)
                sub_name, sub_ext = os.path.splitext(submission.filename)
                target_filename = '%s-%s%s' % (sub_name[:sub_name.rfind('-ss')],doc.rev,sub_ext)
                doc.uploaded_filename = target_filename
                e = NewRevisionDocEvent.objects.create(doc=doc,by=submission.submitter,type='new_revision',desc='New revision available: %s'%doc.rev,rev=doc.rev)
                doc.save_with_history([e])
                path = os.path.join(submission.session.meeting.get_materials_path(),'slides')
                if not os.path.exists(path):
                    os.makedirs(path)
                os.rename(submission.staged_filepath(), os.path.join(path, target_filename))
                post_process(doc)
                acronym = submission.session.group.acronym
                submission.delete()
                return redirect('ietf.meeting.views.session_details',num=num,acronym=acronym)
            elif request.POST.get('disapprove'):
                os.unlink(submission.staged_filepath())
                acronym = submission.session.group.acronym
                submission.delete()
                return redirect('ietf.meeting.views.session_details',num=num,acronym=acronym)
            else:
                pass
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
