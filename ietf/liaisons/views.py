# Copyright The IETF Trust 2007, All Rights Reserved
from django.shortcuts import render_to_response
from django.http import HttpResponse
from django.template import RequestContext
from django.utils import simplejson

from ietf.liaisons.accounts import get_person_for_user
from ietf.liaisons.decorators import can_submit_liaison
from ietf.liaisons.forms import liaison_form_factory
from ietf.liaisons.models import SDOs
from ietf.liaisons.utils import IETFHierarchyManager


@can_submit_liaison
def add_liaison(request):
    if request.method == 'POST':
        form = liaison_form_factory(request, data=request.POST.copy(), 
                                    files = request.FILES)
        if form.is_valid():
            form.save()
    else:
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
    sdo_id = request.GET.get('sdo_id', None)
    if not entity_id and not sdo_id:
        result = {'cc': [], 'error': 'No entity id and no sdo id'}
    if entity_id:
        entity = IETFHierarchyManager().get_entity_by_key(entity_id)
        if not entity:
            result = {'cc': [], 'error': 'Invalid entity id'}
        else:
            result = {'error': False, 'cc': [i.email() for i in entity.get_cc()]}
    if sdo_id:
        try:
            sdo = SDOs.objects.get(pk=sdo_id)
            manager = sdo.liaisonmanager()
            person = get_person_for_user(request.user)
            if manager and manager.person!=person:
                result['cc'].append(manager.person.email())
        except SDOs.DoesNotExist:
            result['error']='Invalid sdo id'
    json_result = simplejson.dumps(result)
    return HttpResponse(json_result, mimetype='text/javascript')
