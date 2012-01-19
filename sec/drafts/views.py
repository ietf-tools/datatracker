from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.core.urlresolvers import reverse
from django.db.models import get_model
from django.forms.formsets import formset_factory
from django.forms.models import inlineformset_factory, modelformset_factory
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.utils import simplejson

from email import *
from forms import *
from sec.sessions.views import get_meeting
from sec.utils.ams_utils import get_base, get_email, get_start_date
from sec.utils.draft import get_rfc_num

import datetime
import glob
import os
import shutil
import textwrap
import time

# -------------------------------------------------
# Helper Functions
# -------------------------------------------------

def archive_draft_files(filename):
    '''
    Takes a string representing the old draft filename, without extensions.
    Moves any matching files to archive directory.
    '''
    if not os.path.isdir(settings.INTERNET_DRAFT_ARCHIVE_DIR):
        raise IOError('Internet-Draft archive directory does not exist (%s)' % settings.INTERNET_DRAFT_ARCHIVE_DIR)
    files = glob.glob(os.path.join(settings.INTERNET_DRAFT_DIR,filename) + '.*')
    for file in files:
        shutil.move(file,settings.INTERNET_DRAFT_ARCHIVE_DIR)
    return

def get_action_details(draft, session):
    '''
    This function takes a draft object and session object and returns a list of dictionaries
    with keys: label, value to be used in displaying information on the confirmation
    page.
    '''
    result = []
    if session['action'] == 'revision':
        m = {'label':'New Revision','value':session['revision']}
        result.append(m)
    
    if session['action'] == 'replace':
        m = {'label':'Replaced By:','value':session['data']['replaced_by']}
        result.append(m)
        
    return result

def get_doc_url(doc):
    name = doc.name
    if doc.get_state_slug() == "rfc":
        aliases = self.docalias_set.filter(name__startswith="rfc")
        if aliases:
            name = aliases[0].name
    return urlreverse('drafts_view', kwargs={ 'id': name })
        
def handle_uploaded_file(f):
    '''
    Save uploaded draft files to temporary directory
    '''
    #destination = open(os.path.join(settings.INTERNET_DRAFT_DIR, f.name), 'wb+')
    destination = open(os.path.join('/tmp', f.name), 'wb+')
    for chunk in f.chunks():
        destination.write(chunk)
    destination.close()

def handle_substate(doc):
    '''
    This function checks to see if the document has a revision needed tag, if so the
    tag gets changed to ad followup
    '''
    """
    if IDInternal.objects.filter(draft=draft.id_document_tag):
        try:
            id = IDInternal.objects.get(draft=draft.id_document_tag)
            revised_state_obj = IDSubState.objects.get(sub_state_id=5)
            followup_state_obj = IDSubState.objects.get(sub_state_id=2)
            if id.cur_sub_state == revised_state_obj:
                save_comment(draft, 'Sub state has been changed to <b>AD Follow up</b> from New ID Needed')
                id.cur_sub_state = followup_state_obj
                id.prev_sub_state = revised_state_obj
                id.save()
        except (ObjectDoesNotExist, MultipleObjectsReturned):
            raise Exception('Error updating ID sub state')
    """
    qs = doc.tags.filter(slug__in=('need-rev','rev-wglc','rev-ad','rev-iesg'))
    if qs:
        for tag in qs:
            doc.tags.remove(tag)
        doc.tags.add('ad-f-up')
        
def process_files(files):
    '''
    This function takes a list of file objects (ie from request.FILES), uploads
    the files by calling handle_file_upload() and returns
    the basename, revision number and a list of file types.  Basename and revision
    are assumed to be the same for all because this is part of the validation process.
    '''
    file = files[files.keys()[0]]
    filename = os.path.splitext(file.name)[0]
    revision = os.path.splitext(file.name)[0][-2:]
    file_type_list = []
    for file in files.values():
        file_type_list.append(os.path.splitext(file.name)[1])
        handle_uploaded_file(file)
    return (filename,revision,file_type_list)

def promote_files(draft, types):
    '''
    This function takes one argument, a draft object.  It then moves the draft files from
    the temporary upload directory to the production directory.
    '''
    filename = '%s-%s' % (draft.name,draft.rev)
    for ext in types:
        path = os.path.join('/tmp', filename + ext)
        shutil.move(path,settings.INTERNET_DRAFT_DIR)

# -------------------------------------------------
# Action Button Functions
# -------------------------------------------------
'''
These functions handle the real work of the action buttons: database updates,
moving files, etc.  Generally speaking the action buttons trigger a multi-page
sequence where information may be gathered using a custom form, an email 
may be produced and presented to the user to edit, and only then when confirmation
is given will the action work take place.  That's when these functions are called.
The details of the action are stored in request.session.
'''

def do_extend(draft, request):
    '''
    Actions:
    - update revision_date
    - set extension_date
    '''
    
    #draft.revision_date = session['data']['revision_date']
    #draft.extension_date = session['data']['revision_date']
    draft.save()
    
    # save scheduled announcement
    announcement_from_form(session['email'],by=request.user.get_profile())
    
    return

def do_replace(draft, request):
    '''
    Actions
    - change state to Replaced
    - create replaced relationship
    - create DocEvent
    '''
    """
    save_document_in_history(draft)
    
    # don't archive document prioir to expiration per Henrik
    
    replaced_by_name = request.session['data']['replaced_by']
    replaced_by_object = get_object_or_404(Document, name=replaced_by_name)
    
    # create document_comment if applicable
    # If the replacing document exists in IDInternal use pidtracker url in the comment
    # otherwise just use the filename.
    if draft.get_state('draft-iesg'):
        comment = 'Document replaced by <a href="https://datatracker.ietf.org/public/pidtracker.cgi?command=view&dTag=%s&rfc_flag=0">%s</a>' % (replaced_by_object.id_document_tag,replaced_by_name)
    else:
        comment = 'Document replaced by %s' % (replaced_by_name)
    
    # handle comment
    # handle_comment(draft,comment)
    
    # change state
    draft.set_state(State.objects.get(type="draft", slug="repl"))
    
    # create relationship
    RelatedDocument.objects.create(source=replaced_by_object,
                                   target=draft,
                                   relationship=DocRelationshipName.objects.get(slug='replaces'))
    # send announcement
    announcement_from_form(request.session['email'],by=request.user.get_profile())
    
    return
    """
    pass
    
def do_resurrect(draft, request):
    '''
     Actions
    - restore last archived version
    - change state to Active
    - create DocEvent
    '''
    # restore latest revision documents file from archive
    files = glob.glob(os.path.join(settings.INTERNET_DRAFT_ARCHIVE_DIR,draft.name) + '-??.*')
    sorted_files = sorted(files)
    latest,ext = os.path.splitext(sorted_files[-1])
    files = glob.glob(os.path.join(settings.INTERNET_DRAFT_ARCHIVE_DIR,latest) + '.*')
    for file in files:
        shutil.move(file,settings.INTERNET_DRAFT_DIR)
    
    # Update draft record
    draft.set_state(State.objects.get(type="draft", slug="active"))
    
    # create DocEvent
    NewRevisionDocEvent.objects.create(type='completed_resurrect',
                                       by=request.user.get_profile(),
                                       doc=draft,
                                       rev=draft.rev)
    
    # send announcement
    announcement_from_form(request.session['email'],by=request.user.get_profile())
    
    return

def do_revision(draft, request):
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
    - reset extension_date
    - create DocEvent
    - handle sub-state
    - schedule notification
    '''
    
    # TODO this behavior may change with archive strategy
    archive_draft_files(draft.name + '-' + draft.rev)
    
    save_document_in_history(draft)

    # save form data
    form = BaseRevisionModelForm(request.session['data'],instance=draft)
    if form.is_valid():
        new_draft = form.save()
    else:
        raise Exception('Problem with input data %s' % form.data)

    # save filetypes and revision
    new_draft.rev = request.session['filename'][-2:]
    # TODO: reset expiry date if necessary
    new_draft.save()
    
    # create DocEvent
    NewRevisionDocEvent.objects.create(type='new_revision',
                                       by=request.user.get_profile(),
                                       doc=draft,
                                       rev=new_draft.rev,
                                       desc='New revision available')

    handle_substate(new_draft)
    
    # move uploaded files to production directory
    promote_files(new_draft, request.session['file_type'])
    
    # send announcement if we are in IESG process
    if new_draft.get_state('draft-iesg'):
        announcement_from_form(request.session['email'],by=request.user.get_profile())

    return

def do_update(draft,request):
    '''
     Actions
    - increment revision #
    - create DocEvent
    - do substate check
    - change state to Active
    '''
    save_document_in_history(draft)
    
    # save form data
    form = BaseRevisionModelForm(request.session['data'],instance=draft)
    if form.is_valid():
        new_draft = form.save()
    else:
        raise Exception('Problem with input data %s' % form.data)
    
    # create DocEvent
    NewRevisionDocEvent.objects.create(type='new_revision',
                                       by=request.user.get_profile(),
                                       doc=draft,
                                       rev=new_draft.rev,
                                       desc='New revision available')

    handle_substate(new_draft)
    
    # update draft record
    new_draft.rev = os.path.splitext(request.session['data']['filename'])[0][-2:]
    new_draft.set_state(State.objects.get(type="draft", slug="active"))
    new_draft.save()
    
    # move uploaded files to production directory
    promote_files(new_draft, request.session['file_type'])
    
    # send announcement
    announcement_from_form(request.session['email'],by=request.user.get_profile())
    
    return

def do_withdraw(draft,request):
    '''
    Actions
    - change state to withdrawn
    - TODO move file to archive
    '''
    withdraw_type = request.session['data']['type']
    if withdraw_type == 'ietf':
        draft.set_state(State.objects.get(type="draft", slug="ietf-rm"))
    elif withdraw_type == 'author':
        draft.set_state(State.objects.get(type="draft", slug="auth-rm"))
    
    # send announcement
    announcement_from_form(request.session['email'],by=request.user.get_profile())
    
    return
    
# -------------------------------------------------
# Standard View Functions
# -------------------------------------------------
def abstract(request, id):
    '''
    View Internet Draft Abstract

    **Templates:**

    * ``drafts/abstract.html``

    **Template Variables:**

    * draft
    '''
    draft = get_object_or_404(Document, name=id)

    return render_to_response('drafts/abstract.html', {
        'draft': draft},
        RequestContext(request, {}),
    )

def add(request):
    '''
    Add Internet Draft

    **Templates:**

    * ``drafts/add.html``

    **Template Variables:**

    * form 
    '''
    request.session.clear()
    
    FileFormset = formset_factory(AddFileForm, formset=BaseFileFormSet, extra=4, max_num=4)
    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            url = reverse('drafts_search')
            return HttpResponseRedirect(url)

        file_formset = FileFormset(request, request.POST, request.FILES, prefix='file')
        form = AddModelForm(request.POST)
        if form.is_valid() and file_formset.is_valid():
            draft = form.save(commit=False)
            
            # process files
            filename,revision,file_type_list = process_files(request.FILES)
            name = get_base(filename)
            
            # set fields (set stream or intended status?)
            draft.rev = revision
            draft.name = name
            draft.type = DocTypeName.objects.get(slug='draft')
            draft.save()
            
            # set state
            draft.set_state(State.objects.get(type="draft", slug="active"))
            
            # create DocAlias
            DocAlias.objects.get_or_create(name=name, document=draft)
            
            # create DocEvent
            NewRevisionDocEvent.objects.create(type='new_revision',
                                               by=request.user.get_profile(),
                                               doc=draft,
                                               rev=draft.rev)
            
            # move uploaded files to production directory
            promote_files(draft, file_type_list)
    
            request.session['action'] = 'add'
            
            messages.success(request, 'New draft added successfully!')
            url = reverse('drafts_authors', kwargs={'id':draft.name})
            return HttpResponseRedirect(url)
            
    else:
        form = AddModelForm()
        file_formset = FileFormset(request, prefix='file')

    return render_to_response('drafts/add.html', {
        'form': form,
        'file_formset': file_formset},
        RequestContext(request, {}),
    )

def announce(request, id):
    '''
    Schedule announcement of new Internet-Draft to I-D Announce list

    **Templates:**

    * none

    **Template Variables:**

    * none
    '''
    draft = get_object_or_404(Document, name=id)

    email_form = EmailForm(get_email_initial(draft,type='new'))
                            
    announcement_from_form(email_form.data,
                           by=request.user.get_profile(),
                           from_val='Internet-Drafts@ietf.org',
                           content_type='Multipart/Mixed; Boundary="NextPart"')
            
    messages.success(request, 'Announcement scheduled successfully!')
    url = reverse('drafts_view', kwargs={'id':id})
    return HttpResponseRedirect(url)
"""
def approvals(request):
    '''
    This view handles setting Initial Approval for drafts
    '''
    
    approved = IdApprovedDetail.objects.all().order_by('filename')
    form = None
    
    return render_to_response('drafts/approvals.html', {
        'form': form,
        'approved': approved},
        RequestContext(request, {}),
    )
"""
def author_delete(request, id, email):
    '''
    This view deletes the specified author(email) from the draft
    '''
    draft = get_object_or_404(Document, name=id)
    author = get_object_or_404(Email, address=email)
    DocumentAuthor.objects.get(document=draft, author=author).delete()
    messages.success(request, 'The author was deleted successfully')
    url = reverse('drafts_authors', kwargs={'id':id})
    return HttpResponseRedirect(url)

def authors(request, id):
    ''' 
    Edit Internet Draft Authors

    **Templates:**

    * ``drafts/authors.html``

    **Template Variables:**

    * form, draft, authors

    '''
    draft = get_object_or_404(Document, name=id)
    authors = draft.authors.all()
    AuthorFormset = formset_factory(AuthorForm, extra=10, max_num=10)
    
    if request.method == 'POST':
        
        # handle deleting an author
        if request.POST.get('submit', '') == 'Delete':
            tag = request.POST.get('author-tag', '')
            idauthor = IDAuthor.objects.get(id=tag)
            idauthor.delete()
            messages.success(request, 'The author was deleted successfully')
            formset = AuthorFormset(prefix='author')
            
        # handle adding an author
        if request.POST.get('submit', '') == 'Submit':
            formset = AuthorFormset(request.POST,prefix='author')
            if formset.is_valid():
                for form in formset.forms:
                    if 'author_name' in form.cleaned_data:
                        name = form.cleaned_data['author_name']
                        email = get_email(name)
                        da = DocumentAuthor(document=draft,author=Email.objects.get(address=email))
                        da.save()

                messages.success(request, 'Authors added successfully!')
                action = request.session.get('action','')
                if action == 'add':
                    url = reverse('drafts_announce', kwargs={'id':id})
                else:
                    url = reverse('drafts_view', kwargs={'id':id})
                return HttpResponseRedirect(url)

    else: 
        #form = AuthorForm()
        formset = AuthorFormset(prefix='author')

    return render_to_response('drafts/authors.html', {
        'draft': draft,
        'authors': authors,
        'formset': formset},
        RequestContext(request, {}),
    )

def confirm(request, id):
    '''
    This view displays changes that will be made and calls appropriate
    function if the user elects to proceed.  If the user cancels then 
    the session data is cleared and view page is returned.
    '''
    draft = get_object_or_404(Document, name=id)
    
    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            # TODO do cancel functions from session (ie remove uploaded files?)
            # clear session data
            request.session.clear()
            url = reverse('drafts_view', kwargs={'id':id})
            return HttpResponseRedirect(url)
        
        action = request.session['action']
        if action == 'revision':
            func = do_revision
        elif action == 'resurrect':
            func = do_resurrect
        elif action == 'replace':
            func = do_replace
        elif action == 'update':
            func = do_update
        elif action == 'extend':
            func = do_extend
        elif action == 'withdraw':
            func = do_withdraw

        func(draft,request)
        
        # clear session data
        request.session.clear()
    
        messages.success(request, '%s action performed successfully!' % action)
        url = reverse('drafts_view', kwargs={'id':id})
        return HttpResponseRedirect(url)

    details = get_action_details(draft, request.session) 
    email = request.session.get('email','')
    action = request.session.get('action','')
    
    return render_to_response('drafts/confirm.html', {
        'details': details,
        'email': email,
        'action': action,
        'draft': draft},
        RequestContext(request, {}),
    )

def dates(request):
    ''' 
    Manage ID Submission Dates

    **Templates:**

    * none

    **Template Variables:**

    * none
    '''
    meeting = get_meeting()
        
    return render_to_response('drafts/dates.html', {
        'meeting':meeting},
        RequestContext(request, {}),
    )

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
            url = reverse('drafts_view', kwargs={'id':id})
            return HttpResponseRedirect(url)
        
        form = EditModelForm(request.POST, instance=draft)
        if form.is_valid():
            if form.changed_data:
                save_document_in_history(draft)
                DocEvent.objects.create(type='changed_document',
                                        by=request.user.get_profile(),
                                        doc=draft,
                                        rev=draft.rev)
                form.save()
                messages.success(request, 'Draft modified successfully!')
            
            url = reverse('drafts_view', kwargs={'id':id})
            return HttpResponseRedirect(url)
        else:
            assert False, form.errors
            
    else:
        form = EditModelForm(instance=draft)
    
    return render_to_response('drafts/edit.html', {
        'form': form,
        'draft': draft},
        RequestContext(request, {}),
    )
    
def email(request, id):
    '''
    This function displays the notification message and allows the
    user to make changes before continuing to confirmation page.
    One exception is the "revision" action, save email data and go
    directly to confirm page.
    '''

    draft = get_object_or_404(Document, name=id)
    
    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            # clear session data
            request.session.clear()
            url = reverse('drafts_view', kwargs={'id':id})
            return HttpResponseRedirect(url)
        
        form = EmailForm(request.POST)
        if form.is_valid():
            request.session['email'] = form.data
            url = reverse('drafts_confirm', kwargs={'id':id})
            return HttpResponseRedirect(url)
    else:
        # the resurrect email body references the last revision number, handle
        # exception if no last revision found
        try:
            form = EmailForm(initial=get_email_initial(
                draft,
                type=request.session['action'],
                input=request.session.get('data', None)))
        except Exception, e:
            return render_to_response('drafts/error.html', { 'error': e},)
        
        # for "revision" action skip email page and go directly to confirm
        if request.session['action'] == 'revision':
            request.session['email'] = form.initial
            url = reverse('drafts_confirm', kwargs={'id':id})
            return HttpResponseRedirect(url)
        
    return render_to_response('drafts/email.html', {
        'form': form,
        'draft': draft},
        RequestContext(request, {}),
    )

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
            url = reverse('drafts_view', kwargs={'id':id})
            return HttpResponseRedirect(url)
       
        form = ExtendForm(request.POST)
        if form.is_valid():
            request.session['data'] = form.data
            request.session['action'] = 'extend'
            url = reverse('drafts_email', kwargs={'id':id})
            return HttpResponseRedirect(url)

    else:
        form = ExtendForm(initial={'revision_date':datetime.date.today().isoformat()})

    return render_to_response('drafts/extend.html', {
        'form': form,
        'draft': draft},
        RequestContext(request, {}),
    )
    
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
        url = reverse('drafts_view', kwargs={'id':id})
        return HttpResponseRedirect(url)
            
    ObsFormset = formset_factory(RfcObsoletesForm, extra=15, max_num=15)
    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            url = reverse('drafts_view', kwargs={'id':id})
            return HttpResponseRedirect(url)
       
        form = RfcModelForm(request.POST, instance=draft)
        obs_formset = ObsFormset(request.POST, prefix='obs')
        if form.is_valid() and obs_formset.is_valid():

            # TODO
            save_document_in_history(draft)
            archive_draft_files(draft.name + '-' + draft.rev)
            
            rfc = form.save()
            
            # create DocEvent
            # create DocEvent
            DocEvent.objects.create(type='published_rfc',
                                    by=request.user.get_profile(),
                                    doc=rfc)
            
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
            
            messages.success(request, 'RFC created successfully!')
            url = reverse('drafts_view', kwargs={'id':id})
            return HttpResponseRedirect(url)
        else:
            # assert False, (form.errors, obs_formset.errors)
            pass      
    else:
        form = RfcModelForm(instance=draft)
        obs_formset = ObsFormset(prefix='obs')
    
    return render_to_response('drafts/makerfc.html', {
        'form': form,
        'obs_formset': obs_formset,
        'draft': draft},
        RequestContext(request, {}),
    )

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
            url = reverse('drafts_view', kwargs={'id':id})
            return HttpResponseRedirect(url)
       
        form = ReplaceForm(draft, request.POST)
        if form.is_valid():
            request.session['data'] = form.data
            request.session['action'] = 'replace'
            url = reverse('drafts_email', kwargs={'id':id})
            return HttpResponseRedirect(url)

    else:
        form = ReplaceForm(draft)

    return render_to_response('drafts/replace.html', {
        'form': form,
        'draft': draft},
        RequestContext(request, {}),
    )

def resurrect(request, id):
    '''
    This view handles resurrection of an Internet-Draft
    Prerequisites: draft must be expired 
    Input: none 
    '''
    
    request.session['action'] = 'resurrect'
    url = reverse('drafts_email', kwargs={'id':id})
    return HttpResponseRedirect(url)

def revision(request, id):
    '''
    This function presents the input form for the New Revision action.  If submitted
    form is valid state is saved in the session and the email page is returned.
    '''

    draft = get_object_or_404(Document, name=id)
    
    FileFormset = formset_factory(RevisionFileForm, formset=BaseFileFormSet, extra=4, max_num=4)
    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            url = reverse('drafts_view', kwargs={'id':id})
            return HttpResponseRedirect(url)
        
        file_formset = FileFormset(request, request.POST, request.FILES, prefix='file')
        form = RevisionModelForm(request.POST, instance=draft)
        # we need to save the draft id in the session so it is available for the file_formset
        # validations
        request.session['draft'] = draft
        if form.is_valid() and file_formset.is_valid():
            # process files
            filename,revision,file_type_list = process_files(request.FILES)
            
            # save state in session and proceed to email page
            request.session['data'] = form.data
            request.session['action'] = 'revision'
            request.session['filename'] = filename
            request.session['revision'] = revision
            request.session['file_type'] = file_type_list
       
            url = reverse('drafts_email', kwargs={'id':id})
            return HttpResponseRedirect(url)

    else:
        form = RevisionModelForm(instance=draft,initial={'revision_date':datetime.date.today().isoformat()})
        file_formset = FileFormset(request, prefix='file')
        
    return render_to_response('drafts/revision.html', {
        'form': form,
        'file_formset': file_formset,
        'draft': draft},
        RequestContext(request, {}),
    )

def search(request):
    ''' 
    Search Internet Drafts

    **Templates:**

    * ``drafts/search.html``

    **Template Variables:**

    * form, results

    '''
    results = []
    request.session.clear()
    
    if request.method == 'POST':
        form = SearchForm(request.POST)
        if request.POST['submit'] == 'Add':
            url = reverse('sec.drafts.views.add')
            return HttpResponseRedirect(url)
        
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
                kwargs['states__slug'] = state
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
            results = qs.order_by('group__name')
            
            # if there's just one result go straight to view
            if len(results) == 1:
                url = reverse('drafts_view', kwargs={'id':results[0].name})
                return HttpResponseRedirect(url)
    else:
        active_state = State.objects.get(type='draft',slug='active')
        form = SearchForm(initial={'state':active_state.pk})

    return render_to_response('drafts/search.html', {
        'results': results,
        'form': form},
        RequestContext(request, {}),
    )

def update(request, id):
    '''
    This view handles the Update action for an Internet-Draft
    Update is when an expired draft gets a new revision, (the state does not change?)
    Prerequisites: draft must be expired 
    Input: upload new files, pages, abstract, title
    '''
    
    draft = get_object_or_404(Document, name=id)
    
    FileFormset = formset_factory(RevisionFileForm, formset=BaseFileFormSet, extra=4, max_num=4)
    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            url = reverse('drafts_view', kwargs={'id':id})
            return HttpResponseRedirect(url)
        
        file_formset = FileFormset(request, request.POST, request.FILES, prefix='file')
        form = RevisionModelForm(request.POST, request.FILES, instance=draft)
        if form.is_valid() and file_formset.is_valid():
            # process files
            filename,revision,file_type_list = process_files(request.FILES)

            # save state in session and proceed to email page
            request.session['data'] = form.data
            request.session['action'] = 'update'
            request.session['revision'] = revision
            request.session['data']['filename'] = filename
            request.session['file_type'] = file_type_list
       
            url = reverse('drafts_email', kwargs={'id':id})
            return HttpResponseRedirect(url)

    else:
        form = RevisionModelForm(instance=draft,initial={'revision_date':datetime.date.today().isoformat()})
        file_formset = FileFormset(request, prefix='file')
        
    return render_to_response('drafts/revision.html', {
        'form': form,
        'file_formset': file_formset,
        'draft': draft},
        RequestContext(request, {}),
    )

def view(request, id):
    ''' 
    View Internet Draft

    **Templates:**

    * ``drafts/view.html``

    **Template Variables:**

    * draft, area, id_tracker_state
    '''
    draft = get_object_or_404(Document, name=id)
    #request.session.clear()

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

    return render_to_response('drafts/view.html', {
        'is_active': is_active,
        'is_expired': is_expired,
        'is_withdrawn': is_withdrawn,
        'is_development': is_development,
        'draft': draft},
        RequestContext(request, {}),
    )

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
            url = reverse('drafts_view', kwargs={'id':id})
            return HttpResponseRedirect(url)
       
        form = WithdrawForm(request.POST)
        if form.is_valid():
            # save state in session and proceed to email page
            request.session['data'] = form.data
            request.session['action'] = 'withdraw'
            
            url = reverse('drafts_email', kwargs={'id':id})
            return HttpResponseRedirect(url)
            
    else:
        form = WithdrawForm()

    return render_to_response('drafts/withdraw.html', {
        'draft': draft,
        'form': form},
        RequestContext(request, {}),
    )
    
