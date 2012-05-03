'''
proc_utils.py

This module contains all the functions for generating static proceedings pages
'''
from django.conf import settings
from django.shortcuts import render_to_response
from ietf.group.models import Group
from ietf.meeting.models import Session
from ietf.doc.models import Document, RelatedDocument
from itertools import chain
from sec.proceedings.models import Registration
from sec.utils.document import get_rfc_num
from sec.utils.group import groups_by_session
from sec.utils.meeting import get_upload_root, get_proceedings_path, get_material
from models import InterimMeeting    # proxy model

import datetime
import os
import shutil

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
    This function creates the proceedings.html document.  It gets called anytime there is an
    update to the meeting or the slides for the meeting.
    '''
    
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
    
def write_html(path,content):
    f = open(path,'w')
    f.write(content)
    f.close()