# Copyright The IETF Trust 2017-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import json

from jwcrypto.jwk import JWK

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.gzip import gzip_page
from django.views.generic.detail import DetailView

from tastypie.exceptions import BadRequest
from tastypie.utils.mime import determine_format, build_content_type
from tastypie.utils import is_valid_jsonp_callback_value
from tastypie.serializers import Serializer

import debug                            # pyflakes:ignore

from ietf.person.models import Person
from ietf.api import _api_list
from ietf.api.serializer import JsonExportMixin
from ietf.utils.decorators import require_api_key
from ietf.ietfauth.utils import role_required


def top_level(request):
    available_resources = {}

    apitop = reverse('ietf.api.views.top_level')

    for name in sorted([ name for name, api in _api_list if len(api._registry) > 0 ]):
        available_resources[name] = {
            'list_endpoint': '%s/%s/' % (apitop, name),
        }

    serializer = Serializer()
    desired_format = determine_format(request, serializer)

    options = {}

    if 'text/javascript' in desired_format:
        callback = request.GET.get('callback', 'callback')

        if not is_valid_jsonp_callback_value(callback):
            raise BadRequest('JSONP callback name is invalid.')

        options['callback'] = callback

    serialized = serializer.serialize(available_resources, desired_format, options)
    return HttpResponse(content=serialized, content_type=build_content_type(desired_format))

def api_help(request):
    key = JWK()
    # import just public part here, for display in info page
    key.import_from_pem(settings.API_PUBLIC_KEY_PEM)
    return render(request, "api/index.html", {'key': key, 'settings':settings, })
    

@method_decorator((login_required, gzip_page), name='dispatch')
class PersonalInformationExportView(DetailView, JsonExportMixin):
    model = Person

    def get(self, request):
        person = get_object_or_404(self.model, user=request.user)
        expand = ['searchrule', 'documentauthor', 'ad_document_set', 'ad_dochistory_set', 'docevent',
            'ballotpositiondocevent', 'deletedevent', 'email_set', 'groupevent', 'role', 'rolehistory', 'iprdisclosurebase',
            'iprevent', 'liaisonstatementevent', 'whitelisted', 'schedule', 'constraint', 'schedulingevent', 'message',
            'sendqueue', 'nominee', 'topicfeedbacklastseen', 'alias', 'email', 'apikeys', 'personevent',
            'reviewersettings', 'reviewsecretarysettings', 'unavailableperiod', 'reviewwish',
            'nextreviewerinteam', 'reviewrequest', 'meetingregistration', 'submissionevent', 'preapproval',
            'user', 'user__communitylist', ]
        return self.json_view(request, filter={'id':person.id}, expand=expand)


@method_decorator((csrf_exempt, require_api_key, role_required('Secretariat')), name='dispatch')
class ApiV2PersonExportView(DetailView, JsonExportMixin):
    model = Person

    def err(self, code, text):
        return HttpResponse(text, status=code, content_type='text/plain')

    def post(self, request):
        querydict = request.POST.copy()
        querydict.pop('apikey', None)
        expand = querydict.pop('_expand', [])
        if not querydict:
            return self.err(400, "No filters provided")

        return self.json_view(request, filter=querydict.dict(), expand=expand)

@require_api_key
@csrf_exempt
def person_access_meetecho(request):
    person = get_object_or_404(Person, user=request.user)
    return HttpResponse(json.dumps({ 'name' : person.name, 'email': person.email().address, }), content_type='application/json')
