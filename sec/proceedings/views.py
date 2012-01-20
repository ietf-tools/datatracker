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
from django.template.loader import get_template
from django.utils import simplejson
from django.db.models import Max,Count,get_model

#from sec.core.models import Acronym
#from sec.core.forms import GroupSelectForm
#from sec.drafts.models import InternetDraft, Rfc
#from sec.proceedings.models import *
#from sec.roles.models import Role
#from sec.utils.decorators import sec_only, check_permissions
#from sec.utils.shortcuts import get_group_or_404, get_meeting_or_404, get_my_groups

from sec.utils.group import get_my_groups
from sec.utils.meeting import get_upload_root
from sec.sessions.forms import GroupSelectForm

from redesign.doc.models import Document
from redesign.group.models import Group

from ietf.ietfauth.decorators import has_role
from ietf.meeting.models import Meeting, Session

from forms import *

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
    This function takes a queryset (or list of objects) and builds a list of tuples for use 
    as choices in a select widget.  First item is the object primary key, second is the object
    name, str(obj).
    '''
    #choices = zip([ x.pk for x in queryset ], [ str(x) for x in queryset ])
    choices = zip([ x.pk for x in queryset ], [ x.acronym for x in queryset ])
    return sorted(choices, key=lambda choices: choices[1])
"""
def create_interim_directory():
    '''
    Create static Interim Meeting directory pages that will live in a different URL space than
    the secretariat Django project
    '''
    
    # produce date sorted output
    page = 'proceedings.html'
    meetings = InterimMeeting.objects.all().order_by('-start_date')
    response = render_to_response('proceedings/interim_directory.html',{'meetings': meetings})
    path = os.path.join(settings.INTERIM_LISTING_DIR, page)
    f = open(path,'w')
    f.write(response.content)
    f.close()
    
    # produce group sorted output
    page = 'proceedings-bygroup.html'
    qs = InterimMeeting.objects.all()
    meetings = sorted(qs, key=lambda a: a.group_acronym)
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
    if not is_interim_meeting(meeting):
        return
        
    # get all the objects we need for the template
    # meeting = get_meeting_or_404(meeting_id)
    year,month,day = parsedate(meeting.start_date)
    group_name = meeting.get_group_acronym()
    group = IETFWG.objects.get(group_acronym=meeting.group_acronym_id)
    area_group = AreaGroup.objects.get(group=group.group_acronym)
    area_name = area_group.area.area_acronym.name
    slides = meeting.interimslide_set.all().order_by('order_num')
    # drafts and rfcs are available from methods on group, but they aren't sorted
    drafts = InternetDraft.objects.filter(group=meeting.group_acronym_id,
                                                    status=1).order_by('start_date')
    rfcs = Rfc.objects.filter(group_acronym=meeting.get_group_acronym()).order_by('rfc_number')
    agenda_url = ''
    minutes_url = ''
    try:
        agenda = InterimAgenda.objects.get(meeting=meeting,group_acronym_id=group.pk)
        if os.path.exists(agenda.file_path):
            agenda_url = agenda.url
    except InterimAgenda.DoesNotExist:
        pass
    
    try:
        minutes = InterimMinute.objects.get(meeting=meeting,group_acronym_id=group.pk)
        if os.path.exists(minutes.file_path):
            minutes_url = minutes.url
    except InterimMinute.DoesNotExist:
        pass
    
    # the simplest way to display the charter is to place it in a <pre> block
    # however, because this forces a fixed-width font, different than the rest of
    # the document we modify the charter by adding replacing linefeeds with <br>'s
    charter = group.charter_text().replace('\n','<br>')
    
    # rather than return the response as in a typical view function we save it as the snapshot
    # proceedings.html
    response = render_to_response('proceedings/proceedings.html',{
        'agenda_url': agenda_url,
        'area_name': area_name,
        'charter': charter,
        'drafts': drafts,
        'group': group,
        'meeting':meeting,
        'minutes_url': minutes_url,
        'rfcs': rfcs,
        'slides': slides}
    )
    
    # save proceedings
    proceedings_path = meeting.get_proceedings_path()
    
    f = open(proceedings_path,'w')
    f.write(response.content)
    f.close()
    
    # save the meeting object, which will cause "updated" field to be current
    # reverted to legacy meeting table which does not have update field
    # meeting.save()
    
    # rebuild the directory
    create_interim_directory()
"""
def find_index(slide_id, qs):
    '''
    This function looks up a slide in a queryset of slides,
    returning the index.
    '''
    for i in range(0,qs.count()):
        if str(qs[i].pk) == slide_id:
            return i
"""
def get_materials_object(meeting_id,type,object_id):
    '''
    This function takes
    meeting_id: id of meeting
    type: string [agenda|minute|slide]
    object_id: the object id
    
    and returns the object instance
    '''
    interim = is_interim_meeting(meeting_id)

    if type == 'slide':
        if interim:
            obj = get_object_or_404(InterimSlide, id=object_id)
        else:
            obj = get_object_or_404(Slide, id=object_id)        
    
    elif type == 'agenda':
        if interim:
            obj = get_object_or_404(InterimAgenda, id=object_id)
        else:
            obj = get_object_or_404(WgAgenda, id=object_id)
    
    elif type == 'minute':
        if interim:
            obj = get_object_or_404(InterimMinute, id=object_id)
        else:
            obj = get_object_or_404(Minute, id=object_id)
        
    return obj
"""
def get_next_slide_num(session):
    '''
    This function takes a session object and returns the
    next slide number to use for a newly added slide as a string.
    '''
    slides = session.materials.filter(type='slides').order_by('-name')
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
    path = os.path.join(get_upload_root(meeting),group.acronym + '.html')
    return path

def get_proceedings_url(meeting,group):
    url = "%s/proceedings/%s/%s.html" % (
        settings.MEDIA_URL,
        meeting.number,
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

"""        
def log_activity(group_id,text,meeting_id,userid):
    '''
    Add a record to session_request_activites.  Based on legacy function
    input: group can be either IETFWG or IRTF
    '''
    # added this conditional because interim activity records are corrupting db
    # TODO: remove this after schema migration
    if int(meeting_id) > 200:
        record = InterimActivity(group_acronym_id=group_id,meeting_num=meeting_id,activity=text,act_by=userid)
    else:
        record = WgProceedingsActivity(group_acronym_id=group_id,meeting_num=meeting_id,activity=text,act_by=userid)
    record.save()
    
def make_directories(meeting):
    '''
    This function takes a meeting object and creates the appropriate materials directories
    '''
    path = meeting.upload_root
    os.umask(0)
    if not os.path.exists(path):
        os.makedirs(path)
    os.mkdir(os.path.join(path,'slides'))
    os.mkdir(os.path.join(path,'agenda'))
    os.mkdir(os.path.join(path,'minutes'))
    os.mkdir(os.path.join(path,'id'))
    os.mkdir(os.path.join(path,'rfc'))
    
def parsedate(d):
    '''
    This function takes a date object and returns a tuple of year,month,day
    '''
    return (d.strftime('%Y'),d.strftime('%m'),d.strftime('%d'))
    
# --------------------------------------------------
# STANDARD VIEW FUNCTIONS
# --------------------------------------------------
@sec_only
def convert(request, meeting_id):
    '''
    Handles the PPT to HTML conversion download/upload process.

    Slides waiting in a list for conversion are listed and manual Upload/Download is

    performed
 

    **Templates:**

    * ``proceedings/convert.html``

    **Template Variables:**

    * meeting , proceeding, slide_info

    '''
    meeting = get_object_or_404(Meeting, meeting_num=meeting_id)
    proceeding = get_object_or_404(Proceeding, meeting_num=meeting_id)

    #Get the file names in queue waiting for the conversion
    slide_list = Slide.objects.filter(meeting=meeting_id,in_q='1')

    return render_to_response('proceedings/convert.html', {
        'meeting': meeting,
        'proceeding': proceeding,
        'slide_list':slide_list},
        RequestContext(request, {}),
    )
"""
#@check_permissions
def delete_material(request,meeting_id,group_id,type,object_id):
    '''
    This view handles deleting material objects and files.  
    "type" argument must be a string [agenda|slide|minute]
    '''
    pass
    """
    obj = get_materials_object(meeting_id,type,object_id)
    meeting = get_meeting_or_404(meeting_id)
    
    path = obj.file_path
    if os.path.exists(path):
        os.remove(path)
        
    '''
    TODO: special case for removing html directories
    # for now this isn't supported
    #if os.path.isdir(path):
    #   shutil.rmtree(path)
    # slide_type_id == 1 is a special type, indicates a direcory containing html docs
        # we need to get the directory name and remove it
        if obj.slide_type_id == 1:
            slide_dir = os.path.splitext(obj.filename)[0]
            path = os.path.join(settings.PROCEEDINGS_DIR,str(meeting_id),'slides',slide_dir)
    '''
    # log activity
    if type == 'agenda':
        text = "agenda was deleted"
    elif type == 'minute':
        text = "minutes was deleted"
    elif type == 'slide':
        text = "slide, '%s', was deleted" % obj.slide_name
    log_activity(group_id,text,meeting_id,request.person)

    obj.delete()
    
    # create DocEvent  deleted_document
    
    create_proceedings(meeting)
        
    messages.success(request,'The material was deleted successfully')
    url = reverse('proceedings_upload_unified', kwargs={'meeting_id':meeting_id,'group_id':obj.group_acronym_id})
    return HttpResponseRedirect(url)

@sec_only
def delete_interim_meeting(request, meeting_id):
    '''
    This view deletes the specified InterimMeeting and any material that has been
    uploaded for it.
    '''
    meeting = get_object_or_404(InterimMeeting, meeting_num=meeting_id)
    
    # delete directories
    path = meeting.get_upload_root()
    if os.path.exists(path):
        shutil.rmtree(path)
    
    meeting.delete()

    url = reverse('proceedings_interim', kwargs={'group_id':meeting.group_acronym_id})
    return HttpResponseRedirect(url)

"""
#@check_permissions
def edit_slide(request, meeting_id, group_id, slide_id):
    '''
    This view allows the user to edit the name of a slide.
    '''
    # we need to pass group to the template for the breadcrumbs
    group = get_object_or_404(Group, id=group_id)
    slide = get_object_or_404(Document, name=slide_id)
    meeting = get_object_or_404(Meeting, number=meeting_id)

    if request.method == 'POST': # If the form has been submitted...
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            url = reverse('proceedings_upload_unified', kwargs={'meeting_id':meeting.id,'group_id':group.id})
            return HttpResponseRedirect(url)
            
        form = EditSlideForm(request.POST, instance=slide) # A form bound to the POST data
        if form.is_valid(): 
            # TODO log activity
            #text = "Title of a slide was changed to '%s' from '%s'" % (form.cleaned_data['slide_name'],form.initial['slide_name']) 
            #log_activity(group_id,text,meeting_id,request.person)
            
            form.save()
            
            # rebuild proceedings.html
            # create_proceedings(slide.meeting.pk)
            url = reverse('proceedings_upload_unified', kwargs={'meeting_id':meeting.id,'group_id':group_id})
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
"""
def interim(request, group_id):
    '''
    This view presents the user with a list of interim meetings for the specified group.
    The user can select a meeting to manage or create a new interim meeting by entering
    a date.
    '''
    group_name = Acronym.objects.get(acronym_id=group_id).acronym
    group = get_object_or_404(IETFWG, group_acronym=group_id)
    if request.method == 'POST': # If the form has been submitted...
        button_text = request.POST.get('submit', '')
        if button_text == 'Back':
            url = reverse('proceedings_select_interim')
            return HttpResponseRedirect(url)
            
        form = InterimMeetingForm(request.POST) # A form bound to the POST data
        if form.is_valid():
            start_date = form.cleaned_data['date']
            meeting=InterimMeeting()
            meeting.group_acronym_id = group_id
            meeting.start_date = start_date
            meeting.save()
            make_directories(meeting)
            messages.success(request, 'Meeting created')
            url = reverse('proceedings_interim', kwargs={'group_id':group_id})
            return HttpResponseRedirect(url)
    else:
        form = InterimMeetingForm(initial={'group_acronym_id':group_id}) # An unbound form
        
    meeting_list = InterimMeeting.objects.filter(group_acronym_id=group_id).order_by('start_date')
    return render_to_response('proceedings/interim_meeting.html',{
        'group_name': group_name,
        'group': group,
        'meeting_list':meeting_list,
        'form':form},
        RequestContext(request, {}),
    )

def interim_directory(request, sortby=None):
    
    if sortby == 'group':
        qs = InterimMeeting.objects.all()
        meetings = sorted(qs, key=lambda a: a.group_acronym)
    else:
        meetings = InterimMeeting.objects.all().order_by('-start_date')

    return render_to_response('proceedings/interim_directory.html', {
    'meetings': meetings},
)
"""
def main(request):
    '''
    List IETF Meetings.  If the user is Secratariat list includes all meetings otherwise
    show only those meetings which are not frozen and whose corrections submission date has
    not passed.

    **Templates:**

    * ``proceedings/list.html``

    **Template Variables:**

    * proceeding_list

    '''
    if has_role(request.user,'Secretariat'):
        meetings = Meeting.objects.filter(type='ietf').order_by('number')
    else:
        # select meetings still within the cutoff period
        meetings = Meeting.objects.filter(type='ietf',date__gt=datetime.datetime.today() - datetime.timedelta(days=settings.SUBMISSION_CORRECTION_DAYS)).order_by('number')
    
    interim_meetings = []
    for group in get_my_groups(request.user):
        # TODO right now interm meetings are tied to groups
        qs = Meeting.objects.filter(type='interim')
        interim_meetings.extend(qs)
    
    # TODO meeting must have an attribute to determine if it is open or not, for now using 
    # frozen in the template
    
    return render_to_response('proceedings/main.html',{
        'meetings': meetings,
        'interim_meetings': interim_meetings},
        RequestContext(request,{}), 
    )
"""    
@sec_only
def modify(request,id):
    '''
    Handle status changes of Proceedings (Activate, Freeze)

    **Templates:**

    * none

    Redirects to view page on success.

    '''
    proceeding = get_object_or_404(Proceeding, meeting_num=id)

    if request.method == 'POST':
        #Handles the freeze request
        if request.POST.get('submit', '') == "Freeze":  
            proceeding.frozen=1
            proceeding.save()
            messages.success(request, 'Proceedings have been freezed successfully!')

        if request.POST.get('submit','') == "Activate":
            proceeding.frozen=0
            proceeding.save()
            messages.success(request, 'Proceedings have been activated successfully!')

        url = reverse('sec.proceedings.views.view', kwargs={'id':str(id)})
        return HttpResponseRedirect(url)
"""
#@check_permissions
def move_slide(request, meeting_id, group_id, slide_id, direction):
    '''
    This view will re-order slides.  In addition to meeting, group and slide IDs it takes
    a direction argument which is a string [up|down].
    '''
    # TODO do we need to change the slide name while we're at it??
    slide = get_object_or_404(Document, name=slide_id)
    
    # get related slides via timeslot
    qs = Document.objects.filter(type='slides',timeslot=slide.timeslot_set.all()[0]).order_by('order')
    
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

    url = reverse('proceedings_upload_unified', kwargs={'meeting_id':meeting_id,'group_id':group_id})
    return HttpResponseRedirect(url)

#@check_permissions
def replace_slide(request, meeting_id, group_id, slide_id):
    '''
    This view allows the user to upload a new file to replace a slide.
    '''
    pass
    """
    # we need to pass group to the template for the breadcrumbs
    group = get_group_or_404(group_id)
    slide = get_materials_object(meeting_id,'slide',slide_id)

    if request.method == 'POST': # If the form has been submitted...
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            url = reverse('proceedings_upload_unified', kwargs={'meeting_id':slide.meeting.pk,'group_id':slide.group_acronym_id})
            return HttpResponseRedirect(url)
            
        form = ReplaceSlideForm(request.POST,request.FILES,instance=slide) # A form bound to the POST data
        if form.is_valid(): 
            # log activity
            text = "slide '%s' was re-uploaded" % (form.cleaned_data['slide_name']) 
            log_activity(group_id,text,meeting_id,request.person)
            
            new_slide = form.save(commit=False)
            
            # handle if the file extension changed
            file = request.FILES[request.FILES.keys()[0]]
            file_ext = os.path.splitext(file.name)[1]
            if file_ext in ('.ppt','.pptx'):
                new_slide.in_q = 1
            else:
                new_slide.in_q = 0
            new_slide.slide_type_id = Slide.REVERSE_SLIDE_TYPES[file_ext.lstrip('.').lower()]
            
            new_slide.save()
            
            filename = '%s-%s%s' % (group.acronym, new_slide.slide_num, file_ext)
            handle_upload_file(file,filename,new_slide.meeting,'slides')
                
            # rebuild proceedings.html
            # create_proceedings(slide.meeting.pk)
            url = reverse('proceedings_upload_unified', kwargs={'meeting_id':slide.meeting.pk,'group_id':slide.group_acronym_id})
            return HttpResponseRedirect(url)
    else:
        form = ReplaceSlideForm(instance=slide)
    
    return render_to_response('proceedings/replace_slide.html',{
        'group': group,
        'interim': is_interim_meeting(meeting_id),
        'meeting':slide.meeting,
        'slide':slide,
        'form':form},
        RequestContext(request, {}),
    )
    
@sec_only
def status(request,id):
    '''
    Edits the status associated with proceedings: Freeze/Unfreeze proceeding status.

    **Templates:**

    * ``proceedings/view.html``

    **Template Variables:**

    * meeting , proceeding

    '''

    meeting = get_object_or_404(Meeting, meeting_num=id)
    proceeding = get_object_or_404(Proceeding, meeting_num=id)

    return render_to_response('proceedings/status.html', {
        'meeting':meeting,
        'proceeding':proceeding},
        RequestContext(request,{}), 
    )
""" 
def select(request, meeting_id):
    '''
    A screen to select which group you want to upload material for.  Works for Secretariat staff
    and external (ADs, chairs, etc).
    NOTE: only those groups with sessions scheduled for the given meeting will appear in drop-downs
    '''
    if request.method == 'POST':
        redirect_url = reverse('proceedings_upload_unified', kwargs={'meeting_id':meeting_id,'group_id':request.POST['group']})
        return HttpResponseRedirect(redirect_url)
        
    meeting = get_object_or_404(Meeting, number=meeting_id)
    
    all_sessions = Session.objects.filter(meeting=meeting)
    
    if has_role(request.user,'Secretariat'):
        # initialize WG form
        groups = [ a.group for a in all_sessions.filter(group__type='wg') ]
        choices = build_choices(groups)
        group_form = GroupSelectForm(choices=choices)
        
        # intialize IRTF form
        irtfs = [ a.group for a in all_sessions.filter(group__type='rg') ]
        choices = build_choices(irtfs)
        irtf_form = GroupSelectForm(choices=choices)
        
        # TODO - training groups aren't loaded
        # initialize Training form
        #training_sessions = [ a.group for a in all_sessions.filter(group___type='train')]
        #choices = build_choices(training_sessions)
        #training_form = GroupSelectForm(choices=choices)
        training_form = None
    else:
        groups = get_my_groups(request.user)
        
        # initialize WG form
        #group_id_list = [ g.group_acronym.acronym_id for g in groups ]
        groups_scheduled = [ a.group for a in all_sessions.filter(group__type='wg') if a.group in groups ]
        choices = build_choices(groups_scheduled)
        group_form = GroupSelectForm(choices=choices)
        
        # initialize IRTF form
        #scheduled_irtfs = [ x.group_acronym_id for x in all_sessions.filter(irtf=True) ]
        #irtfs = [ x.irtf for x in request.person.irtfchair_set.all() if x.irtf.irtf_id in scheduled_irtfs ]
        irtfs = [ a.group for a in all_sessions.filter(group__type='rg') if a.group in groups ]
        choices = build_choices(irtfs)
        irtf_form = GroupSelectForm(choices=choices)
        
        # TODO support is_ietf_iab_chair
        # initialize training.  for IETF, IAB Chairs
        #if request.user_is_ietf_iab_chair:
        #    training_form = GroupSelectForm(choices=(('-1','Wednesday Plenary'),('-2','Thursday Plenary')))
        #else:
        #    training_form = None
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
    pass
"""
    if request.method == 'POST':
        redirect_url = reverse('proceedings_interim', kwargs={'group_id':request.POST['group']})
        return HttpResponseRedirect(redirect_url)
    
    if request.user_is_secretariat:
        # initialize working groups form
        #choices = build_choices(IETFWG.objects.filter(status=1, meeting_scheduled="YES"))
        choices = build_choices(IETFWG.objects.filter(status=1))
        group_form = GroupSelectForm(choices=choices)
        
        # per Alexa, not supporting Interim IRTF meetings at this time
        # intialize IRTF form
        #choices = build_choices(IRTF.objects.all())
        #choices = build_choices(IRTF.objects.filter(meeting_scheduled=True))
        #irtf_form = GroupSelectForm(choices=choices)
        
    else:
        # these forms aren't used for non-secretariat
        groups = get_my_groups(request)
        choices = build_choices(groups)
        group_form = GroupSelectForm(choices=choices)
        irtf_form = None
        training_form = None
    
    return render_to_response('proceedings/interim_select.html', {
        'group_form': group_form},
        #'irtf_form': irtf_form,
        RequestContext(request,{}), 
    )
    
@sec_only
def upload_presentation(request,id,slide_id):
    '''
    Handles the upload process for the converted slide files.
      
    The files are in PPT/PPTX format. Manual downlaod and conversion to PDF is performed. 
    
    **Templates:**

    * ``proceedings/upload_presentation.html``

    **Template Variables:**

    * meeting,upload_presentation,slide

    '''
    meeting = get_object_or_404(Meeting, meeting_num=id)
    slide = get_object_or_404(Slide,id=slide_id)

    if request.method == 'POST':
        upload_presentation  = UploadPresentationForm(request.POST,request.FILES)
        if upload_presentation.is_valid():
            file = request.FILES[request.FILES.keys()[0]]
            base, extension = os.path.splitext(file.name)
            file_name = '%s-%s%s' % (slide.group_name, slide.slide_num, extension)
            handle_presentation_upload(file,file_name,meeting)
            slide.slide_type_id = Slide.REVERSE_SLIDE_TYPES[extension.lstrip('.').lower()]
            slide.slide_name = upload_presentation.cleaned_data['slide_name']
            slide.in_q = 0
            slide.save()

            messages.success(request,'Presentation file uploaded sucessfully')
            url = reverse('proceedings_convert', kwargs={'id':id})
            return HttpResponseRedirect(url)

    else:
         upload_presentation = UploadPresentationForm(initial={'slide_name': slide.slide_name})

    return render_to_response('proceedings/upload_presentation.html', {
               'meeting': meeting,
               'upload_presentation': upload_presentation,
               'slide': slide},
       RequestContext(request, {}),
    )
"""
#@check_permissions
def upload_unified(request, meeting_id, group_id):
    '''
    This view is the main view for uploading / re-ordering material for regular and interim
    meetings.
    '''
    
    meeting = get_object_or_404(Meeting, id=meeting_id)
    group = get_object_or_404(Group, id=group_id)
    
    # even though documents can be associated to a specific session, for now we are going to 
    # associate to the first session and keep the UI the same
    session = Session.objects.filter(meeting=meeting,group=group)[0]
    
    # TODO are wgproceedingsactivities 
    #activities = WgProceedingsActivity.objects.filter(meeting_num=meeting_id,group_acronym_id=group_id)
    
    # Initialize -------------------------------
    #irtf = 0
    #interim = 0
    #slide_class = Slide

    # this identification should happen at another layer, but all this will go away 
    # with new db schema
    #if 0 < int(group_id) < 100:
    #    irtf = 1
    #if is_interim_meeting(meeting_id):
    #    interim = 1
    #    slide_class = InterimSlide
    
    if request.method == 'POST':
        button_text = request.POST.get('submit','')
        if button_text == 'Back':
            if meeting.type.slug == 'interim':
                url = reverse('proceedings_interim', kwargs={'group_id':group.pk})
            else:
                url = reverse('proceedings_select', kwargs={'meeting_id':meeting_id})
            return HttpResponseRedirect(url)
        
        form = UnifiedUploadForm(request.POST,request.FILES)
        if form.is_valid():
            material_type = form.cleaned_data['material_type']
            slide_name =  form.cleaned_data['slide_name']
            
            file = request.FILES[request.FILES.keys()[0]]
            file_ext = os.path.splitext(file.name)[1]
            
            # handle slides
            if material_type.slug == 'slides':
                order_num = get_next_order_num(session)
                slide_num = get_next_slide_num(session)
                filename = 'slides-%s-%s-%s' % (meeting.number, group.acronym, slide_num)
                obj = Document.objects.create(type=material_type,
                                              group=group,
                                              name=filename,
                                              order=order_num,
                                              title=slide_name)
            
            # handle minutes and agenda
            else:
                filename = '%s-%s-%s' % (material_type.slug,meeting.number,group.acronym)
                # don't create new doc record if one arleady exists
                obj, created = Document.objects.get_or_create(
                    type=material_type,
                    group=group,
                    name=filename)

            disk_filename = filename + file_ext
            handle_upload_file(file,disk_filename,meeting,material_type.slug)
                
            # create DocEvent uploaded_document
            
            # create session relationship
            session.materials.add(obj)
            
            # generate proceedings
            
            #create_proceedings(meeting)
            messages.success(request,'File uploaded sucessfully')
    
    else:
        form = UnifiedUploadForm(initial={'meeting_id':meeting.pk,'group_id':group.pk,'material_type':'slides'})
    
    slides = session.materials.filter(type='slides').order_by('order')
    minutes = session.materials.filter(type='minutes')
    minutes = minutes[0] if minutes else None
    agenda = session.materials.filter(type='agenda')
    agenda = agenda[0] if agenda else None
    
    if os.path.exists(get_proceedings_path(meeting,group)):
        proceedings_url = get_proceedings_url(meeting, group)
    else: 
        proceedings_url = ''
    
    return render_to_response('proceedings/upload_unified.html', {
        #'activities': activities,
        'meeting': meeting,
        'group': group,
        'minutes': minutes,
        'agenda': agenda,
        'form': form,
        'slides':slides,
        'proceedings_url': proceedings_url},
        RequestContext(request, {}),
    )

def view(request, id):
    '''
    View Meeting information.

    **Templates:**

    * ``proceedings/view.html``

    **Template Variables:**

    * meeting , proceeding

    '''
    meeting = get_object_or_404(Meeting, number=id)
    
    if not has_role(request.user,'Secretariat'):
        url = reverse('proceedings_select', kwargs={'meeting_id':id})
        return HttpResponseRedirect(url)
    
    # set legacy values
    meeting.frozen = 0
    meeting.end_date = meeting.date + datetime.timedelta(days=6)
    
    return render_to_response('proceedings/view.html', {
        'meeting': meeting},
        RequestContext(request, {}),
    )































