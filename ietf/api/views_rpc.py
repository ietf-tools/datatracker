# Copyright The IETF Trust 2023, All Rights Reserved

import json

from django.db.models import Q
from django.http import (
    HttpResponse,
    JsonResponse,
    HttpResponseNotAllowed,
    HttpResponseNotFound,
)
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt

from ietf.api.ietf_utils import requires_api_token
from ietf.doc.factories import WgDraftFactory # DO NOT MERGE INTO MAIN
from ietf.doc.models import Document
from ietf.person.factories import PersonFactory # DO NOT MERGE INTO MAIN
from ietf.person.models import Person

@csrf_exempt
@requires_api_token("ietf.api.views_rpc")
def rpc_person(request, person_id):
    person = get_object_or_404(Person, pk=person_id)
    return JsonResponse({
        "id": person.id,
        "plain_name": person.plain_name(),
    })

@csrf_exempt
@requires_api_token("ietf.api.views_rpc")
def rpc_persons(request):
    """ Get a batch of rpc person names"""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    
    pks = json.loads(request.body)
    response = dict()
    for p in Person.objects.filter(pk__in=pks):
        response[str(p.pk)] = p.plain_name()
    return JsonResponse(response)

@csrf_exempt
@requires_api_token("ietf.api.views_rpc")
def rpc_draft(request, doc_id):
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    
    try:
        d = Document.objects.get(pk=doc_id, type_id="draft")
    except Document.DoesNotExist:
        return HttpResponseNotFound()
    return JsonResponse({
        "id": d.pk,
        "name": d.name,
        "rev": d.rev,
        "stream": d.stream.slug,
        "title": d.title,
        "pages": d.pages,
        "authors": [
            {
                "id": p.pk,
                "plain_name": p.person.plain_name(),
            } for p in d.documentauthor_set.all()
        ]
    })

@csrf_exempt
@requires_api_token("ietf.api.views_rpc")
def submitted_to_rpc(request):
    """ Return documents in datatracker that have been submitted to the RPC but are not yet in the queue
    
    Those queries overreturn - there may be things, particularly not from the IETF stream that are already in the queue.
    """
    ietf_docs = Q(states__type_id="draft-iesg",states__slug__in=["ann"])
    irtf_iab_ise_docs = Q(states__type_id__in=["draft-stream-iab","draft-stream-irtf","draft-stream-ise"],states__slug__in=["rfc-edit"])
    #TODO: Need a way to talk about editorial stream docs
    docs = Document.objects.filter(type_id="draft").filter(ietf_docs|irtf_iab_ise_docs)
    response = {"submitted_to_rpc": []}
    for doc in docs:
        response["submitted_to_rpc"].append({"name":doc.name, "pk": doc.pk, "stream": doc.stream_id, "submitted": f"{doc.sent_to_rfc_editor_event().time:%Y-%m-%d}"}) #TODO reconcile timezone

    return JsonResponse(response)


@csrf_exempt
@requires_api_token("ietf.api.views_rpc")
def create_demo_person(request):
    """ Helper for creating rpc demo objects - SHOULD NOT MAKE IT INTO PRODUCTION

    """
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    
    request_params = json.loads(request.body)
    name = request_params["name"]
    person = Person.objects.filter(name=name).first() or PersonFactory(name=name)
    return JsonResponse({"user_id":person.user.pk,"person_pk":person.pk})


@csrf_exempt
@requires_api_token("ietf.api.views_rpc")
def create_demo_draft(request):
    """ Helper for creating rpc demo objects - SHOULD NOT MAKE IT INTO PRODUCTION

    """
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
        doc = WgDraftFactory(**kwargs) # Yes, things may be a little strange if the stream isn't IETF, but until we nned something different...
        event_type = "iesg_approved" if stream_id == "ietf" else "requested_publication"
        if not doc.docevent_set.filter(type=event_type).exists(): # Not using get_or_create here on purpose - these are wobbly facades we're creating
            doc.docevent_set.create(type=event_type, by_id=1, desc="Sent off to the RPC")
    return JsonResponse({ "doc_id":doc.pk, "name":doc.name })
