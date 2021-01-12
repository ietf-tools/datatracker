# Copyright The IETF Trust 2013-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime
import glob
import itertools
import os

import debug                            # pyflakes:ignore

from django.conf import settings
from django.contrib import messages
from django.urls import reverse
from django.db.models import Max
from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404, redirect

from ietf.secr.utils.decorators import sec_only
from ietf.secr.utils.group import get_my_groups
from ietf.secr.utils.meeting import get_timeslot, get_proceedings_url
from ietf.doc.models import Document, DocEvent
from ietf.person.models import Person
from ietf.ietfauth.utils import has_role, role_required
from ietf.meeting.models import Meeting, Session
from ietf.meeting.utils import add_event_info_to_session_qs

from ietf.secr.proceedings.forms import RecordingForm, RecordingEditForm 
from ietf.secr.proceedings.proc_utils import (create_recording)

# -------------------------------------------------
# Globals 
# -------------------------------------------------
AUTHORIZED_ROLES=('WG Chair','WG Secretary','RG Chair','RG Secretary', 'AG Secretary', 'RAG Secretary', 'IRTF Chair','IETF Trust Chair','IAB Group Chair','IAOC Chair','IAD','Area Director','Secretariat','Team Chair')
# -------------------------------------------------
# Helper Functions
# -------------------------------------------------

def build_choices(queryset):
    '''
    This function takes a queryset (or list) of Groups and builds a list of tuples for use
    as choices in a select widget.  Using acronym for both value and label.
    '''
    choices = [ (g.acronym,g.acronym) for g in queryset ]
    return sorted(choices, key=lambda choices: choices[1])

def find_index(slide_id, qs):
    '''
    This function looks up a slide in a queryset of slides,
    returning the index.
    '''
    for i in range(0,qs.count()):
        if str(qs[i].pk) == slide_id:
            return i

def get_doc_filename(doc):
    '''
    This function takes a Document of type slides,minute or agenda and returns
    the full path to the file on disk.  
    '''
    session = doc.session_set.all()[0]
    meeting = session.meeting
    if doc.external_url:
        return os.path.join(meeting.get_materials_path(),doc.type.slug,doc.uploaded_filename)
    else:
        path = os.path.join(meeting.get_materials_path(),doc.type.slug,doc.name)
        files = glob.glob(path + '.*')
        # TODO we might want to choose from among multiple files using some logic
        return files[0]

def get_unmatched_recordings(meeting):
    '''
    Returns a list of recording filenames that haven't been matched to a session
    '''
    unmatched_recordings = []
    path = os.path.join(settings.MEETING_RECORDINGS_DIR,'ietf{}'.format(meeting.number))
    try:
        files = os.listdir(path)
    except OSError:
        files = []
    url = settings.IETF_AUDIO_URL + 'ietf%s' % meeting.number 
    recordings = Document.objects.filter(type='recording',external_url__startswith=url)
    filenames = [ d.external_url.split('/')[-1] for d in recordings ]
    for file in files:
        if file not in filenames:
            unmatched_recordings.append(file)
    return unmatched_recordings

def get_extras(meeting):
    '''
    Gather "extras" which are one off groups. ie iab-wcit(86)
    '''
    groups = []
    sessions = Session.objects.filter(meeting=meeting).exclude(group__parent__type__in=('area','irtf'))
    for session in sessions:
        timeslot = get_timeslot(session)
        if timeslot and timeslot.type_id == 'regular' and session.materials.all():
            groups.append(session.group)
    return groups

def get_next_slide_num(session):
    '''
    This function takes a session object and returns the
    next slide number to use for a newly added slide as a string.
    '''

    if session.meeting.type_id == 'ietf':
        pattern = 'slides-%s-%s' % (session.meeting.number,session.group.acronym)
    elif session.meeting.type_id == 'interim':
        pattern = 'slides-%s' % (session.meeting.number)
    slides = Document.objects.filter(type='slides',name__startswith=pattern)
    if slides:
        nums = [ s.name.split('-')[-1] for s in slides ]
        nums.sort(key=int)
        return str(int(nums[-1]) + 1)
    else:
        return '0'

def get_next_order_num(session):
    '''
    This function takes a session object and returns the
    next slide order number to use for a newly added slide as an integer.
    '''
    max_order = session.materials.aggregate(Max('order'))['order__max']

    return max_order + 1 if max_order else 1

def parsedate(d):
    '''
    This function takes a date object and returns a tuple of year,month,day
    '''
    return (d.strftime('%Y'),d.strftime('%m'),d.strftime('%d'))

# --------------------------------------------------
# STANDARD VIEW FUNCTIONS
# --------------------------------------------------

@role_required(*AUTHORIZED_ROLES)
def main(request):
    '''
    List IETF Meetings.  If the user is Secratariat list includes all meetings otherwise
    show only those meetings whose corrections submission date has not passed.

    **Templates:**

    * ``proceedings/main.html``

    **Template Variables:**

    * meetings, interim_meetings, today

    '''
    if has_role(request.user,'Secretariat'):
        meetings = Meeting.objects.filter(type='ietf').order_by('-number')
    else:
        # select meetings still within the cutoff period
        today = datetime.date.today()
        meetings = [m for m in Meeting.objects.filter(type='ietf').order_by('-number') if m.get_submission_correction_date()>=today]

    groups = get_my_groups(request.user)
    interim_sessions = add_event_info_to_session_qs(Session.objects.filter(group__in=groups, meeting__type='interim')).filter(current_status='sched').select_related('meeting')
    interim_meetings = sorted({s.meeting for s in interim_sessions}, key=lambda m: m.date, reverse=True)
    # tac on group for use in templates
    for m in interim_meetings:
        m.group = m.session_set.first().group

    # we today's date to see if we're past the submissio cutoff
    today = datetime.date.today()

    return render(request, 'proceedings/main.html',{
        'meetings': meetings,
        'interim_meetings': interim_meetings,
        'today': today},
    )

@sec_only
def process_pdfs(request, meeting_num):
    '''
    This function is used to update the database once meeting materials in PPT format
    are converted to PDF format and uploaded to the server.  It basically finds every PowerPoint
    slide document for the given meeting and checks to see if there is a PDF version.  If there
    is external_url is changed.  Then when proceedings are generated the URL will refer to the
    PDF document.
    '''
    warn_count = 0
    count = 0
    meeting = get_object_or_404(Meeting, number=meeting_num)
    ppt = Document.objects.filter(session__meeting=meeting,type='slides',uploaded_filename__endswith='.ppt').exclude(states__slug='deleted')
    pptx = Document.objects.filter(session__meeting=meeting,type='slides',uploaded_filename__endswith='.pptx').exclude(states__slug='deleted')
    for doc in itertools.chain(ppt,pptx):
        base,ext = os.path.splitext(doc.uploaded_filename)
        pdf_file = base + '.pdf'
        path = os.path.join(settings.SECR_PROCEEDINGS_DIR,meeting_num,'slides',pdf_file)
        if os.path.exists(path):
            doc.uploaded_filename = pdf_file
            e = DocEvent.objects.create(
                type='changed_document',
                by=Person.objects.get(name="(System)"),
                doc=doc,
                rev=doc.rev,
                desc='Set URL to PDF version',
            )
            doc.save_with_history([e])
            count += 1
        else:
            warn_count += 1

    if warn_count:
        messages.warning(request, '%s PDF files processed.  %s PowerPoint files still not converted.' % (count, warn_count))
    else:
        messages.success(request, '%s PDF files processed' % count)
    url = reverse('ietf.secr.proceedings.views.select', kwargs={'meeting_num':meeting_num})
    return HttpResponseRedirect(url)

@role_required('Secretariat')
def recording(request, meeting_num):
    '''
    Enter Session recording info.  Creates Document and associates it with Session.
    For auditing purposes, lists all scheduled sessions and associated recordings, if
    any.  Also lists those audio recording files which haven't been matched to a
    session.
    '''
    meeting = get_object_or_404(Meeting, number=meeting_num)
    sessions = Session.objects.filter(
        timeslotassignments__schedule__in=[meeting.schedule, meeting.schedule.base if meeting.schedule else None]
    ).exclude(
        type__in=['reg','break']
    ).order_by('group__acronym')

    if request.method == 'POST':
        form = RecordingForm(request.POST,meeting=meeting)
        if form.is_valid():
            external_url =  form.cleaned_data['external_url']
            session = form.cleaned_data['session']
            
            if Document.objects.filter(type='recording',external_url=external_url):
                messages.error(request, "Recording already exists")
                return redirect('ietf.secr.proceedings.views.recording', meeting_num=meeting_num)
            else:
                create_recording(session,external_url)
            
            messages.success(request,'Recording added')
            return redirect('ietf.secr.proceedings.views.recording', meeting_num=meeting_num)
    
    else:
        form = RecordingForm(meeting=meeting)
    
    return render(request, 'proceedings/recording.html',{
        'meeting':meeting,
        'form':form,
        'sessions':sessions,
        'unmatched_recordings': get_unmatched_recordings(meeting)},
    )

@role_required('Secretariat')
def recording_edit(request, meeting_num, name):
    '''
    Edit recording Document
    '''
    recording = get_object_or_404(Document, name=name)
    meeting = get_object_or_404(Meeting, number=meeting_num)
    
    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            return redirect('ietf.secr.proceedings.views.recording', meeting_num=meeting_num)
            
        form = RecordingEditForm(request.POST, instance=recording)
        if form.is_valid():
            # save record and rebuild proceedings
            form.save(commit=False)
            e = DocEvent.objects.create(
                type='changed_document',
                by=request.user.person,
                doc=recording,
                rev=recording.rev,
                desc='Changed URL to %s' % recording.external_url,
            )
            recording.save_with_history([e])

            messages.success(request,'Recording saved')
            return redirect('ietf.secr.proceedings.views.recording', meeting_num=meeting_num)
    else:
        form = RecordingEditForm(instance=recording)
    
    return render(request, 'proceedings/recording_edit.html',{
        'meeting':meeting,
        'form':form,
        'recording':recording},
    )
    
# TODO - should probably rename this since it's not selecting groups anymore
def select(request, meeting_num):
    '''
        Provide the secretariat only functions related to meeting materials management
    '''

    if not has_role(request.user,'Secretariat'):
        return HttpResponseRedirect(reverse('ietf.meeting.views.materials_editable_groups', kwargs={'num':meeting_num}))

    meeting = get_object_or_404(Meeting, number=meeting_num)
    proceedings_url = get_proceedings_url(meeting)

    # get the time proceedings were generated
    path = os.path.join(settings.SECR_PROCEEDINGS_DIR,meeting.number,'index.html')
    if os.path.exists(path):
        last_run = datetime.datetime.fromtimestamp(os.path.getmtime(path))
    else:
        last_run = None

    # count PowerPoint files waiting to be converted
    # TODO : This should look at SessionPresentation instead
    ppt = Document.objects.filter(session__meeting=meeting,type='slides',uploaded_filename__endswith='.ppt').exclude(states__slug='deleted')
    pptx = Document.objects.filter(session__meeting=meeting,type='slides',uploaded_filename__endswith='.pptx').exclude(states__slug='deleted')
    ppt_count = ppt.count() + pptx.count()

    return render(request, 'proceedings/select.html', {
        'meeting': meeting,
        'last_run': last_run,
        'proceedings_url': proceedings_url,
        'ppt_count': ppt_count},
    )

