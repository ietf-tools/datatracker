# Copyright The IETF Trust 2017-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import json
import pytz

from jwcrypto.jwk import JWK

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
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

import ietf
from ietf.person.models import Person, Email
from ietf.api import _api_list
from ietf.api.serializer import JsonExportMixin
from ietf.ietfauth.views import send_account_creation_email
from ietf.ietfauth.utils import role_required
from ietf.meeting.models import Meeting
from ietf.stats.models import MeetingRegistration
from ietf.utils.decorators import require_api_key
from ietf.utils.log import log
from ietf.utils.models import DumpInfo


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
            'user', 'user__communitylist', 'personextresource_set', ]


        return self.json_view(request, filter={'id':person.id}, expand=expand)


@method_decorator((csrf_exempt, require_api_key, role_required('Robot')), name='dispatch')
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

# @require_api_key
# @csrf_exempt
# def person_access_token(request):
#     person = get_object_or_404(Person, user=request.user)
#     
#     if request.method == 'POST':
#         client_id = request.POST.get('client_id', None)
#         client_secret = request.POST.get('client_secret', None)
#         client = get_object_or_404(ClientRecord, client_id=client_id, client_secret=client_secret)
# 
#         return HttpResponse(json.dumps({
#                 'name' : person.plain_name(),
#                 'email': person.email().address,
#                 'roles': {
#                         'chair': list(person.role_set.filter(name='chair', group__state__in=['active', 'bof', 'proposed']).values_list('group__acronym', flat=True)),
#                         'secr': list(person.role_set.filter(name='secr', group__state__in=['active', 'bof', 'proposed']).values_list('group__acronym', flat=True)),
#                     }
#             }), content_type='application/json')
#     else:
#         return HttpResponse(status=405)

@require_api_key
@role_required('Robot')
@csrf_exempt
def api_new_meeting_registration(request):
    '''REST API to notify the datatracker about a new meeting registration'''
    def err(code, text):
        return HttpResponse(text, status=code, content_type='text/plain')
    required_fields = [ 'meeting', 'first_name', 'last_name', 'affiliation', 'country_code',
                        'email', 'reg_type', 'ticket_type', ]
    fields = required_fields + []
    if request.method == 'POST':
        # parameters:
        #   apikey:
        #   meeting
        #   name
        #   email
        #   reg_type (In Person, Remote, Hackathon Only)
        #   ticket_type (full_week, one_day, student)
        #   
        data = {'attended': False, }
        missing_fields = []
        for item in fields:
            value = request.POST.get(item, None)
            if value is None and item in required_fields:
                missing_fields.append(item)
            data[item] = value
        log("Meeting registration notification: %s" % json.dumps(data))
        if missing_fields:
            return err(400, "Missing parameters: %s" % ', '.join(missing_fields))
        number = data['meeting']
        try:
            meeting = Meeting.objects.get(number=number)
        except Meeting.DoesNotExist:
            return err(400, "Invalid meeting value: '%s'" % (number, ))
        reg_type = data['reg_type']
        email = data['email']
        try:
            validate_email(email)
        except ValidationError:
            return err(400, "Invalid email value: '%s'" % (email, ))
        if request.POST.get('cancelled', 'false') == 'true':
            MeetingRegistration.objects.filter(
                meeting_id=meeting.pk,
                email=email,
                reg_type=reg_type).delete()
            return HttpResponse('OK', status=200, content_type='text/plain')
        else:
            object, created = MeetingRegistration.objects.get_or_create(
                meeting_id=meeting.pk,
                email=email,
                reg_type=reg_type)
            try:
                # Update attributes
                for key in set(data.keys())-set(['attended', 'apikey', 'meeting', 'email']):
                    new = data.get(key)
                    setattr(object, key, new)
                person = Person.objects.filter(email__address=email)
                if person.exists():
                    object.person = person.first()
                object.save()
            except ValueError as e:
                return err(400, "Unexpected POST data: %s" % e)
            response = "Accepted, New registration" if created else "Accepted, Updated registration"
            if User.objects.filter(username=email).exists() or Email.objects.filter(address=email).exists():
                pass
            else:
                send_account_creation_email(request, email)
                response += ", Email sent"
            return HttpResponse(response, status=202, content_type='text/plain')
    else:
        return HttpResponse(status=405)


def version(request):
    dumpinfo = DumpInfo.objects.order_by('-date').first()
    dumptime = pytz.timezone(dumpinfo.tz).localize(dumpinfo.date).strftime('%Y-%m-%d %H:%M:%S %z') if dumpinfo else None
    return HttpResponse(
            json.dumps({
                        'version': ietf.__version__+ietf.__patch__,
                        'date': ietf.__date__[7:-2],
                        'dumptime': dumptime,
                    }),
                content_type='application/json',
            )
    

@require_api_key
@csrf_exempt
def app_auth(request):
    return HttpResponse(
            json.dumps({'success': True}),
            content_type='application/json')
