from django.conf import settings
from django.contrib.auth.decorators import login_required
#from django.contrib import messages
from session_messages import create_message
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.core.urlresolvers import reverse
from django.db.models import get_model
from django.forms.formsets import formset_factory
from django.forms.models import inlineformset_factory, modelformset_factory
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.utils import simplejson

from forms import *
#from sec.utils.ams_utils import get_base, get_person
#from email import *

import datetime
import glob
import os
import shutil
import textwrap
import time

# -------------------------------------------------
# Helper Functions
# -------------------------------------------------
"""
def announcement_from_form(data, **kwargs):
    '''
    This function creates a new scheduled_announcements record.  Taking as input EmailForm.data
    and key word arguments used to override some of the scheduled_announcement fields
    '''
    # possible overrides
    scheduled_by = kwargs.get('scheduled_by','IETFDEV')
    from_val = kwargs.get('from_val','ID Tracker <internet-drafts-reply@ietf.org>')
    content_type = kwargs.get('content_type','')
    
    # from the form
    subject = data['subject']
    to_val = data['to']
    cc_val = data['cc']
    body = data['body']
    
    sa = ScheduledAnnouncement(scheduled_by=scheduled_by,
                               scheduled_date=datetime.date.today().isoformat(),
                               scheduled_time=time.strftime('%H:%M:%S'),
                               subject=subject,
                               to_val=to_val,
                               cc_val=cc_val,
                               from_val=from_val,
                               body=body,
                               first_q=1,
                               content_type=content_type)
    sa.save()
    return sa

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
    
def create_tombstone(draft, text):
    '''
    This function takes a draft object and text field and creates a tombstone file
    for the draft, using 'text' as the contents.  Previous version of the draft
    will first be moved to the archive directory.

    NOTE: this function assumes it gets called before the draft revision number
    is incremented.  This way any errors moving/creating files will be raised
    before other data is changed.
    '''
    # TODO: handle tombstone IOErrors

    disclaimer = '''\n\nInternet-Drafts are not archival documents, and copies of Internet-Drafts
that have been deleted from the directory are not available.  The
Secretariat does not have any information regarding the future plans of
the author(s) or working group, if applicable, with respect to this
deleted Internet-Draft.  For more information, or to request a copy of
the document, please contact the author(s) directly. 

Draft Author(s):
%s
''' % ('\n'.join(get_authors(draft)))

    # archive draft files
    archive_draft_files(draft.filename + '-' + draft.revision)

    # write the tombstone file
    new_revision = str(int(draft.revision)+1).zfill(2)
    new_filename = draft.filename + '-' + new_revision + '.txt'
    filepath = os.path.join(settings.INTERNET_DRAFT_DIR,new_filename)
    f = open(filepath,'w')
    
    # use textwrap to ensure lines don't exceed 80 chars
    formatted_text = textwrap.fill(text,80)
    f.write(formatted_text)
    f.write(disclaimer)
    f.close()

def get_action_details(draft, session):
    '''
    This function takes a draft object and session object and returns a list of dictionaries
    with keys: lablel, value to be used in displaying information on the confirmation
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
    
def handle_uploaded_file(f):
    '''
    Save uploaded draft files to temporary directory
    '''
    #destination = open(os.path.join(settings.INTERNET_DRAFT_DIR, f.name), 'wb+')
    destination = open(os.path.join('/tmp', f.name), 'wb+')
    for chunk in f.chunks():
        destination.write(chunk)
    destination.close()
    
def handle_comment(draft,text):
    '''
    This function takes a draft object and comment text and creates a document_comment
    record if the idtracker record exists.
    
    NOTE: this function must be called after saving the edited draft, so the revision value
    used in the DocumentComment is correct.
    '''
    try: 
        internal = IDInternal.objects.get(draft=draft.id_document_tag)
    except (IDInternal.DoesNotExist, IDInternal.MultipleObjectsReturned):
        return
    new_comment = DocumentComment(document=internal,rfc_flag=0,public_flag=1,version=draft.revision,
                                  comment_text=text)
    new_comment.save()
    
def handle_substate(draft):
    # check IDInternal sub_state
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
    
def promote_files(draft):
    '''
    This function takes one argument, a draft object.  It then moves the draft files from
    the temporary upload directory to the production directory.
    '''
    filename = '%s-%s' % (draft.filename,draft.revision)
    for ext in draft.file_type.split(','):
        path = os.path.join('/tmp', filename + ext)
        shutil.move(path,settings.INTERNET_DRAFT_DIR)
    
def save_comment(draft,text):
    '''Takes a InternetDraft object and creates a new DocumentComment record using text as 
    comment_text'''
    
    internal = IDInternal.objects.get(draft=draft.id_document_tag)
    new_comment = DocumentComment(document=internal,rfc_flag=0,public_flag=1,version=draft.revision,
                                  comment_text=text)
    new_comment.save()

# -------------------------------------------------
# Action Button Functions
# -------------------------------------------------
'''
These functions handle the real work of the action buttons: database updates,
moving files, etc.  Generally speaking the action buttons trigger a multi-page
sequence where information may be gathered using a custom form, an email 
may be produced and presented to the user to edit, and only then when confirmation
is given will the action work take place.  That's when these functions are called.
They all take a session argument where deatils of the requested action are stored.
'''

def do_extend(draft, session):
    '''
    Actions:
    - update revision_date
    - set extension_date
    '''
    
    draft.revision_date = session['data']['revision_date']
    draft.extension_date = session['data']['revision_date']
    draft.save()
    
    # save scheduled announcement
    announcement_from_form(session['email'])
    
    return

def do_makerfc(draft, session):
    '''
    Actions:
    - create tombstone / move draft files to archive
    - change revision,status of draft
    '''
    # increment revision
    old_revision = draft.revision
    new_revision = str(int(old_revision)+1).zfill(2)
    
    # create RFC tombstone
    intended_status = draft.intended_status
    status_dict = {'BCP':'a BCP',
                   'Draft Standard':'a Draft Standard',
                   'Experimental':'an Experimental RFC',
                   'Historic':'an Historic RFC',
                   'Informational':'an Informational RFC',
                   'Proposed Standard':'a Proposed Standard',
                   'Standard':'a Full Standard'}
    new_filename = draft.filename + '-' + new_revision + '.txt'
    old_filename = draft.filename + '-' + old_revision + '.txt'
    rfc_number = session['data']['rfc_number']
    rfc_published_date = session['data']['rfc_published_date']
    text = 'This Internet-Draft, %s, was published as %s, RFC %s\n(http://www.ietf.org/rfc/rfc%s.txt), on %s.\n' % (old_filename, status_dict[draft.intended_status.intended_status], rfc_number, rfc_number, rfc_published_date)
    create_tombstone(draft,text)
    
    # update draft record
    draft.revision = new_revision
    draft.status = IDStatus.objects.get(status_id=3)
    draft.rfc_number = rfc_number
    draft.save()
        
def do_replace(draft, session):
    '''
    Actions
    - create tombstone
    - increment revision
    - revision_date = today
    - change ID status to Replaced (5)
    - update field replaced_by with id_document_tag of replacing document
      (appears in GUI as filename)
    - set expired_tomstone = 0
    - call handle_comment
    - NOTE: not creating id_internal record here as it seems this code doesn't work in legacy app
    '''
    
    # create tombstone
    # NOTE: we need special handling if the document is expired AND the expired tombstone still exists
    filename = draft.filename + '-' + draft.revision + '.txt'
    path = os.path.join(settings.INTERNET_DRAFT_DIR,filename)
    if draft.status.status_id == 2 and os.path.exists(path):
        # decrement revision to get last legitimate document revision
        draft.revision = str(int(draft.revision)-1).zfill(2)
        draft.save()
        filename = draft.filename + '-' + draft.revision + '.txt'

    replaced_by_filename = session['data']['replaced_by']
    replaced_by_object = InternetDraft.objects.get(filename=replaced_by_filename)
    text = 'This Internet-Draft, %s, has been replaced by another document, %s, and has been deleted from the Internet-Drafts directory.' % (filename, replaced_by_filename)
    create_tombstone(draft,text)
    
    # create document_comment if applicable
    # If the replacing document exists in IDInternal use pidtracker url in the comment
    # otherwise just use the filename.
    if IDInternal.objects.filter(draft=draft.id_document_tag):
        comment = 'Document replaced by <a href="https://datatracker.ietf.org/public/pidtracker.cgi?command=view&dTag=%s&rfc_flag=0">%s</a>' % (replaced_by_object.id_document_tag,replaced_by_filename)
    else:
        comment = 'Document replaced by %s' % (replaced_by_filename)
    
    # handle comment
    handle_comment(draft,comment)
    
    # Update draft record
    draft.revision = str(int(draft.revision)+1).zfill(2)
    draft.revision_date = datetime.date.today().isoformat()
    draft.status = IDStatus.objects.get(status_id=5)
    draft.replaced_by = replaced_by_object
    draft.expired_tombstone = 0
    draft.save()
    
    # save scheduled announcement
    announcement_from_form(session['email'])
    
    return
    
def do_resurrect(draft, session):
    '''
     Actions
    - if tombstone exists remove and decrement revision #
    - restore last archived version
    - revision_date = today
    - change ID status to Active
    - set expired_tombstone = 0
    - call handle_comment
    '''
    
    # if tombstone exists remove and decrement revision number
    tombstone = os.path.join(settings.INTERNET_DRAFT_DIR,draft.filename + '-' + draft.revision + '.txt')
    if os.path.exists(tombstone):
        os.remove(tombstone)
        draft.revision = str(int(draft.revision)-1).zfill(2)
    
    # restore latest revision documents file from archive
    files = glob.glob(os.path.join(settings.INTERNET_DRAFT_ARCHIVE_DIR,draft.filename) + '-??.*')
    sorted_files = sorted(files)
    latest,ext = os.path.splitext(sorted_files[-1])
    files = glob.glob(os.path.join(settings.INTERNET_DRAFT_ARCHIVE_DIR,latest) + '.*')
    for file in files:
        shutil.move(file,settings.INTERNET_DRAFT_DIR)
    
    # Update draft record
    draft.revision_date = datetime.date.today().isoformat()
    draft.status = IDStatus.objects.get(status_id=1)
    draft.expired_tombstone = 0
    draft.save()
    
    # handle document_comment
    handle_comment(draft,'This document has been resurrected.')
    
    # save scheduled announcement
    announcement_from_form(session['email'])
    
    return


def do_revision(draft, session):
    '''
    This function handles adding a new revision of an existing Internet-Draft.  
    Prerequisites: draft must be active
    Input: title, revision_date, txt_page_count, abstract, file input fields to upload new 
    draft document(s)
    Actions
    - move current doc(s) to archive directory
    - upload new docs to live dir
    - increment revision 
    - revision_date = today
    - reset extension_date
    - add id comment
    - handle sub-state
    - schedule notification
    '''
    
    # move old file(s) to archive
    # try this first in case there are errors, we abort before making any db changes
    try:
        archive_draft_files(draft.filename + '-' + draft.revision)
    except IOError, e:
        raise Exception('Error archiving draft files to %s<br>(%s)' % (settings.INTERNET_DRAFT_ARCHIVE_DIR, e.strerror))
    
    # save form data
    form = BaseRevisionModelForm(session['data'],instance=draft)
    if form.is_valid():
        new_draft = form.save()
    else:
        raise Exception('Problem with input data %s' % form.data)

    # save filetypes and revision
    new_draft.file_type = session['file_type']
    #new_draft.revision = os.path.splitext(session['filename'])[0][-2:]
    new_draft.revision = session['filename'][-2:]
    new_draft.extension_date = None
    new_draft.save()
    
    # create document_comment if applicable
    handle_comment(new_draft,'New version available')

    handle_substate(new_draft)
    
    # move uploaded files to production directory
    promote_files(new_draft)
    
    # save scheduled announcement
    # only do this if a IDInternal record exists
    if IDInternal.objects.filter(draft=draft.id_document_tag):
        announcement_from_form(session['email'])
    
    # clear session data
    session.clear()

    return

def do_update(draft,session):
    '''
     Actions
    - if tombstone exists remove it
    - increment revision #
    - revision_date = today
    - call handle_comment
    - do substate check and comment
    - status = Active
    '''
    
    # if tombstone exists remove
    tombstone = os.path.join(settings.INTERNET_DRAFT_DIR,draft.filename + '-' + draft.revision + '.txt')
    if os.path.exists(tombstone):
        os.remove(tombstone)
        
    # save form data
    form = BaseRevisionModelForm(session['data'],instance=draft)
    if form.is_valid():
        new_draft = form.save()
    else:
        raise Exception('Problem with input data %s' % form.data)
    
    # create document_comment if applicable
    handle_comment(new_draft,'New version available')

    handle_substate(new_draft)
    
    # update draft record
    new_draft.file_type = session['file_type']
    new_draft.revision = os.path.splitext(session['data']['filename'])[0][-2:]
    new_draft.revision_date = datetime.date.today().isoformat()
    new_draft.status = IDStatus.objects.get(status_id=1)
    new_draft.expired_tombstone = 0
    new_draft.save()
    
    # move uploaded files to production directory
    promote_files(new_draft)
    
    # save scheduled announcement
    announcement_from_form(session['email'])
    
    return
    
def do_withdraw(draft,session):
    '''
    Actions
    - create tombstone
    - increment revision #
    - revision_date = today
    - set draft status to withdrawn
    - no handled_comment (legacy apps do not apply comments for withdrawn)
    '''
    
    withdraw_type = session['data']['type']
    if withdraw_type == 'ietf':
        draft.status = IDStatus.objects.get(status_id=6)
        header = 'This Internet-Draft, %s, has been withdrawn by the IETF, and has been deleted from the Internet-Drafts directory.' % (draft.file())
    elif withdraw_type == 'author':
        draft.status = IDStatus.objects.get(status_id=4)
        header = 'This Internet-Draft, %s, has been withdrawn by the submitter, and has been deleted from the Internet-Drafts directory.' % (draft.file())
    
    # create tombstone
    create_tombstone(draft,header)
    
    # update draft record
    draft.revision = str(int(draft.revision)+1).zfill(2)
    draft.revision_date = datetime.date.today().isoformat()
    draft.save()
    
    # save scheduled announcement
    announcement_from_form(session['email'])
    
    return
    
# -------------------------------------------------
# Standard View Functions
# -------------------------------------------------
"""
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
"""
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
            
            # set defaults
            draft.intended_status = IDIntendedStatus.objects.get(intended_status_id=8)
            draft.revision_date = draft.start_date
            draft.status = IDStatus.objects.get(status_id=1)
            # draft.replaced_by = 0
            
            # process files
            filename,revision,file_type_list = process_files(request.FILES)

            draft.revision = revision
            draft.filename = get_base(filename)
            draft.file_type = ','.join(file_type_list)
            draft.save()
            
            # move uploaded files to production directory
            promote_files(draft)
    
            request.session['action'] = 'add'
            
            messages.success(request, 'New draft added successfully!')
            url = reverse('drafts_authors', kwargs={'id':draft.id_document_tag})
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
    draft = get_object_or_404(InternetDraft, id_document_tag=id)

    email_form = EmailForm(get_email_initial(draft,type='new'))
                            
    announcement_from_form(email_form.data,
                           to_val='i-d-announce@ietf.org',
                           from_val='Internet-Drafts@ietf.org',
                           content_type='Multipart/Mixed; Boundary="NextPart"')
            
    messages.success(request, 'Announcement scheduled successfully!')
    url = reverse('drafts_view', kwargs={'id':id})
    return HttpResponseRedirect(url)
    
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
    
def author_delete(request, id):
    idauthor = IDAuthor.objects.get(id=id)
    doc_id = idauthor.document.id_document_tag
    idauthor.delete()
    messages.success(request, 'The author was deleted successfully')
    url = reverse('drafts_authors', kwargs={'id':doc_id})
    return HttpResponseRedirect(url)

def authors(request, id):
    ''' 
    Edit Internet Draft Authors

    **Templates:**

    * ``drafts/authors.html``

    **Template Variables:**

    * form, draft, authors

    '''
    draft = get_object_or_404(InternetDraft, id_document_tag=id)
    authors = IDAuthor.objects.filter(document=draft)
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
                        person = get_person(name)
                        # when first adding a draft authors is an empty set, and the max would result in 
                        # a NoneType
                        if authors:
                            max_order = authors.aggregate(models.Max('author_order'))['author_order__max']
                        else: 
                            max_order = 0
                        obj = IDAuthor(document=draft,person=person,author_order=max_order + 1)
                        obj.save()

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
    draft = get_object_or_404(InternetDraft, id_document_tag=id)
    
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
        elif action == 'makerfc':
            func = do_makerfc

        func(draft,request.session)
        
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
    DatesFormset = modelformset_factory(IDDates, form=SubmissionDatesForm, extra=0)
    qset = IDDates.objects.all().order_by('id')
    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            #url = reverse('drafts_search')
            url = reverse('home')
            return HttpResponseRedirect(url)
            
        if button_text == 'Reset':
            formset = DatesFormset(queryset = qset)
            # get date of next meeting
            qs = Meeting.objects.filter(start_date__gte=datetime.datetime.now()).order_by('start_date')
            if qs:
                # the cutoff date calculations are hard coded becuase this data
                # is not in the db
                next_meeting = qs[0]
                formset.forms[0].initial={'date':next_meeting.start_date-datetime.timedelta(days=20)}
                formset.forms[1].initial={'date':next_meeting.start_date-datetime.timedelta(days=13)}
                formset.forms[2].initial={'date':next_meeting.start_date+datetime.timedelta(days=1)}
                formset.forms[3].initial={'date':next_meeting.start_date-datetime.timedelta(days=10)}
                formset.forms[4].initial={'date':next_meeting.start_date+datetime.timedelta(days=8)}
                formset.forms[5].initial={'date':next_meeting.start_date-datetime.timedelta(days=27)}
                messages.success(request, 'Dates changed to meeting %s default' % next_meeting)
            else:
                messages.error(request, 'Error No meeting found with start_date after today')
            
        else:
            formset = DatesFormset(request.POST)
            if formset.is_valid():
                formset.save()
                
                messages.success(request, 'Submission Dates modified successfully!')
                url = reverse('drafts_search')
                return HttpResponseRedirect(url)
    else:
        #form = SubmissionDatesForm()
        formset = DatesFormset(queryset = qset)
        
    return render_to_response('drafts/dates.html', {
        'qset': qset,
        'formset': formset},
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
    draft = get_object_or_404(InternetDraft, id_document_tag=id)
    
    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            url = reverse('drafts_view', kwargs={'id':id})
            return HttpResponseRedirect(url)
        
        form = EditModelForm(request.POST, request.FILES, instance=draft)
        if form.is_valid():
            form.save()
            messages.success(request, 'Draft modified successfully!')
            url = reverse('drafts_view', kwargs={'id':id})
            return HttpResponseRedirect(url)

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

    draft = get_object_or_404(InternetDraft, id_document_tag=id)
    
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
            #assert False, form.data
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
    draft = get_object_or_404(InternetDraft, id_document_tag=id)
    
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

    draft = get_object_or_404(InternetDraft, id_document_tag=id)
    
    # error out if draft intended status is empty
    draft_intended_status = draft.intended_status.intended_status_id
    if draft_intended_status == 8:
        messages.error(request, 'ERROR: intended status is set to None')
        url = reverse('drafts_view', kwargs={'id':id})
        return HttpResponseRedirect(url)
            
    ObsFormset = formset_factory(RfcObsoletesForm, extra=15, max_num=15)
    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            url = reverse('drafts_view', kwargs={'id':id})
            return HttpResponseRedirect(url)
       
        form = RfcForm(request.POST)
        obs_formset = ObsFormset(request.POST, prefix='obs')
        if form.is_valid() and obs_formset.is_valid():
            request.session['data'] = form.data
            request.session['action'] = 'makerfc'
            
            do_makerfc(draft,request.session)
            
            # save RFC Record
            rfc = form.save()
            
            # add rfc_authors records
            for author in draft.authors.all():
                a = RfcAuthor.objects.create(person=author.person,rfc=rfc)
                a.save()
                
            # handle rfc_obsoletes formset
            # NOTE: because we are just adding RFCs in this form we don't need to worry
            # about the previous state of the obs forms
            for obs_form in obs_formset.forms:
                if obs_form.has_changed():
                    rfc_acted_on = obs_form.cleaned_data.get('rfc','')
                    relation = obs_form.cleaned_data.get('relation','')
                    if rfc and relation:
                        # form validation ensures the rfc_acted_on exists, can safely use get
                        rfc_acted_on_obj = Rfc.objects.get(rfc_number=rfc_acted_on)
                        object = RfcObsolete(rfc=rfc,action=relation,rfc_acted_on=rfc_acted_on_obj)
                        object.save()
            
            messages.success(request, 'RFC created successfully!')
            url = reverse('drafts_view', kwargs={'id':id})
            return HttpResponseRedirect(url)
        else:
            # assert False, (form.errors, obs_formset.errors)
            pass      
    else:
        # SET FORM DEFAULTS
        initial = {}
        initial['title'] = draft.title
        initial['txt_page_count'] = draft.txt_page_count
        initial['rfc_published_date'] = datetime.date.today().isoformat()
        initial['group_acronym'] = draft.group.acronym
        initial['area_acronym'] = AreaGroup.objects.get(group=draft.group.acronym_id).area.area_acronym.acronym
        
        # initialize RFC Status to Draft Intended Status
        # unfortunatley the IDs are not the same so we need to perform a lookup
        try:
            rfc_status = RfcStatus.objects.get(status=draft.intended_status.intended_status)
            initial['status'] = rfc_status.status_id
        except RfcStatus.DoesNotExist:
            pass
        # set status date fields
        if rfc_status.status == 'Proposed Standard':
            initial['proposed_date'] = datetime.date.today().isoformat()
        if rfc_status.status == 'Draft Standard':
            initial['draft_date'] = datetime.date.today().isoformat()
        if rfc_status.status == 'Standard':
            initial['standard_date'] = datetime.date.today().isoformat()
        if rfc_status.status == 'Historic':
            initial['historic_date'] = datetime.date.today().isoformat()
            
        form = RfcForm(initial=initial)
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
    
    draft = get_object_or_404(InternetDraft, id_document_tag=id)
    
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

    draft = get_object_or_404(InternetDraft, id_document_tag=id)
    
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
            request.session['file_type'] = ','.join(file_type_list)
       
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
"""
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
            intended_status = form.cleaned_data['intended_status']
            document_name = form.cleaned_data['document_name']
            group_acronym = form.cleaned_data['group_acronym']
            filename = form.cleaned_data['filename']
            status = form.cleaned_data['status']
            revision_date_start = form.cleaned_data['revision_date_start'] 
            revision_date_end = form.cleaned_data['revision_date_end'] 
            # construct seach query
            if intended_status:
                kwargs['intended_std_level'] = intended_status
            if document_name:
                kwargs['title__istartswith'] = document_name
            if status:
                kwargs['states__type'] = 'draft'
                kwargs['states__slug'] = status
            if filename:
                kwargs['name__istartswith'] = filename
            if group_acronym:
                kwargs['group__acronym__istartswith'] = group_acronym
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
    else:
        # have status default to active
        form = SearchForm(initial={'status':'1'})

    return render_to_response('drafts/search.html', {
        'results': results,
        'form': form},
        RequestContext(request, {}),
    )
"""
def update(request, id):
    '''
    This view handles the Update action for an Internet-Draft
    Update is when an expired draft get a new revision, not the state does not change.
    Prerequisites: draft must be expired 
    Input: upload new files, pages, abstract, title
   
    '''
    
    draft = get_object_or_404(InternetDraft, id_document_tag=id)
    
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
            request.session['file_type'] = ','.join(file_type_list)
       
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
"""
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
    
    # add legacy fields
    draft.review_by_rfc_editor = bool(draft.tags.filter(slug='rfc-rev'))
    draft.revision_date = draft.latest_event(type='new_revision').time.date()
    draft.start_date = draft.docevent_set.filter(type='new_revision').order_by('time')[0].time.date()
    e = draft.latest_event(type__in=('expired_document', 'new_revision', "completed_resurrect"))
    draft.expired_date = e.time.date() if e and e.type == "expired_document" else None
    r = draft.docalias_set.filter(name__startswith='rfc')[0]
    draft.rfc_number = r.name[3:] if r else None
    
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
"""
def withdraw(request, id):
    '''
    This view handles withdrawing an Internet-Draft
    Prerequisites: draft must be active
    Input: by IETF or Author 
    '''
    
    draft = get_object_or_404(InternetDraft, id_document_tag=id)

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
"""