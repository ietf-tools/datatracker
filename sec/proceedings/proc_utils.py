'''
proc_utils.py

This module contains all the functions for generating static proceedings pages
'''
from django.conf import settings
from django.shortcuts import render_to_response
from ietf.group.models import Group, Role
from ietf.meeting.models import Session, TimeSlot
from ietf.meeting.views import agenda_info
from ietf.doc.models import Document, RelatedDocument, DocEvent
from itertools import chain
from sec.proceedings.models import Registration
from sec.utils.document import get_rfc_num
from sec.utils.group import groups_by_session
from sec.utils.meeting import get_upload_root, get_proceedings_path, get_material
from models import InterimMeeting    # proxy model

from urllib2 import urlopen
import datetime
import os
import shutil

# -------------------------------------------------
# Helper Functions
# -------------------------------------------------

def copy_files(meeting):
    '''
    This function copies all the static html pages from the last meeting
    NOTE: it won't overwrite files already there because these may be 
    modified manually
    '''
    file_list = ['acknowledgement.html','overview.html','irtf.html']
    last_meeting = str(int(meeting.number) - 1)
    
    for file in file_list:
        source = os.path.join(settings.PROCEEDINGS_DIR,last_meeting,file)
        target = os.path.join(settings.PROCEEDINGS_DIR,meeting.number,file)
        if not os.path.exists(target):
            shutil.copy(source,target)

def get_progress_stats(sdate,edate):
    '''
    This function takes a date range and produces a dictionary of statistics / objects for use
    in a progress report.
    '''
    data = {}
    data['sdate'] = sdate
    data['edate'] = edate
    data['docevents'] = DocEvent.objects.filter(doc__type='draft',time__gte=sdate,time__lte=edate)
    data['action_events'] = data['docevents'].filter(type='iesg_approved')
    data['lc_events'] = data['docevents'].filter(type='sent_last_call')
    
    data['new_groups'] = Group.objects.filter(type='wg',
                                              groupevent__changestategroupevent__state='active',
                                              groupevent__time__gte=sdate,
                                              groupevent__time__lte=edate)
    
    data['concluded_groups'] = Group.objects.filter(type='wg',
                                                    groupevent__changestategroupevent__state='conclude',
                                                    groupevent__time__gte=sdate,
                                                    groupevent__time__lte=edate)
                                  
    data['new_docs'] = Document.objects.filter(type='draft').filter(docevent__type='new_revision',
                                                                    docevent__time__gte=sdate,
                                                                    docevent__time__lte=edate).distinct()
    
    data['rfcs'] = DocEvent.objects.filter(type='published_rfc',
                                           doc__type='draft',
                                           time__gte=sdate,
                                           time__lte=edate)
                                   
    data['counts'] = {'std':data['rfcs'].filter(doc__intended_std_level__in=('ps','ds','std')).count(),
                      'bcp':data['rfcs'].filter(doc__intended_std_level='bcp').count(),
                      'exp':data['rfcs'].filter(doc__intended_std_level='exp').count(),
                      'inf':data['rfcs'].filter(doc__intended_std_level='inf').count()}
    
    return data
    
def write_html(path,content):
    f = open(path,'w')
    f.write(content)
    f.close()
    
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
    meetings = InterimMeeting.objects.order_by('-date')
    response = render_to_response('proceedings/interim_directory.html',{'meetings': meetings})
    path = os.path.join(settings.INTERIM_LISTING_DIR, page)
    f = open(path,'w')
    f.write(response.content)
    f.close()
    
    # produce group sorted output
    page = 'proceedings-bygroup.html'
    qs = InterimMeeting.objects.all()
    meetings = sorted(qs, key=lambda a: a.group().acronym)
    response = render_to_response('proceedings/interim_directory.html',{'meetings': meetings})
    path = os.path.join(settings.INTERIM_LISTING_DIR, page)
    f = open(path,'w')
    f.write(response.content)
    f.close()
    
def create_proceedings(meeting, group):
    '''
    This function creates the  proceedings html document.  It gets called anytime there is an
    update to the meeting or the slides for the meeting.
    NOTE: execution is aborted if the meeting is older than 79 because the format changed.
    '''
    # abort, old format
    if meeting.type_id == 'ietf' and int(meeting.number) < 79:
        return
        
    session = Session.objects.filter(meeting=meeting,group=group)[0]
    agenda,minutes,slides = get_material(session)
    chairs = group.role_set.filter(name='chair')
    secretaries = group.role_set.filter(name='secr')
    ads = group.parent.role_set.filter(name='ad')
    tas = group.role_set.filter(name='techadv')
    
    docs = Document.objects.filter(group=group,type='draft').order_by('time')
    drafts = docs.filter(states__slug='active')
    rfcs = docs.filter(states__slug='rfc')
    
    # stage Documents and add bytes/url for use in template
    meeting_root = get_upload_root(meeting)
    if meeting.type.slug == 'ietf':
        url_root = "%s/proceedings/%s/" % (settings.MEDIA_URL,meeting.number)
    else:
        url_root = "%s/proceedings/interim/%s/%s/" % (
            settings.MEDIA_URL,
            meeting.date.strftime('%Y/%m/%d'),
            group.acronym)
    for draft in drafts:
        source = os.path.join(draft.get_file_path(),draft.filename_with_rev())
        target = os.path.join(meeting_root,'id')
        if not os.path.exists(target):
            os.makedirs(target)
        shutil.copy(source,target)
        draft.url = url_root + "id/%s" % draft.filename_with_rev()
        draft.bytes = os.path.getsize(source)
    
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
        shutil.copy(source,target)
        rfc.url = url_root + "rfc/%s" % filename
        rfc.bytes = os.path.getsize(source)
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
        
    # the simplest way to display the charter is to place it in a <pre> block
    # however, because this forces a fixed-width font, different than the rest of
    # the document we modify the charter by adding replacing linefeeds with <br>'s
    # TODO when get_charter_text() works we should use it
    #charter = get_charter_text(group).replace('\n','<br>')
    ctime = None
    cpath = os.path.join(settings.GROUP_DESCRIPTION_DIR,'%s.desc.txt' % group.acronym.lower())
    if os.path.exists(cpath):
        f = open(cpath,'r')
        desc = f.read()
        f.close()
        ctime = datetime.datetime.fromtimestamp(os.path.getmtime(cpath))
        charter = desc.replace('\n','<br>')
    else:
        charter = 'Charter not found.'
    
    # rather than return the response as in a typical view function we save it as the snapshot
    # proceedings.html
    response = render_to_response('proceedings/proceedings.html',{
        'charter': charter,
        'ctime': ctime,
        'drafts': drafts,
        'group': group,
        'chairs': chairs,
        'secretaries': secretaries,
        'ads': ads,
        'tas': tas,
        'meeting':meeting,
        'rfcs': rfcs,
        'slides': slides}
    )
    
    # save proceedings
    proceedings_path = get_proceedings_path(meeting,group)
    
    f = open(proceedings_path,'w')
    f.write(response.content)
    f.close()
    
    # rebuild the directory
    if meeting.type == 'interim':
        create_interim_directory()

# -------------------------------------------------
# Functions for generating Proceedings Pages
# -------------------------------------------------

def gen_areas(context):
    meeting = context['meeting']
    gmet, gnot = groups_by_session(None,meeting)
    
    # append proceedings URL
    for group in gmet + gnot:
        group.proceedings_url = "%s/proceedings/%s/%s.html" % (settings.MEDIA_URL,meeting.number,group.acronym)
    
    for (counter,area) in enumerate(context['areas'], start=1):    
        groups_met = {'wg':filter(lambda a: a.parent==area and a.state.slug!='bof' and a.type_id=='wg',gmet),
                      'bof':filter(lambda a: a.parent==area and a.state.slug=='bof' and a.type_id=='wg',gmet),
                      'ag':filter(lambda a: a.parent==area and a.type_id=='ag',gmet)}
                      
        groups_not = {'wg':filter(lambda a: a.parent==area and a.state.slug!='bof' and a.type_id=='wg',gnot),
                      'bof':filter(lambda a: a.parent==area and a.state.slug=='bof' and a.type_id=='wg',gnot),
                      'ag':filter(lambda a: a.parent==area and a.type_id=='ag',gnot)}
                      
        html = render_to_response('proceedings/area.html',{
            'area': area,
            'meeting': meeting,
            'groups_met': groups_met,
            'groups_not': groups_not,
            'index': counter}
        )
        
        path = os.path.join(settings.PROCEEDINGS_DIR,meeting.number,'%s.html' % area.acronym)
        write_html(path,html.content)

def gen_acknowledgement(context):
    meeting = context['meeting']
    
    html = render_to_response('proceedings/acknowledgement.html',{
        'meeting': meeting}
    )
    
    path = os.path.join(settings.PROCEEDINGS_DIR,meeting.number,'acknowledgement.html')
    write_html(path,html.content)
    
def gen_agenda(context):
    meeting = context['meeting']
    
    # grab the agenda from datatracker
    #url = 'https://datatracker.ietf.org/meeting/%s/agenda.html' % meeting.number
    #html = urlopen(url).read()
    
    #timeslots, update, meeting, venue, ads, plenaryw_agenda, plenaryt_agenda = agenda_info(meeting.number)
    timeslots = TimeSlot.objects.filter(meeting=meeting).order_by('time')
    
    html = render_to_response('proceedings/agenda.html',{
        'meeting': meeting,
        'timeslots': timeslots}
    )
    
    path = os.path.join(settings.PROCEEDINGS_DIR,meeting.number,'agenda.html')
    write_html(path,html.content)
    
def gen_attendees(context):
    meeting = context['meeting']
    
    attendees = Registration.objects.using('ietf' + meeting.number).all().order_by('lname')
    
    html = render_to_response('proceedings/attendee.html',{
        'meeting': meeting,
        'attendees': attendees}
    )
    
    path = os.path.join(settings.PROCEEDINGS_DIR,meeting.number,'attendee.html')
    write_html(path,html.content)
    
def gen_index(context):
    index = render_to_response('proceedings/index.html',context)
    path = os.path.join(settings.PROCEEDINGS_DIR,context['meeting'].number,'index.html')
    write_html(path,index.content)

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
    
    path = os.path.join(settings.PROCEEDINGS_DIR,meeting.number,'overview.html')
    write_html(path,html.content)
    
def gen_plenaries(context):
    meeting = context['meeting']
    admin_session = Session.objects.get(meeting=meeting,name__contains='Administration Plenary')
    admin_slides = admin_session.materials.filter(type='slides')
    admin_minutes = admin_session.materials.filter(type='minutes')
    admin = render_to_response('proceedings/plenary.html',{
        'title': 'Administrative',
        'meeting': meeting,
        'slides': admin_slides,
        'minutes': admin_minutes}
    )
    path = os.path.join(settings.PROCEEDINGS_DIR,context['meeting'].number,'administrative-plenary.html')
    write_html(path,admin.content)
    
    tech_session = Session.objects.get(meeting=meeting,name__contains='Technical Plenary')
    tech_slides = tech_session.materials.filter(type='slides')
    tech_minutes = tech_session.materials.filter(type='minutes')
    tech = render_to_response('proceedings/plenary.html',{
        'title': 'Technical',
        'meeting': meeting,
        'slides': tech_slides,
        'minutes': tech_minutes}
    )
    path = os.path.join(settings.PROCEEDINGS_DIR,context['meeting'].number,'technical-plenary.html')
    write_html(path,tech.content)

def gen_progress(context):
    meeting = context['meeting']
    
    start_date = meeting.get_submission_start_date()
    end_date = meeting.get_submission_cut_off_date()
    data = get_progress_stats(start_date,end_date)
    data['meeting'] = meeting
    
    html = render_to_response('proceedings/progress.html',data)
    
    path = os.path.join(settings.PROCEEDINGS_DIR,meeting.number,'progress-report.html')
    write_html(path,html.content)
    
def gen_research(context):
    meeting = context['meeting']
    gmet, gnot = groups_by_session(None,meeting)
    
    groups = filter(lambda a: a.type_id=='rg', gmet)
    
    # append proceedings URL
    for group in groups:
        group.proceedings_url = "%s/proceedings/%s/%s.html" % (settings.MEDIA_URL,meeting.number,group.acronym)
    
    html = render_to_response('proceedings/rg_irtf.html',{
        'meeting': meeting,
        'groups': groups}
    )
    
    path = os.path.join(settings.PROCEEDINGS_DIR,meeting.number,'rg_irtf.html')
    write_html(path,html.content)
        
def gen_training(context):
    meeting = context['meeting']
    timeslots = context['others']
    sessions = [ t.session for t in timeslots ]
    for counter,session in enumerate(sessions, start=1):
        slides = session.materials.filter(type='slides')
        minutes = session.materials.filter(type='minutes')
        html = render_to_response('proceedings/training.html',{
            'title': '4.%s %s' % (counter, session.name),
            'meeting': meeting,
            'slides': slides,
            'minutes': minutes}
        )
        path = os.path.join(settings.PROCEEDINGS_DIR,meeting.number,'train-%s.html' % counter )
        write_html(path,html.content)
    
