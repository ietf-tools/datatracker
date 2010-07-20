# Copyright The IETF Trust 2007, All Rights Reserved
from django.shortcuts import render_to_response
from django.http import HttpResponse
from django.template import RequestContext
from django.utils import simplejson

from ietf.liaisons.decorators import can_submit_liaison
from ietf.liaisons.forms import liaison_form_factory
from ietf.liaisons.utils import IETFHierarchyManager


@can_submit_liaison
def add_liaison(request):
    form = liaison_form_factory(request)

    return render_to_response(
        'liaisons/liaisondetail_edit.html',
        {'form': form},
        context_instance=RequestContext(request),
    )


@can_submit_liaison
def get_poc_for_incoming(request):
    entity_id = request.GET.get('entity_id', None)
    if not entity_id:
        result = {'poc': None, 'error': 'No entity id'}
    else:
        entity = IETFHierarchyManager().get_entity_by_key(entity_id)
        if not entity:
            result = {'poc': None, 'error': 'Invalid entity id'}
        else:
            result = {'error': False, 'poc': [i.email() for i in entity.get_poc()]}
    json_result = simplejson.dumps(result)
    return HttpResponse(json_result, mimetype='text/javascript')


@can_submit_liaison
def get_cc_for_incoming(request):
    entity_id = request.GET.get('to_entity_id', None)
    if not entity_id:
        result = {'cc': None, 'error': 'No entity id'}
    else:
        entity = IETFHierarchyManager().get_entity_by_key(entity_id)
        if not entity:
            result = {'cc': None, 'error': 'Invalid entity id'}
        else:
            result = {'error': False, 'cc': [i.email() for i in entity.get_cc()]}
    json_result = simplejson.dumps(result)
    return HttpResponse(json_result, mimetype='text/javascript')
