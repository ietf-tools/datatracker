# Copyright The IETF Trust 2013-2020, All Rights Reserved
# -*- coding: utf-8 -*-


'''
proc_utils.py

This module contains all the functions for generating static proceedings pages
'''
import datetime
import os
import re
import subprocess
from urllib.parse import urlencode

import debug        # pyflakes:ignore

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist

from ietf.doc.models import Document, DocAlias, DocEvent, NewRevisionDocEvent, State
from ietf.group.models import Group
from ietf.meeting.models import Meeting, SessionPresentation, TimeSlot, SchedTimeSessAssignment, Session
from ietf.person.models import Person
from ietf.utils.log import log
from ietf.utils.mail import send_mail

AUDIO_FILE_RE = re.compile(r'ietf(?P<number>[\d]+)-(?P<room>.*)-(?P<time>[\d]{8}-[\d]{4})')
VIDEO_TITLE_RE = re.compile(r'IETF(?P<number>[\d]+)-(?P<name>.*)-(?P<date>\d{8})-(?P<time>\d{4})')


def _get_session(number,name,date,time):
    '''Lookup session using data from video title'''
    meeting = Meeting.objects.get(number=number)
    timeslot_time = datetime.datetime.strptime(date + time,'%Y%m%d%H%M')
    try:
        assignment = SchedTimeSessAssignment.objects.get(
            schedule__in = [meeting.schedule, meeting.schedule.base],
            session__group__acronym = name.lower(),
            timeslot__time = timeslot_time,
        )
    except (SchedTimeSessAssignment.DoesNotExist, SchedTimeSessAssignment.MultipleObjectsReturned):
        return None

    return assignment.session

def _get_urls_from_json(doc):
    '''Returns list of dictonary titel,url from search results'''
    urls = []
    for item in doc['items']:
        title = item['snippet']['title']
        #params = dict(v=item['snippet']['resourceId']['videoId'], list=item['snippet']['playlistId'])
        params = [('v',item['snippet']['resourceId']['videoId']), ('list',item['snippet']['playlistId'])]
        url = settings.YOUTUBE_BASE_URL + '?' + urlencode(params)
        urls.append(dict(title=title, url=url))
    return urls

def import_audio_files(meeting):
    '''
    Checks for audio files and creates corresponding materials (docs) for the Session
    Expects audio files in the format ietf[meeting num]-[room]-YYYMMDD-HHMM.*,
    
    Example: ietf90-salonb-20140721-1710.mp3
    '''
    from ietf.meeting.utils import add_event_info_to_session_qs

    unmatched_files = []
    path = os.path.join(settings.MEETING_RECORDINGS_DIR, meeting.type.slug + meeting.number)
    if not os.path.exists(path):
        return None
    for filename in os.listdir(path):
        timeslot = get_timeslot_for_filename(filename)
        if timeslot:
            sessions = add_event_info_to_session_qs(Session.objects.filter(
                timeslotassignments__schedule=timeslot.meeting.schedule_id,
            ).exclude(
                agenda_note__icontains='canceled'
            )).filter(
                current_status='sched',
            ).order_by('timeslotassignments__timeslot__time')
            if not sessions:
                continue
            url = settings.IETF_AUDIO_URL + 'ietf{}/{}'.format(meeting.number, filename)
            doc = get_or_create_recording_document(url, sessions[0])
            attach_recording(doc, sessions)
        else:
            # use for reconciliation email
            unmatched_files.append(filename)
    
    if unmatched_files:
        send_audio_import_warning(unmatched_files)

def get_timeslot_for_filename(filename):
    '''Returns a timeslot matching the filename given.
    NOTE: currently only works with ietfNN prefix (regular meetings)
    '''
    from ietf.meeting.utils import add_event_info_to_session_qs

    basename, _ = os.path.splitext(filename)
    match = AUDIO_FILE_RE.match(basename)
    if match:
        try:
            meeting = Meeting.objects.get(number=match.groupdict()['number'])
            room_mapping = {normalize_room_name(room.name): room.name for room in meeting.room_set.all()}
            time = datetime.datetime.strptime(match.groupdict()['time'],'%Y%m%d-%H%M')
            slots = TimeSlot.objects.filter(
                meeting=meeting,
                location__name=room_mapping[match.groupdict()['room']],
                time=time,
                sessionassignments__schedule__in=[meeting.schedule, meeting.schedule.base if meeting.schedule else None],
            ).distinct()
            uncancelled_slots = [t for t in slots if not add_event_info_to_session_qs(t.sessions.all()).filter(current_status='canceled').exists()]
            return uncancelled_slots[0]
        except (ObjectDoesNotExist, KeyError, IndexError):
            return None

def attach_recording(doc, sessions):
    '''Associate recording document with sessions'''
    for session in sessions:
        if doc not in session.materials.all():
            # add document to session
            presentation = SessionPresentation.objects.create(
                session=session,
                document=doc,
                rev=doc.rev)
            session.sessionpresentation_set.add(presentation)
            if not doc.docalias.filter(name__startswith='recording-{}-{}'.format(session.meeting.number,session.group.acronym)):
                sequence = get_next_sequence(session.group,session.meeting,'recording')
                name = 'recording-{}-{}-{}'.format(session.meeting.number,session.group.acronym,sequence)
                DocAlias.objects.create(name=name).docs.add(doc)

def normalize_room_name(name):
    '''Returns room name converted to be used as portion of filename'''
    return name.lower().replace(' ','').replace('/','_')

def get_or_create_recording_document(url,session):
    try:
        return Document.objects.get(external_url=url)
    except ObjectDoesNotExist:
        return create_recording(session,url)

def create_recording(session, url, title=None, user=None):
    '''
    Creates the Document type=recording, setting external_url and creating
    NewRevisionDocEvent
    '''
    sequence = get_next_sequence(session.group,session.meeting,'recording')
    name = 'recording-{}-{}-{}'.format(session.meeting.number,session.group.acronym,sequence)
    time = session.official_timeslotassignment().timeslot.time.strftime('%Y-%m-%d %H:%M')
    if not title:
        if url.endswith('mp3'):
            title = 'Audio recording for {}'.format(time)
        else:
            title = 'Video recording for {}'.format(time)
        
    doc = Document.objects.create(name=name,
                                  title=title,
                                  external_url=url,
                                  group=session.group,
                                  rev='00',
                                  type_id='recording')
    doc.set_state(State.objects.get(type='recording', slug='active'))

    DocAlias.objects.create(name=doc.name).docs.add(doc)
    
    # create DocEvent
    NewRevisionDocEvent.objects.create(type='new_revision',
                                       by=user or Person.objects.get(name='(System)'),
                                       doc=doc,
                                       rev=doc.rev,
                                       desc='New revision available',
                                       time=doc.time)
    pres = SessionPresentation.objects.create(session=session,document=doc,rev=doc.rev)
    session.sessionpresentation_set.add(pres)

    return doc

def get_next_sequence(group,meeting,type):
    '''
    Returns the next sequence number to use for a document of type = type.
    Takes a group=Group object, meeting=Meeting object, type = string
    '''
    aliases = DocAlias.objects.filter(name__startswith='{}-{}-{}-'.format(type,meeting.number,group.acronym))
    if not aliases:
        return 1
    aliases = aliases.order_by('name')
    sequence = int(aliases.last().name.split('-')[-1]) + 1
    return sequence

def send_audio_import_warning(unmatched_files):
    '''Send email to interested parties that some audio files weren't matched to timeslots'''
    send_mail(request = None,
              to       = settings.AUDIO_IMPORT_EMAIL,
              frm      = "IETF Secretariat <ietf-secretariat@ietf.org>",
              subject  = "Audio file import warning",
              template = "proceedings/audio_import_warning.txt",
              context  = dict(unmatched_files=unmatched_files),
              extra    = {})

# -------------------------------------------------
# End Recording Functions
# -------------------------------------------------

def get_progress_stats(sdate,edate):
    '''
    This function takes a date range and produces a dictionary of statistics / objects for
    use in a progress report.  Generally the end date will be the date of the last meeting
    and the start date will be the date of the meeting before that.
    '''
    data = {}
    data['sdate'] = sdate
    data['edate'] = edate

    events = DocEvent.objects.filter(doc__type='draft',time__gte=sdate,time__lt=edate)
    
    data['actions_count'] = events.filter(type='iesg_approved').count()
    data['last_calls_count'] = events.filter(type='sent_last_call').count()
    new_draft_events = events.filter(newrevisiondocevent__rev='00')
    new_drafts = list(set([ e.doc_id for e in new_draft_events ]))
    data['new_docs'] = list(set([ e.doc for e in new_draft_events ]))
    data['new_drafts_count'] = len(new_drafts)
    data['new_drafts_updated_count'] = events.filter(doc__id__in=new_drafts,newrevisiondocevent__rev='01').count()
    data['new_drafts_updated_more_count'] = events.filter(doc__id__in=new_drafts,newrevisiondocevent__rev='02').count()
    
    update_events = events.filter(type='new_revision').exclude(doc__id__in=new_drafts)
    data['updated_drafts_count'] = len(set([ e.doc_id for e in update_events ]))
    
    # Calculate Final Four Weeks stats (ffw)
    ffwdate = edate - datetime.timedelta(days=28)
    ffw_new_count = events.filter(time__gte=ffwdate,newrevisiondocevent__rev='00').count()
    try:
        ffw_new_percent = format(ffw_new_count / float(data['new_drafts_count']),'.0%')
    except ZeroDivisionError:
        ffw_new_percent = 0
        
    data['ffw_new_count'] = ffw_new_count
    data['ffw_new_percent'] = ffw_new_percent
    
    ffw_update_events = events.filter(time__gte=ffwdate,type='new_revision').exclude(doc__id__in=new_drafts)
    ffw_update_count = len(set([ e.doc_id for e in ffw_update_events ]))
    try:
        ffw_update_percent = format(ffw_update_count / float(data['updated_drafts_count']),'.0%')
    except ZeroDivisionError:
        ffw_update_percent = 0
    
    data['ffw_update_count'] = ffw_update_count
    data['ffw_update_percent'] = ffw_update_percent

    rfcs = events.filter(type='published_rfc')
    data['rfcs'] = rfcs.select_related('doc').select_related('doc__group').select_related('doc__intended_std_level')

    data['counts'] = {'std':rfcs.filter(doc__intended_std_level__in=('ps','ds','std')).count(),
                      'bcp':rfcs.filter(doc__intended_std_level='bcp').count(),
                      'exp':rfcs.filter(doc__intended_std_level='exp').count(),
                      'inf':rfcs.filter(doc__intended_std_level='inf').count()}

    data['new_groups'] = Group.objects.filter(
        type='wg',
        groupevent__changestategroupevent__state='active',
        groupevent__time__gte=sdate,
        groupevent__time__lt=edate)
        
    data['concluded_groups'] = Group.objects.filter(
        type='wg',
        groupevent__changestategroupevent__state='conclude',
        groupevent__time__gte=sdate,
        groupevent__time__lt=edate)

    return data

def is_powerpoint(doc):
    '''
    Returns true if document is a Powerpoint presentation
    '''
    return doc.file_extension() in ('ppt','pptx')

def post_process(doc):
    '''
    Does post processing on uploaded file.
    - Convert PPT to PDF
    '''
    if is_powerpoint(doc) and hasattr(settings,'SECR_PPT2PDF_COMMAND'):
        try:
            cmd = list(settings.SECR_PPT2PDF_COMMAND) # Don't operate on the list actually in settings
            cmd.append(doc.get_file_path())                                 # outdir
            cmd.append(os.path.join(doc.get_file_path(),doc.uploaded_filename))  # filename
            subprocess.check_call(cmd)
        except (subprocess.CalledProcessError, OSError) as error:
            log("Error converting PPT: %s" % (error))
            return
        # change extension
        base,ext = os.path.splitext(doc.uploaded_filename)
        doc.uploaded_filename = base + '.pdf'

        e = DocEvent.objects.create(
            type='changed_document',
            by=Person.objects.get(name="(System)"),
            doc=doc,
            rev=doc.rev,
            desc='Converted document to PDF',
        )
        doc.save_with_history([e])
