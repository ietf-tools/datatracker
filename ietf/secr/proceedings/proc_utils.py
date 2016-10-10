'''
proc_utils.py

This module contains all the functions for generating static proceedings pages
'''
from urllib2 import urlopen
import datetime
import glob
import os
import shutil

import debug        # pyflakes:ignore

from django.conf import settings
from django.http import HttpRequest
from django.shortcuts import render_to_response, render
from django.db.utils import ConnectionDoesNotExist

from ietf.doc.models import Document, RelatedDocument, DocEvent, NewRevisionDocEvent, State
from ietf.group.models import Group, Role
from ietf.group.utils import get_charter_text
from ietf.meeting.helpers import get_schedule
from ietf.meeting.models import Session, Meeting, SchedTimeSessAssignment, SessionPresentation
from ietf.person.models import Person
from ietf.secr.proceedings.models import InterimMeeting    # proxy model
from ietf.secr.proceedings.models import Registration
from ietf.secr.utils.document import get_rfc_num
from ietf.secr.utils.group import groups_by_session
from ietf.secr.utils.meeting import get_proceedings_path, get_materials, get_session


# -------------------------------------------------
# Helper Functions
# -------------------------------------------------
def check_audio_files(group,meeting):
    '''
    Checks for audio files and creates corresponding materials (docs) for the Session
    Expects audio files in the format ietf[meeting num]-[room]-YYYMMDD-HHMM-*,
    
    Example: ietf90-salonb-20140721-1710-pm3.mp3
    
    '''
    for session in Session.objects.filter(group=group,
                                          meeting=meeting,
                                          status=('sched'),
                                          timeslotassignments__schedule=meeting.agenda):
        timeslot = session.official_timeslotassignment().timeslot
        if not (timeslot.location and timeslot.time):
            continue
        room = timeslot.location.name.lower()
        room = room.replace(' ','')
        room = room.replace('/','_')
        time = timeslot.time.strftime("%Y%m%d-%H%M")
        filename = 'ietf{}-{}-{}*'.format(meeting.number,room,time)
        path = os.path.join(settings.MEETING_RECORDINGS_DIR,'ietf{}'.format(meeting.number),filename)
        for file in glob.glob(path):
            url = 'https://www.ietf.org/audio/ietf{}/{}'.format(meeting.number,os.path.basename(file))
            doc = Document.objects.filter(external_url=url).first()
            if not doc:
                create_recording(session,url)


def create_recording(session,url):
    '''
    Creates the Document type=recording, setting external_url and creating
    NewRevisionDocEvent
    '''
    sequence = get_next_sequence(session.group,session.meeting,'recording')
    name = 'recording-{}-{}-{}'.format(session.meeting.number,session.group.acronym,sequence)
    time = session.official_timeslotassignment().timeslot.time.strftime('%Y-%m-%d %H:%M')
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

    doc.docalias_set.create(name=name)
    
    # create DocEvent
    NewRevisionDocEvent.objects.create(type='new_revision',
                                       by=Person.objects.get(name='(System)'),
                                       doc=doc,
                                       rev=doc.rev,
                                       desc='New revision available',
                                       time=doc.time)
    session.sessionpresentation_set.add(SessionPresentation(session=session,document=doc,rev=doc.rev))

def mycomp(timeslot):
    '''
    This takes a timeslot object and returns a key to sort by the area acronym or None
    '''
    try:
        session = get_session(timeslot)
        group = session.group
        key = '%s:%s' % (group.parent.acronym, group.acronym)
    except AttributeError:
        key = None
    return key

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
    data['new_drafts_count'] = len(new_drafts)
    data['new_drafts_updated_count'] = events.filter(doc__in=new_drafts,newrevisiondocevent__rev='01').count()
    data['new_drafts_updated_more_count'] = events.filter(doc__in=new_drafts,newrevisiondocevent__rev='02').count()
    
    update_events = events.filter(type='new_revision').exclude(doc__in=new_drafts)
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
    
    ffw_update_events = events.filter(time__gte=ffwdate,type='new_revision').exclude(doc__in=new_drafts)
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

def get_next_sequence(group,meeting,type):
    '''
    Returns the next sequence number to use for a document of type = type.
    Takes a group=Group object, meeting=Meeting object, type = string
    '''
    return Document.objects.filter(name__startswith='{}-{}-{}-'.format(type,meeting.number,group.acronym)).count() + 1

def write_html(path,content):
    f = open(path,'w')
    f.write(content)
    f.close()
    try:
        os.chmod(path, 0664)
    except OSError:
        pass
# -------------------------------------------------
# End Helper Functions
# -------------------------------------------------

def create_interim_directory():
    '''
    Create static Interim Meeting directory pages that will live in a different URL space than
    the secretariat Django project
    '''

    # produce date sorted output
    page = 'proceedings.html'
    meetings = InterimMeeting.objects.filter(session__status='sched').order_by('-date')
    response = render(HttpRequest(), 'proceedings/interim_directory.html',{'meetings': meetings})
    path = os.path.join(settings.SECR_INTERIM_LISTING_DIR, page)
    f = open(path,'w')
    f.write(response.content)
    f.close()

    # produce group sorted output
    page = 'proceedings-bygroup.html'
    qs = InterimMeeting.objects.filter(session__status='sched')
    meetings = sorted(qs, key=lambda a: a.group().acronym)
    response = render(HttpRequest(), 'proceedings/interim_directory.html',{'meetings': meetings})
    path = os.path.join(settings.SECR_INTERIM_LISTING_DIR, page)
    f = open(path,'w')
    f.write(response.content)
    f.close()

def create_proceedings(meeting, group, is_final=False):
    '''
    This function creates the  proceedings html document.  It gets called anytime there is an
    update to the meeting or the slides for the meeting.
    NOTE: execution is aborted if the meeting is older than 79 because the format changed.
    '''
    # abort, proceedings from meetings before 79 have a different format, don't overwrite
    if meeting.type_id == 'ietf' and int(meeting.number) < 79:
        return

    check_audio_files(group,meeting)
    materials = get_materials(group,meeting)

    chairs = group.role_set.filter(name='chair')
    secretaries = group.role_set.filter(name='secr')
    if group.parent:        # Certain groups like Tools Team do no have a parent
        ads = group.parent.role_set.filter(name='ad')
    else:
        ads = None
    tas = group.role_set.filter(name='techadv')

    docs = Document.objects.filter(group=group,type='draft').order_by('time')

    meeting_root = meeting.get_materials_path()
    url_root = "%sproceedings/%s/" % (settings.IETF_HOST_URL,meeting.number)

    # Only do these tasks if we are running official proceedings generation,
    # otherwise skip them for expediency.  This procedure is called any time meeting
    # materials are uploaded/deleted, and we don't want to do all this work each time.

    if is_final:
        # ----------------------------------------------------------------------
        # Find active Drafts and RFCs, copy them to id and rfc directories

        drafts = docs.filter(states__slug='active')
        for draft in drafts:
            source = os.path.join(draft.get_file_path(),draft.filename_with_rev())
            target = os.path.join(meeting_root,'id')
            if not os.path.exists(target):
                os.makedirs(target)
            if os.path.exists(source):
                shutil.copy(source,target)
                draft.bytes = os.path.getsize(source)
            else:
                draft.bytes = 0
            draft.url = url_root + "id/%s" % draft.filename_with_rev()

        rfcs = docs.filter(states__slug='rfc')
        for rfc in rfcs:
            # TODO should use get_file_path() here but is incorrect for rfcs
            rfc_num = get_rfc_num(rfc)
            filename = "rfc%s.txt" % rfc_num
            alias = rfc.docalias_set.filter(name='rfc%s' % rfc_num)
            source = os.path.join(settings.RFC_PATH,filename)
            target = os.path.join(meeting_root,'rfc')
            rfc.rmsg = ''
            rfc.msg = ''

            if not os.path.exists(target):
                os.makedirs(target)
            try:
                shutil.copy(source,target)
                rfc.bytes = os.path.getsize(source)
            except IOError:
                pass
            rfc.url = url_root + "rfc/%s" % filename
            rfc.num = "RFC %s" % rfc_num
            # check related documents
            # check obsoletes
            related = rfc.relateddocument_set.all()
            for item in related.filter(relationship='obs'):
                rfc.msg += 'obsoletes %s ' % item.target.name
                #rfc.msg += ' '.join(item.__str__().split()[1:])
            updates_list = [x.target.name.upper() for x in related.filter(relationship='updates')]
            if updates_list:
                rfc.msg += 'updates ' + ','.join(updates_list)
            # check reverse related
            rdocs = RelatedDocument.objects.filter(target=alias)
            for item in rdocs.filter(relationship='obs'):
                rfc.rmsg += 'obsoleted by RFC %s ' % get_rfc_num(item.source)
            updated_list = ['RFC %s' % get_rfc_num(x.source) for x in rdocs.filter(relationship='updates')]
            if updated_list:
                rfc.msg += 'updated by ' + ','.join(updated_list)
    else:
        drafts = rfcs = None

    # ----------------------------------------------------------------------
    # check for blue sheets
    if meeting.number.startswith('interim'):
        pattern = os.path.join(meeting_root,'bluesheets','bluesheets-%s*' % (meeting.number))
    else:
        pattern = os.path.join(meeting_root,'bluesheets','bluesheets-%s-%s-*' % (meeting.number,group.acronym.lower()))
    files = glob.glob(pattern)
    bluesheets = []
    for name in files:
        basename = os.path.basename(name)
        obj = {'name': basename,
               'url': url_root + "bluesheets/" + basename}
        bluesheets.append(obj)
    bluesheets = sorted(bluesheets, key = lambda x: x['name'])


    # the simplest way to display the charter is to place it in a <pre> block
    # however, because this forces a fixed-width font, different than the rest of
    # the document we modify the charter by adding replacing linefeeds with <br>'s
    if group.charter:
        charter = get_charter_text(group).replace('\n','<br />')
        ctime = group.charter.time
    else:
        charter = None
        ctime = None

    status_update = group.latest_event(type='status_update',time__lte=meeting.get_submission_correction_date())

    # rather than return the response as in a typical view function we save it as the snapshot
    # proceedings.html
    response = render_to_response('proceedings/proceedings.html',{
        'bluesheets': bluesheets,
        'charter': charter,
        'ctime': ctime,
        'drafts': drafts,
        'group': group,
        'chairs': chairs,
        'secretaries': secretaries,
        'ads': ads,
        'tas': tas,
        'meeting': meeting,
        'rfcs': rfcs,
        'materials': materials,
        'status_update': status_update,}
    )

    # save proceedings
    proceedings_path = get_proceedings_path(meeting,group)

    f = open(proceedings_path,'w')
    f.write(response.content)
    f.close()
    try:
        os.chmod(proceedings_path, 0664)
    except OSError:
        pass

    # rebuild the directory
    if meeting.type.slug == 'interim':
        create_interim_directory()

# -------------------------------------------------
# Functions for generating Proceedings Pages
# -------------------------------------------------

def gen_areas(context):
    meeting = context['meeting']
    gmet, gnot = groups_by_session(None,meeting)

    # append proceedings URL
    for group in gmet + gnot:
        group.proceedings_url = "%sproceedings/%s/%s.html" % (settings.IETF_HOST_URL,meeting.number,group.acronym)

    for (counter,area) in enumerate(context['areas'], start=1):
        groups_met = {'wg':filter(lambda a: a.parent==area and a.state.slug not in ('bof','bof-conc') and a.type_id=='wg',gmet),
                      'bof':filter(lambda a: a.parent==area and a.state.slug in ('bof','bof-conc') and a.type_id=='wg',gmet),
                      'ag':filter(lambda a: a.parent==area and a.type_id=='ag',gmet)}

        groups_not = {'wg':filter(lambda a: a.parent==area and a.state.slug not in ('bof','bof-conc') and a.type_id=='wg',gnot),
                      'bof':filter(lambda a: a.parent==area and a.state.slug=='bof' and a.type_id=='wg',gnot),
                      'ag':filter(lambda a: a.parent==area and a.type_id=='ag',gnot)}

        html = render_to_response('proceedings/area.html',{
            'area': area,
            'meeting': meeting,
            'groups_met': groups_met,
            'groups_not': groups_not,
            'index': counter}
        )

        path = os.path.join(settings.SECR_PROCEEDINGS_DIR,meeting.number,'%s.html' % area.acronym)
        write_html(path,html.content)

def gen_acknowledgement(context):
    meeting = context['meeting']

    html = render_to_response('proceedings/acknowledgement.html',{
        'meeting': meeting}
    )

    path = os.path.join(settings.SECR_PROCEEDINGS_DIR,meeting.number,'acknowledgement.html')
    write_html(path,html.content)

def gen_agenda(context):
    meeting = context['meeting']
    schedule = get_schedule(meeting)
    schedtimesessassignments = SchedTimeSessAssignment.objects.filter(schedule=schedule).exclude(session__isnull=True)

    html = render_to_response('proceedings/agenda.html',{
        'meeting': meeting,
        'schedtimesessassignments': schedtimesessassignments}
    )

    path = os.path.join(settings.SECR_PROCEEDINGS_DIR,meeting.number,'agenda.html')
    write_html(path,html.content)

    # get the text agenda from datatracker
    url = 'https://datatracker.ietf.org/meeting/%s/agenda.txt' % meeting.number
    text = urlopen(url).read()
    path = os.path.join(settings.SECR_PROCEEDINGS_DIR,meeting.number,'agenda.txt')
    write_html(path,text)

def gen_attendees(context):
    meeting = context['meeting']

    attendees = Registration.objects.using('ietf' + meeting.number).all().order_by('lname')

    if settings.SERVER_MODE!='production':
        try:
            attendees.count()
        except ConnectionDoesNotExist:
            attendees = Registration.objects.none()

    html = render_to_response('proceedings/attendee.html',{
        'meeting': meeting,
        'attendees': attendees}
    )

    path = os.path.join(settings.SECR_PROCEEDINGS_DIR,meeting.number,'attendee.html')
    write_html(path,html.content)

def gen_group_pages(context):
    meeting = context['meeting']

    for group in Group.objects.filter(type__in=('wg','ag','rg'), state__in=('bof','proposed','active')):
        create_proceedings(meeting,group,is_final=True)

def gen_index(context):
    index = render_to_response('proceedings/index.html',context)
    path = os.path.join(settings.SECR_PROCEEDINGS_DIR,context['meeting'].number,'index.html')
    write_html(path,index.content)

def gen_irtf(context):
    meeting = context['meeting']
    irtf_chair = Role.objects.filter(group__acronym='irtf',name='chair')[0]

    html = render_to_response('proceedings/irtf.html',{
        'irtf_chair':irtf_chair}
    )
    path = os.path.join(settings.SECR_PROCEEDINGS_DIR,meeting.number,'irtf.html')
    write_html(path,html.content)

def gen_overview(context):
    meeting = context['meeting']

    ietf_chair = Role.objects.get(group__acronym='ietf',name='chair')
    ads = Role.objects.filter(group__type='area',group__state='active',name='ad')
    sorted_ads = sorted(ads, key = lambda a: a.person.name_parts()[3])

    html = render_to_response('proceedings/overview.html',{
        'meeting': meeting,
        'ietf_chair': ietf_chair,
        'ads': sorted_ads}
    )

    path = os.path.join(settings.SECR_PROCEEDINGS_DIR,meeting.number,'overview.html')
    write_html(path,html.content)

def gen_plenaries(context):
    '''
    This function generates pages for the Plenaries.  At meeting 85 the Plenary sessions
    were combined into one, so we need to handle not finding one of the sessions.
    '''
    meeting = context['meeting']

    # Administration Plenary
    try:
        admin_session = Session.objects.get(meeting=meeting,name__contains='Administration Plenary')
        admin_slides = admin_session.materials.filter(type='slides')
        admin_minutes = admin_session.materials.filter(type='minutes')
        admin = render_to_response('proceedings/plenary.html',{
            'title': 'Administrative',
            'meeting': meeting,
            'slides': admin_slides,
            'minutes': admin_minutes}
        )
        path = os.path.join(settings.SECR_PROCEEDINGS_DIR,context['meeting'].number,'administrative-plenary.html')
        write_html(path,admin.content)
    except Session.DoesNotExist:
        pass

    # Technical Plenary
    try:
        tech_session = Session.objects.get(meeting=meeting,name__contains='Technical Plenary')
        tech_slides = tech_session.materials.filter(type='slides')
        tech_minutes = tech_session.materials.filter(type='minutes')
        tech = render_to_response('proceedings/plenary.html',{
            'title': 'Technical',
            'meeting': meeting,
            'slides': tech_slides,
            'minutes': tech_minutes}
        )
        path = os.path.join(settings.SECR_PROCEEDINGS_DIR,context['meeting'].number,'technical-plenary.html')
        write_html(path,tech.content)
    except Session.DoesNotExist:
        pass

def gen_progress(context, final=True):
    '''
    This function generates the Progress Report.  This report is actually produced twice.  First
    for inclusion in the Admin Plenary, then for the final proceedings.  When produced the first
    time we want to exclude the headers because they are broken links until all the proceedings
    are generated.
    '''
    meeting = context['meeting']

    # proceedings are run sometime after the meeting, so end date = the passed meeting
    # date and start date = the date of the meeting before that
    previous_meetings = Meeting.objects.filter(type='ietf',date__lt=meeting.date).order_by('-date')
    start_date = previous_meetings[0].date
    end_date = meeting.date
    data = get_progress_stats(start_date,end_date)
    data['meeting'] = meeting
    data['final'] = final

    html = render_to_response('proceedings/progress.html',data)

    path = os.path.join(settings.SECR_PROCEEDINGS_DIR,meeting.number,'progress-report.html')
    write_html(path,html.content)

def gen_research(context):
    meeting = context['meeting']
    gmet, gnot = groups_by_session(None,meeting)

    groups = [ g for g in gmet if g.type_id=='rg' or (g.type_id=='ag' and g.parent.acronym=='irtf') ]

    # append proceedings URL
    for group in groups:
        group.proceedings_url = "%sproceedings/%s/%s.html" % (settings.IETF_HOST_URL,meeting.number,group.acronym)

    html = render_to_response('proceedings/rg_irtf.html',{
        'meeting': meeting,
        'groups': groups}
    )

    path = os.path.join(settings.SECR_PROCEEDINGS_DIR,meeting.number,'rg_irtf.html')
    write_html(path,html.content)

def gen_training(context):
    meeting = context['meeting']
    timeslots = context['others']
    sessions = [ get_session(t) for t in timeslots ]
    for counter,session in enumerate(sessions, start=1):
        slides = session.materials.filter(type='slides')
        minutes = session.materials.filter(type='minutes')
        html = render_to_response('proceedings/training.html',{
            'title': '4.%s %s' % (counter, session.name),
            'meeting': meeting,
            'slides': slides,
            'minutes': minutes}
        )
        path = os.path.join(settings.SECR_PROCEEDINGS_DIR,meeting.number,'train-%s.html' % counter )
        write_html(path,html.content)

