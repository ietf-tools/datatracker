import datetime
import glob
import os
import shutil
from dateutil.parser import parse

from django.conf import settings
from django.contrib import messages
from django.db.models import Max
from django.forms.formsets import formset_factory
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils.http import urlencode

from ietf.doc.models import Document, DocumentAuthor, DocAlias, DocRelationshipName, RelatedDocument, State
from ietf.doc.models import DocEvent, NewRevisionDocEvent
from ietf.doc.utils import add_state_change_event
from ietf.ietfauth.utils import role_required
from ietf.meeting.helpers import get_meeting
from ietf.name.models import StreamName
from ietf.person.models import Person
from ietf.secr.drafts.email import announcement_from_form, get_email_initial
from ietf.secr.drafts.forms import ( AddModelForm, AuthorForm, BaseRevisionModelForm, EditModelForm,
                                    EmailForm, ExtendForm, ReplaceForm, RevisionModelForm, RfcModelForm,
                                    RfcObsoletesForm, SearchForm, UploadForm, WithdrawForm )
from ietf.secr.utils.ams_utils import get_base
from ietf.secr.utils.document import get_rfc_num, get_start_date
from ietf.submit.models import Submission, Preapproval, DraftSubmissionStateName, SubmissionEvent
from ietf.submit.mail import announce_new_version, announce_to_lists, announce_to_authors
from ietf.utils.draft import Draft


# -------------------------------------------------
# Helper Functions
# -------------------------------------------------

def archive_draft_files(filename):
    '''
    Takes a string representing the old draft filename, without extensions.
    Moves any matching files to archive directory.
    '''
    files = glob.glob(os.path.join(settings.INTERNET_DRAFT_PATH,filename) + '.*')
    for file in files:
        shutil.move(file,settings.INTERNET_DRAFT_ARCHIVE_DIR)
    return

def get_action_details(draft, request):
    '''
    This function takes a draft object and request object and returns a list of dictionaries
    with keys: label, value to be used in displaying information on the confirmation
    page.
    '''
    result = []
    data = request.POST
    
    if data['action'] == 'revision':
        m = {'label':'New Revision','value':data['revision']}
        result.append(m)
    
    if data['action'] == 'replace':
        m = {'label':'Replaced By:','value':data['replaced_by']}
        result.append(m)
        
    return result

def handle_uploaded_file(f):
    '''
    Save uploaded draft files to temporary directory
    '''
    destination = open(os.path.join(settings.IDSUBMIT_MANUAL_STAGING_DIR, f.name), 'wb+')
    for chunk in f.chunks():
        destination.write(chunk)
    destination.close()

def handle_substate(doc):
    '''
    This function checks to see if the document has a revision needed tag, if so the
    tag gets changed to ad followup, and a DocEvent is created.
    '''
    qs = doc.tags.filter(slug__in=('need-rev','rev-wglc','rev-ad','rev-iesg'))
    if qs:
        for tag in qs:
            doc.tags.remove(tag)
        doc.tags.add('ad-f-up')
        
        # add DocEvent
        system = Person.objects.get(name="(system)")
        DocEvent.objects.create(type="changed_document",
                                doc=doc,
                                rev=doc.rev,
                                desc="Sub state has been changed to <b>AD Followup</b> from <b>Revised ID Needed</b>",
                                by=system)
        
def process_files(request,draft):
    '''
    This function takes a request object and draft object.
    It obtains the list of file objects (ie from request.FILES), uploads
    the files by calling handle_file_upload() and returns
    the basename, revision number and a list of file types.  Basename and revision
    are assumed to be the same for all because this is part of the validation process.
    '''
    files = request.FILES
    file = files[files.keys()[0]]
    filename = os.path.splitext(file.name)[0]
    revision = os.path.splitext(file.name)[0][-2:]
    file_type_list = []
    for file in files.values():
        extension = os.path.splitext(file.name)[1]
        file_type_list.append(extension)
        handle_uploaded_file(file)
    
    return (filename,revision,file_type_list)

def post_submission(request, draft):
    with open(draft.get_file_name()) as file:
        wrapper = Draft(file.read().decode('utf8'), file.name)
    submission = Submission(
        name=draft.name,
        title=draft.title,
        rev=draft.rev,
        pages=draft.pages,
        file_size=os.path.getsize(draft.get_file_name()),
        document_date=wrapper.get_creation_date(),
        submission_date=datetime.date.today(),
        group_id=draft.group.id,
        remote_ip=request.META['REMOTE_ADDR'],
        first_two_pages=''.join(wrapper.pages[:2]),
        state=DraftSubmissionStateName.objects.get(slug="posted"),
        abstract=draft.abstract,
        file_types=','.join(file_types_for_draft(draft)),
    )
    submission.save()

    SubmissionEvent.objects.create(
        submission=submission,
        by=request.user.person,
        desc="Submitted and posted manually")

    return submission

def file_types_for_draft(draft):
    '''Returns list of file extensions that exist for this draft'''
    basename, ext = os.path.splitext(draft.get_file_name())
    files = glob.glob(basename + '.*')
    file_types = []
    for filename in files:
        base, ext = os.path.splitext(filename)
        if ext:
            file_types.append(ext)
    return file_types

def promote_files(draft, types):
    '''
    This function takes one argument, a draft object.  It then moves the draft files from
    the temporary upload directory to the production directory.
    '''
    filename = '%s-%s' % (draft.name,draft.rev)
    for ext in types:
        path = os.path.join(settings.IDSUBMIT_MANUAL_STAGING_DIR, filename + ext)
        shutil.move(path,settings.INTERNET_DRAFT_PATH)

# -------------------------------------------------
# Action Button Functions
# -------------------------------------------------
'''
These functions handle the real work of the action buttons: database updates,
moving files, etc.  Generally speaking the action buttons trigger a multi-page
sequence where information may be gathered using a custom form, an email 
may be produced and presented to the user to edit, and only then when confirmation
is given will the action work take place.  That's when these functions are called.
'''

def do_extend(draft, request):
    '''
    Actions:
    - update revision_date
    - set extension_date
    '''

    e = DocEvent.objects.create(
        type='changed_document',
        by=request.user.person,
        doc=draft,
        rev=draft.rev,
        time=draft.time,
        desc='Extended expiry',
    )
    draft.expires = parse(request.POST.get('expiration_date'))
    draft.save_with_history([e])

    # save scheduled announcement
    form = EmailForm(request.POST)
    announcement_from_form(form.data,by=request.user.person)
    
    return

def do_replace(draft, request):
    'Perform document replace'

    replaced = DocAlias.objects.get(name=request.POST.get('replaced'))          # a DocAlias
    replaced_by = Document.objects.get(name=request.POST.get('replaced_by'))    # a Document

    # create relationship
    RelatedDocument.objects.create(source=replaced_by,
                                   target=replaced,
                                   relationship=DocRelationshipName.objects.get(slug='replaces'))



    draft.set_state(State.objects.get(type="draft", slug="repl"))

    e = DocEvent.objects.create(
        type='changed_document',
        by=request.user.person,
        doc=replaced_by,
        rev=replaced_by.rev,
        time=draft.time,
        desc='This document now replaces <b>%s</b>' % replaced,
    )

    draft.save_with_history([e])

    # move replaced document to archive
    archive_draft_files(replaced.document.name + '-' + replaced.document.rev)

    # send announcement
    form = EmailForm(request.POST)
    announcement_from_form(form.data,by=request.user.person)

    return
    
def do_resurrect(draft, request):
    '''
     Actions
    - restore last archived version
    - change state to Active
    - reset expires
    - create DocEvent
    '''
    # restore latest revision documents file from archive
    files = glob.glob(os.path.join(settings.INTERNET_DRAFT_ARCHIVE_DIR,draft.name) + '-??.*')
    sorted_files = sorted(files)
    latest,ext = os.path.splitext(sorted_files[-1])
    files = glob.glob(os.path.join(settings.INTERNET_DRAFT_ARCHIVE_DIR,latest) + '.*')
    for file in files:
        shutil.move(file,settings.INTERNET_DRAFT_PATH)
    
    # Update draft record
    draft.set_state(State.objects.get(type="draft", slug="active"))
    
    # set expires
    draft.expires = datetime.datetime.now() + datetime.timedelta(settings.INTERNET_DRAFT_DAYS_TO_EXPIRE)

    # create DocEvent
    e = NewRevisionDocEvent.objects.create(type='completed_resurrect',
                                           by=request.user.person,
                                           doc=draft,
                                           rev=draft.rev,
                                           time=draft.time)
    
    draft.save_with_history([e])

    # send announcement
    form = EmailForm(request.POST)
    announcement_from_form(form.data,by=request.user.person)
    
    return

def do_revision(draft, request, filename, file_type_list):
    '''
    This function handles adding a new revision of an existing Internet-Draft.  
    Prerequisites: draft must be active
    Input: title, revision_date, pages, abstract, file input fields to upload new 
    draft document(s)
    Actions
    - move current doc(s) to archive directory
    - upload new docs to live dir
    - save doc in history
    - increment revision 
    - reset expires
    - create DocEvent
    - handle sub-state
    - schedule notification
    '''
    
    # TODO this behavior may change with archive strategy
    archive_draft_files(draft.name + '-' + draft.rev)
    
    # save form data
    form = BaseRevisionModelForm(request.POST,instance=draft)
    if form.is_valid():
        new_draft = form.save(commit=False)
    else:
        raise Exception(form.errors)
        raise Exception('Problem with input data %s' % form.data)

    # set revision and expires
    new_draft.rev = filename[-2:]
    new_draft.expires = datetime.datetime.now() + datetime.timedelta(settings.INTERNET_DRAFT_DAYS_TO_EXPIRE)

    # create DocEvent
    e = NewRevisionDocEvent.objects.create(type='new_revision',
                                           by=request.user.person,
                                           doc=draft,
                                           rev=new_draft.rev,
                                           desc='New revision available',
                                           time=draft.time)

    new_draft.save_with_history([e])

    handle_substate(new_draft)
    
    # move uploaded files to production directory
    promote_files(new_draft, file_type_list)
    
    # save the submission record
    submission = post_submission(request, new_draft)

    announce_to_lists(request, submission)
    announce_new_version(request, submission, draft, '')
    announce_to_authors(request, submission)
        
    return

def do_update(draft,request,filename,file_type_list):
    '''
     Actions
    - increment revision #
    - reset expires
    - create DocEvent
    - do substate check
    - change state to Active
    '''
    # save form data
    form = BaseRevisionModelForm(request.POST,instance=draft)
    if form.is_valid():
        new_draft = form.save(commit=False)
    else:
        raise Exception('Problem with input data %s' % form.data)

    handle_substate(new_draft)
    
    # update draft record
    new_draft.rev = os.path.splitext(filename)[0][-2:]
    new_draft.expires = datetime.datetime.now() + datetime.timedelta(settings.INTERNET_DRAFT_DAYS_TO_EXPIRE)

    new_draft.set_state(State.objects.get(type="draft", slug="active"))
    
    # create DocEvent
    e = NewRevisionDocEvent.objects.create(type='new_revision',
                                           by=request.user.person,
                                           doc=new_draft,
                                           rev=new_draft.rev,
                                           desc='New revision available',
                                           time=new_draft.time)
    
    new_draft.save_with_history([e])

    # move uploaded files to production directory
    promote_files(new_draft, file_type_list)
    
    # save the submission record
    post_submission(request, new_draft)

def do_update_announce(draft, request):
    # send announcement
    form = EmailForm(request.POST)
    announcement_from_form(form.data,by=request.user.person)
    
    return

def do_withdraw(draft,request):
    '''
    Actions
    - change state to withdrawn
    - TODO move file to archive
    '''
    withdraw_type = request.POST.get('withdraw_type')

    prev_state = draft.get_state("draft")
    new_state = None
    if withdraw_type == 'ietf':
        new_state = State.objects.get(type="draft", slug="ietf-rm")
    elif withdraw_type == 'author':
        new_state = State.objects.get(type="draft", slug="auth-rm")

    if not new_state:
        return

    draft.set_state(new_state)

    e = add_state_change_event(draft, request.user.person, prev_state, new_state)
    if e:
        draft.save_with_history([e])

    # send announcement
    form = EmailForm(request.POST)
    announcement_from_form(form.data,by=request.user.person)
    
    return

# -------------------------------------------------
# Standard View Functions
# -------------------------------------------------
@role_required('Secretariat')
def abstract(request, id):
    '''
    View Internet Draft Abstract

    **Templates:**

    * ``drafts/abstract.html``

    **Template Variables:**

    * draft
    '''
    draft = get_object_or_404(Document, name=id)

    return render(request, 'drafts/abstract.html', {
        'draft': draft},
    )

@role_required('Secretariat')
def add(request):
    '''
    Add Internet Draft

    **Templates:**

    * ``drafts/add.html``

    **Template Variables:**

    * form 
    '''

    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            return redirect('drafts')

        upload_form = UploadForm(request.POST, request.FILES)
        form = AddModelForm(request.POST)
        if form.is_valid() and upload_form.is_valid():
            draft = form.save(commit=False)
            
            # process files
            filename,revision,file_type_list = process_files(request, draft)
            name = get_base(filename)
            
            # set fields (set stream or intended status?)
            draft.rev = revision
            draft.name = name
            draft.type_id = 'draft'

            # set stream based on document name
            if not draft.stream:
                stream_slug = None
                if draft.name.startswith("draft-iab-"):
                    stream_slug = "iab"
                elif draft.name.startswith("draft-irtf-"):
                    stream_slug = "irtf"
                elif draft.name.startswith("draft-ietf-") and (draft.group.type_id != "individ"):
                    stream_slug = "ietf"
                
                if stream_slug:
                    draft.stream = StreamName.objects.get(slug=stream_slug)
                
            # set expires
            draft.expires = datetime.datetime.now() + datetime.timedelta(settings.INTERNET_DRAFT_DAYS_TO_EXPIRE)

            draft.save(force_insert=True)
            
            # set state
            draft.set_state(State.objects.get(type="draft", slug="active"))
            
            # automatically set state "WG Document"
            if draft.stream_id == "ietf" and draft.group.type_id == "wg":
                draft.set_state(State.objects.get(type="draft-stream-%s" % draft.stream_id, slug="wg-doc"))
            
            # create DocAlias
            DocAlias.objects.get_or_create(name=name, document=draft)
            
            # create DocEvent
            NewRevisionDocEvent.objects.create(type='new_revision',
                                               by=request.user.person,
                                               doc=draft,
                                               rev=draft.rev,
                                               time=draft.time,
                                               desc="New revision available")
        
            # move uploaded files to production directory
            promote_files(draft, file_type_list)
            
            # save the submission record
            post_submission(request, draft)
            
            messages.success(request, 'New draft added successfully!')
            params = dict(action='add')
            url = reverse('ietf.secr.drafts.views.authors', kwargs={'id':draft.pk})
            url = url + '?' + urlencode(params)
            return redirect(url)

    else:
        form = AddModelForm()
        upload_form = UploadForm()
        
    return render(request, 'drafts/add.html', {
        'form': form,
        'upload_form': upload_form},
    )

@role_required('Secretariat')
def announce(request, id):
    '''
    Schedule announcement of new Internet-Draft to I-D Announce list

    **Templates:**

    * none

    **Template Variables:**

    * none
    '''
    draft = get_object_or_404(Document, name=id)

    email_form = EmailForm(get_email_initial(draft,action='new'))
                            
    announcement_from_form(email_form.data,
                           by=request.user.person,
                           from_val='Internet-Drafts@ietf.org',
                           content_type='Multipart/Mixed; Boundary="NextPart"')
            
    messages.success(request, 'Announcement scheduled successfully!')
    return redirect('ietf.secr.drafts.views.view', id=id)

@role_required('Secretariat')
def approvals(request):
    '''
    This view handles setting Initial Approval for drafts
    '''
    
    approved = Preapproval.objects.all().order_by('name')
    form = None
    
    return render(request, 'drafts/approvals.html', {
        'form': form,
        'approved': approved},
    )

@role_required('Secretariat')
def author_delete(request, id, oid):
    '''
    This view deletes the specified author from the draft
    '''
    author = DocumentAuthor.objects.get(id=oid)

    if request.method == 'POST' and request.POST['post'] == 'yes':
        author.delete()
        messages.success(request, 'The author was deleted successfully')
        return redirect('ietf.secr.drafts.views.authors', id=id)

    return render(request, 'confirm_delete.html', {'object': author})

@role_required('Secretariat')
def authors(request, id):
    ''' 
    Edit Internet Draft Authors

    **Templates:**

    * ``drafts/authors.html``

    **Template Variables:**

    * form, draft

    '''
    draft = get_object_or_404(Document, name=id)
    action = request.GET.get('action')

    if request.method == 'POST':
        form = AuthorForm(request.POST)
        button_text = request.POST.get('submit', '') 
        if button_text == 'Done':
            if action == 'add':
                return redirect('ietf.secr.drafts.views.announce', id=id)
            return redirect('ietf.secr.drafts.views.view', id=id)

        if form.is_valid():
            person = form.cleaned_data['person']
            email = form.cleaned_data['email']
            affiliation = form.cleaned_data.get('affiliation') or ""
            country = form.cleaned_data.get('country') or ""

            authors = draft.documentauthor_set.all()
            if authors:
                order = authors.aggregate(Max('order')).values()[0] + 1
            else:
                order = 1
            DocumentAuthor.objects.create(document=draft, person=person, email=email, affiliation=affiliation, country=country, order=order)
            
            messages.success(request, 'Author added successfully!')
            return redirect('ietf.secr.drafts.views.authors', id=id)

    else: 
        form = AuthorForm()

    return render(request, 'drafts/authors.html', {
        'draft': draft,
        'form': form},
    )

@role_required('Secretariat')
def confirm(request, id):
    draft = get_object_or_404(Document, name=id)

    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            return redirect('ietf.secr.drafts.views.view', id=id)

        action = request.POST.get('action','')
        form = EmailForm(request.POST)
        if form.is_valid():
            email = form.data
            details = get_action_details(draft, request)
            hidden_form = EmailForm(request.POST, hidden=True)

            return render(request, 'drafts/confirm.html', {
                'details': details,
                'email': email,
                'action': action,
                'draft': draft,
                'form': hidden_form},
            )
        else:
            return render(request, 'drafts/email.html', {
                'form': form,
                'draft': draft,
                'action': action},
            )

@role_required('Secretariat')
def do_action(request, id):
    '''
    This view displays changes that will be made and calls appropriate
    function if the user elects to proceed.  If the user cancels then 
    the view page is returned.
    '''
    draft = get_object_or_404(Document, name=id)

    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            return redirect('ietf.secr.drafts.views.view', id=id)

        action = request.POST.get('action')

        if action == 'revision':
            func = do_revision
        elif action == 'resurrect':
            func = do_resurrect
        elif action == 'replace':
            func = do_replace
        elif action == 'update':
            func = do_update_announce
        elif action == 'extend':
            func = do_extend
        elif action == 'withdraw':
            func = do_withdraw

        func(draft,request)
    
        messages.success(request, '%s action performed successfully!' % action)
        return redirect('ietf.secr.drafts.views.view', id=id)

@role_required('Secretariat')
def dates(request):
    ''' 
    Manage ID Submission Dates

    **Templates:**

    * none

    **Template Variables:**

    * none
    '''
    meeting = get_meeting()
        
    return render(request, 'drafts/dates.html', {
        'meeting':meeting},
    )

@role_required('Secretariat')
def edit(request, id):
    '''
    Since there's a lot going on in this function we are summarizing in the docstring.
    Also serves as a record of requirements.

    if revision number increases add document_comments and send notify-revision
    if revision date changed and not the number return error
    check if using restricted words (?)
    send notification based on check box
    revision date = now if a new status box checked add_id5.cfm 
    (notify_[resurrection,revision,updated,extended])
    if rfcnum="" rfcnum=0
    if status != 2, expired_tombstone="0"
    if new revision move current txt and ps files to archive directory (add_id5.cfm)
    if status > 3 create tombstone, else send revision notification (EmailIDRevision.cfm)
    '''
    draft = get_object_or_404(Document, name=id)
    
    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            return redirect('ietf.secr.drafts.views.view', id=id)

        form = EditModelForm(request.POST, instance=draft)
        if form.is_valid():
            if form.changed_data:
                e = DocEvent.objects.create(type='changed_document',
                                            by=request.user.person,
                                            doc=draft,
                                            rev=draft.rev,
                                            desc='Changed field(s): %s' % ','.join(form.changed_data))
                # see EditModelForm.save() for detailed logic
                form.save(commit=False)
                draft.save_with_history([e])
                
                messages.success(request, 'Draft modified successfully!')
            
            return redirect('ietf.secr.drafts.views.view', id=id)
        else:
            #assert False, form.errors
            pass
    else:
        form = EditModelForm(instance=draft)
    
    return render(request, 'drafts/edit.html', {
        'form': form,
        'draft': draft},
    )
    
@role_required('Secretariat')
def email(request, id):
    '''
    This function displays the notification message and allows the
    user to make changes before continuing to confirmation page.
    '''
    draft = get_object_or_404(Document, name=id)
    action = request.GET.get('action')
    data = request.GET

    # the resurrect email body references the last revision number, handle
    # exception if no last revision found
    # if this exception was handled closer to the source it would be easier to debug
    # other problems with get_email_initial
    try:
        form = EmailForm(initial=get_email_initial(draft,action=action,input=data))
    except Exception, e:
        return render(request, 'drafts/error.html', { 'error': e},)

    return render(request, 'drafts/email.html', {
        'form': form,
        'draft': draft,
        'action': action,
    })

@role_required('Secretariat')
def extend(request, id):
    '''
    This view handles extending the expiration date for an Internet-Draft
    Prerequisites: draft must be active
    Input: new date
    Actions
    - revision_date = today
    # - call handle_comment
    '''
    draft = get_object_or_404(Document, name=id)
    
    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            return redirect('ietf.secr.drafts.views.view', id=id)

        form = ExtendForm(request.POST)
        if form.is_valid():
            params = form.cleaned_data
            params['action'] = 'extend'
            url = reverse('ietf.secr.drafts.views.email', kwargs={'id':id})
            url = url + '?' + urlencode(params)
            return redirect(url)

    else:
        form = ExtendForm(initial={'revision_date':datetime.date.today().isoformat()})

    return render(request, 'drafts/extend.html', {
        'form': form,
        'draft': draft},
    )
    
@role_required('Secretariat')
def makerfc(request, id):
    ''' 
    Make RFC out of Internet Draft

    **Templates:**

    * ``drafts/makerfc.html``

    **Template Variables:**

    * draft 
    '''

    draft = get_object_or_404(Document, name=id)
    
    # raise error if draft intended standard is empty
    if not draft.intended_std_level:
        messages.error(request, 'ERROR: intended RFC status is not set')
        return redirect('ietf.secr.drafts.views.view', id=id)

    ObsFormset = formset_factory(RfcObsoletesForm, extra=15, max_num=15)
    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            return redirect('ietf.secr.drafts.views.view', id=id)

        form = RfcModelForm(request.POST, instance=draft)
        obs_formset = ObsFormset(request.POST, prefix='obs')
        if form.is_valid() and obs_formset.is_valid():

            # TODO
            archive_draft_files(draft.name + '-' + draft.rev)
            
            rfc = form.save(commit=False)
            
            # create DocEvent
            e = DocEvent.objects.create(type='published_rfc',
                                        by=request.user.person,
                                        doc=rfc,
                                        rev=draft.rev,
                                        desc="Published RFC")

            # change state
            draft.set_state(State.objects.get(type="draft", slug="rfc"))
            
            # handle rfc_obsoletes formset
            # NOTE: because we are just adding RFCs in this form we don't need to worry
            # about the previous state of the obs forms
            for obs_form in obs_formset.forms:
                if obs_form.has_changed():
                    rfc_acted_on = obs_form.cleaned_data.get('rfc','')
                    target = DocAlias.objects.get(name="rfc%s" % rfc_acted_on)
                    relation = obs_form.cleaned_data.get('relation','')
                    if rfc and relation:
                        # form validation ensures the rfc_acted_on exists, can safely use get
                        RelatedDocument.objects.create(source=draft,
                                                       target=target,
                                                       relationship=DocRelationshipName.objects.get(slug=relation))

            rfc.save_with_history([e])

            messages.success(request, 'RFC created successfully!')
            return redirect('ietf.secr.drafts.views.view', id=id)
        else:
            # assert False, (form.errors, obs_formset.errors)
            pass      
    else:
        form = RfcModelForm(instance=draft)
        obs_formset = ObsFormset(prefix='obs')
    
    return render(request, 'drafts/makerfc.html', {
        'form': form,
        'obs_formset': obs_formset,
        'draft': draft},
    )

@role_required('Secretariat')
def nudge_report(request):
    '''
    This view produces the Nudge Report, basically a list of documents that are in the IESG
    process but have not had activity in some time
    '''
    docs = Document.objects.filter(type='draft',states__slug='active')
    docs = docs.filter(states=12,tags='need-rev')
                
    return render(request, 'drafts/report_nudge.html', {
        'docs': docs},
    )
    
@role_required('Secretariat')
def replace(request, id):
    '''
    This view handles replacing one Internet-Draft with another 
    Prerequisites: draft must be active
    Input: replacement draft filename
  
    # TODO: support two different replaced messages in email
    '''
    
    draft = get_object_or_404(Document, name=id)
    
    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            return redirect('ietf.secr.drafts.views.view', id=id)

        form = ReplaceForm(request.POST, draft=draft)
        if form.is_valid():
            #params = form.cleaned_data
            params = {}
            params['replaced'] = form.data['replaced']
            params['replaced_by'] = form.data['replaced_by']
            params['action'] = 'replace'
            url = reverse('ietf.secr.drafts.views.email', kwargs={'id':id})
            url = url + '?' + urlencode(params)
            return redirect(url)

    else:
        form = ReplaceForm(draft=draft)

    return render(request, 'drafts/replace.html', {
        'form': form,
        'draft': draft},
    )

@role_required('Secretariat')
def revision(request, id):
    '''
    This function presents the input form for the New Revision action.
    on POST, updates draft to new revision and sends notification.
    '''

    draft = get_object_or_404(Document, name=id)
    
    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            return redirect('ietf.secr.drafts.views.view', id=id)

        upload_form = UploadForm(request.POST, request.FILES, draft=draft)
        form = RevisionModelForm(request.POST, instance=draft)
        if form.is_valid() and upload_form.is_valid():
            # process files
            filename,revision,file_type_list = process_files(request,draft)
            
            do_revision(draft, request, filename, file_type_list)

            messages.success(request, 'New Revision successful!')
            return redirect('ietf.secr.drafts.views.view', id=id)

    else:
        form = RevisionModelForm(instance=draft,initial={'revision_date':datetime.date.today().isoformat()})
        upload_form = UploadForm(draft=draft)
        
    return render(request, 'drafts/revision.html', {
        'form': form,
        'upload_form': upload_form,
        'draft': draft},
    )

@role_required('Secretariat')
def search(request):
    ''' 
    Search Internet Drafts

    **Templates:**

    * ``drafts/search.html``

    **Template Variables:**

    * form, results

    '''
    results = []
    
    if request.method == 'POST':
        form = SearchForm(request.POST)
        if request.POST['submit'] == 'Add':
            return redirect('sec.drafts.views.add')

        if form.is_valid():
            kwargs = {} 
            intended_std_level = form.cleaned_data['intended_std_level']
            title = form.cleaned_data['document_title']
            group = form.cleaned_data['group']
            name = form.cleaned_data['filename']
            state = form.cleaned_data['state']
            revision_date_start = form.cleaned_data['revision_date_start'] 
            revision_date_end = form.cleaned_data['revision_date_end'] 
            # construct seach query
            if intended_std_level:
                kwargs['intended_std_level'] = intended_std_level
            if title:
                kwargs['title__istartswith'] = title
            if state:
                kwargs['states__type'] = 'draft'
                kwargs['states'] = state
            if name:
                kwargs['name__istartswith'] = name
            if group:
                kwargs['group__acronym__istartswith'] = group
            if revision_date_start:
                kwargs['docevent__type'] = 'new_revision'
                kwargs['docevent__time__gte'] = revision_date_start
            if revision_date_end:
                kwargs['docevent__type'] = 'new_revision'
                kwargs['docevent__time__lte'] = revision_date_end
            
            # perform query
            if kwargs:
                qs = Document.objects.filter(**kwargs)
            else:
                qs = Document.objects.all()
            #results = qs.order_by('group__name')
            results = qs.order_by('name')
            
            # if there's just one result go straight to view
            if len(results) == 1:
                return redirect('ietf.secr.drafts.views.view', id=results[0].name)
    else:
        active_state = State.objects.get(type='draft',slug='active')
        form = SearchForm(initial={'state':active_state.pk})

    return render(request, 'drafts/search.html', {
        'results': results,
        'form': form},
    )

@role_required('Secretariat')
def update(request, id):
    '''
    This view handles the Update action for an Internet-Draft
    Update is when an expired draft gets a new revision, (the state does not change?)
    Prerequisites: draft must be expired 
    Input: upload new files, pages, abstract, title
    '''
    
    draft = get_object_or_404(Document, name=id)
    
    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            return redirect('ietf.secr.drafts.views.view', id=id)

        upload_form = UploadForm(request.POST, request.FILES, draft=draft)
        form = RevisionModelForm(request.POST, instance=draft)
        if form.is_valid() and upload_form.is_valid():
            # process files
            filename,revision,file_type_list = process_files(request,draft)

            do_update(draft, request, filename, file_type_list)

            params = dict(action='update')
            params['filename'] = filename
            url = reverse('ietf.secr.drafts.views.email', kwargs={'id':id})
            url = url + '?' + urlencode(params)
            return redirect(url)

    else:
        form = RevisionModelForm(instance=draft,initial={'revision_date':datetime.date.today().isoformat()})
        upload_form = UploadForm(draft=draft)
        
    return render(request, 'drafts/revision.html', {
        'form': form,
        'upload_form':upload_form,
        'draft': draft},
    )

@role_required('Secretariat')
def view(request, id):
    ''' 
    View Internet Draft

    **Templates:**

    * ``drafts/view.html``

    **Template Variables:**

    * draft, area, id_tracker_state
    '''
    draft = get_object_or_404(Document, name=id)

    # TODO fix in Django 1.2
    # some boolean state variables for use in the view.html template to manage display
    # of action buttons.  NOTE: Django 1.2 support new smart if tag in templates which
    # will remove the need for these variables
    state = draft.get_state_slug()
    is_active = True if state == 'active' else False
    is_expired = True if state == 'expired' else False
    is_withdrawn = True if (state in ('auth-rm','ietf-rm')) else False
    
    # TODO should I rewrite all these or just use proxy.InternetDraft?
    # add legacy fields
    draft.iesg_state = draft.get_state('draft-iesg')
    draft.review_by_rfc_editor = bool(draft.tags.filter(slug='rfc-rev'))
    
    # can't assume there will be a new_revision record
    r_event = draft.latest_event(type__in=('new_revision','completed_resurrect'))
    draft.revision_date = r_event.time.date() if r_event else None
    
    draft.start_date = get_start_date(draft)
    
    e = draft.latest_event(type__in=('expired_document', 'new_revision', "completed_resurrect"))
    draft.expiration_date = e.time.date() if e and e.type == "expired_document" else None
    draft.rfc_number = get_rfc_num(draft)
    
    # check for replaced bys
    qs = Document.objects.filter(relateddocument__target__document=draft, relateddocument__relationship='replaces')
    if qs:
        draft.replaced_by = qs[0]
    
    # check for DEVELOPMENT setting and pass to template
    is_development = False
    try:
        is_development = settings.DEVELOPMENT
    except AttributeError:
        pass

    return render(request, 'drafts/view.html', {
        'is_active': is_active,
        'is_expired': is_expired,
        'is_withdrawn': is_withdrawn,
        'is_development': is_development,
        'draft': draft},
    )

@role_required('Secretariat')
def withdraw(request, id):
    '''
    This view handles withdrawing an Internet-Draft
    Prerequisites: draft must be active
    Input: by IETF or Author 
    '''
    
    draft = get_object_or_404(Document, name=id)

    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            return redirect('ietf.secr.drafts.views.view', id=id)

        form = WithdrawForm(request.POST)
        if form.is_valid():
            params = form.cleaned_data
            params['action'] = 'withdraw'
            url = reverse('ietf.secr.drafts.views.email', kwargs={'id':id})
            url = url + '?' + urlencode(params)
            return redirect(url)

    else:
        form = WithdrawForm()

    return render(request, 'drafts/withdraw.html', {
        'draft': draft,
        'form': form},
    )
    
