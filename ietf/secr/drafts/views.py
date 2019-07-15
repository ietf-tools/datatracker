# Copyright The IETF Trust 2013-2019, All Rights Reserved
# -*- coding: utf-8 -*-


from __future__ import absolute_import, print_function, unicode_literals

import datetime
import glob
import io
import os
import shutil
from dateutil.parser import parse
from collections import OrderedDict

from django.conf import settings
from django.contrib import messages
from django.db.models import Max
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils.http import urlencode

from ietf.doc.models import Document, DocumentAuthor, State
from ietf.doc.models import DocEvent, NewRevisionDocEvent
from ietf.doc.utils import add_state_change_event
from ietf.ietfauth.utils import role_required
from ietf.meeting.helpers import get_meeting
from ietf.secr.drafts.email import announcement_from_form, get_email_initial
from ietf.secr.drafts.forms import AuthorForm, EditModelForm, EmailForm, ExtendForm, SearchForm, WithdrawForm
from ietf.secr.utils.document import get_rfc_num, get_start_date
from ietf.submit.models import Preapproval
from ietf.utils.log import log

# -------------------------------------------------
# Helper Functions
# -------------------------------------------------

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
    destination = io.open(os.path.join(settings.IDSUBMIT_MANUAL_STAGING_DIR, f.name), 'wb+')
    for chunk in f.chunks():
        destination.write(chunk)
    destination.close()

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
    log("Resurrecting %s.  Moving files:" % draft.name)
    for file in files:
        try:
            shutil.move(file, settings.INTERNET_DRAFT_PATH)
            log("  Moved file %s to %s" % (file, settings.INTERNET_DRAFT_PATH))
        except shutil.Error as e:
            log("  Exception %s when attempting to move %s" % (e, file))

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
                order = list(authors.aggregate(Max('order')).values())[0] + 1
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

        if action == 'resurrect':
            func = do_resurrect
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
    except Exception as e:
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
    qs = Document.objects.filter(relateddocument__target__docs=draft, relateddocument__relationship='replaces')
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
            params = OrderedDict([('action', 'withdraw')])
            params['withdraw_type'] = form.cleaned_data['withdraw_type']
            url = reverse('ietf.secr.drafts.views.email', kwargs={'id':id})
            url = url + '?' + urlencode(params)
            return redirect(url)

    else:
        form = WithdrawForm()

    return render(request, 'drafts/withdraw.html', {
        'draft': draft,
        'form': form},
    )
    
