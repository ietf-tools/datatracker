 # -*- coding: utf-8 -*-
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import HttpResponse, Http404, HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.template.loader import render_to_string
from django.utils import simplejson
from django.db.models import Count

from ietf.dbtemplate.models import DBTemplate
from ietf.dbtemplate.views import template_edit
from ietf.name.models import NomineePositionState
from ietf.nomcom.decorators import member_required, private_key_required
from ietf.nomcom.forms import (EditPublicKeyForm, NominateForm, MergeForm,
                               NomComTemplateForm, PositionForm, PrivateKeyForm)
from ietf.nomcom.models import Position, NomineePosition
from ietf.nomcom.utils import (get_nomcom_by_year, HOME_TEMPLATE,
                               retrieve_nomcom_private_key,
                               store_nomcom_private_key)


def index(request, year):
    nomcom = get_nomcom_by_year(year)
    home_template = '/nomcom/%s/%s' % (nomcom.group.acronym, HOME_TEMPLATE)
    template = render_to_string(home_template, {})
    return render_to_response('nomcom/index.html',
                              {'nomcom': nomcom,
                               'year': year,
                               'selected': 'index',
                               'template': template}, RequestContext(request))


@member_required(role='member')
def private_key(request, year):
    nomcom = get_nomcom_by_year(year)
    private_key = retrieve_nomcom_private_key(request, year)

    back_url = request.GET.get('back_to', reverse('nomcom_private_index', None, args=(year, )))
    if request.method == 'POST':
        form = PrivateKeyForm(data=request.POST)
        if form.is_valid():
            store_nomcom_private_key(request, year, form.cleaned_data.get('key', ''))
            return HttpResponseRedirect(back_url)
    else:
        form = PrivateKeyForm(initial={'key': private_key})
    return render_to_response('nomcom/private_key.html',
                              {'nomcom': nomcom,
                               'year': year,
                               'back_url': back_url,
                               'form': form,
                               'private_key': private_key,
                               'selected': 'private_key'}, RequestContext(request))


@member_required(role='member')
def private_index(request, year):
    nomcom = get_nomcom_by_year(year)

    filters = {}
    selected_state = request.GET.get('state')
    selected_position = request.GET.get('position')

    if selected_state:
        if selected_state == 'questionnaire':
            filters['questionnaires__isnull'] = False
        else:
            filters['state__slug'] = selected_state

    if selected_position:
            filters['position__id'] = selected_position

    nominee_positions = NomineePosition.objects.all()
    if filters:
        nominee_positions = nominee_positions.filter(**filters)

    stats = NomineePosition.objects.values('position__name').annotate(total=Count('position'))
    states = list(NomineePositionState.objects.values('slug', 'name')) + [{'slug': u'questionnaire', 'name': u'Questionnaire'}]
    positions = NomineePosition.objects.values('position__name', 'position__id').distinct()
    for s in stats:
        for state in states:
            if state['slug'] == 'questionnaire':
                s[state['slug']] = NomineePosition.objects.filter(position__name=s['position__name'], questionnaires__isnull=False).count()
            else:
                s[state['slug']] = NomineePosition.objects.filter(position__name=s['position__name'], state=state['slug']).count()

    return render_to_response('nomcom/private_index.html',
                              {'nomcom': nomcom,
                               'year': year,
                               'nominee_positions': nominee_positions,
                               'stats': stats,
                               'states': states,
                               'positions': positions,
                               'selected_state': selected_state,
                               'selected_position': selected_position and int(selected_position) or None,
                               'selected': 'index'}, RequestContext(request))


@member_required(role='chair')
def private_merge(request, year):
    nomcom = get_nomcom_by_year(year)
    message = None
    if request.method == 'POST':
        form = MergeForm(request.POST, nomcom=nomcom)
        if form.is_valid():
            form.save()
            message = ('success', 'The emails has been unified')
    else:
        form = MergeForm(nomcom=nomcom)

    return render_to_response('nomcom/private_merge.html',
                              {'nomcom': nomcom,
                               'year': year,
                               'form': form,
                               'message': message,
                               'selected': 'merge'}, RequestContext(request))


def requirements(request, year):
    nomcom = get_nomcom_by_year(year)
    positions = nomcom.position_set.all()
    return render_to_response('nomcom/requirements.html',
                              {'nomcom': nomcom,
                               'positions': positions,
                               'year': year,
                               'selected': 'requirements'}, RequestContext(request))


def questionnaires(request, year):
    nomcom = get_nomcom_by_year(year)
    positions = nomcom.position_set.all()
    return render_to_response('nomcom/questionnaires.html',
                              {'nomcom': nomcom,
                               'positions': positions,
                               'year': year,
                               'selected': 'questionnaires'}, RequestContext(request))


@login_required
def public_nominate(request, year):
    return nominate(request, year, True)


@member_required(role='member')
def private_nominate(request, year):
    return nominate(request, year, False)


def nominate(request, year, public):
    nomcom = get_nomcom_by_year(year)
    has_publickey = nomcom.public_key and True or False
    if public:
        template = 'nomcom/public_nominate.html'
    else:
        template = 'nomcom/private_nominate.html'

    if not has_publickey:
            message = ('warning', "Nomcom don't have public key to ecrypt data, please contact with nomcom chair")
            return render_to_response(template,
                              {'has_publickey': has_publickey,
                               'message': message,
                               'nomcom': nomcom,
                               'year': year,
                               'selected': 'nominate'}, RequestContext(request))

    message = None
    if request.method == 'POST':
        form = NominateForm(data=request.POST, nomcom=nomcom, user=request.user, public=public)
        if form.is_valid():
            form.save()
            message = ('success', 'Your nomination has been registered. Thank you for the nomination.')
    else:
        form = NominateForm(nomcom=nomcom, user=request.user, public=public)

    return render_to_response(template,
                              {'has_publickey': has_publickey,
                               'form': form,
                               'message': message,
                               'nomcom': nomcom,
                               'year': year,
                               'selected': 'nominate'}, RequestContext(request))


@login_required
def comments(request, year):
    # TODO: complete to do comments
    nomcom = get_nomcom_by_year(year)
    return render_to_response('nomcom/comments.html',
                              {'nomcom': nomcom,
                               'year': year,
                               'selected': 'comments'}, RequestContext(request))


@member_required(role='chair')
def edit_publickey(request, year):
    nomcom = get_nomcom_by_year(year)

    message = ('warning', 'Previous data will remain encrypted with the old key')
    if request.method == 'POST':
        form = EditPublicKeyForm(request.POST,
                                 request.FILES,
                                 instance=nomcom,
                                 initial={'public_key': None})
        if form.is_valid():
            form.save()
            message = ('success', 'The public key has been changed')
    else:
        form = EditPublicKeyForm()

    return render_to_response('nomcom/edit_publickey.html',
                              {'form': form,
                               'group': nomcom.group,
                               'message': message,
                               'year': year,
                               'selected': 'edit_publickey'}, RequestContext(request))


@member_required(role='chair')
def list_templates(request, year):
    nomcom = get_nomcom_by_year(year)
    positions = nomcom.position_set.all()
    template_list = DBTemplate.objects.filter(group=nomcom.group).exclude(path__contains='/position/')

    return render_to_response('nomcom/list_templates.html',
                              {'template_list': template_list,
                               'positions': positions,
                               'year': year,
                               'selected': 'edit_templates',
                               'nomcom': nomcom}, RequestContext(request))


@member_required(role='chair')
def edit_template(request, year, template_id):
    nomcom = get_nomcom_by_year(year)
    return_url = request.META.get('HTTP_REFERER', None)

    return template_edit(request, nomcom.group.acronym, template_id,
                         base_template='nomcom/edit_template.html',
                         formclass=NomComTemplateForm,
                         extra_context={'year': year,
                                        'return_url': return_url,
                                        'nomcom': nomcom})


@member_required(role='chair')
def list_positions(request, year):
    nomcom = get_nomcom_by_year(year)
    positions = nomcom.position_set.all()

    return render_to_response('nomcom/list_positions.html',
                              {'positions': positions,
                               'year': year,
                               'selected': 'edit_positions',
                               'nomcom': nomcom}, RequestContext(request))


@member_required(role='chair')
def remove_position(request, year, position_id):
    nomcom = get_nomcom_by_year(year)
    try:
        position = nomcom.position_set.get(id=position_id)
    except Position.DoesNotExist:
        raise Http404

    if request.POST.get('remove', None):
        position.delete()
        return HttpResponseRedirect(reverse('nomcom_list_positions', None, args=(year, )))
    return render_to_response('nomcom/remove_position.html',
                              {'year': year,
                               'position': position,
                               'nomcom': nomcom}, RequestContext(request))


@member_required(role='chair')
def edit_position(request, year, position_id=None):
    nomcom = get_nomcom_by_year(year)
    if position_id:
        try:
            position = nomcom.position_set.get(id=position_id)
        except Position.DoesNotExist:
            raise Http404
    else:
        position = None

    if request.method == 'POST':
        form = PositionForm(request.POST, instance=position, nomcom=nomcom)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(reverse('nomcom_list_positions', None, args=(year, )))
    else:
        form = PositionForm(instance=position, nomcom=nomcom)

    return render_to_response('nomcom/edit_position.html',
                              {'form': form,
                               'position': position,
                               'year': year,
                               'nomcom': nomcom}, RequestContext(request))


def ajax_position_text(request, position_id):
    try:
        position_text = Position.objects.get(id=position_id).initial_text
    except Position.DoesNotExist:
        position_text = ""

    result = {'text': position_text}

    json_result = simplejson.dumps(result)
    return HttpResponse(json_result, mimetype='application/json')
