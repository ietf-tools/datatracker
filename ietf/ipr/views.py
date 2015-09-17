# Copyright The IETF Trust 2007, All Rights Reserved

import datetime
import itertools

from django.conf import settings
from django.contrib import messages
from django.core.urlresolvers import reverse as urlreverse
from django.db.models import Q
from django.forms.models import inlineformset_factory
from django.forms.formsets import formset_factory
from django.http import HttpResponse, Http404, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404, redirect
from django.template.loader import render_to_string

from ietf.doc.models import DocAlias
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
from ietf.message.models import Message
from ietf.message.utils import infer_message
from ietf.person.models import Person
from ietf.secr.utils.document import get_rfc_num, is_draft
from ietf.utils.draft_search import normalize_draftname
from ietf.utils.mail import send_mail, send_mail_message
from ietf.mailtrigger.utils import gather_address_lists

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
        doc = rel.document.document
        authors = doc.authors.all()
        
        if is_draft(doc):
            doc_info = 'Internet-Draft entitled "{}" ({})'.format(doc.title,doc.name)
        else:
            doc_info = 'RFC entitled "{}" (RFC{})'.format(doc.title,get_rfc_num(doc))
            
        # build cc list
        if doc.group.acronym == 'none':
            if doc.ad and is_draft(doc):
                cc_list = doc.ad.role_email('ad').address
            else:
                role = Role.objects.filter(group__acronym='gen',name='ad')[0]
                cc_list = role.email.address

        else:
            cc_list = get_wg_email_list(doc.group)

        (to_list,cc_list) = gather_address_lists('ipr_posted_on_doc',doc=doc)
        author_names = ', '.join([a.person.name for a in authors])
    
        context = dict(
            doc_info=doc_info,
            to_email=to_list,
            to_name=author_names,
            cc_email=cc_list,
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
            to_email=role.email.address,
            to_name=role.person.name,
            ipr=ipr)
        text = render_to_string('ipr/posted_generic_email.txt',context)
        messages.append(text)
        
    return messages

def get_wg_email_list(group):
    """Returns a string of comman separated email addresses for the Area Directors and WG Chairs
    """
    result = []
    roles = itertools.chain(Role.objects.filter(group=group.parent,name='ad'),
                            Role.objects.filter(group=group,name='chair'))
    for role in roles:
        result.append(role.email.address)

    if group.list_email:
        result.append(group.list_email)

    return ', '.join(result)

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

# ----------------------------------------------------------------
# Ajax Views
# ----------------------------------------------------------------
def ajax_search(request):
    q = [w.strip() for w in request.GET.get('q', '').split() if w.strip()]

    if not q:
        objs = IprDisclosureBase.objects.none()
    else:
        query = Q()
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
            return redirect("ipr_history", id=ipr.id)
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
            return redirect("ipr_history", id=ipr.id)
        
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
            return redirect("ipr_history", id=ipr.id)
    else:
        form = AddEmailForm(ipr=ipr)
        
    return render(request, 'ipr/add_email.html',dict(ipr=ipr,form=form))
        
@role_required('Secretariat',)
def admin(request, state):
    """Administrative disclosure listing.  For non-posted disclosures"""
    states = IprDisclosureStateName.objects.filter(slug__in=[state, "rejected"] if state == "removed" else [state])
    if not states:
        raise Http404

    iprs = IprDisclosureBase.objects.filter(state__in=states).order_by('-time')

    tabs = [
        t + (t[0].lower() == state.lower(),)
        for t in [
            ('Pending', urlreverse('ipr_admin', kwargs={'state':'pending'})),
            ('Removed', urlreverse('ipr_admin', kwargs={'state':'removed'})),
            ('Parked', urlreverse('ipr_admin', kwargs={'state':'parked'})),
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
    
    DraftFormset = inlineformset_factory(IprDisclosureBase, IprDocRel, form=DraftForm, can_delete=True, extra=1)

    if request.method == 'POST':
        form = ipr_form_mapping[ipr.__class__.__name__](request.POST,instance=ipr)
        if type != 'generic':
            draft_formset = DraftFormset(request.POST, instance=ipr)
        else:
            draft_formset = None

        if request.user.is_anonymous():
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
            return redirect("ipr_show", id=ipr.id)

    else:
        if ipr.updates:
            form = ipr_form_mapping[ipr.__class__.__name__](instance=ipr,initial={'updates':[ x.target for x in ipr.updates ]})
        else:
            form = ipr_form_mapping[ipr.__class__.__name__](instance=ipr)
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
            return redirect("ipr_show", id=ipr.id)
            
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
                response_due = form.cleaned_data['response_due'],
                message = msg,
            )

            # send email
            send_mail_message(None,msg)

            messages.success(request, 'Email sent.')
            return redirect('ipr_show', id=ipr.id)
    
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
    events = ipr.iprevent_set.all().order_by("-time", "-id").select_related("by")
    if not has_role(request.user, "Secretariat"):
        events = events.exclude(type='private_comment')
        
    return render(request, "ipr/details_history.html",  {
        'events':events,
        'ipr': ipr,
        'tabs': get_details_tabs(ipr, 'History'),
        'selected_tab_entry':'history'
    })

def iprs_for_drafts_txt(request):
    docipr = {}

    for o in IprDocRel.objects.filter(disclosure__state='posted').select_related('document'):
        name = o.document.name
        if name.startswith("rfc"):
            name = name.upper()

        if not name in docipr:
            docipr[name] = []

        docipr[name].append(o.disclosure_id)

    lines = [ u"# Machine-readable list of IPR disclosures by draft name" ]
    for name, iprs in docipr.iteritems():
        lines.append(name + "\t" + "\t".join(unicode(ipr_id) for ipr_id in sorted(iprs)))

    return HttpResponse("\n".join(lines), content_type="text/plain; charset=%s"%settings.DEFAULT_CHARSET)

def new(request, type, updates=None):
    """Submit a new IPR Disclosure.  If the updates field != None, this disclosure
    updates one or more other disclosures."""

    # 1 to show initially + the template
    DraftFormset = inlineformset_factory(IprDisclosureBase, IprDocRel, form=DraftForm, can_delete=False, extra=1 + 1)

    if request.method == 'POST':
        form = ipr_form_mapping[type](request.POST)
        if type != 'generic':
            draft_formset = DraftFormset(request.POST, instance=IprDisclosureBase())
        else:
            draft_formset = None

        if request.user.is_anonymous():
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
            disclosure.by = person
            disclosure.state = IprDisclosureStateName.objects.get(slug='pending')
            disclosure.save()
            
            if type != 'generic':
                draft_formset = DraftFormset(request.POST, instance=disclosure)
                draft_formset.save()

            set_disclosure_title(disclosure)
            disclosure.save()
            
            if updates:
                for ipr in updates:
                    RelatedIpr.objects.create(source=disclosure,target=ipr,relationship_id='updates')
                
            # create IprEvent
            IprEvent.objects.create(
                type_id='submitted',
                by=person,
                disclosure=disclosure,
                desc="Disclosure Submitted")

            # send email notification
            (to, cc) = gather_address_lists('ipr_disclosure_submitted')
            send_mail(request, to, ('IPR Submitter App', 'ietf-ipr@ietf.org'),
                'New IPR Submission Notification',
                "ipr/new_update_email.txt",
                {"ipr": disclosure,},
                cc=cc)
            
            return render(request, "ipr/submitted.html")

    else:
        if updates:
            form = ipr_form_mapping[type](initial={'updates':str(updates)})
        else:
            form = ipr_form_mapping[type]()
        disclosure = IprDisclosureBase()    # dummy disclosure for inlineformset
        draft_formset = DraftFormset(instance=disclosure)

    return render(request, "ipr/details_edit.html",  {
        'form': form,
        'draft_formset':draft_formset,
        'type':type,
    })

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
                    response_due = datetime.datetime.now().date() + datetime.timedelta(days=30),
                    message = message,
                )
            messages.success(request,'Notifications sent')
            return redirect("ipr_show", id=ipr.id)
            
    else:
        if type == 'update':
            initial = [ {'type':'update_notify','text':m} for m in get_update_submitter_emails(ipr) ]
        else:
            initial = [ {'type':'msgout','text':m} for m in get_posted_emails(ipr) ]
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
    return redirect("ipr_notify", id=ipr.id, type='posted')
    
def search(request):
    search_type = request.GET.get("submit")
    if search_type:
        form = SearchForm(request.GET)
        docid = request.GET.get("id") or request.GET.get("id_document_tag") or ""
        docs = doc = None
        iprs = []
        
        # set states
        states = request.GET.getlist('state',('posted','removed'))
        if states == ['all']:
            states = IprDisclosureStateName.objects.values_list('slug',flat=True)
        
        # get query field
        q = ''
        if request.GET.get(search_type):
            q = request.GET.get(search_type)

        if q or docid:
            # Search by RFC number or draft-identifier
            # Document list with IPRs
            if search_type in ["draft", "rfc"]:
                doc = q

                if docid:
                    start = DocAlias.objects.filter(name=docid)
                else:
                    if search_type == "draft":
                        q = normalize_draftname(q)
                        start = DocAlias.objects.filter(name__contains=q, name__startswith="draft")
                    elif search_type == "rfc":
                        start = DocAlias.objects.filter(name="rfc%s" % q.lstrip("0"))
                
                # one match
                if len(start) == 1:
                    first = start[0]
                    doc = str(first)
                    docs = related_docs(first)
                    iprs = iprs_from_docs(docs,states=states)
                    template = "ipr/search_doc_result.html"
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
                docs = list(DocAlias.objects.filter(document__group=q))
                related = []
                for doc in docs:
                    doc.product_of_this_wg = True
                    related += related_docs(doc)
                iprs = iprs_from_docs(list(set(docs+related)),states=states)
                docs = [ doc for doc in docs if doc.document.ipr() ]
                docs = sorted(docs, key=lambda x: max([ipr.disclosure.time for ipr in x.document.ipr()]), reverse=True)
                template = "ipr/search_wg_result.html"
                q = Group.objects.get(id=q).acronym     # make acronym for use in template

            # Search by rfc and id title
            # Document list with IPRs
            elif search_type == "doctitle":
                docs = list(DocAlias.objects.filter(document__title__icontains=q))
                related = []
                for doc in docs:
                    related += related_docs(doc)
                iprs = iprs_from_docs(list(set(docs+related)),states=states)
                docs = [ doc for doc in docs if doc.document.ipr() ]
                docs = sorted(docs, key=lambda x: max([ipr.disclosure.time for ipr in x.document.ipr()]), reverse=True)
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
                "iprs": iprs,
                "docs": docs,
                "doc": doc,
                "form":form,
                "states":states
            })

        return HttpResponseRedirect(request.path)

    else:
        form = SearchForm(initial={'state':['all']})
        return render(request, "ipr/search.html", {"form":form })

def get_details_tabs(ipr, selected):
    return [
        t + (t[0].lower() == selected.lower(),)
        for t in [
        ('Disclosure', urlreverse('ipr_show', kwargs={ 'id': ipr.pk })),
        ('History', urlreverse('ipr_history', kwargs={ 'id': ipr.pk }))
    ]]

def show(request, id):
    """View of individual declaration"""
    ipr = get_object_or_404(IprDisclosureBase, id=id).get_child()
    if not has_role(request.user, 'Secretariat'):
        if ipr.state.slug == 'removed':
            return render(request, "ipr/removed.html", {
                'ipr': ipr
            })
        elif ipr.state.slug != 'posted':
            raise Http404

    return render(request, "ipr/details_view.html",  {
        'ipr': ipr,
        'tabs': get_details_tabs(ipr, 'Disclosure'),
        'updates_iprs': ipr.relatedipr_source_set.all(),
        'updated_by_iprs': ipr.relatedipr_target_set.filter(source__state="posted")
    })

def showlist(request):
    """List all disclosures by type, posted only"""
    generic = GenericIprDisclosure.objects.filter(state__in=('posted','removed')).prefetch_related('relatedipr_source_set__target','relatedipr_target_set__source').order_by('-time')
    specific = HolderIprDisclosure.objects.filter(state__in=('posted','removed')).prefetch_related('relatedipr_source_set__target','relatedipr_target_set__source').order_by('-time')
    thirdpty = ThirdPartyIprDisclosure.objects.filter(state__in=('posted','removed')).prefetch_related('relatedipr_source_set__target','relatedipr_target_set__source').order_by('-time')
    nondocspecific = NonDocSpecificIprDisclosure.objects.filter(state__in=('posted','removed')).prefetch_related('relatedipr_source_set__target','relatedipr_target_set__source').order_by('-time')
    
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
            return redirect("ipr_show", id=ipr.id)
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
