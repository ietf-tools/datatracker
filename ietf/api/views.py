# Copyright The IETF Trust 2017-2020, All Rights Reserved
# -*- coding: utf-8 -*-

import base64
import binascii
import json
import jsonschema
import pytz
import re

from contextlib import suppress
from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import HttpResponse, Http404, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.gzip import gzip_page
from django.views.generic.detail import DetailView
from email.message import EmailMessage
from jwcrypto.jwk import JWK
from tastypie.exceptions import BadRequest
from tastypie.serializers import Serializer
from tastypie.utils import is_valid_jsonp_callback_value
from tastypie.utils.mime import determine_format, build_content_type
from textwrap import dedent
from traceback import format_exception, extract_tb
from typing import Iterable, Optional

import ietf
from ietf.api import _api_list
from ietf.api.ietf_utils import is_valid_token, requires_api_token
from ietf.api.serializer import JsonExportMixin
from ietf.doc.utils import DraftAliasGenerator, fuzzy_find_documents
from ietf.group.utils import GroupAliasGenerator, role_holder_emails
from ietf.ietfauth.utils import role_required
from ietf.ietfauth.views import send_account_creation_email
from ietf.ipr.utils import ingest_response_email as ipr_ingest_response_email
from ietf.meeting.models import Meeting
from ietf.nomcom.models import Volunteer, NomCom
from ietf.nomcom.utils import ingest_feedback_email as nomcom_ingest_feedback_email
from ietf.person.models import Person, Email
from ietf.stats.models import MeetingRegistration
from ietf.sync.iana import ingest_review_email as iana_ingest_review_email
from ietf.utils import log
from ietf.utils.decorators import require_api_key
from ietf.utils.mail import send_smtp
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
            'iprevent', 'liaisonstatementevent', 'allowlisted', 'schedule', 'constraint', 'schedulingevent', 'message',
            'sendqueue', 'nominee', 'topicfeedbacklastseen', 'alias', 'email', 'apikeys', 'personevent',
            'reviewersettings', 'reviewsecretarysettings', 'unavailableperiod', 'reviewwish',
            'nextreviewerinteam', 'reviewrequest', 'meetingregistration', 'submissionevent', 'preapproval',
            'user', 'communitylist', 'personextresource_set', ]


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
                        'email', 'reg_type', 'ticket_type', 'checkedin', 'is_nomcom_volunteer']
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
                    if key == 'checkedin':
                        new = bool(data.get(key).lower() == 'true')
                    else:
                        new = data.get(key)
                    setattr(object, key, new)
                person = Person.objects.filter(email__address=email)
                if person.exists():
                    object.person = person.first()
                object.save()
            except ValueError as e:
                return err(400, "Unexpected POST data: %s" % e)
            response = "Accepted, New registration" if created else "Accepted, Updated registration"
            if User.objects.filter(username__iexact=email).exists() or Email.objects.filter(address=email).exists():
                pass
            else:
                send_account_creation_email(request, email)
                response += ", Email sent"

            # handle nomcom volunteer
            if request.POST.get('is_nomcom_volunteer', 'false').lower() == 'true' and object.person:
                try:
                    nomcom = NomCom.objects.get(is_accepting_volunteers=True)
                except (NomCom.DoesNotExist, NomCom.MultipleObjectsReturned):
                    nomcom = None
                if nomcom:
                    Volunteer.objects.get_or_create(
                        nomcom=nomcom,
                        person=object.person,
                        defaults={
                            "affiliation": data["affiliation"],
                            "origin": "registration"
                        }
                    )
            return HttpResponse(response, status=202, content_type='text/plain')
    else:
        return HttpResponse(status=405)


def version(request):
    dumpdate = None
    dumpinfo = DumpInfo.objects.order_by('-date').first()
    if dumpinfo:
        dumpdate = dumpinfo.date
        if dumpinfo.tz != "UTC":
            dumpdate = pytz.timezone(dumpinfo.tz).localize(dumpinfo.date.replace(tzinfo=None))
    dumptime = dumpdate.strftime('%Y-%m-%d %H:%M:%S %z') if dumpinfo else None
    return HttpResponse(
            json.dumps({
                        'version': ietf.__version__+ietf.__patch__,
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



def find_doc_for_rfcdiff(name, rev):
    """rfcdiff lookup heuristics

    Returns a tuple with:
      [0] - condition string
      [1] - document found (or None)
      [2] - historic version
      [3] - revision actually found (may differ from :rev: input)
    """
    found = fuzzy_find_documents(name, rev)
    condition = 'no such document'
    if found.documents.count() != 1:
        return (condition, None, None, rev)
    doc = found.documents.get()
    if found.matched_rev is None or doc.rev == found.matched_rev:
        condition = 'current version'
        return (condition, doc, None, found.matched_rev)
    else:
        candidate = doc.history_set.filter(rev=found.matched_rev).order_by("-time").first()
        if candidate:
            condition = 'historic version'
            return (condition, doc, candidate, found.matched_rev)
        else:
            condition = 'version dochistory not found'
            return (condition, doc, None, found.matched_rev)

# This is a proof of concept of a service that would redirect to the current revision
# def rfcdiff_latest(request, name, rev=None):
#     condition, doc, history = find_doc_for_rfcdiff(name, rev)
#     if not doc:
#         raise Http404
#     if history:
#         return redirect(history.get_href())
#     else:
#         return redirect(doc.get_href())

HAS_TOMBSTONE = [
    2821, 2822, 2873, 2919, 2961, 3023, 3029, 3031, 3032, 3033, 3034, 3035, 3036,
    3037, 3038, 3042, 3044, 3050, 3052, 3054, 3055, 3056, 3057, 3059, 3060, 3061,
    3062, 3063, 3064, 3067, 3068, 3069, 3070, 3071, 3072, 3073, 3074, 3075, 3076,
    3077, 3078, 3080, 3081, 3082, 3084, 3085, 3086, 3087, 3088, 3089, 3090, 3094,
    3095, 3096, 3097, 3098, 3101, 3102, 3103, 3104, 3105, 3106, 3107, 3108, 3109,
    3110, 3111, 3112, 3113, 3114, 3115, 3116, 3117, 3118, 3119, 3120, 3121, 3123,
    3124, 3126, 3127, 3128, 3130, 3131, 3132, 3133, 3134, 3135, 3136, 3137, 3138,
    3139, 3140, 3141, 3142, 3143, 3144, 3145, 3147, 3149, 3150, 3151, 3152, 3153,
    3154, 3155, 3156, 3157, 3158, 3159, 3160, 3161, 3162, 3163, 3164, 3165, 3166,
    3167, 3168, 3169, 3170, 3171, 3172, 3173, 3174, 3176, 3179, 3180, 3181, 3182,
    3183, 3184, 3185, 3186, 3187, 3188, 3189, 3190, 3191, 3192, 3193, 3194, 3197,
    3198, 3201, 3202, 3203, 3204, 3205, 3206, 3207, 3208, 3209, 3210, 3211, 3212,
    3213, 3214, 3215, 3216, 3217, 3218, 3220, 3221, 3222, 3224, 3225, 3226, 3227,
    3228, 3229, 3230, 3231, 3232, 3233, 3234, 3235, 3236, 3237, 3238, 3240, 3241,
    3242, 3243, 3244, 3245, 3246, 3247, 3248, 3249, 3250, 3253, 3254, 3255, 3256,
    3257, 3258, 3259, 3260, 3261, 3262, 3263, 3264, 3265, 3266, 3267, 3268, 3269,
    3270, 3271, 3272, 3273, 3274, 3275, 3276, 3278, 3279, 3280, 3281, 3282, 3283,
    3284, 3285, 3286, 3287, 3288, 3289, 3290, 3291, 3292, 3293, 3294, 3295, 3296,
    3297, 3298, 3301, 3302, 3303, 3304, 3305, 3307, 3308, 3309, 3310, 3311, 3312,
    3313, 3315, 3317, 3318, 3319, 3320, 3321, 3322, 3323, 3324, 3325, 3326, 3327,
    3329, 3330, 3331, 3332, 3334, 3335, 3336, 3338, 3340, 3341, 3342, 3343, 3346,
    3348, 3349, 3351, 3352, 3353, 3354, 3355, 3356, 3360, 3361, 3362, 3363, 3364,
    3366, 3367, 3368, 3369, 3370, 3371, 3372, 3374, 3375, 3377, 3378, 3379, 3383,
    3384, 3385, 3386, 3387, 3388, 3389, 3390, 3391, 3394, 3395, 3396, 3397, 3398,
    3401, 3402, 3403, 3404, 3405, 3406, 3407, 3408, 3409, 3410, 3411, 3412, 3413,
    3414, 3415, 3416, 3417, 3418, 3419, 3420, 3421, 3422, 3423, 3424, 3425, 3426,
    3427, 3428, 3429, 3430, 3431, 3433, 3434, 3435, 3436, 3437, 3438, 3439, 3440,
    3441, 3443, 3444, 3445, 3446, 3447, 3448, 3449, 3450, 3451, 3452, 3453, 3454,
    3455, 3458, 3459, 3460, 3461, 3462, 3463, 3464, 3465, 3466, 3467, 3468, 3469,
    3470, 3471, 3472, 3473, 3474, 3475, 3476, 3477, 3480, 3481, 3483, 3485, 3488,
    3494, 3495, 3496, 3497, 3498, 3501, 3502, 3503, 3504, 3505, 3506, 3507, 3508,
    3509, 3511, 3512, 3515, 3516, 3517, 3518, 3520, 3521, 3522, 3523, 3524, 3525,
    3527, 3529, 3530, 3532, 3533, 3534, 3536, 3537, 3538, 3539, 3541, 3543, 3544,
    3545, 3546, 3547, 3548, 3549, 3550, 3551, 3552, 3555, 3556, 3557, 3558, 3559,
    3560, 3562, 3563, 3564, 3565, 3568, 3569, 3570, 3571, 3572, 3573, 3574, 3575,
    3576, 3577, 3578, 3579, 3580, 3581, 3582, 3583, 3584, 3588, 3589, 3590, 3591,
    3592, 3593, 3594, 3595, 3597, 3598, 3601, 3607, 3609, 3610, 3612, 3614, 3615,
    3616, 3625, 3627, 3630, 3635, 3636, 3637, 3638
]


def get_previous_url(name, rev=None):
    '''Return previous url'''
    condition, document, history, found_rev = find_doc_for_rfcdiff(name, rev)
    previous_url = ''
    if condition in ('historic version', 'current version'):
        doc = history if history else document
        previous_url = doc.get_href()
    elif condition == 'version dochistory not found':
        document.rev = found_rev
        previous_url = document.get_href()
    return previous_url


def rfcdiff_latest_json(request, name, rev=None):
    response = dict()
    condition, document, history, found_rev = find_doc_for_rfcdiff(name, rev)
    if document and document.type_id == "rfc":
        draft = document.came_from_draft()
    if condition == 'no such document':
        raise Http404
    elif condition in ('historic version', 'current version'):
        doc = history if history else document
        if doc.type_id == "rfc":
                response['content_url'] = doc.get_href()
                response['name']=doc.name
                if draft:
                    prev_rev = draft.rev
                    if doc.rfc_number in HAS_TOMBSTONE and prev_rev != '00':
                        prev_rev = f'{(int(draft.rev)-1):02d}'
                    response['previous'] = f'{draft.name}-{prev_rev}'
                    response['previous_url'] = get_previous_url(draft.name, prev_rev)            
        elif doc.type_id == "draft" and not found_rev and doc.relateddocument_set.filter(relationship_id="became_rfc").exists():
                rfc = doc.related_that_doc("became_rfc")[0]
                response['content_url'] = rfc.get_href()
                response['name']=rfc.name
                prev_rev = doc.rev
                if rfc.rfc_number in HAS_TOMBSTONE and prev_rev != '00':
                    prev_rev = f'{(int(doc.rev)-1):02d}'
                response['previous'] = f'{doc.name}-{prev_rev}'
                response['previous_url'] = get_previous_url(doc.name, prev_rev)
        else:
            response['content_url'] = doc.get_href()
            response['rev'] = doc.rev
            response['name'] = doc.name
            if doc.rev == '00':
                replaces_docs = (history.doc if condition=='historic version' else doc).related_that_doc('replaces')
                if replaces_docs:
                    replaces = replaces_docs[0]
                    response['previous'] = f'{replaces.name}-{replaces.rev}'
                    response['previous_url'] = get_previous_url(replaces.name, replaces.rev)
                else:
                    match = re.search("-(rfc)?([0-9][0-9][0-9]+)bis(-.*)?$", name)
                    if match and match.group(2):
                        response['previous'] = f'rfc{match.group(2)}'
                        response['previous_url'] = get_previous_url(f'rfc{match.group(2)}')
            else:
                # not sure what to do if non-numeric values come back, so at least log it
                log.assertion('doc.rev.isdigit()')
                prev_rev = f'{(int(doc.rev)-1):02d}'
                response['previous'] = f'{doc.name}-{prev_rev}'
                response['previous_url'] = get_previous_url(doc.name, prev_rev)
    elif condition == 'version dochistory not found':
        response['warning'] = 'History for this version not found - these results are speculation'
        response['name'] = document.name
        response['rev'] = found_rev
        document.rev = found_rev
        response['content_url'] = document.get_href()
        # not sure what to do if non-numeric values come back, so at least log it
        log.assertion('found_rev.isdigit()')
        if int(found_rev) > 0:
            prev_rev = f'{(int(found_rev)-1):02d}'
            response['previous'] = f'{document.name}-{prev_rev}'
            response['previous_url'] = get_previous_url(document.name, prev_rev)
        else:
            match = re.search("-(rfc)?([0-9][0-9][0-9]+)bis(-.*)?$", name)
            if match and match.group(2):
                response['previous'] = f'rfc{match.group(2)}'
                response['previous_url'] = get_previous_url(f'rfc{match.group(2)}')
    if not response:
        raise Http404
    return HttpResponse(json.dumps(response), content_type='application/json')

@csrf_exempt
def directauth(request):
    if request.method == "POST":
        raw_data = request.POST.get("data", None)
        if raw_data:
            try:
                data = json.loads(raw_data)
            except json.decoder.JSONDecodeError:
                data = None

        if raw_data is None or data is None:
            log.log("Request body is either missing or invalid")
            return HttpResponse(json.dumps(dict(result="failure",reason="invalid post")), content_type='application/json')

        authtoken = data.get('authtoken', None)
        username = data.get('username', None)
        password = data.get('password', None)

        if any([item is None for item in (authtoken, username, password)]):
            log.log("One or more mandatory fields are missing: authtoken, username, password")
            return HttpResponse(json.dumps(dict(result="failure",reason="invalid post")), content_type='application/json')

        if not is_valid_token("ietf.api.views.directauth", authtoken):
            log.log("Auth token provided is invalid")
            return HttpResponse(json.dumps(dict(result="failure",reason="invalid authtoken")), content_type='application/json')
        
        user_query = User.objects.filter(username__iexact=username)

        # Matching email would be consistent with auth everywhere else in the app, but until we can map users well
        # in the imap server, people's annotations are associated with a very specific login.
        # If we get a second user of this API, add an "allow_any_email" argument.


        # Note well that we are using user.username, not what was passed to the API.
        user_count = user_query.count()
        if user_count == 1 and authenticate(username = user_query.first().username, password = password):
            user = user_query.get()
            if user_query.filter(person__isnull=True).count() == 1: # Can't inspect user.person direclty here
                log.log(f"Direct auth success (personless user): {user.pk}:{user.username}")
            else:
                log.log(f"Direct auth success: {user.pk}:{user.person.plain_name()}")
            return HttpResponse(json.dumps(dict(result="success")), content_type='application/json')

        log.log(f"Direct auth failure: {username} ({user_count} user(s) found)")
        return HttpResponse(json.dumps(dict(result="failure", reason="authentication failed")), content_type='application/json') 

    else:
        log.log(f"Request must be POST: {request.method} received")
        return HttpResponse(status=405)


@requires_api_token
@csrf_exempt
def draft_aliases(request):
    if request.method == "GET":
        return JsonResponse(
            {
                "aliases": [
                    {
                        "alias": alias,
                        "domains": ["ietf"],
                        "addresses": address_list,
                    }
                    for alias, address_list in DraftAliasGenerator()
                ]
            }
        )
    return HttpResponse(status=405)


@requires_api_token
@csrf_exempt
def group_aliases(request):
    if request.method == "GET":
        return JsonResponse(
            {
                "aliases": [
                    {
                        "alias": alias,
                        "domains": domains,
                        "addresses": address_list,
                    } 
                    for alias, domains, address_list in GroupAliasGenerator()
                ]
            }
        )
    return HttpResponse(status=405)


@requires_api_token
@csrf_exempt
def active_email_list(request):
    if request.method == "GET":
        return JsonResponse(
            {
                "addresses": list(Email.objects.filter(active=True).values_list("address", flat=True)),
            }
        )
    return HttpResponse(status=405)


@requires_api_token
def role_holder_addresses(request):
    if request.method == "GET":
        return JsonResponse(
            {
                "addresses": list(
                    role_holder_emails()
                    .order_by("address")
                    .values_list("address", flat=True)
                )
            }
        )
    return HttpResponse(status=405)


_response_email_json_validator = jsonschema.Draft202012Validator(
    schema={
        "type": "object",
        "properties": {
            "dest": {
                "type": "string",
            },
            "message": {
                "type": "string",  # base64-encoded mail message
            },
        },
        "required": ["dest", "message"],
    }
)


class EmailIngestionError(Exception):
    """Exception indicating ingestion failed"""
    def __init__(
        self,
        msg="Message rejected",
        *,
        email_body: Optional[str] = None,
        email_recipients: Optional[Iterable[str]] = None,
        email_attach_traceback=False,
        email_original_message: Optional[bytes]=None,
    ):
        self.msg = msg
        self.email_body = email_body
        self.email_subject = msg
        self.email_recipients = email_recipients 
        self.email_attach_traceback = email_attach_traceback
        self.email_original_message = email_original_message
        self.email_from = settings.SERVER_EMAIL
            
    @staticmethod
    def _summarize_error(error):
        frame = extract_tb(error.__traceback__)[-1]
        return dedent(f"""\
            Error details:
              Exception type: {type(error).__module__}.{type(error).__name__}
              File: {frame.filename}
              Line: {frame.lineno}""")

    def as_emailmessage(self) -> Optional[EmailMessage]:
        """Generate an EmailMessage to report an error"""
        if self.email_body is None:
            return None  
        error = self if self.__cause__ is None else self.__cause__
        format_values = dict(
            error=error,
            error_summary=self._summarize_error(error),
        )
        msg = EmailMessage()
        if self.email_recipients is None:
            msg["To"] = tuple(adm[1] for adm in settings.ADMINS) 
        else: 
            msg["To"] = self.email_recipients
        msg["From"] = self.email_from
        msg["Subject"] = self.msg
        msg.set_content(
            self.email_body.format(**format_values)
        )
        if self.email_attach_traceback:
            msg.add_attachment(
                "".join(format_exception(None, error, error.__traceback__)),
                filename="traceback.txt",
            )
        if self.email_original_message is not None:
            # Attach incoming message if it was provided. Send as a generic media
            # type because we don't know for sure that it was actually a valid
            # message.
            msg.add_attachment(
                self.email_original_message,
                'application', 'octet-stream',  # media type
                filename='original-message',
            )
        return msg


def ingest_email_handler(request, test_mode=False):
    """Ingest incoming email - handler
    
    Returns a 4xx or 5xx status code if the HTTP request was invalid or something went
    wrong while processing it. If the request was valid, returns a 200. This may or may
    not indicate that the message was accepted.
    
    If test_mode is true, actual processing of a valid message will be skipped. In this
    mode, a valid request with a valid destination will be treated as accepted. The
    "bad_dest" error may still be returned.
    """

    def _http_err(code, text):
        return HttpResponse(text, status=code, content_type="text/plain")

    def _api_response(result):
        return JsonResponse(data={"result": result})

    if request.method != "POST":
        return _http_err(405, "Method not allowed")

    if request.content_type != "application/json":
        return _http_err(415, "Content-Type must be application/json")

    # Validate
    try:
        payload = json.loads(request.body)
        _response_email_json_validator.validate(payload)
    except json.decoder.JSONDecodeError as err:
        return _http_err(400, f"JSON parse error at line {err.lineno} col {err.colno}: {err.msg}")
    except jsonschema.exceptions.ValidationError as err:
        return _http_err(400, f"JSON schema error at {err.json_path}: {err.message}")
    except Exception:
        return _http_err(400, "Invalid request format")

    try:
        message = base64.b64decode(payload["message"], validate=True)
    except binascii.Error:
        return _http_err(400, "Invalid message: bad base64 encoding")

    dest = payload["dest"]
    valid_dest = False
    try:
        if dest == "iana-review":
            valid_dest = True
            if not test_mode:
                iana_ingest_review_email(message)
        elif dest == "ipr-response":
            valid_dest = True
            if not test_mode:
                ipr_ingest_response_email(message)
        elif dest.startswith("nomcom-feedback-"):
            maybe_year = dest[len("nomcom-feedback-"):]
            if maybe_year.isdecimal():
                valid_dest = True
                if not test_mode:
                    nomcom_ingest_feedback_email(message, int(maybe_year))
    except EmailIngestionError as err:
        error_email = err.as_emailmessage()
        if error_email is not None:
            with suppress(Exception): # send_smtp logs its own exceptions, ignore them here
                send_smtp(error_email)
        return _api_response("bad_msg")

    if not valid_dest:
        return _api_response("bad_dest")

    return _api_response("ok")


@requires_api_token
@csrf_exempt
def ingest_email(request):
    """Ingest incoming email

    Hands off to ingest_email_handler() with test_mode=False. This allows @requires_api_token to
    give the test endpoint a distinct token from the real one.
    """
    return ingest_email_handler(request, test_mode=False)


@requires_api_token
@csrf_exempt
def ingest_email_test(request):
    """Ingest incoming email test endpoint
    
    Hands off to ingest_email_handler() with test_mode=True. This allows @requires_api_token to
    give the test endpoint a distinct token from the real one.
    """
    return ingest_email_handler(request, test_mode=True)
