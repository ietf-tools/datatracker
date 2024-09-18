# Copyright The IETF Trust 2007-2023, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime
import itertools

from django.conf import settings
from django.contrib import messages
from django.db.models import Q
from django.forms.models import inlineformset_factory, model_to_dict
from django.forms.formsets import formset_factory
from django.http import HttpResponse, Http404, HttpResponseRedirect, HttpResponseBadRequest
from django.shortcuts import render, get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import reverse as urlreverse
from django.utils.html import escape

import debug                            # pyflakes:ignore

from ietf.doc.models import Document
from ietf.group.models import Role, Group
from ietf.ietfauth.utils import role_required, has_role
from ietf.ipr.mail import (message_from_message, get_reply_to, get_update_submitter_emails)
from ietf.ipr.fields import select2_id_ipr_title_json
from ietf.ipr.forms import (HolderIprDisclosureForm, GenericDisclosureForm,
    ThirdPartyIprDisclosureForm, DraftForm, SearchForm, MessageModelForm,
    AddCommentForm, AddEmailForm, NotifyForm, StateForm, NonDocSpecificIprDisclosureForm,
    GenericIprDisclosureForm)
from ietf.ipr.models import (IprDisclosureStateName, IprDisclosureBase,
    HolderIprDisclosure, GenericIprDisclosure, ThirdPartyIprDisclosure,
    NonDocSpecificIprDisclosure, IprDocRel,
    RelatedIpr,IprEvent)
from ietf.ipr.utils import (get_genitive, get_ipr_summary,
    iprs_from_docs, related_docs)
from ietf.mailtrigger.utils import gather_address_lists
from ietf.message.models import Message
from ietf.message.utils import infer_message
from ietf.name.models import IprLicenseTypeName
from ietf.person.models import Person
from ietf.utils import log
from ietf.utils.draft_search import normalize_draftname
from ietf.utils.mail import send_mail, send_mail_message
from ietf.utils.response import permission_denied
from ietf.utils.text import text_to_dict
from ietf.utils.timezone import datetime_from_date, datetime_today, DEADLINE_TZINFO

# ----------------------------------------------------------------
# Globals
# ----------------------------------------------------------------
# maps string type or ipr model class to corresponding edit form
ipr_form_mapping = { 'specific':HolderIprDisclosureForm,
                     'generic':GenericDisclosureForm,
                     'third-party':ThirdPartyIprDisclosureForm,
                     'HolderIprDisclosure':HolderIprDisclosureForm,
                     'GenericIprDisclosure':GenericIprDisclosureForm,
                     'ThirdPartyIprDisclosure':ThirdPartyIprDisclosureForm,
                     'NonDocSpecificIprDisclosure':NonDocSpecificIprDisclosureForm }

class_to_type = { 'HolderIprDisclosure':'specific',
                  'GenericIprDisclosure':'generic',
                  'ThirdPartyIprDisclosure':'third-party',
                  'NonDocSpecificIprDisclosure':'generic' }
# ----------------------------------------------------------------
# Helper Functions
# ----------------------------------------------------------------
def get_document_emails(ipr):
    """Returns a list of messages to inform document authors that a new IPR disclosure
    has been posted"""
    messages = []
    for rel in ipr.iprdocrel_set.all():
        doc = rel.document

        if doc.type_id=="draft":
            doc_info = 'Internet-Draft entitled "{}" ({})'.format(doc.title,doc.name)
        elif doc.type_id=="rfc":
            doc_info = 'RFC entitled "{}" (RFC{})'.format(doc.title, doc.rfc_number)
        else:
            log.unreachable("2023-08-15")
            return ""

        addrs = gather_address_lists('ipr_posted_on_doc',doc=doc).as_strings(compact=False)

        author_names = ', '.join(a.person.name for a in doc.documentauthor_set.select_related("person"))
    
        context = dict(
            settings=settings,
            doc_info=doc_info,
            to_email=addrs.to,
            to_name=author_names,
            cc_email=addrs.cc,
            ipr=ipr)
        text = render_to_string('ipr/posted_document_email.txt',context)
        messages.append(text)
    
    return messages

def get_posted_emails(ipr):
    """Return a list of messages suitable to initialize a NotifyFormset for
    the notify view when a new disclosure is posted"""
    messages = []

    addrs = gather_address_lists('ipr_posting_confirmation',ipr=ipr).as_strings(compact=False)
    context = dict(
        settings=settings,
        to_email=addrs.to,
        to_name=ipr.submitter_name,
        cc_email=addrs.cc,
        ipr=ipr)
    text = render_to_string('ipr/posted_submitter_email.txt',context)
    messages.append(text)
    
    # add email to related document authors / parties
    if ipr.iprdocrel_set.all():
        messages.extend(get_document_emails(ipr))
    
    # if Generic disclosure add message for General Area AD
    if isinstance(ipr, (GenericIprDisclosure,NonDocSpecificIprDisclosure)):
        role = Role.objects.filter(group__acronym='gen',name='ad').first()
        context = dict(
            settings=settings,
            to_email=role.email.address,
            to_name=role.person.name,
            ipr=ipr)
        text = render_to_string('ipr/posted_generic_email.txt',context)
        messages.append(text)
        
    return messages

def set_disclosure_title(disclosure):
    """Set the title of the disclosure"""

    if isinstance(disclosure, HolderIprDisclosure):
        ipr_summary = get_ipr_summary(disclosure)
        title = get_genitive(disclosure.holder_legal_name) + ' Statement about IPR related to {}'.format(ipr_summary)
    elif isinstance(disclosure, (GenericIprDisclosure,NonDocSpecificIprDisclosure)):
        title = get_genitive(disclosure.holder_legal_name) + ' General License Statement'
    elif isinstance(disclosure, ThirdPartyIprDisclosure):
        ipr_summary = get_ipr_summary(disclosure)
        title = get_genitive(disclosure.ietfer_name) + ' Statement about IPR related to {} belonging to {}'.format(ipr_summary,disclosure.holder_legal_name)
    
    # truncate for db
    if len(title) > 255:
        title = title[:252] + "..."
    disclosure.title = title

def ipr_rfc_number(disclosureDate, thirdPartyDisclosureFlag):
    """Return the RFC as a string that was in force when the disclosure was made."""

    # This works because the oldest IPR disclosure in the database was
    # made on 1993-07-23, which is more than a year after RFC 1310.

    # RFC publication date comes from the RFC Editor announcement
    ipr_rfc_pub_datetime = {
        1310 : datetime.datetime(1992,  3, 13,  0,  0, tzinfo=datetime.timezone.utc),
        1802 : datetime.datetime(1994,  3, 23,  0,  0, tzinfo=datetime.timezone.utc),
        2026 : datetime.datetime(1996, 10, 29,  0,  0, tzinfo=datetime.timezone.utc),
        3668 : datetime.datetime(2004,  2, 18,  0,  0, tzinfo=datetime.timezone.utc),
        3979 : datetime.datetime(2005,  3,  2,  2, 23, tzinfo=datetime.timezone.utc),
        4879 : datetime.datetime(2007,  4, 10, 18, 21, tzinfo=datetime.timezone.utc),
        8179 : datetime.datetime(2017,  5, 31, 23,  1, tzinfo=datetime.timezone.utc),
    }

    if disclosureDate < ipr_rfc_pub_datetime[1310]:
        rfcnum = "Error!"
    elif disclosureDate < ipr_rfc_pub_datetime[1802]:
        rfcnum = "RFC 1310"
    elif disclosureDate < ipr_rfc_pub_datetime[2026]:
        rfcnum = "RFC 1802"
    elif disclosureDate < ipr_rfc_pub_datetime[3668]:
        rfcnum = "RFC 2026"
    elif disclosureDate < ipr_rfc_pub_datetime[3979]:
        rfcnum = "RFC 3668"
    elif disclosureDate < ipr_rfc_pub_datetime[8179]:
        rfcnum = "RFC 3979"
    else:
        rfcnum = "RFC 8179"

    if (thirdPartyDisclosureFlag) and (rfcnum == "RFC 3979") and \
       (disclosureDate > ipr_rfc_pub_datetime[4879]):
        rfcnum = rfcnum + " as updated by RFC 4879"

    return rfcnum
# ----------------------------------------------------------------
# Ajax Views
# ----------------------------------------------------------------
def ajax_search(request):
    q = [w.strip() for w in request.GET.get('q', '').split() if w.strip()]

    if not q:
        objs = IprDisclosureBase.objects.none()
    else:
        query = Q()  # all objects returned if no other terms in the queryset
        for t in q:
            query &= Q(title__icontains=t)

        objs = IprDisclosureBase.objects.filter(query)

    objs = objs.distinct()[:10]
    
    return HttpResponse(select2_id_ipr_title_json(objs), content_type='application/json')

# ----------------------------------------------------------------
# Views
# ----------------------------------------------------------------
def about(request):
    return render(request, "ipr/disclosure.html", {})

@role_required('Secretariat',)
def add_comment(request, id):
    """Add comment to disclosure history"""
    ipr = get_object_or_404(IprDisclosureBase, id=id)
    login = request.user.person

    if request.method == 'POST':
        form = AddCommentForm(request.POST)
        if form.is_valid():
            if form.cleaned_data.get('private'):
                type_id = 'private_comment'
            else:
                type_id = 'comment'
                
            IprEvent.objects.create(
                by=login,
                type_id=type_id,
                disclosure=ipr,
                desc=form.cleaned_data['comment']
            )
            messages.success(request, 'Comment added.')
            return redirect("ietf.ipr.views.history", id=ipr.id)
    else:
        form = AddCommentForm()
  
    return render(request, 'ipr/add_comment.html',dict(ipr=ipr,form=form))

@role_required('Secretariat',)
def add_email(request, id):
    """Add email to disclosure history"""
    ipr = get_object_or_404(IprDisclosureBase, id=id)
    
    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            return redirect("ietf.ipr.views.history", id=ipr.id)
        
        form = AddEmailForm(request.POST,ipr=ipr)
        if form.is_valid():
            message = form.cleaned_data['message']
            in_reply_to = form.cleaned_data['in_reply_to']
            # create Message
            msg = message_from_message(message,request.user.person)
            
            # create IprEvent
            if form.cleaned_data['direction'] == 'incoming':
                type_id = 'msgin'
            else:
                type_id = 'msgout'
            IprEvent.objects.create(
                type_id = type_id,
                by = request.user.person,
                disclosure = ipr,
                message = msg,
                in_reply_to = in_reply_to
            )
            messages.success(request, 'Email added.')
            return redirect("ietf.ipr.views.history", id=ipr.id)
    else:
        form = AddEmailForm(ipr=ipr)
        
    return render(request, 'ipr/add_email.html',dict(ipr=ipr,form=form))
        
@role_required('Secretariat',)
def admin(request, state):
    """Administrative disclosure listing.  For non-posted disclosures"""
    states = IprDisclosureStateName.objects.filter(slug__in=[state, "rejected", "removed_objfalse"] if state == "removed" else [state])
    if not states:
        raise Http404

    iprs = IprDisclosureBase.objects.filter(state__in=states).order_by('-time')

    tabs = [
        t + (t[0].lower() == state.lower(),)
        for t in [
            ('Pending', urlreverse('ietf.ipr.views.admin', kwargs={'state':'pending'})),
            ('Removed', urlreverse('ietf.ipr.views.admin', kwargs={'state':'removed'})),
            ('Parked', urlreverse('ietf.ipr.views.admin', kwargs={'state':'parked'})),
        ]]

    return render(request, 'ipr/admin_list.html',  {
        'iprs': iprs,
        'tabs': tabs,
        'states': states,
        'administrative_list': state,
    })

@role_required('Secretariat',)
def edit(request, id, updates=None):
    """Secretariat only edit disclosure view"""
    ipr = get_object_or_404(IprDisclosureBase, id=id).get_child()
    type = class_to_type[ipr.__class__.__name__]
    
    DraftFormset = inlineformset_factory(IprDisclosureBase, IprDocRel, form=DraftForm, can_delete=True, extra=0)

    if request.method == 'POST':
        form = ipr_form_mapping[ipr.__class__.__name__](request.POST,instance=ipr)
        if type != 'generic':
            draft_formset = DraftFormset(request.POST, instance=ipr)
        else:
            draft_formset = None

        if request.user.is_anonymous:
            person = Person.objects.get(name="(System)")
        else:
            person = request.user.person
            
        # check formset validity
        if type != 'generic':
            valid_formsets = draft_formset.is_valid()
        else:
            valid_formsets = True

        if form.is_valid() and valid_formsets:
            updates = form.cleaned_data.get('updates')
            disclosure = form.save(commit=False)
            disclosure.save()

            if type != 'generic':
                draft_formset = DraftFormset(request.POST, instance=disclosure)
                draft_formset.clean()
                draft_formset.save()

            set_disclosure_title(disclosure)
            disclosure.save()
            
            # clear and recreate IPR relationships
            RelatedIpr.objects.filter(source=ipr).delete()
            if updates:
                for target in updates:
                    RelatedIpr.objects.create(source=disclosure,target=target,relationship_id='updates')
                
            # create IprEvent
            IprEvent.objects.create(
                type_id='changed_disclosure',
                by=person,
                disclosure=disclosure,
                desc="Changed disclosure metadata")
            
            messages.success(request,'Disclosure modified')
            return redirect("ietf.ipr.views.show", id=ipr.id)

    else:
        initial = model_to_dict(ipr)
        patent_info = text_to_dict(initial.get('patent_info', ''))
        if list(patent_info.keys()):
            patent_dict = dict([ ('patent_'+k.lower(), v) for k,v in list(patent_info.items()) ])
        else:
            patent_dict = {'patent_notes': initial.get('patent_info', '')}
        initial.update(patent_dict)
        if ipr.updates:
            initial.update({'updates':[ x.target for x in ipr.updates ]})
            form = ipr_form_mapping[ipr.__class__.__name__](instance=ipr, initial=initial)
        else:
            form = ipr_form_mapping[ipr.__class__.__name__](instance=ipr, initial=initial)
        #disclosure = IprDisclosureBase()    # dummy disclosure for inlineformset
        draft_formset = DraftFormset(instance=ipr, queryset=IprDocRel.objects.all())

    return render(request, "ipr/details_edit.html",  {
        'form': form,
        'draft_formset':draft_formset,
        'type':type
    })

@role_required('Secretariat',)
def email(request, id):
    """Send an email regarding this disclosure"""
    ipr = get_object_or_404(IprDisclosureBase, id=id).get_child()
    
    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            return redirect("ietf.ipr.views.show", id=ipr.id)
            
        form = MessageModelForm(request.POST)
        if form.is_valid():
            # create Message
            msg = Message.objects.create(
                by = request.user.person,
                subject = form.cleaned_data['subject'],
                frm = form.cleaned_data['frm'],
                to = form.cleaned_data['to'],
                cc = form.cleaned_data['cc'],
                bcc = form.cleaned_data['bcc'],
                reply_to = form.cleaned_data['reply_to'],
                body = form.cleaned_data['body']
            )

            # create IprEvent
            IprEvent.objects.create(
                type_id = 'msgout',
                by = request.user.person,
                disclosure = ipr,
                response_due = datetime_from_date(form.cleaned_data['response_due'], DEADLINE_TZINFO),
                message = msg,
            )

            # send email
            send_mail_message(None,msg)

            messages.success(request, 'Email sent.')
            return redirect('ietf.ipr.views.show', id=ipr.id)
    
    else:
        reply_to = get_reply_to()
        addrs = gather_address_lists('ipr_disclosure_followup',ipr=ipr).as_strings(compact=False)
        initial = { 
            'to': addrs.to,
            'cc': addrs.cc,
            'frm': settings.IPR_EMAIL_FROM,
            'subject': 'Regarding {}'.format(ipr.title),
            'reply_to': reply_to,
        }
        form = MessageModelForm(initial=initial)
    
    return render(request, "ipr/email.html",  {
        'ipr': ipr,
        'form':form
    })
    
def history(request, id):
    """Show the history for a specific IPR disclosure"""
    ipr = get_object_or_404(IprDisclosureBase, id=id).get_child()

    if not has_role(request.user, 'Secretariat'):
        if ipr.state.slug != 'posted':
            raise Http404

    events = ipr.iprevent_set.all().order_by("-time", "-id").select_related("by")
    if not has_role(request.user, "Secretariat"):
        events = events.exclude(type='private_comment')
        
    return render(request, "ipr/details_history.html",  {
        'events':events,
        'ipr': ipr,
        'tabs': get_details_tabs(ipr, 'History'),
        'selected_tab_entry':'history'
    })

def by_draft_txt(request):
    docipr = {}

    for o in IprDocRel.objects.filter(disclosure__state='posted').select_related('document'):
        name = o.document.name
        if name.startswith("rfc"):
            name = name.upper()

        if not name in docipr:
            docipr[name] = []

        docipr[name].append(o.disclosure_id)

    lines = [ "# Machine-readable list of IPR disclosures by draft name" ]
    for name, iprs in docipr.items():
        lines.append(name + "\t" + "\t".join(str(ipr_id) for ipr_id in sorted(iprs)))

    return HttpResponse("\n".join(lines), content_type="text/plain; charset=%s"%settings.DEFAULT_CHARSET)

def by_draft_recursive_txt(request):
    """Returns machine-readable list of IPR disclosures by draft name, recursive.
    NOTE: this view is expensive and should be removed _after_ tools.ietf.org is retired,
    including util function and management commands that generate the content for
    this view."""

    with open('/a/ietfdata/derived/ipr_draft_recursive.txt') as f:
        content = f.read()
    return HttpResponse(content, content_type="text/plain; charset=%s"%settings.DEFAULT_CHARSET)


def new(request, _type, updates=None):
    """Submit a new IPR Disclosure.  If the updates field != None, this disclosure
    updates one or more other disclosures."""
    # Note that URL patterns won't ever send updates - updates is only non-null when called from code

    # This odd construct flipping generic and general allows the URLs to say 'general' while having a minimal impact on the code.
    # A cleanup to change the code to switch on type 'general' should follow.
    if (
        _type == "generic" and updates
    ):  # Only happens when called directly from the updates view
        pass
    elif _type == "generic":
        return HttpResponseRedirect(
            urlreverse("ietf.ipr.views.new", kwargs=dict(_type="general"))
        )
    elif _type == "general":
        _type = "generic"
    else:
        pass

    # 1 to show initially + the template
    DraftFormset = inlineformset_factory(
        IprDisclosureBase, IprDocRel, form=DraftForm, can_delete=False, extra=1 + 1
    )

    if request.method == "POST":
        form = ipr_form_mapping[_type](request.POST)
        if _type != "generic":
            draft_formset = DraftFormset(request.POST, instance=IprDisclosureBase())
        else:
            draft_formset = None

        if request.user.is_anonymous:
            person = Person.objects.get(name="(System)")
        else:
            person = request.user.person

        # check formset validity
        if _type != "generic":
            valid_formsets = draft_formset.is_valid()
        else:
            valid_formsets = True

        if form.is_valid() and valid_formsets:
            if "updates" in form.cleaned_data:
                updates = form.cleaned_data["updates"]
                del form.cleaned_data["updates"]
            disclosure = form.save(commit=False)
            disclosure.by = person
            disclosure.state = IprDisclosureStateName.objects.get(slug="pending")
            disclosure.save()

            if _type != "generic":
                draft_formset = DraftFormset(request.POST, instance=disclosure)
                draft_formset.save()

            set_disclosure_title(disclosure)
            disclosure.save()

            if updates:
                for ipr in updates:
                    RelatedIpr.objects.create(
                        source=disclosure, target=ipr, relationship_id="updates"
                    )

            # create IprEvent
            IprEvent.objects.create(
                type_id="submitted",
                by=person,
                disclosure=disclosure,
                desc="Disclosure Submitted",
            )

            # send email notification
            (to, cc) = gather_address_lists("ipr_disclosure_submitted")
            send_mail(
                request,
                to,
                ("IPR Submitter App", "ietf-ipr@ietf.org"),
                "New IPR Submission Notification",
                "ipr/new_update_email.txt",
                {
                    "ipr": disclosure,
                },
                cc=cc,
            )

            return render(request, "ipr/submitted.html")

    else:
        if updates:
            original = IprDisclosureBase(id=updates).get_child()
            initial = model_to_dict(original)
            initial.update(
                {
                    "updates": str(updates),
                }
            )
            patent_info = text_to_dict(initial.get("patent_info", ""))
            if list(patent_info.keys()):
                patent_dict = dict(
                    [("patent_" + k.lower(), v) for k, v in list(patent_info.items())]
                )
            else:
                patent_dict = {"patent_notes": initial.get("patent_info", "")}
            initial.update(patent_dict)
            form = ipr_form_mapping[_type](initial=initial)
        else:
            form = ipr_form_mapping[_type]()
        disclosure = IprDisclosureBase()  # dummy disclosure for inlineformset
        draft_formset = DraftFormset(instance=disclosure)

    return render(
        request,
        "ipr/details_edit.html",
        {
            "form": form,
            "draft_formset": draft_formset,
            "type": _type,
        },
    )


@role_required('Secretariat',)
def notify(request, id, type):
    """Send email notifications.
    type = update: send notice to old ipr submitter(s)
    type = posted: send notice to submitter, etc. that new IPR was posted
    """
    ipr = get_object_or_404(IprDisclosureBase, id=id).get_child()
    NotifyFormset = formset_factory(NotifyForm,extra=0)
    
    if request.method == 'POST':
        formset = NotifyFormset(request.POST)
        if formset.is_valid():
            for form in formset.forms:
                message = infer_message(form.cleaned_data['text'])
                message.by = request.user.person
                message.save()
                send_mail_message(None,message)
                IprEvent.objects.create(
                    type_id = form.cleaned_data['type'],
                    by = request.user.person,
                    disclosure = ipr,
                    response_due = datetime_today(DEADLINE_TZINFO) + datetime.timedelta(days=30),
                    message = message,
                )
            messages.success(request,'Notifications sent')
            return redirect("ietf.ipr.views.show", id=ipr.id)
            
    else:
        if type == 'update':
            initial = [ {'type':'update_notify','text':escape(m)} for m in get_update_submitter_emails(ipr) ]
        else:
            initial = [ {'type':'msgout','text':escape(m)} for m in get_posted_emails(ipr) ]
        formset = NotifyFormset(initial=initial)
        
    return render(request, "ipr/notify.html", {
        'formset': formset,
        'ipr': ipr,
    })

@role_required('Secretariat',)
def post(request, id):
    """Post the disclosure and redirect to notification view"""
    ipr = get_object_or_404(IprDisclosureBase, id=id).get_child()
    person = request.user.person
    
    ipr.state = IprDisclosureStateName.objects.get(slug='posted')
    ipr.save()
    
    # create event
    IprEvent.objects.create(
        type_id='posted',
        by=person,
        disclosure=ipr,
        desc="Disclosure Posted")
    
    messages.success(request, 'Disclosure Posted')
    return redirect('ietf.ipr.views.notify', id=ipr.id, type='posted')
    
def search(request):
    search_type = request.GET.get("submit")
    if search_type and "\x00" in search_type:
        return HttpResponseBadRequest("Null characters are not allowed")

    # query field
    q = ''
    # legacy support
    if not search_type and request.GET.get("option", None) == "document_search":
        docname = request.GET.get("document_search", "")
        if docname and "\x00" in docname:
            return HttpResponseBadRequest("Null characters are not allowed")
        if docname.startswith("draft-"):
            search_type = "draft"
            q = docname
        if docname.startswith("rfc"):
            search_type = "rfc"
            q = docname
    if search_type:
        form = SearchForm(request.GET)
        docid = request.GET.get("id") or request.GET.get("id_document_tag") or ""
        if docid and "\x00" in docid:
            return HttpResponseBadRequest("Null characters are not allowed")
        docs = doc = None
        iprs = []
        related_iprs = []

        # set states
        states = request.GET.getlist('state',settings.PUBLISH_IPR_STATES)
        if any("\x00" in state for state in states if state):
            return HttpResponseBadRequest("Null characters are not allowed")
        if states == ['all']:
            states = IprDisclosureStateName.objects.values_list('slug',flat=True)
        
        # get query field
        if request.GET.get(search_type):
            q = request.GET.get(search_type)
            if q and "\x00" in q:
                return HttpResponseBadRequest("Null characters are not allowed")

        if q or docid:
            # Search by RFC number or draft-identifier
            # Document list with IPRs
            if search_type in ["draft", "rfc"]:
                doc = q

                if docid:
                    start = Document.objects.filter(name__iexact=docid)
                else:
                    if search_type == "draft":
                        q = normalize_draftname(q)
                        start = Document.objects.filter(name__icontains=q, name__startswith="draft")
                    elif search_type == "rfc":
                        start = Document.objects.filter(name="rfc%s" % q.lstrip("0"))
                
                # one match
                if len(start) == 1:
                    first = start[0]
                    doc = first
                    docs = set([first])
                    docs.update(
                        related_docs(
                            first, relationship=("replaces", "obs"), reverse_relationship=()
                        )
                    )
                    docs.update(
                        set(
                            [
                                draft
                                for drafts in [
                                    related_docs(
                                        d, relationship=(), reverse_relationship=("became_rfc",)
                                    )
                                    for d in docs
                                ]
                                for draft in drafts
                            ]
                        )
                    )
                    docs.discard(None)
                    docs = sorted(
                        docs,
                        key=lambda d: (
                            d.rfc_number if d.rfc_number is not None else 0,
                            d.became_rfc().rfc_number if d.became_rfc() else 0,
                        ),
                        reverse=True,
                    )
                    iprs = iprs_from_docs(docs, states=states)
                    template = "ipr/search_doc_result.html"
                    updated_docs = related_docs(first, ("updates",))
                    related_iprs = list(
                        set(iprs_from_docs(updated_docs, states=states)) - set(iprs)
                    )
                # multiple matches, select just one
                elif start:
                    docs = start
                    template = "ipr/search_doc_list.html"
                # no match
                else:
                    template = "ipr/search_doc_result.html"

            # Search by legal name
            # IPR list with documents
            elif search_type == "holder":
                iprs = IprDisclosureBase.objects.filter(holder_legal_name__icontains=q, state_id__in=states)
                template = "ipr/search_holder_result.html"
                
            # Search by patents field or content of emails for patent numbers
            # IPR list with documents
            elif search_type == "patent":
                iprs = IprDisclosureBase.objects.filter(state_id__in=states)
                iprs = iprs.filter(Q(holderiprdisclosure__patent_info__icontains=q) |
                                   Q(thirdpartyiprdisclosure__patent_info__icontains=q) |
                                   Q(nondocspecificiprdisclosure__patent_info__icontains=q))
                template = "ipr/search_patent_result.html"

            # Search by wg acronym
            # Document list with IPRs
            elif search_type == "group":
                docs = list(Document.objects.filter(group=q))
                related = []
                for doc in docs:
                    doc.product_of_this_wg = True
                    related += related_docs(doc)
                iprs = iprs_from_docs(list(set(docs+related)),states=states)
                docs = [ doc for doc in docs if doc.ipr() ]
                docs = sorted(docs, key=lambda x: max([ipr.disclosure.time for ipr in x.ipr()]), reverse=True)
                template = "ipr/search_wg_result.html"
                q = Group.objects.get(id=q).acronym     # make acronym for use in template

            # Search by rfc and id title
            # Document list with IPRs
            elif search_type == "doctitle":
                docs = list(Document.objects.filter(title__icontains=q))
                related = []
                for doc in docs:
                    related += related_docs(doc)
                iprs = iprs_from_docs(list(set(docs+related)),states=states)
                docs = [ doc for doc in docs if doc.ipr() ]
                docs = sorted(docs, key=lambda x: max([ipr.disclosure.time for ipr in x.ipr()]), reverse=True)
                template = "ipr/search_doctitle_result.html"

            # Search by title of IPR disclosure
            # IPR list with documents
            elif search_type == "iprtitle":
                iprs = IprDisclosureBase.objects.filter(title__icontains=q, state_id__in=states)
                template = "ipr/search_iprtitle_result.html"

            else:
                raise Http404("Unexpected search type in IPR query: %s" % search_type)
                
            # sort and render response
            # convert list of IprDocRel to iprs
            if iprs and isinstance(iprs[0],IprDocRel):
                iprs = [ x.disclosure for x in iprs ]
            # don't remove updated, per Robert
            # iprs = [ ipr for ipr in iprs if not ipr.updated_by.all() ]
            if has_role(request.user, "Secretariat"):
                iprs = sorted(iprs, key=lambda x: (x.time, x.id), reverse=True)
                iprs = sorted(iprs, key=lambda x: x.state.order)
            else:
                iprs = sorted(iprs, key=lambda x: (x.time, x.id), reverse=True)

            return render(request, template, {
                "q": q,
                "iprs":     iprs,
                "docs":     docs,
                "doc":      doc,
                "form":     form,
                "states":   states,
                "related_iprs":  related_iprs,
            })

        return HttpResponseRedirect(request.path)

    else:
        form = SearchForm(initial={'state':['all']})
        return render(request, "ipr/search.html", {"form":form })

def get_details_tabs(ipr, selected):
    return [
        t + (t[0].lower() == selected.lower(),)
        for t in [
        ('Disclosure', urlreverse('ietf.ipr.views.show', kwargs={ 'id': ipr.pk })),
        ('History', urlreverse('ietf.ipr.views.history', kwargs={ 'id': ipr.pk }))
    ]]

def show(request, id):
    """View of individual declaration"""
    ipr = get_object_or_404(IprDisclosureBase, id=id).get_child()
    if not has_role(request.user, 'Secretariat'):
        if ipr.state.slug in ['removed', 'removed_objfalse']:
            return render(request, "ipr/removed.html", {
                'ipr': ipr
            })
        elif ipr.state.slug != 'posted':
            permission_denied(request, "Restricted to role: Secretariat.")

    updates_iprs = ipr.relatedipr_source_set.all().order_by('source__time')
    prev_rel = updates_iprs.last()
    prev = prev_rel.target.get_child() if prev_rel else None

    return render(request, "ipr/details_view.html",  {
        'ipr': ipr,
        'prev': prev,
        'in_force_ipr_rfc': ipr_rfc_number(ipr.time, ipr.is_thirdparty),
        'tabs': get_details_tabs(ipr, 'Disclosure'),
        'choices_abc': [ i.desc for i in IprLicenseTypeName.objects.filter(slug__in=['no-license', 'royalty-free', 'reasonable', ]) ],
        'updates_iprs': updates_iprs,
        'updated_by_iprs': ipr.relatedipr_target_set.filter(source__state="posted").order_by('target__time')
    })

def showlist(request):
    """List all disclosures by type, posted only"""
    generic = GenericIprDisclosure.objects.filter(state__in=settings.PUBLISH_IPR_STATES).prefetch_related('relatedipr_source_set__target','relatedipr_target_set__source').order_by('-time')
    specific = HolderIprDisclosure.objects.filter(state__in=settings.PUBLISH_IPR_STATES).prefetch_related('relatedipr_source_set__target','relatedipr_target_set__source').order_by('-time')
    thirdpty = ThirdPartyIprDisclosure.objects.filter(state__in=settings.PUBLISH_IPR_STATES).prefetch_related('relatedipr_source_set__target','relatedipr_target_set__source').order_by('-time')
    nondocspecific = NonDocSpecificIprDisclosure.objects.filter(state__in=settings.PUBLISH_IPR_STATES).prefetch_related('relatedipr_source_set__target','relatedipr_target_set__source').order_by('-time')
    
    # combine nondocspecific with generic and re-sort
    generic = itertools.chain(generic,nondocspecific)
    generic = sorted(generic, key=lambda x: x.time,reverse=True)
    
    return render(request, "ipr/list.html", {
            'generic_disclosures' : generic,
            'specific_disclosures': specific,
            'thirdpty_disclosures': thirdpty,
    })

@role_required('Secretariat',)
def state(request, id):
    """Change the state of the disclosure"""
    ipr = get_object_or_404(IprDisclosureBase, id=id)
    login = request.user.person

    if request.method == 'POST':
        form = StateForm(request.POST)
        if form.is_valid():
            ipr.state = form.cleaned_data.get('state')
            ipr.save()
            IprEvent.objects.create(
                by=login,
                type_id=ipr.state.pk,
                disclosure=ipr,
                desc="State Changed to %s" % ipr.state.name
            )
            if form.cleaned_data.get('comment'):
                if form.cleaned_data.get('private'):
                    type_id = 'private_comment'
                else:
                    type_id = 'comment'
                
                IprEvent.objects.create(
                    by=login,
                    type_id=type_id,
                    disclosure=ipr,
                    desc=form.cleaned_data['comment']
                )
            messages.success(request, 'State Changed')
            return redirect("ietf.ipr.views.show", id=ipr.id)
    else:
        form = StateForm(initial={'state':ipr.state.pk,'private':True})
  
    return render(request, 'ipr/state.html', dict(ipr=ipr, form=form))

# use for link to update specific IPR
def update(request, id):
    """Calls the 'new' view with updates parameter = ipd.id"""
    # determine disclosure type
    ipr = get_object_or_404(IprDisclosureBase,id=id)
    child = ipr.get_child()
    type = class_to_type[child.__class__.__name__]
    return new(request, type, updates=id)
