import datetime
import glob
import itertools
import os
import subprocess

import debug                            # pyflakes:ignore

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse
from django.db.models import Max
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response, get_object_or_404, redirect
from django.template import RequestContext
from django.utils.text import slugify

from ietf.secr.lib.template import jsonapi
from ietf.secr.sreq.forms import GroupSelectForm
from ietf.secr.utils.decorators import check_permissions, sec_only
from ietf.secr.utils.document import get_full_path
from ietf.secr.utils.group import get_my_groups, groups_by_session
from ietf.secr.utils.meeting import get_materials, get_timeslot, get_proceedings_path, get_proceedings_url
from ietf.doc.models import Document, DocAlias, DocEvent, State, NewRevisionDocEvent
from ietf.group.models import Group
from ietf.ietfauth.utils import has_role, role_required
from ietf.meeting.models import Meeting, Session, TimeSlot, SchedTimeSessAssignment

from ietf.secr.proceedings.forms import EditSlideForm, RecordingForm, RecordingEditForm, ReplaceSlideForm, UnifiedUploadForm
from ietf.secr.proceedings.proc_utils import ( gen_acknowledgement, gen_agenda, gen_areas,
    gen_attendees, gen_group_pages, gen_index, gen_irtf, gen_overview, gen_plenaries,
    gen_progress, gen_research, gen_training, create_proceedings, create_recording )
from ietf.secr.proceedings.utils import handle_upload_file
from ietf.utils.log import log

# -------------------------------------------------
# Globals 
# -------------------------------------------------
AUTHORIZED_ROLES=('WG Chair','WG Secretary','RG Chair','RG Secretary', 'AG Secretary','IRTF Chair','IETF Trust Chair','IAB Group Chair','IAOC Chair','IAD','Area Director','Secretariat','Team Chair')
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
    the full path to the file on disk.  During migration of the system the
    filename was saved in external_url, new files will also use this convention.
    '''
    session = doc.session_set.all()[0]
    meeting = session.meeting
    if doc.external_url:
        return os.path.join(meeting.get_materials_path(),doc.type.slug,doc.external_url)
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
    for file in files:
        if not Document.objects.filter(external_url__endswith=file).exists():
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
        if timeslot and timeslot.type.slug == 'session' and session.materials.all():
            groups.append(session.group)
    return groups

def get_next_slide_num(session):
    '''
    This function takes a session object and returns the
    next slide number to use for a newly added slide as a string.
    '''

    """
    slides = session.materials.filter(type='slides').order_by('-name')
    if slides:
        # we need this special case for non wg/rg sessions because the name format is different
        # it should be changed to match the rest
        if session.group.type.slug not in ('wg','rg'):
            nums = [ s.name.split('-')[3] for s in slides ]
        else:
            nums = [ s.name.split('-')[-1] for s in slides ]
    """
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
            cmd = settings.SECR_PPT2PDF_COMMAND
            cmd.append(doc.get_file_path())                                 # outdir
            cmd.append(os.path.join(doc.get_file_path(),doc.external_url))  # filename
            subprocess.check_call(cmd)
        except (subprocess.CalledProcessError, OSError) as error:
            log("Error converting PPT: %s" % (error))
            return
        # change extension
        base,ext = os.path.splitext(doc.external_url)
        doc.external_url = base + '.pdf'
        doc.save()
        
# -------------------------------------------------
# AJAX Functions
# -------------------------------------------------
@sec_only
def ajax_generate_proceedings(request, meeting_num):
    '''
    Ajax function which takes a meeting number and generates the proceedings
    pages for the meeting.  It returns a snippet of HTML that gets placed in the
    Secretariat Only section of the select page.
    '''
    meeting = get_object_or_404(Meeting, number=meeting_num)
    areas = Group.objects.filter(type='area',state='active').order_by('name')
    others = TimeSlot.objects.filter(meeting=meeting,type='other').order_by('time')
    extras = get_extras(meeting)
    context = {'meeting':meeting,
               'areas':areas,
               'others':others,
               'extras':extras,
               'request':request}
    proceedings_url = get_proceedings_url(meeting)

    # the acknowledgement page can be edited manually so only produce if it doesn't already exist
    path = os.path.join(settings.SECR_PROCEEDINGS_DIR,meeting.number,'acknowledgement.html')
    if not os.path.exists(path):
        gen_acknowledgement(context)
    gen_overview(context)
    gen_progress(context)
    gen_agenda(context)
    gen_attendees(context)
    gen_index(context)
    gen_areas(context)
    gen_plenaries(context)
    gen_training(context)
    gen_irtf(context)
    gen_research(context)
    gen_group_pages(context)

    # get the time proceedings were generated
    path = os.path.join(settings.SECR_PROCEEDINGS_DIR,meeting.number,'index.html')
    last_run = datetime.datetime.fromtimestamp(os.path.getmtime(path))

    return render_to_response('includes/proceedings_functions.html',{
        'meeting':meeting,
        'last_run':last_run,
        'proceedings_url':proceedings_url},
        RequestContext(request,{}),
    )

@jsonapi
def ajax_order_slide(request):
    '''
    Ajax function to change the order of presentation slides.
    This function expects a POST request with the following parameters
    order: new order of slide, 0 based
    slide_name: slide primary key (name)
    '''
    if request.method != 'POST' or not request.POST:
        return { 'success' : False, 'error' : 'No data submitted or not POST' }
    slide_name = request.POST.get('slide_name',None)
    order = request.POST.get('order',None)
    slide = get_object_or_404(Document, name=slide_name)

    # get all the slides for this session
    session = slide.session_set.all()[0]
    qs = session.materials.exclude(states__slug='deleted').filter(type='slides').order_by('order')

    # move slide and reorder list
    slides = list(qs)
    index = slides.index(slide)
    slides.pop(index)
    slides.insert(int(order),slide)
    for ord,item in enumerate(slides,start=1):
        if item.order != ord:
            item.order = ord
            item.save()

    return {'success':True,'order':order,'slide':slide_name}

# --------------------------------------------------
# STANDARD VIEW FUNCTIONS
# --------------------------------------------------
@role_required('Secretariat')
def build(request,meeting_num,acronym):
    '''
    This is a utility or test view.  It simply rebuilds the proceedings html for the specified
    meeting / group.
    '''
    meeting = Meeting.objects.get(number=meeting_num)
    group = get_object_or_404(Group,acronym=acronym)

    create_proceedings(meeting,group,is_final=True)

    messages.success(request,'proceedings.html was rebuilt')
    url = reverse('proceedings_upload_unified', kwargs={'meeting_num':meeting_num,'acronym':acronym})
    return HttpResponseRedirect(url)

@check_permissions
def delete_material(request,slide_id):
    '''
    This view handles deleting meeting materials.  We don't actually delete the
    document object but set the state to deleted and add a 'deleted' DocEvent.
    '''
    doc = get_object_or_404(Document, name=slide_id)
    # derive other objects
    session = doc.session_set.all()[0]
    meeting = session.meeting
    group = session.group

    path = get_full_path(doc)
    if path and os.path.exists(path):
        os.remove(path)

    # leave it related
    #session.materials.remove(doc)

    state = State.objects.get(type=doc.type,slug='deleted')
    doc.set_state(state)

    # create   deleted_document
    DocEvent.objects.create(doc=doc,
                            by=request.user.person,
                            type='deleted')

    create_proceedings(meeting,group)

    messages.success(request,'The material was deleted successfully')
    if group.type.slug in ('wg','rg'):
        url = reverse('proceedings_upload_unified', kwargs={'meeting_num':meeting.number,'acronym':group.acronym})
    else:
        url = reverse('proceedings_upload_unified', kwargs={'meeting_num':meeting.number,'session_id':session.id})

    return HttpResponseRedirect(url)

@check_permissions
def edit_slide(request, slide_id):
    '''
    This view allows the user to edit the name of a slide.
    '''
    slide = get_object_or_404(Document, name=slide_id)
    # derive other objects
    session = slide.session_set.all()[0]
    meeting = session.meeting
    group = session.group

    if group.type.slug in ('wg','rg'):
        url = reverse('proceedings_upload_unified', kwargs={'meeting_num':meeting.number,'acronym':group.acronym})
    else:
        url = reverse('proceedings_upload_unified', kwargs={'meeting_num':meeting.number,'session_id':session.id})

    if request.method == 'POST': # If the form has been submitted...
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            return HttpResponseRedirect(url)

        form = EditSlideForm(request.POST, instance=slide) # A form bound to the POST data
        if form.is_valid():
            form.save()

            # rebuild proceedings.html
            create_proceedings(meeting,group)
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
        today = datetime.datetime.today()
        meetings = [m for m in Meeting.objects.filter(type='ietf').order_by('-number') if m.get_submission_correction_date()>=today]

    groups = get_my_groups(request.user)
    interim_meetings = Meeting.objects.filter(type='interim',session__group__in=groups,session__status='sched').order_by('-date')
    # tac on group for use in templates
    for m in interim_meetings:
        m.group = m.session_set.first().group

    # we today's date to see if we're past the submissio cutoff
    today = datetime.date.today()

    return render_to_response('proceedings/main.html',{
        'meetings': meetings,
        'interim_meetings': interim_meetings,
        'today': today},
        RequestContext(request,{}),
    )

@check_permissions
def move_slide(request, slide_id, direction):
    '''
    This view will re-order slides.  In addition to meeting, group and slide IDs it takes
    a direction argument which is a string [up|down].
    '''
    slide = get_object_or_404(Document, name=slide_id)

    # derive other objects
    session = slide.session_set.all()[0]
    meeting = session.meeting
    group = session.group
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

    if group.type.slug in ('wg','rg'):
        url = reverse('proceedings_upload_unified', kwargs={'meeting_num':meeting.number,'acronym':group.acronym})
    else:
        url = reverse('proceedings_upload_unified', kwargs={'meeting_num':meeting.number,'session_id':session.id})
    return HttpResponseRedirect(url)

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
    ppt = Document.objects.filter(session__meeting=meeting,type='slides',external_url__endswith='.ppt').exclude(states__slug='deleted')
    pptx = Document.objects.filter(session__meeting=meeting,type='slides',external_url__endswith='.pptx').exclude(states__slug='deleted')
    for doc in itertools.chain(ppt,pptx):
        base,ext = os.path.splitext(doc.external_url)
        pdf_file = base + '.pdf'
        path = os.path.join(settings.SECR_PROCEEDINGS_DIR,meeting_num,'slides',pdf_file)
        if os.path.exists(path):
            doc.external_url = pdf_file
            doc.save()
            count += 1
        else:
            warn_count += 1

    if warn_count:
        messages.warning(request, '%s PDF files processed.  %s PowerPoint files still not converted.' % (count, warn_count))
    else:
        messages.success(request, '%s PDF files processed' % count)
    url = reverse('proceedings_select', kwargs={'meeting_num':meeting_num})
    return HttpResponseRedirect(url)

@role_required('Secretariat')
def progress_report(request, meeting_num):
    '''
    This function generates the proceedings progress report for use at the Plenary.
    '''
    meeting = get_object_or_404(Meeting, number=meeting_num)
    gen_progress({'meeting':meeting},final=False)

    url = reverse('proceedings_select', kwargs={'meeting_num':meeting_num})
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
    sessions = meeting.session_set.filter(type__in=('session','plenary','other'),status='sched').order_by('group__acronym')
    
    if request.method == 'POST':
        form = RecordingForm(request.POST,meeting=meeting)
        if form.is_valid():
            external_url =  form.cleaned_data['external_url']
            session = form.cleaned_data['session']
            
            if Document.objects.filter(type='recording',external_url=external_url):
                messages.error(request, "Recording already exists")
                return redirect('proceedings_recording', meeting_num=meeting_num)
            else:
                create_recording(session,external_url)
            
            # rebuild proceedings
            create_proceedings(meeting,session.group)
            
            messages.success(request,'Recording added')
            return redirect('proceedings_recording', meeting_num=meeting_num)
    
    else:
        form = RecordingForm(meeting=meeting)
    
    return render_to_response('proceedings/recording.html',{
        'meeting':meeting,
        'form':form,
        'sessions':sessions,
        'unmatched_recordings': get_unmatched_recordings(meeting)},
        RequestContext(request, {}),
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
            return redirect("proceedings_recording", meeting_num=meeting_num)
            
        form = RecordingEditForm(request.POST, instance=recording)
        if form.is_valid():
            # save record and rebuild proceedings
            form.save()
            create_proceedings(meeting,recording.group)
            messages.success(request,'Recording saved')
            return redirect('proceedings_recording', meeting_num=meeting_num)
    else:
        form = RecordingEditForm(instance=recording)
    
    return render_to_response('proceedings/recording_edit.html',{
        'meeting':meeting,
        'form':form,
        'recording':recording},
        RequestContext(request, {}),
    )
    
@check_permissions
def replace_slide(request, slide_id):
    '''
    This view allows the user to upload a new file to replace a slide.
    '''
    slide = get_object_or_404(Document, name=slide_id)
    # derive other objects
    session = slide.session_set.all()[0]
    meeting = session.meeting
    group = session.group

    if group.type.slug in ('wg','rg'):
        url = reverse('proceedings_upload_unified', kwargs={'meeting_num':meeting.number,'acronym':group.acronym})
    else:
        url = reverse('proceedings_upload_unified', kwargs={'meeting_num':meeting.number,'session_id':session.id})

    if request.method == 'POST': # If the form has been submitted...
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            return HttpResponseRedirect(url)

        form = ReplaceSlideForm(request.POST,request.FILES,instance=slide) # A form bound to the POST data
        if form.is_valid():
            new_slide = form.save(commit=False)
            new_slide.time = datetime.datetime.now()

            file = request.FILES[request.FILES.keys()[0]]
            file_ext = os.path.splitext(file.name)[1]
            disk_filename = new_slide.name + file_ext
            handle_upload_file(file,disk_filename,meeting,'slides')

            new_slide.external_url = disk_filename
            new_slide.save()
            post_process(new_slide)
            
            # create DocEvent uploaded
            DocEvent.objects.create(doc=slide,
                                    by=request.user.person,
                                    type='uploaded')

            # rebuild proceedings.html
            create_proceedings(meeting,group)

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

@role_required(*AUTHORIZED_ROLES)
def select(request, meeting_num):
    '''
    A screen to select which group you want to upload material for.  Users of this view area
    Secretariat staff and community (WG Chairs, ADs, etc).  Only those groups with sessions
    scheduled for the given meeting will appear in drop-downs.  For Group and IRTF selects, the
    value will be group.acronym to use in pretty URLs.  Since Training sessions have no acronym
    we'll use the session id.
    '''
    if request.method == 'POST':
        if request.POST.get('group',None):
            redirect_url = reverse('proceedings_upload_unified', kwargs={'meeting_num':meeting_num,'acronym':request.POST['group']})
            return HttpResponseRedirect(redirect_url)
        else:
            messages.error(request, 'No Group selected')


    meeting = get_object_or_404(Meeting, number=meeting_num)
    user = request.user
    try:
        person = user.person
    except ObjectDoesNotExist:
        messages.warning(request, 'The account %s is not associated with any groups.  If you have multiple Datatracker accounts you may try another or report a problem to ietf-action@ietf.org' % request.user)
        return HttpResponseRedirect(reverse('proceedings'))
    groups_session, groups_no_session = groups_by_session(user, meeting)
    proceedings_url = get_proceedings_url(meeting)

    # get the time proceedings were generated
    path = os.path.join(settings.SECR_PROCEEDINGS_DIR,meeting.number,'index.html')
    if os.path.exists(path):
        last_run = datetime.datetime.fromtimestamp(os.path.getmtime(path))
    else:
        last_run = None

    # initialize group form
    wgs = filter(lambda x: x.type_id in ('wg','ag','team'),groups_session)
    group_form = GroupSelectForm(choices=build_choices(wgs))

    # intialize IRTF form, only show if user is sec or irtf chair
    if has_role(user,'Secretariat') or person.role_set.filter(name__slug='chair',group__type__slug__in=('irtf','rg')):
        rgs = filter(lambda x: x.type_id == 'rg',groups_session)
        irtf_form = GroupSelectForm(choices=build_choices(rgs))
    else:
        irtf_form = None

    # initialize Training form, this select widget needs to have a session id, because
    # it's utilmately the session that we associate material with
    other_groups = filter(lambda x: x.type_id not in ('wg','ag','rg'),groups_session)
    if other_groups:
        add_choices = []
        sessions = Session.objects.filter(meeting=meeting,group__in=other_groups)
        for session in sessions:
            if session.name.lower().find('plenary') != -1:
                continue
            if session.name:
                name = (session.name[:75] + '..') if len(session.name) > 75 else session.name
                add_choices.append((session.id,name))
            else:
                add_choices.append((session.id,session.group.name))
        choices = sorted(add_choices,key=lambda x: x[1])
        training_form = GroupSelectForm(choices=choices)
    else:
        training_form = None

    # iniialize plenary form
    if has_role(user,['Secretariat','IETF Chair','IETF Trust Chair','IAB Chair','IAOC Chair','IAD']):
        ss = SchedTimeSessAssignment.objects.filter(schedule=meeting.agenda,timeslot__type='plenary')
        choices = [ (i.session.id, i.session.name) for i in sorted(ss,key=lambda x: x.session.name) ]
        plenary_form = GroupSelectForm(choices=choices)
    else:
        plenary_form = None

    # count PowerPoint files waiting to be converted
    if has_role(user,'Secretariat'):
        ppt = Document.objects.filter(session__meeting=meeting,type='slides',external_url__endswith='.ppt').exclude(states__slug='deleted')
        pptx = Document.objects.filter(session__meeting=meeting,type='slides',external_url__endswith='.pptx').exclude(states__slug='deleted')
        ppt_count = ppt.count() + pptx.count()
    else:
        ppt_count = 0

    return render_to_response('proceedings/select.html', {
        'group_form': group_form,
        'irtf_form': irtf_form,
        'training_form': training_form,
        'plenary_form': plenary_form,
        'meeting': meeting,
        'last_run': last_run,
        'proceedings_url': proceedings_url,
        'ppt_count': ppt_count},
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
    def redirection_back(meeting, group):
        if meeting.type.slug == 'interim':
            url = reverse('proceedings')
        else:
            url = reverse('proceedings_select', kwargs={'meeting_num':meeting.number})
        return HttpResponseRedirect(url)
        
    meeting = get_object_or_404(Meeting, number=meeting_num)
    now = datetime.datetime.now()
    if acronym:
        group = get_object_or_404(Group, acronym=acronym)
        sessions = Session.objects.filter(meeting=meeting,group=group)
        if not sessions.exists():
            meeting_name = "IETF %s"%meeting.number if meeting.number.isdigit() else meeting.number
            messages.warning(request, 'There does not seem to be a %s session in %s.' % (group.acronym, meeting_name))
            return redirection_back(meeting, group)
        session = sessions[0]
        session_name = ''
    elif session_id:
        session = get_object_or_404(Session, id=int(session_id))
        sessions = [session]
        group = session.group
        session_name = session.name

    if request.method == 'POST':
        button_text = request.POST.get('submit','')
        if button_text == 'Back':
            return redirection_back(meeting, group)
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

            # NonSession material, use short name for shorter URLs
            if session.short:
                filename += "-%s" % session.short
            elif session_name:
                filename += "-%s" % slugify(session_name)
            # --------------------------------

            if material_type.slug == 'slides':
                order_num = get_next_order_num(session)
                slide_num = get_next_slide_num(session)
                filename += "-%s" % slide_num

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
                if slide_name:
                    doc.title = slide_name
                else:
                    doc.title = doc.name
            else:
                doc.title = '%s for %s at %s' % (material_type.slug.capitalize(), group.acronym.upper(), meeting)
            doc.save()

            DocAlias.objects.get_or_create(name=doc.name, document=doc)

            handle_upload_file(file,disk_filename,meeting,material_type.slug)
            
            # set Doc state
            if doc.type.slug=='slides':
                doc.set_state(State.objects.get(type=doc.type,slug='archived'))
                doc.set_state(State.objects.get(type='reuse_policy',slug='single'))
            else:
                doc.set_state(State.objects.get(type=doc.type,slug='active'))
                
            # create session relationship, per Henrik we should associate documents to all sessions
            # for the current meeting (until tools support different materials for diff sessions)
            for s in sessions:
                try:
                    sp = s.sessionpresentation_set.get(document=doc)
                    sp.rev = doc.rev
                    sp.save()
                except ObjectDoesNotExist:
                    s.sessionpresentation_set.create(document=doc,rev=doc.rev)

            # create NewRevisionDocEvent instead of uploaded, per Ole
            NewRevisionDocEvent.objects.create(type='new_revision',
                                       by=request.user.person,
                                       doc=doc,
                                       rev=doc.rev,
                                       desc='New revision available',
                                       time=now)
            
            post_process(doc)
            create_proceedings(meeting,group)
            messages.success(request,'File uploaded sucessfully')

    else:
        form = UnifiedUploadForm(initial={'meeting_id':meeting.id,'acronym':group.acronym,'material_type':'slides'})

    materials = get_materials(group,meeting)

    # gather DocEvents
    # include deleted material to catch deleted doc events
    #docs = session.materials.all()
    # Don't report on draft DocEvents since the secr/materials app isn't managing them
    docs = session.materials.exclude(type='draft')
    docevents = DocEvent.objects.filter(doc__in=docs)

    path = get_proceedings_path(meeting,group)
    if os.path.exists(path):
        proceedings_url = get_proceedings_url(meeting,group)
    else:
        proceedings_url = ''

    return render_to_response('proceedings/upload_unified.html', {
        'docevents': docevents,
        'meeting': meeting,
        'group': group,
        'materials': materials,
        'form': form,
        'session_name': session_name,   # for Tutorials, etc
        'proceedings_url': proceedings_url},
        RequestContext(request, {}),
    )
