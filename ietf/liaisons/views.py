# Copyright The IETF Trust 2007, All Rights Reserved
import json
from email.utils import parseaddr

from django.contrib import messages
from django.core.urlresolvers import reverse as urlreverse
from django.core.validators import validate_email, ValidationError
from django.db.models import Q, Prefetch
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import render, render_to_response, get_object_or_404, redirect
from django.template import RequestContext

from ietf.doc.models import Document
from ietf.ietfauth.utils import role_required, has_role
from ietf.group.models import Group, Role
from ietf.liaisons.models import (LiaisonStatement,LiaisonStatementEvent,
    LiaisonStatementAttachment)
from ietf.liaisons.utils import (get_person_for_user, can_add_outgoing_liaison,
    can_add_incoming_liaison, can_edit_liaison,can_submit_liaison_required,
    can_add_liaison)
from ietf.liaisons.forms import liaison_form_factory, SearchLiaisonForm, EditAttachmentForm, AddCommentForm
from ietf.liaisons.mails import notify_pending_by_email, send_liaison_by_email
from ietf.liaisons.fields import select2_id_liaison_json
from ietf.name.models import LiaisonStatementTagName

EMAIL_ALIASES = {
    'IETFCHAIR':'The IETF Chair <chair@ietf.org>',
    'IESG':'The IESG <iesg@ietf.org>',
    'IAB':'The IAB <iab@iab.org>',
    'IABCHAIR':'The IAB Chair <iab-chair@iab.org>',
    'IABEXECUTIVEDIRECTOR':'The IAB Executive Director <execd@iab.org>'}

# -------------------------------------------------
# Helper Functions
# -------------------------------------------------
def _can_reply(liaison, user):
    '''Returns true if the user can send a reply to this liaison'''
    if user.is_authenticated():
        person = get_person_for_user(user)
        if has_role(user, "Secretariat"):
            return True
        if liaison.is_outgoing() and Role.objects.filter(group__in=liaison.to_groups.all(),person=person,name='auth'):
            return True
        if not liaison.is_outgoing() and Role.objects.filter(group__in=liaison.from_groups.all(),person=person,name='liaiman'):
            return True
    return False

def _can_take_care(liaison, user):
    '''Returns True if user can take care of awaiting actions associated with this liaison'''
    if not liaison.deadline or liaison.action_taken:
        return False

    if user.is_authenticated():
        if has_role(user, "Secretariat"):
            return True
        else:
            return _find_person_in_emails(liaison, get_person_for_user(user))
    return False

def _find_person_in_emails(liaison, person):
    '''Returns true if person corresponds with any of the email addresses associated
    with this liaison statement'''
    if not person:
        return False

    emails = ','.join(e for e in [liaison.response_contacts, liaison.cc_contacts,
                                  liaison.to_contacts,liaison.technical_contacts] if e)
    for email in emails.split(','):
        name, addr = parseaddr(email)
        try:
            validate_email(addr)
        except ValidationError:
            continue

        if person.email_set.filter(address=addr):
            return True
        elif addr in ('chair@ietf.org', 'iesg@ietf.org') and has_role(person.user, "IETF Chair"):
            return True
        elif addr in ('iab@iab.org', 'iab-chair@iab.org') and has_role(person.user, "IAB Chair"):
            return True
        elif addr in ('execd@iab.org', ) and has_role(person.user, "IAB Executive Director"):
            return True

    return False

def contacts_from_roles(roles):
    '''Returns contact string for given roles'''
    emails = [ u'{} <{}>'.format(r.person.plain_name(),r.email.address) for r in roles ]
    return ','.join(emails)

def get_cc(group):
    '''Returns list of emails to use as CC for group.  Simplified refactor of IETFHierarchy
    get_cc() and get_from_cc()
    '''
    emails = []

    # role based CCs
    if group.acronym in ('ietf','iesg'):
        emails.append(EMAIL_ALIASES['IESG'])
        emails.append(EMAIL_ALIASES['IETFCHAIR'])
    elif group.acronym in ('iab'):
        emails.append(EMAIL_ALIASES['IAB'])
        emails.append(EMAIL_ALIASES['IABCHAIR'])
        emails.append(EMAIL_ALIASES['IABEXECUTIVEDIRECTOR'])
    elif group.type_id == 'area':
        emails.append(EMAIL_ALIASES['IETFCHAIR'])
        ad_roles = group.role_set.filter(name='ad')
        emails.extend([ u'{} <{}>'.format(r.person.plain_name(),r.email.address) for r in ad_roles ])
    elif group.type_id == 'wg':
        ad_roles = group.parent.role_set.filter(name='ad')
        emails.extend([ u'{} <{}>'.format(r.person.plain_name(),r.email.address) for r in ad_roles ])
        chair_roles = group.role_set.filter(name='chair')
        emails.extend([ u'{} <{}>'.format(r.person.plain_name(),r.email.address) for r in chair_roles ])
        if group.list_email:
            emails.append(u'{} Discussion List <{}>'.format(group.name,group.list_email))
    elif group.type_id == 'sdo':
        liaiman_roles = group.role_set.filter(name='liaiman')
        emails.extend([ u'{} <{}>'.format(r.person.plain_name(),r.email.address) for r in liaiman_roles ])

    # explicit CCs
    if group.liaisonstatementgroupcontacts_set.exists() and group.liaisonstatementgroupcontacts_set.first().cc_contacts:
        emails = emails + group.liaisonstatementgroupcontacts_set.first().cc_contacts.split(',')

    return emails

def get_contacts_for_group(group):
    '''Returns default contacts for groups as a comma separated string'''
    contacts = []

    # use explicit default contacts if defined
    if group.liaisonstatementgroupcontacts_set.first():
        contacts.append(group.liaisonstatementgroupcontacts_set.first().contacts)

    # otherwise construct based on group type
    elif group.type_id == 'area':
        roles = group.role_set.filter(name='ad')
        contacts.append(contacts_from_roles(roles))
    elif group.type_id == 'wg':
        roles = group.role_set.filter(name='chair')
        contacts.append(contacts_from_roles(roles))
    elif group.acronym == 'ietf':
        contacts.append(EMAIL_ALIASES['IETFCHAIR'])
    elif group.acronym == 'iab':
        contacts.append(EMAIL_ALIASES['IABCHAIR'])
        contacts.append(EMAIL_ALIASES['IABEXECUTIVEDIRECTOR'])
    elif group.acronym == 'iesg':
        contacts.append(EMAIL_ALIASES['IESG'])

    return ','.join(contacts)

def get_details_tabs(stmt, selected):
    return [
        t + (t[0].lower() == selected.lower(),)
        for t in [
        ('Statement', urlreverse('ietf.liaisons.views.liaison_detail', kwargs={ 'object_id': stmt.pk })),
        ('History', urlreverse('ietf.liaisons.views.liaison_history', kwargs={ 'object_id': stmt.pk }))
    ]]

def needs_approval(group,person):
    '''Returns True if the person does not have authority to send a Liaison Statement
    from group.  For outgoing Liaison Statements only'''
    user = person.user
    if group.acronym in ('ietf','iesg') and has_role(user, 'IETF Chair'):
        return False
    if group.acronym == 'iab' and (has_role(user,'IAB Chair') or has_role(user,'IAB Executive Director')):
        return False
    if group.type_id == 'area' and group.role_set.filter(name='ad',person=person):
        return False
    if group.type_id == 'wg' and group.parent and group.parent.role_set.filter(name='ad',person=person):
        return False
    return True

def normalize_sort(request):
    sort = request.GET.get('sort', "")
    if sort not in ('date', 'deadline', 'title', 'to_groups', 'from_groups'):
        sort = "date"

    # reverse dates
    order_by = "-" + sort if sort in ("date", "deadline") else sort

    return sort, order_by

def post_only(group,person):
    '''Returns true if the user is restricted to post_only (vs. post_and_send) for this
    group.  This is for incoming liaison statements.
    - Secretariat have full access.
    - Authorized Individuals have full access for the group they are associated with
    - Liaison Managers can post only
    '''
    if group.type_id == 'sdo' and ( not(has_role(person.user,"Secretariat") or group.role_set.filter(name='auth',person=person)) ):
        return True
    else:
        return False

# -------------------------------------------------
# Ajax Functions
# -------------------------------------------------
@can_submit_liaison_required
def ajax_get_liaison_info(request):
    '''Returns dictionary of info to update entry form given the groups
    that have been selected
    '''
    person = get_person_for_user(request.user)

    from_groups = request.GET.getlist('from_groups', None)
    if not any(from_groups):
        from_groups = []
    to_groups = request.GET.getlist('to_groups', None)
    if not any(to_groups):
        to_groups = []
    from_groups = [ Group.objects.get(id=id) for id in from_groups ]
    to_groups = [ Group.objects.get(id=id) for id in to_groups ]

    cc = []
    does_need_approval = []
    can_post_only = []
    to_contacts = []
    response_contacts = []
    result = {'response_contacts':[],'to_contacts': [], 'cc': [], 'needs_approval': False, 'post_only': False, 'full_list': []}

    for group in from_groups:
        cc.extend(get_cc(group))
        does_need_approval.append(needs_approval(group,person))
        can_post_only.append(post_only(group,person))
        response_contacts.append(get_contacts_for_group(group))

    for group in to_groups:
        cc.extend(get_cc(group))
        to_contacts.append(get_contacts_for_group(group))

    # if there are from_groups and any need approval
    if does_need_approval:
        if  any(does_need_approval):
            does_need_approval = True
        else:
            does_need_approval = False
    else:
        does_need_approval = True

    result.update({'error': False,
                   'cc': list(set(cc)),
                   'response_contacts':list(set(response_contacts)),
                   'to_contacts': list(set(to_contacts)),
                   'needs_approval': does_need_approval,
                   'post_only': any(can_post_only)})

    json_result = json.dumps(result)
    return HttpResponse(json_result, content_type='text/javascript')

def ajax_select2_search_liaison_statements(request):
    query = [w.strip() for w in request.GET.get('q', '').split() if w.strip()]

    if not query:
        objs = LiaisonStatement.objects.none()
    else:
        qs = LiaisonStatement.objects.filter(state='posted')

        for term in query:
            if term.isdigit():
                q = Q(title__icontains=term)|Q(pk=term)
            else:
                q = Q(title__icontains=term)
            qs = qs.filter(q)

        objs = qs.distinct().order_by("-id")[:20]

    return HttpResponse(select2_id_liaison_json(objs), content_type='application/json')


# -------------------------------------------------
# Redirects for backwards compatibility
# -------------------------------------------------

def redirect_add(request):
    """Redirects old add urls"""
    if 'incoming' in request.GET.keys():
        return redirect('ietf.liaisons.views.liaison_add', type='incoming')
    else:
        return redirect('ietf.liaisons.views.liaison_add', type='outgoing')

def redirect_for_approval(request, object_id=None):
    """Redirects old approval urls"""
    if object_id:
        return redirect('ietf.liaisons.views.liaison_detail', object_id=object_id)
    else:
        return redirect('ietf.liaisons.views.liaison_list', state='pending')

# -------------------------------------------------
# View Functions
# -------------------------------------------------
@role_required('Secretariat',)
def add_comment(request, object_id):
    """Add comment to history"""
    statement = get_object_or_404(LiaisonStatement, id=object_id)
    login = request.user.person

    if request.method == 'POST':
        form = AddCommentForm(request.POST)
        if form.is_valid():
            if form.cleaned_data.get('private'):
                type_id = 'private_comment'
            else:
                type_id = 'comment'
                
            LiaisonStatementEvent.objects.create(
                by=login,
                type_id=type_id,
                statement=statement,
                desc=form.cleaned_data['comment']
            )
            messages.success(request, 'Comment added.')
            return redirect("ietf.liaisons.views.liaison_history", object_id=statement.id)
    else:
        form = AddCommentForm()
  
    return render(request, 'liaisons/add_comment.html',dict(liaison=statement,form=form))

@can_submit_liaison_required
def liaison_add(request, type=None, **kwargs):
    if type == 'incoming' and not can_add_incoming_liaison(request.user):
        return HttpResponseForbidden("Restricted to users who are authorized to submit incoming liaison statements")
    if type == 'outgoing' and not can_add_outgoing_liaison(request.user):
        return HttpResponseForbidden("Restricted to users who are authorized to submit outgoing liaison statements")

    if request.method == 'POST':
        form = liaison_form_factory(request, data=request.POST.copy(),
                                    files=request.FILES, type=type, **kwargs)

        if form.is_valid():
            liaison = form.save()

            # notifications
            if 'save' in request.POST:
                # the result of an edit, no notifications necessary
                messages.success(request, 'The statement has been updated')
            elif 'send' in request.POST and liaison.state.slug == 'posted':
                send_liaison_by_email(request, liaison)
                messages.success(request, 'The statement has been sent and posted')
            elif liaison.state.slug == 'pending':
                notify_pending_by_email(request, liaison)
                messages.success(request, 'The statement has been submitted and is awaiting approval')

            return redirect('ietf.liaisons.views.liaison_detail', object_id=liaison.pk)

    else:
        form = liaison_form_factory(request,type=type,**kwargs)

    return render_to_response(
        'liaisons/edit.html',
        {'form': form,
         'liaison': kwargs.get('instance')},
        context_instance=RequestContext(request),
    )

def liaison_history(request, object_id):
    """Show the history for a specific liaison statement"""
    liaison = get_object_or_404(LiaisonStatement, id=object_id)
    events = liaison.liaisonstatementevent_set.all().order_by("-time", "-id").select_related("by")
    if not has_role(request.user, "Secretariat"):
        events = events.exclude(type='private_comment')

    return render(request, "liaisons/detail_history.html",  {
        'events':events,
        'liaison': liaison,
        'tabs': get_details_tabs(liaison, 'History'),
        'selected_tab_entry':'history'
    })

def liaison_delete_attachment(request, object_id, attach_id):
    liaison = get_object_or_404(LiaisonStatement, pk=object_id)
    attach = get_object_or_404(LiaisonStatementAttachment, pk=attach_id)
    if not ( request.user.is_authenticated() and can_edit_liaison(request.user, liaison) ):
        return HttpResponseForbidden("You are not authorized for this action")

    attach.removed = True
    attach.save()

    # create event
    LiaisonStatementEvent.objects.create(
        type_id='modified',
        by=get_person_for_user(request.user),
        statement=liaison,
        desc='Attachment Removed: {}'.format(attach.document.title)
    )
    messages.success(request, 'Attachment Deleted')
    return redirect('ietf.liaisons.views.liaison_detail', object_id=liaison.pk)

def liaison_detail(request, object_id):
    liaison = get_object_or_404(LiaisonStatement, pk=object_id)
    can_edit = request.user.is_authenticated() and can_edit_liaison(request.user, liaison)
    can_take_care = _can_take_care(liaison, request.user)
    can_reply = _can_reply(liaison, request.user)
    person = get_person_for_user(request.user)


    if request.method == 'POST':
        if request.POST.get('approved'):
            liaison.change_state(state_id='approved',person=person)
            liaison.change_state(state_id='posted',person=person)
            send_liaison_by_email(request, liaison)
            messages.success(request,'Liaison Statement Approved and Posted')
        elif request.POST.get('dead'):
            liaison.change_state(state_id='dead',person=person)
            messages.success(request,'Liaison Statement Killed')
        elif request.POST.get('resurrect'):
            liaison.change_state(state_id='pending',person=person)
            messages.success(request,'Liaison Statement Resurrected')
        elif request.POST.get('do_action_taken') and can_take_care:
            liaison.tags.remove('required')
            liaison.tags.add('taken')
            can_take_care = False
            messages.success(request,'Action handled')

    relations_by = [i.target for i in liaison.source_of_set.filter(target__state__slug='posted')]
    relations_to = [i.source for i in liaison.target_of_set.filter(source__state__slug='posted')]

    return render_to_response("liaisons/detail.html", {
        "liaison": liaison,
        'tabs': get_details_tabs(liaison, 'Statement'),
        "can_edit": can_edit,
        "can_take_care": can_take_care,
        "can_reply": can_reply,
        "relations_to": relations_to,
        "relations_by": relations_by,
    }, context_instance=RequestContext(request))

def liaison_edit(request, object_id):
    liaison = get_object_or_404(LiaisonStatement, pk=object_id)
    if not (request.user.is_authenticated() and can_edit_liaison(request.user, liaison)):
        return HttpResponseForbidden('You do not have permission to edit this liaison statement')
    return liaison_add(request, instance=liaison)

def liaison_edit_attachment(request, object_id, doc_id):
    '''Edit the Liaison Statement attachment title'''
    liaison = get_object_or_404(LiaisonStatement, pk=object_id)
    doc = get_object_or_404(Document, pk=doc_id)
    if not ( request.user.is_authenticated() and can_edit_liaison(request.user, liaison) ):
        return HttpResponseForbidden("You are not authorized for this action")

    if request.method == 'POST':
        form = EditAttachmentForm(request.POST)
        if form.is_valid():
            title = form.cleaned_data.get('title')
            doc.title = title
            doc.save()

            # create event
            LiaisonStatementEvent.objects.create(
                type_id='modified',
                by=get_person_for_user(request.user),
                statement=liaison,
                desc='Attachment Title changed to {}'.format(title)
            )
            messages.success(request,'Attachment title changed')
            return redirect('ietf.liaisons.views.liaison_detail', object_id=liaison.pk)

    else:
        form = EditAttachmentForm(initial={'title':doc.title})

    return render_to_response(
        'liaisons/edit_attachment.html',
        {'form': form,
         'liaison': liaison},
        context_instance=RequestContext(request),
    )

def liaison_list(request, state='posted'):
    """A generic list view with tabs for different states: posted, pending, dead"""
    # use prefetch to speed up main liaison page load
    selected_menu_entry = state
    liaisons = LiaisonStatement.objects.filter(state=state).prefetch_related(
        Prefetch('from_groups',queryset=Group.objects.order_by('acronym').select_related('type'),to_attr='prefetched_from_groups'),
        Prefetch('to_groups',queryset=Group.objects.order_by('acronym').select_related('type'),to_attr='prefetched_to_groups'),
        Prefetch('tags',queryset=LiaisonStatementTagName.objects.filter(slug='taken'),to_attr='prefetched_tags'),
        Prefetch('liaisonstatementevent_set',queryset=LiaisonStatementEvent.objects.filter(type='posted'),to_attr='prefetched_posted_events')
        )
    
    # check authorization for pending and dead tabs
    if state in ('pending','dead') and not can_add_liaison(request.user):
        msg = "Restricted to participants who are authorized to submit liaison statements on behalf of the various IETF entities"
        return HttpResponseForbidden(msg)

    if 'tags' in request.GET:
        value = request.GET.get('tags')
        liaisons = liaisons.filter(tags__slug=value)
        selected_menu_entry = 'action needed'

    # perform search / filter
    if 'text' in request.GET:
        form = SearchLiaisonForm(data=request.GET,queryset=liaisons)
        search_conducted = True
        if form.is_valid():
            results = form.get_results()
            liaisons = results
    else:
        form = SearchLiaisonForm(queryset=liaisons)
        search_conducted = False

    # perform sort
    sort, order_by = normalize_sort(request)
    if sort == 'date':
        liaisons = sorted(liaisons, key=lambda a: a.sort_date, reverse=True)

    if sort == 'from_groups':
        liaisons = sorted(liaisons, key=lambda a: a.sort_date, reverse=True)
        liaisons = sorted(liaisons, key=lambda a: a.from_groups_display.lower())
    if sort == 'to_groups':
        liaisons = sorted(liaisons, key=lambda a: a.sort_date, reverse=True)
        liaisons = sorted(liaisons, key=lambda a: a.to_groups_display.lower())
    if sort == 'deadline':
        liaisons = liaisons.order_by('-deadline')
    if sort == 'title':
        liaisons = liaisons.order_by('title')

    # add menu entries
    entries = []
    entries.append(("Posted", urlreverse("ietf.liaisons.views.liaison_list", kwargs={'state':'posted'})))
    if can_add_liaison(request.user):
        entries.append(("Action Needed", urlreverse("ietf.liaisons.views.liaison_list", kwargs={'state':'posted'}) + '?tags=required'))
        entries.append(("Pending", urlreverse("ietf.liaisons.views.liaison_list", kwargs={'state':'pending'})))
        entries.append(("Dead", urlreverse("ietf.liaisons.views.liaison_list", kwargs={'state':'dead'})))

    # add menu actions
    actions = []
    if can_add_incoming_liaison(request.user):
        actions.append(("New incoming liaison", urlreverse("ietf.liaisons.views.liaison_add", kwargs={'type':'incoming'})))
    if can_add_outgoing_liaison(request.user):
        actions.append(("New outgoing liaison", urlreverse("ietf.liaisons.views.liaison_add", kwargs={'type':'outgoing'})))

    return render(request, 'liaisons/liaison_base.html',  {
        'liaisons':liaisons,
        'selected_menu_entry':selected_menu_entry,
        'menu_entries':entries,
        'menu_actions':actions,
        'sort':sort,
        'form':form,
        'with_search':True,
        'search_conducted':search_conducted,
        'state':state,
    })

def liaison_reply(request,object_id):
    '''Returns a new liaison form with initial data to reply to the given liaison'''
    liaison = get_object_or_404(LiaisonStatement, pk=object_id)
    if liaison.is_outgoing():
        reply_type = 'incoming'
    else:
        reply_type = 'outgoing'
    initial = dict(
        to_groups=[ x.pk for x in liaison.from_groups.all() ],
        from_groups=[ x.pk for x in liaison.to_groups.all() ],
        to_contacts=liaison.response_contacts,
        related_to=str(liaison.pk))

    return liaison_add(request,type=reply_type,initial=initial)

@role_required('Secretariat',)
def liaison_resend(request, object_id):
    '''Resend the liaison statement notification email'''
    liaison = get_object_or_404(LiaisonStatement, pk=object_id)
    person = get_person_for_user(request.user)
    send_liaison_by_email(request,liaison)
    LiaisonStatementEvent.objects.create(type_id='resent',by=person,statement=liaison,desc='Statement Resent')
    messages.success(request,'Liaison Statement resent')
    return redirect('ietf.liaisons.views.liaison_list')

