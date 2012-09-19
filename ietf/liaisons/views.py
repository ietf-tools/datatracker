# Copyright The IETF Trust 2007, All Rights Reserved
import datetime
from email.utils import parseaddr

from django.conf import settings
from django.core.urlresolvers import reverse
from django.db.models import Q
from django.core.validators import email_re
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseForbidden
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.utils import simplejson
from django.views.generic.list_detail import object_list, object_detail

from ietf.liaisons.accounts import (get_person_for_user, can_add_outgoing_liaison,
                                    can_add_incoming_liaison, LIAISON_EDIT_GROUPS,
                                    is_ietfchair, is_iabchair, is_iab_executive_director,
                                    can_edit_liaison, is_secretariat)
from ietf.liaisons.decorators import can_submit_liaison
from ietf.liaisons.forms import liaison_form_factory
from ietf.liaisons.models import LiaisonDetail, OutgoingLiaisonApproval
from ietf.liaisons.utils import IETFHM

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    from ietf.liaisons.proxy import LiaisonDetailProxy as LiaisonDetail


@can_submit_liaison
def add_liaison(request, liaison=None):
    if request.method == 'POST':
        form = liaison_form_factory(request, data=request.POST.copy(),
                                    files = request.FILES, liaison=liaison)
        if form.is_valid():
            liaison = form.save()
            if request.POST.get('send', None):
                liaison.send_by_email()
            return HttpResponseRedirect(reverse('liaison_list'))
    else:
        form = liaison_form_factory(request, liaison=liaison)

    return render_to_response(
        'liaisons/liaisondetail_edit.html',
        {'form': form,
         'liaison': liaison},
        context_instance=RequestContext(request),
    )


@can_submit_liaison
def get_info(request):
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
                       'cc': [i.email() for i in to_entity.get_cc(person=person)] +\
                             [i.email() for i in from_entity.get_from_cc(person=person)],
                       'poc': [i.email() for i in to_entity.get_poc()],
                       'needs_approval': from_entity.needs_approval(person=person),
                       'post_only': from_entity.post_only(person=person, user=request.user)})
        if is_secretariat(request.user):
            full_list = [(i.pk, i.email()) for i in set(from_entity.full_user_list())]
            full_list.sort(lambda x,y: cmp(x[1], y[1]))
            full_list = [(person.pk, person.email())] + full_list
            result.update({'full_list': full_list})

    json_result = simplejson.dumps(result)
    return HttpResponse(json_result, mimetype='text/javascript')


if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    def approvable_liaison_statements(group_codes):
        # this is a bit complicated because IETFHM encodes the
        # groups, it should just give us a list of ids or acronyms
        group_acronyms = []
        group_ids = []
        for x in group_codes:
            if "_" in x:
                group_ids.append(x.split("_")[1])
            else:
                group_acronyms.append(x)

        return LiaisonDetail.objects.filter(approved=None).filter(Q(from_group__acronym__in=group_acronyms) | Q (from_group__pk__in=group_ids))

def liaison_list(request):
    user = request.user
    can_send_outgoing = can_add_outgoing_liaison(user)
    can_send_incoming = can_add_incoming_liaison(user)
    can_approve = False
    can_edit = False

    person = get_person_for_user(request.user)
    if person:
        approval_codes = IETFHM.get_all_can_approve_codes(person)
        if settings.USE_DB_REDESIGN_PROXY_CLASSES:
            if is_secretariat(request.user):
                can_approve = LiaisonDetail.objects.filter(approved=None).order_by("-submitted").count()
            else:
                can_approve = approvable_liaison_statements(approval_codes).count()
        else:
            can_approve = LiaisonDetail.objects.filter(approval__isnull=False, approval__approved=False, from_raw_code__in=approval_codes).count()

    order = request.GET.get('order_by', 'submitted_date')
    plain_order = order
    reverse_order = order.startswith('-')
    if reverse_order:
        plain_order = order[1:]
    if plain_order not in ('submitted_date', 'deadline_date', 'title', 'to_body', 'from_raw_body'):
        order = 'submitted_date'
        reverse_order = True
        plain_order = 'submitted_date'
    elif plain_order in ('submitted_date', 'deadline_date'):
        # Reverse order for date fields, humans find it more natural
        if reverse_order:
            order = plain_order
        else:
            order = '-%s' % plain_order
    if settings.USE_DB_REDESIGN_PROXY_CLASSES:
        public_liaisons = LiaisonDetail.objects.exclude(approved=None).order_by(order)
    else:
        public_liaisons = LiaisonDetail.objects.filter(Q(approval__isnull=True)|Q(approval__approved=True)).order_by(order)

    return object_list(request, public_liaisons,
                       allow_empty=True,
                       template_name='liaisons/liaisondetail_list.html',
                       extra_context={'can_manage': can_approve or can_send_incoming or can_send_outgoing,
                                      'can_approve': can_approve,
                                      'can_edit': can_edit,
                                      'can_send_incoming': can_send_incoming,
                                      'can_send_outgoing': can_send_outgoing,
                                      plain_order: not reverse_order and '-' or None},
                      )


@can_submit_liaison
def liaison_approval_list(request):
    if is_secretariat(request.user):
        to_approve = LiaisonDetail.objects.filter(approved=None).order_by("-submitted")
    else:
        person = get_person_for_user(request.user)
        approval_codes = IETFHM.get_all_can_approve_codes(person)
        if settings.USE_DB_REDESIGN_PROXY_CLASSES:
            to_approve = approvable_liaison_statements(approval_codes).order_by("-submitted")
        else:
            to_approve = LiaisonDetail.objects.filter(approval__isnull=False, approval__approved=False, from_raw_code__in=approval_codes).order_by("-submitted_date")

    return object_list(request, to_approve,
                       allow_empty=True,
                       template_name='liaisons/liaisondetail_approval_list.html',
                      )


@can_submit_liaison
def liaison_approval_detail(request, object_id):
    if is_secretariat(request.user):
        to_approve = LiaisonDetail.objects.filter(approved=None).order_by("-submitted")
    else:
        person = get_person_for_user(request.user)
        approval_codes = IETFHM.get_all_can_approve_codes(person)
        if settings.USE_DB_REDESIGN_PROXY_CLASSES:
            to_approve = approvable_liaison_statements(approval_codes).order_by("-submitted")
        else:
            to_approve = LiaisonDetail.objects.filter(approval__isnull=False, approval__approved=False, from_raw_code__in=approval_codes).order_by("-submitted_date")

    if request.method=='POST' and request.POST.get('do_approval', False):
        try:
            liaison = to_approve.get(pk=object_id)
            if settings.USE_DB_REDESIGN_PROXY_CLASSES:
                liaison.approved = datetime.datetime.now()
                liaison.save()
            else:
                approval = liaison.approval
                if not approval:
                    approval = OutgoingLiaisonApproval.objects.create(approved=True, approval_date=datetime.datetime.now())
                    liaison.approval = approval
                    liaison.save()
                else:
                    approval.approved=True
                    approval.save()
            liaison.send_by_email()
        except LiaisonDetail.DoesNotExist:
            pass
        return HttpResponseRedirect(reverse('liaison_list'))
    return  object_detail(request,
                          to_approve,
                          object_id=object_id,
                          template_name='liaisons/liaisondetail_approval_detail.html',
                         )


def _can_take_care(liaison, user):
    if not liaison.deadline_date or liaison.action_taken:
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
    emails = ','.join([ e for e in [liaison.cc1, liaison.cc2, liaison.to_email,
                       liaison.to_poc, liaison.submitter_email,
                       liaison.replyto, liaison.response_contact,
                       liaison.technical_contact] if e ])
    for email in emails.split(','):
        name, addr = parseaddr(email)
        if settings.USE_DB_REDESIGN_PROXY_CLASSES:
            person.emailaddress_set = person.email_set
        if email_re.search(addr) and person.emailaddress_set.filter(address=addr):
            return True
        elif addr in ('chair@ietf.org', 'iesg@ietf.org') and is_ietfchair(person):
            return True
        elif addr in ('iab@iab.org', 'iab-chair@iab.org') and is_iabchair(person):
            return True
        elif addr in ('execd@iab.org', ) and is_iab_executive_director(person):
            return True
    return False


def liaison_detail(request, object_id):
    if settings.USE_DB_REDESIGN_PROXY_CLASSES:
        qfilter = Q()
        public_liaisons = LiaisonDetail.objects.exclude(approved=None).order_by("-submitted_date")
    else:
        qfilter = Q(approval__isnull=True)|Q(approval__approved=True)
        public_liaisons = LiaisonDetail.objects.filter(qfilter).order_by("-submitted_date")
    liaison = get_object_or_404(public_liaisons, pk=object_id)
    can_edit = False
    user = request.user
    can_take_care = _can_take_care(liaison, user)
    if user.is_authenticated() and can_edit_liaison(user, liaison):
        can_edit = True
    if request.method == 'POST' and request.POST.get('do_action_taken', None) and can_take_care:
        liaison.action_taken = True
        liaison.save()
        can_take_care = False
    relations = liaison.liaisondetail_set.filter(qfilter)
    return  object_detail(request,
                          public_liaisons,
                          template_name="liaisons/liaisondetail_detail.html",
                          object_id=object_id,
                          extra_context = {'can_edit': can_edit,
                                           'relations': relations,
                                           'can_take_care': can_take_care}
                         )

def liaison_edit(request, object_id):
    liaison = get_object_or_404(LiaisonDetail, pk=object_id)
    user = request.user
    if not (user.is_authenticated() and can_edit_liaison(user, liaison)):
        return HttpResponseForbidden('You have no permission to edit this liaison')
    return add_liaison(request, liaison=liaison)

def ajax_liaison_list(request):
    order = request.GET.get('order_by', 'submitted_date')
    plain_order = order
    reverse_order = order.startswith('-')
    if reverse_order:
        plain_order = order[1:]
    if plain_order not in ('submitted_date', 'deadline_date', 'title', 'to_body', 'from_raw_body'):
        order = 'submitted_date'
        reverse_order = True
        plain_order = 'submitted_date'
    elif plain_order in ('submitted_date', 'deadline_date'):
        # Reverse order for date fields, humans find it more natural
        if reverse_order:
            order = plain_order
        else:
            order = '-%s' % plain_order
    
    if settings.USE_DB_REDESIGN_PROXY_CLASSES:
        public_liaisons = LiaisonDetail.objects.exclude(approved=None).order_by(order)
    else:
        public_liaisons = LiaisonDetail.objects.filter(Q(approval__isnull=True)|Q(approval__approved=True)).order_by(order)

    return object_list(request, public_liaisons,
                       allow_empty=True,
                       template_name='liaisons/liaisondetail_simple_list.html',
                       extra_context={plain_order: not reverse_order and '-' or None}
                      )
