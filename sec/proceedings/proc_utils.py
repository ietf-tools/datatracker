'''
proc_utils.py

This module contains all the functions for generating static proceedings pages
'''
from django.conf import settings
from django.shortcuts import render_to_response
from ietf.group.models import Group
from ietf.meeting.models import Session
from ietf.doc.models import Document, RelatedDocument
from sec.utils.document import get_rfc_num
from sec.utils.meeting import get_upload_root, get_proceedings_path, get_material
from models import InterimMeeting    # proxy model

import datetime
import os
import shutil

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
    groups_met, groups_not = groups_by_session(None,context['meeting'])
    for area in context['areas']:
        #
        html = render_to_response('proceedings/area.html',context)
        path = os.path.join(settings.PROCEEDINGS_DIR,context['meeting'].number,'%s.html' % area.acronym)
        write_html(path,html.content)
    
def gen_index(context):
    index = render_to_response('proceedings/index.html',context)
    path = os.path.join(settings.PROCEEDINGS_DIR,context['meeting'].number,'index.html')
    write_html(path,index.content)

def write_html(path,content):
    f = open(path,'w')
    f.write(content)
    f.close()