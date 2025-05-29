# Copyright The IETF Trust 2023-2024, All Rights Reserved

import json

from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, HttpResponseNotAllowed, JsonResponse

from ietf.api.ietf_utils import requires_api_token
from ietf.doc.factories import WgDraftFactory
from ietf.doc.models import Document
from ietf.person.factories import PersonFactory
from ietf.person.models import Person


@csrf_exempt
@requires_api_token("ietf.api.views_rpc")
def create_demo_person(request):
    """Helper for creating rpc demo objects - SHOULD NOT MAKE IT INTO PRODUCTION"""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    request_params = json.loads(request.body)
    name = request_params["name"]
    person = Person.objects.filter(name=name).first() or PersonFactory(name=name)
    return JsonResponse({"user_id": person.user.pk, "person_pk": person.pk})


@csrf_exempt
@requires_api_token("ietf.api.views_rpc")
def create_demo_draft(request):
    """Helper for creating rpc demo objects - SHOULD NOT MAKE IT INTO PRODUCTION"""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    request_params = json.loads(request.body)
    name = request_params.get("name")
    rev = request_params.get("rev")
    states = request_params.get("states")
    stream_id = request_params.get("stream_id", "ietf")
    doc = None
    if not name:
        return HttpResponse(status=400, content="Name is required")
    doc = Document.objects.filter(name=name).first()
    if not doc:
        kwargs = {"name": name, "stream_id": stream_id}
        if states:
            kwargs["states"] = states
        if rev:
            kwargs["rev"] = rev
        doc = WgDraftFactory(
            **kwargs
        )  # Yes, things may be a little strange if the stream isn't IETF, but until we nned something different...
        event_type = "iesg_approved" if stream_id == "ietf" else "requested_publication"
        if not doc.docevent_set.filter(
            type=event_type
        ).exists():  # Not using get_or_create here on purpose - these are wobbly facades we're creating
            doc.docevent_set.create(
                type=event_type, by_id=1, desc="Sent off to the RPC"
            )
    return JsonResponse({"doc_id": doc.pk, "name": doc.name})
