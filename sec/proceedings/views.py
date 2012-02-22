from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.core.urlresolvers import reverse
from django.db.models import Max
from django.forms.formsets import formset_factory
from django.forms.models import inlineformset_factory, modelformset_factory
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.template import Context
from django.template.defaultfilters import slugify
from django.template.loader import get_template
from django.utils import simplejson
from django.db.models import Max,Count,get_model

from sec.utils.decorators import check_permissions, sec_only
from sec.utils.group import get_my_groups, groups_by_session
from sec.utils.meeting import get_upload_root
from sec.sreq.forms import GroupSelectForm

from ietf.doc.models import Document, DocAlias, DocEvent, State, NewRevisionDocEvent
from ietf.group.models import Group
from ietf.group.proxy import IETFWG
from ietf.group.utils import get_charter_text
from ietf.ietfauth.decorators import has_role
from ietf.meeting.models import Meeting, Session
from ietf.name.models import MeetingTypeName, SessionStatusName

from forms import *
from models import InterimMeeting    # proxy model

import datetime
import glob
import itertools
import os
import re
import shutil
import zipfile

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

def create_proceedings(meeting):
    '''
    This function creates the proceedings.html document.  It gets called anytime there is an
    update to the meeting or the slides for the meeting.
    
    NOTE:
    AS OF DEPLOYMENT (06-06-2011) THIS FUNCTION ONLY USED FOR INTERIM MEETINGS.
    So we check if the meeting is interim, if not we do nothing.  For now regular
    proceedings are being built by Priyanka's PHP app.
    
    If activating for regulary proceedings need to:
    - remove abort
    - change the proceedings_path
    - changes slides queryset
    - change minutes and agenda queries
    '''
    
    # abort if not interim
    if meeting.type_id != 'interim':
        return
    
    # get InterimMeeting proxy object
    interim_meeting = InterimMeeting.objects.get(id=meeting.id)
    group = interim_meeting.group()
    session = Session.objects.filter(meeting=meeting,group=group)[0]
    agenda,minutes,slides = get_material(session)
    chairs = group.role_set.filter(name='chair')
    secretaries = group.role_set.filter(name='secr')
    ads = group.parent.role_set.filter(name='ad')
    tas = group.role_set.filter(name='techadv')
    
    drafts = Document.objects.filter(group=group,
                                     type='draft',
                                     states__slug='active').order_by('time')
    # TODO order by RFC number
    rfcs = Document.objects.filter(group=group,
                                    type='rfc',
                                    states__slug='active').order_by('time')
    
    # the simplest way to display the charter is to place it in a <pre> block
    # however, because this forces a fixed-width font, different than the rest of
    # the document we modify the charter by adding replacing linefeeds with <br>'s
    charter = get_charter_text(group).replace('\n','<br>')
    
    # rather than return the response as in a typical view function we save it as the snapshot
    # proceedings.html
    response = render_to_response('proceedings/proceedings.html',{
        'charter': charter,
        'drafts': drafts,
        'group': group,
        'chairs': chairs,
        'secretaries': secretaries,
        'ads': ads,
        'tas': tas,
        'meeting':interim_meeting,
        'rfcs': rfcs,
        'slides': slides}
    )
    
    # save proceedings
    proceedings_path = interim_meeting.get_proceedings_path()
    
    f = open(proceedings_path,'w')
    f.write(response.content)
    f.close()
    
    # rebuild the directory
    create_interim_directory()

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
    the full path to the file on disk.  During migration of the system the
    filename was saved in external_url, new files will also use this convention.
    '''
    session = doc.session_set.all()[0]
    meeting = session.meeting
    if doc.external_url:
        return os.path.join(get_upload_root(meeting),doc.type.slug,doc.external_url)
    else:
        path = os.path.join(get_upload_root(meeting),doc.type.slug,doc.name)
        files = glob.glob(path + '.*')
        # TODO we might want to choose from among multiple files using some logic
        return files[0]

def get_material(session):
    '''
    This function takes a session object and returns a tuple of active materials:
    agenda(Document), minutes(Document), slides(list of Documents)
    '''
    active_materials = session.materials.exclude(states__slug='deleted')
    slides = active_materials.filter(type='slides').order_by('order')
    minutes = active_materials.filter(type='minutes')
    minutes = minutes[0] if minutes else None
    agenda = active_materials.filter(type='agenda')
    agenda = agenda[0] if agenda else None
    
    return agenda,minutes,slides

def get_next_interim_num(acronym,date):
    '''
    This function takes a group acronym and date object and returns the next number to use for an
    interim meeting.  The format is interim-[year]-[acronym]-[1-9]
    '''
    base = 'interim-%s-%s-' % (date.year, acronym)
    # can't use count() to calculate the next number in case one was deleted
    meetings = list(Meeting.objects.filter(type='interim',number__startswith=base).order_by('number'))
    if meetings:
        parts = meetings[-1].number.split('-')
        return base + str(int(parts[-1]) + 1)
    else:
        return base + '1'
    
def get_next_slide_num(session):
    '''
    This function takes a session object and returns the
    next slide number to use for a newly added slide as a string.
    '''
    # slides = session.materials.filter(type='slides').order_by('-name')
    # can't use this approach because if there's a slide out there that isn't
    # related to the session somehow, we may get an error trying to create
    # a docuument object with a duplicate name
    if session.meeting.type_id == 'ietf':
        pattern = 'slides-%s-%s' % (session.meeting.number,session.group.acronym)
    elif session.meeting.type_id == 'interim':
        pattern = 'slides-%s' % (session.meeting.number)
    slides = Document.objects.filter(type='slides',name__startswith=pattern).order_by('-name')
    if slides:
        last_num = slides[0].name.split('-')[-1]
        return str(int(last_num) + 1)
    else:
        return '0'

def get_next_order_num(session):
    '''
    This function takes a session object and returns the
    next slide order number to use for a newly added slide as an integer.
    '''
    max_order = session.materials.aggregate(Max('order'))['order__max']
    
    return max_order + 1 if max_order else 1

# --- These could be properties/methods on meeting
def get_proceedings_path(meeting,group):
    if meeting.type_id == 'ietf':
        path = os.path.join(get_upload_root(meeting),group.acronym + '.html')
    elif meeting.type_id == 'interim':
        path = os.path.join(get_upload_root(meeting),'proceedings.html')
    return path

def get_proceedings_url(meeting,group):
    if meeting.type_id == 'ietf':
        url = "%s/proceedings/%s/%s.html" % (
            settings.MEDIA_URL,
            meeting.number,
            group.acronym)
    elif meeting.type_id == 'interim':
        url = "%s/proceedings/interim/%s/%s/proceedings.html" % (
            settings.MEDIA_URL,
            meeting.date.strftime('%Y/%m/%d'),
            group.acronym)
    return url
    
def handle_upload_file(file,filename,meeting,subdir): 
    '''
    This function takes a file object, a filename and a meeting object and subdir as string.
    It saves the file to the appropriate directory, get_upload_root() + subdir.
    If the file is a zip file, it creates a new directory in 'slides', which is the basename of the
    zip file and unzips the file in the new directory.
    '''
    # filename gets saved elsewhere w/o lower so don't do it here
    #filename = filename.lower()
    base, extension = os.path.splitext(filename)
    
    if extension == '.zip':
        path = os.path.join(get_upload_root(meeting),subdir,base)
        if not os.path.exists(path):
            os.mkdir(path)
    else:
        path = os.path.join(get_upload_root(meeting),subdir)
        
    destination = open(os.path.join(path,filename), 'wb+')
    for chunk in file.chunks():
        destination.write(chunk)
    destination.close()

    # unzip zipfile
    if extension == '.zip':
        os.chdir(path)
        os.system('unzip %s' % filename)

def make_directories(meeting):
    '''
    This function takes a meeting object and creates the appropriate materials directories
    '''
    path = get_upload_root(meeting)
    os.umask(0)
    for leaf in ('slides','agenda','minutes','id','rfc'):
        target = os.path.join(path,leaf)
        if not os.path.exists(target):
            os.makedirs(target)
    
def parsedate(d):
    '''
    This function takes a date object and returns a tuple of year,month,day
    '''
    return (d.strftime('%Y'),d.strftime('%m'),d.strftime('%d'))
    
# --------------------------------------------------
# STANDARD VIEW FUNCTIONS
# --------------------------------------------------
@sec_only
def build_proc(request,meeting_num):
    '''
    This is a utility or test view.  It simply rebuilds the proceedings.html for the specified
    interim meeting.
    '''
    meeting = InterimMeeting.objects.get(number=meeting_num)
    create_proceedings(meeting)
    
    messages.success(request,'proceedings.html was rebuilt')
    url = reverse('proceedings_upload_unified', kwargs={'meeting_num':meeting_num,'acronym':meeting.group().acronym})
    return HttpResponseRedirect(url)
    
@check_permissions
def delete_material(request,meeting_num,acronym,name):
    '''
    This view handles deleting meeting materials.  We don't actually delete the
    document object but set the state to deleted and add a 'deleted' DocEvent.
    '''
    doc = get_object_or_404(Document, name=name)
    meeting = Meeting.objects.get(number=meeting_num)
    session = Session.objects.filter(meeting=meeting.id,group__acronym=acronym)[0]
    
    # don't delete the file, in the future may support undo feature
    #files = glob.glob(os.path.join(doc.get_file_path(),name) + '.*')
    #for file in files:
    #    os.remove(file)
    
    # leave it related
    #session.materials.remove(doc)
    
    state = State.objects.get(type=doc.type,slug='deleted')
    doc.set_state(state)
    
    # create   deleted_document
    DocEvent.objects.create(doc=doc,
                            by=request.user.get_profile(),
                            type='deleted')
                                    
    create_proceedings(meeting)
        
    messages.success(request,'The material was deleted successfully')
    url = reverse('proceedings_upload_unified', kwargs={'meeting_num':meeting_num,'acronym':acronym})
    return HttpResponseRedirect(url)

@sec_only
def delete_interim_meeting(request, meeting_num):
    '''
    This view deletes the specified Interim Meeting and any material that has been
    uploaded for it.  The pattern in urls.py ensures we don't call this with a regular
    meeting number.
    '''
    meeting = get_object_or_404(Meeting, number=meeting_num)
    sessions = Session.objects.filter(meeting=meeting)
    group = sessions[0].group
    
    # delete directories
    path = get_upload_root(meeting)
    
    # do a quick sanity check on this path before we go and delete it
    parts = path.split('/')
    assert parts[-1] == group.acronym
    
    if os.path.exists(path):
        shutil.rmtree(path)
    
    meeting.delete()
    sessions.delete()

    url = reverse('proceedings_interim', kwargs={'acronym':group.acronym})
    return HttpResponseRedirect(url)

@check_permissions
def edit_slide(request, meeting_num, acronym, slide_id):
    '''
    This view allows the user to edit the name of a slide.
    '''
    # we need to pass group to the template for the breadcrumbs
    group = get_object_or_404(Group, acronym=acronym)
    slide = get_object_or_404(Document, name=slide_id)
    meeting = get_object_or_404(Meeting, number=meeting_num)

    if request.method == 'POST': # If the form has been submitted...
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            url = reverse('proceedings_upload_unified', kwargs={'meeting_num':meeting_num,'acronym':group.acronym})
            return HttpResponseRedirect(url)
            
        form = EditSlideForm(request.POST, instance=slide) # A form bound to the POST data
        if form.is_valid(): 
            form.save()
            
            # rebuild proceedings.html
            create_proceedings(slide.meeting.pk)
            url = reverse('proceedings_upload_unified', kwargs={'meeting_num':meeting_num,'acronym':acronym})
            return HttpResponseRedirect(url)
    else:
        form = EditSlideForm(instance=slide)
    
    return render_to_response('proceedings/edit_slide.html',{
        'group': group,
        'meeting':meeting,
        'slide':slide,
        'form':form},
        RequestContext(request, {}),
    )

def interim(request, acronym):
    '''
    This view presents the user with a list of interim meetings for the specified group.
    The user can select a meeting to manage or create a new interim meeting by entering
    a date.
    '''
    group = get_object_or_404(Group, acronym=acronym)
    if request.method == 'POST': # If the form has been submitted...
        button_text = request.POST.get('submit', '')
        if button_text == 'Back':
            url = reverse('proceedings_select_interim')
            return HttpResponseRedirect(url)
            
        form = InterimMeetingForm(request.POST) # A form bound to the POST data
        if form.is_valid():
            date = form.cleaned_data['date']
            number = get_next_interim_num(acronym,date)
            meeting=Meeting.objects.create(type_id='interim',
                                           date=date,
                                           number=number)
            
            # create session to associate this meeting with a group and hold material
            Session.objects.create(meeting=meeting,
                                   group=group,
                                   requested_by=request.user.get_profile(),
                                   status_id='sched')
                                   
            create_interim_directory()
            make_directories(meeting)

            messages.success(request, 'Meeting created')
            url = reverse('proceedings_interim', kwargs={'acronym':acronym})
            return HttpResponseRedirect(url)
    else:
        form = InterimMeetingForm(initial={'group_acronym_id':acronym}) # An unbound form
        
    meetings = Meeting.objects.filter(type='interim',session__group__acronym=acronym).order_by('date')
    
    return render_to_response('proceedings/interim_meeting.html',{
        'group': group,
        'meetings':meetings,
        'form':form},
        RequestContext(request, {}),
    )

def interim_directory(request, sortby=None):
    
    if sortby == 'group':
        qs = InterimMeeting.objects.all()
        meetings = sorted(qs, key=lambda a: a.group.acronym)
    else:
        meetings = InterimMeeting.objects.all().order_by('-date')

    return render_to_response('proceedings/interim_directory.html', {
    'meetings': meetings},
)

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
        meetings = Meeting.objects.filter(type='ietf').order_by('number')
    else:
        # select meetings still within the cutoff period
        meetings = Meeting.objects.filter(type='ietf',date__gt=datetime.datetime.today() - datetime.timedelta(days=settings.SUBMISSION_CORRECTION_DAYS)).order_by('number')
    
    groups = get_my_groups(request.user)
    interim_meetings = Meeting.objects.filter(type='interim',session__group__in=groups).order_by('-date')
    # tac on group for use in templates
    for m in interim_meetings:
        m.group = m.session_set.all()[0].group
    
    # we today's date to see if we're past the submissio cutoff
    today = datetime.date.today()
    
    return render_to_response('proceedings/main.html',{
        'meetings': meetings,
        'interim_meetings': interim_meetings,
        'today': today},
        RequestContext(request,{}), 
    )

@check_permissions
def move_slide(request, meeting_num, acronym, slide_id, direction):
    '''
    This view will re-order slides.  In addition to meeting, group and slide IDs it takes
    a direction argument which is a string [up|down].
    '''
    slide = get_object_or_404(Document, name=slide_id)
    
    # get related slides via timeslot
    session = Session.objects.filter(meeting__number=meeting_num,group__acronym=acronym)[0]
    qs = session.materials.exclude(states__slug='deleted').filter(type='slides').order_by('order')
    
    # if direction is up and we aren't already the first slide
    if direction == 'up' and slide_id != str(qs[0].pk):
        index = find_index(slide_id, qs)
        slide_before = qs[index-1]
        slide_before.order, slide.order = slide.order, slide_before.order
        slide.save()
        slide_before.save()

    # if direction is down, more than one slide and we aren't already the last slide
    if direction == 'down' and qs.count() > 1 and slide_id != str(qs[qs.count()-1].pk):
        index = find_index(slide_id, qs)
        slide_after = qs[index+1]
        slide_after.order, slide.order = slide.order, slide_after.order
        slide.save()
        slide_after.save()

    url = reverse('proceedings_upload_unified', kwargs={'meeting_num':meeting_num,'acronym':acronym})
    return HttpResponseRedirect(url)

@check_permissions
def replace_slide(request, meeting_num, acronym, slide_id):
    '''
    This view allows the user to upload a new file to replace a slide.
    '''
    # we need to pass group to the template for the breadcrumbs
    group = get_object_or_404(Group, acronym=acronym)
    slide = get_object_or_404(Document, name=slide_id)
    meeting = get_object_or_404(Meeting, number=meeting_num)

    if request.method == 'POST': # If the form has been submitted...
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            url = reverse('proceedings_upload_unified', kwargs={'meeting_num':meeting_num,'acronym':acronym})
            return HttpResponseRedirect(url)
            
        form = ReplaceSlideForm(request.POST,request.FILES,instance=slide) # A form bound to the POST data
        if form.is_valid(): 
            new_slide = form.save(commit=False)
            new_slide.time = datetime.datetime.now()
            new_slide.save()
            
            file = request.FILES[request.FILES.keys()[0]]
            file_ext = os.path.splitext(file.name)[1]
            disk_filename = new_slide.name + file_ext
            handle_upload_file(file,disk_filename,meeting,'slides')
            
            # create DocEvent uploaded
            DocEvent.objects.create(doc=slide,
                                    by=request.user.get_profile(),
                                    type='uploaded')
                                    
            # rebuild proceedings.html
            create_proceedings(slide.meeting.pk)
            
            url = reverse('proceedings_upload_unified', kwargs={'meeting_num':meeting_num,'acronym':acronym})
            return HttpResponseRedirect(url)
    else:
        form = ReplaceSlideForm(instance=slide)
    
    return render_to_response('proceedings/replace_slide.html',{
        'group': group,
        'meeting':meeting,
        'slide':slide,
        'form':form},
        RequestContext(request, {}),
    )

def select(request, meeting_num):
    '''
    A screen to select which group you want to upload material for.  Users of this view area
    Secretariat staff and community (WG Chairs, ADs, etc).  Only those groups with sessions
    scheduled for the given meeting will appear in drop-downs.  For Group and IRTF selects, the
    value will be group.acronym to use in pretty URLs.  Since Training sessions have no acronym
    we'll use the session id.
    '''
    if request.method == 'POST':
        redirect_url = reverse('proceedings_upload_unified', kwargs={'meeting_num':meeting_num,'acronym':request.POST['group']})
        return HttpResponseRedirect(redirect_url)
        
    meeting = get_object_or_404(Meeting, number=meeting_num)
    
    groups_session, groups_no_session = groups_by_session(request.user, meeting)
    
    # initialize group form
    wgs = filter(lambda x: x.type_id == 'wg',groups_session)
    group_form = GroupSelectForm(choices=build_choices(wgs))
        
    # intialize IRTF form
    rgs = filter(lambda x: x.type_id == 'rg',groups_session)
    irtf_form = GroupSelectForm(choices=build_choices(rgs))
        
    # initialize Training form, this select widget needs to have a session id, because it's
    # utilmately the session that we associate material with
    # NOTE: there are two ways to query for the groups we want, the later seems more specific
    if has_role(request.user,'Secretariat'):
        choices = []
        #for session in Session.objects.filter(meeting=meeting).exclude(name=""):
        for session in Session.objects.filter(meeting=meeting,timeslot__type__in=('other','plenary')).order_by('name'):
            choices.append((session.id,session.timeslot_set.all()[0].name))
        training_form = GroupSelectForm(choices=choices)
    else:
        training_form = None
        
    return render_to_response('proceedings/select.html', {
        'group_form': group_form,
        'irtf_form': irtf_form,
        'training_form': training_form,
        'meeting':meeting},
        RequestContext(request,{}), 
    )

def select_interim(request):
    '''
    A screen to select which group you want to upload Interim material for.  Works for Secretariat staff
    and external (ADs, chairs, etc)
    '''
    if request.method == 'POST':
        redirect_url = reverse('proceedings_interim', kwargs={'acronym':request.POST['group']})
        return HttpResponseRedirect(redirect_url)
    
    if request.user_is_secretariat:
        # initialize working groups form
        choices = build_choices(Group.objects.active_wgs())
        group_form = GroupSelectForm(choices=choices)
        
        # per Alexa, not supporting Interim IRTF meetings at this time
        # intialize IRTF form
        #choices = build_choices(Group.objects.filter(type='wg', state='active')
        #irtf_form = GroupSelectForm(choices=choices)
        
    else:
        # these forms aren't used for non-secretariat
        groups = get_my_groups(request.user)
        choices = build_choices(groups)
        group_form = GroupSelectForm(choices=choices)
        irtf_form = None
        training_form = None
    
    return render_to_response('proceedings/interim_select.html', {
        'group_form': group_form},
        #'irtf_form': irtf_form,
        RequestContext(request,{}), 
    )

@check_permissions
def upload_unified(request, meeting_num, acronym=None, session_id=None):
    '''
    This view is the main view for uploading / re-ordering material for regular and interim
    meetings.  There are two urls.py entries which map to this view.  The acronym_id option is used
    most often for groups of regular and interim meetings.  session_id is used for uploading 
    material for Training sessions (where group is not a unique identifier).  We could have used
    session_id all the time but this makes for an ugly URL which most of the time would be 
    avoided by using acronym.
    '''
    meeting = get_object_or_404(Meeting, number=meeting_num)
    now = datetime.datetime.now()
    if acronym:
        group = get_object_or_404(Group, acronym=acronym)
        sessions = Session.objects.filter(meeting=meeting,group=group)
        session = sessions[0]
        session_name = ''
    elif session_id:
        sessions = None
        session = get_object_or_404(Session, id=int(session_id))
        group = Group.objects.get(acronym='none')
        session_name = session.name
    
    if request.method == 'POST':
        button_text = request.POST.get('submit','')
        if button_text == 'Back':
            if meeting.type.slug == 'interim':
                url = reverse('proceedings_interim', kwargs={'acronym':group.acronym})
            else:
                url = reverse('proceedings_select', kwargs={'meeting_num':meeting_num})
            return HttpResponseRedirect(url)
        
        form = UnifiedUploadForm(request.POST,request.FILES)
        if form.is_valid():
            material_type = form.cleaned_data['material_type']
            slide_name =  form.cleaned_data['slide_name']
            
            file = request.FILES[request.FILES.keys()[0]]
            file_ext = os.path.splitext(file.name)[1]

            # set the filename
            if meeting.type.slug == 'ietf':
                filename = '%s-%s-%s' % (material_type.slug,meeting.number,group.acronym)
            elif meeting.type.slug == 'interim':
                filename = '%s-%s' % (material_type.slug,meeting.number)
            if material_type.slug == 'slides':
                order_num = get_next_order_num(session)
                slide_num = get_next_slide_num(session)
                filename += "-%s" % slide_num
            if session_name:
                filename += "-%s" % slugify(session_name)
            disk_filename = filename + file_ext
            
            # create the Document object, in the case of slides the name will always be unique
            # so you'll get a new object, agenda and minutes will reuse doc object if it exists
            doc, created = Document.objects.get_or_create(type=material_type,
                                                          group=group,
                                                          name=filename)
            doc.external_url = disk_filename
            doc.time = now
            if created:
                doc.rev = '1'
            else:
                doc.rev = str(int(doc.rev) + 1)
            if material_type.slug == 'slides':
                doc.order=order_num
                doc.title=slide_name
            doc.save()

            DocAlias.objects.get_or_create(name=doc.name, document=doc)
            
            handle_upload_file(file,disk_filename,meeting,material_type.slug)
                
            # set Doc state
            state = State.objects.get(type=doc.type,slug='active')
            doc.set_state(state)
            
            # create session relationship, per Henrik we should associate documents to all sessions
            # for the current meeting (until tools support different materials for diff sessions)
            if sessions:
                for s in sessions:
                    s.materials.add(doc)
            else:
                session.materials.add(doc)
            
            # create NewRevisionDocEvent instead of uploaded, per Ole
            NewRevisionDocEvent.objects.create(type='new_revision',
                                       by=request.user.get_profile(),
                                       doc=doc,
                                       rev=doc.rev,
                                       desc='New revision available',
                                       time=now)
            
            create_proceedings(meeting)
            messages.success(request,'File uploaded sucessfully')
    
    else:
        form = UnifiedUploadForm(initial={'meeting_id':meeting.id,'acronym':group.acronym,'material_type':'slides'})
    
    agenda,minutes,slides = get_material(session)
    
    # gather DocEvents
    # include deleted material to catch deleted doc events
    docs = session.materials.all()
    docevents = DocEvent.objects.filter(doc__in=docs)
    
    if os.path.exists(get_proceedings_path(meeting,group)):
        proceedings_url = get_proceedings_url(meeting, group)
    else: 
        proceedings_url = ''
    
    return render_to_response('proceedings/upload_unified.html', {
        'docevents': docevents,
        'meeting': meeting,
        'group': group,
        'minutes': minutes,
        'agenda': agenda,
        'form': form,
        'session_name': session_name,   # for Tutorials, etc
        'slides':slides,
        'proceedings_url': proceedings_url},
        RequestContext(request, {}),
    )
































