# Copyright The IETF Trust 2007, All Rights Reserved
import datetime
import json
from email.utils import parseaddr

from django.core.validators import validate_email, ValidationError
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import render_to_response, get_object_or_404, redirect
from django.template import RequestContext

from ietf.liaisons.models import LiaisonStatement
from ietf.liaisons.accounts import (get_person_for_user, can_add_outgoing_liaison,
                                    can_add_incoming_liaison, 
                                    is_ietfchair, is_iabchair, is_iab_executive_director,
                                    can_edit_liaison, is_secretariat)
from ietf.liaisons.forms import liaison_form_factory
from ietf.liaisons.utils import IETFHM, can_submit_liaison_required, approvable_liaison_statements
from ietf.liaisons.mails import notify_pending_by_email, send_liaison_by_email
from ietf.liaisons.fields import select2_id_liaison_json



@can_submit_liaison_required
def add_liaison(request, liaison=None):
    if request.method == 'POST':
        form = liaison_form_factory(request, data=request.POST.copy(),
                                    files = request.FILES, liaison=liaison)
        if form.is_valid():
            liaison = form.save()
            if request.POST.get('send', False):
                if not liaison.approved:
                    notify_pending_by_email(request, liaison)
                else:
                    send_liaison_by_email(request, liaison)
            return redirect('liaison_list')
    else:
        form = liaison_form_factory(request, liaison=liaison)

    return render_to_response(
        'liaisons/edit.html',
        {'form': form,
         'liaison': liaison},
        context_instance=RequestContext(request),
    )


@can_submit_liaison_required
def ajax_get_liaison_info(request):
    person = get_person_for_user(request.user)

    to_entity_id = request.GET.get('to_entity_id', None)
    from_entity_id = request.GET.get('from_entity_id', None)

    result = {'poc': [], 'cc': [], 'needs_approval': False, 'post_only': False, 'full_list': []}

    to_error = 'Invalid TO entity id'
    if to_entity_id:
        to_entity = IETFHM.get_entity_by_key(to_entity_id)
        if to_entity:
            to_error = ''

    from_error = 'Invalid FROM entity id'
    if from_entity_id:
        from_entity = IETFHM.get_entity_by_key(from_entity_id)
        if from_entity:
            from_error = ''

    if to_error or from_error:
        result.update({'error': '\n'.join([to_error, from_error])})
    else:
        result.update({'error': False,
                       'cc': ([i.email() for i in to_entity.get_cc(person=person)] +
                              [i.email() for i in from_entity.get_from_cc(person=person)]),
                       'poc': [i.email() for i in to_entity.get_poc()],
                       'needs_approval': from_entity.needs_approval(person=person),
                       'post_only': from_entity.post_only(person=person, user=request.user)})
        if is_secretariat(request.user):
            full_list = [(i.pk, i.email()) for i in set(from_entity.full_user_list())]
            full_list.sort(key=lambda x: x[1])
            full_list = [(person.pk, person.email())] + full_list
            result.update({'full_list': full_list})

    json_result = json.dumps(result)
    return HttpResponse(json_result, content_type='text/javascript')

def normalize_sort(request):
    sort = request.GET.get('sort', "")
    if sort not in ('submitted', 'deadline', 'title', 'to_name', 'from_name'):
        sort = "submitted"

    # reverse dates
    order_by = "-" + sort if sort in ("submitted", "deadline") else sort

    return sort, order_by

def liaison_list(request):
    sort, order_by = normalize_sort(request)
    liaisons = LiaisonStatement.objects.exclude(approved=None).order_by(order_by).prefetch_related("attachments")

    can_send_outgoing = can_add_outgoing_liaison(request.user)
    can_send_incoming = can_add_incoming_liaison(request.user)

    approvable = approvable_liaison_statements(request.user).count()

    return render_to_response('liaisons/overview.html', {
        "liaisons": liaisons,
        "can_manage": approvable or can_send_incoming or can_send_outgoing,
        "approvable": approvable,
        "can_send_incoming": can_send_incoming,
        "can_send_outgoing": can_send_outgoing,
        "sort": sort,
    }, context_instance=RequestContext(request))

def ajax_select2_search_liaison_statements(request):
    q = [w.strip() for w in request.GET.get('q', '').split() if w.strip()]

    if not q:
        objs = LiaisonStatement.objects.none()
    else:
        qs = LiaisonStatement.objects.exclude(approved=None).all()

        for t in q:
            qs = qs.filter(title__icontains=t)

        objs = qs.distinct().order_by("-id")[:20]

    return HttpResponse(select2_id_liaison_json(objs), content_type='application/json')

@can_submit_liaison_required
def liaison_approval_list(request):
    liaisons = approvable_liaison_statements(request.user).order_by("-submitted")

    return render_to_response('liaisons/approval_list.html', {
        "liaisons": liaisons,
    }, context_instance=RequestContext(request))


@can_submit_liaison_required
def liaison_approval_detail(request, object_id):
    liaison = get_object_or_404(approvable_liaison_statements(request.user), pk=object_id)

    if request.method == 'POST' and request.POST.get('do_approval', False):
        liaison.approved = datetime.datetime.now()
        liaison.save()

        send_liaison_by_email(request, liaison)
        return redirect('liaison_list')

    return render_to_response('liaisons/approval_detail.html', {
        "liaison": liaison,
        "is_approving": True,
    }, context_instance=RequestContext(request))


def _can_take_care(liaison, user):
    if not liaison.deadline or liaison.action_taken:
        return False

    if user.is_authenticated():
        if is_secretariat(user):
            return True
        else:
            return _find_person_in_emails(liaison, get_person_for_user(user))
    return False
            

def _find_person_in_emails(liaison, person):
    if not person:
        return False

    emails = ','.join(e for e in [liaison.cc, liaison.to_contact, liaison.to_name,
                                  liaison.reply_to, liaison.response_contact,
                                  liaison.technical_contact] if e)
    for email in emails.split(','):
        name, addr = parseaddr(email)
        try:
            validate_email(addr)
        except ValidationError:
            continue

        if person.email_set.filter(address=addr):
            return True
        elif addr in ('chair@ietf.org', 'iesg@ietf.org') and is_ietfchair(person):
            return True
        elif addr in ('iab@iab.org', 'iab-chair@iab.org') and is_iabchair(person):
            return True
        elif addr in ('execd@iab.org', ) and is_iab_executive_director(person):
            return True

    return False


def liaison_detail(request, object_id):
    liaison = get_object_or_404(LiaisonStatement.objects.exclude(approved=None), pk=object_id)
    can_edit = request.user.is_authenticated() and can_edit_liaison(request.user, liaison)
    can_take_care = _can_take_care(liaison, request.user)

    if request.method == 'POST' and request.POST.get('do_action_taken', None) and can_take_care:
        liaison.action_taken = True
        liaison.save()
        can_take_care = False

    relations = liaison.liaisonstatement_set.exclude(approved=None)

    return render_to_response("liaisons/detail.html", {
        "liaison": liaison,
        "can_edit": can_edit,
        "can_take_care": can_take_care,
        "relations": relations,
    }, context_instance=RequestContext(request))

def liaison_edit(request, object_id):
    liaison = get_object_or_404(LiaisonStatement, pk=object_id)
    if not (request.user.is_authenticated() and can_edit_liaison(request.user, liaison)):
        return HttpResponseForbidden('You do not have permission to edit this liaison statement')
    return add_liaison(request, liaison=liaison)
