# Copyright The IETF Trust 2023, All Rights Reserved

import json

from drf_spectacular.utils import extend_schema_view, extend_schema, OpenApiParameter
from rest_framework import serializers, viewsets, mixins
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.response import Response

from django.db.models import OuterRef, Subquery, Q
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    JsonResponse,
    HttpResponseNotAllowed,
    HttpResponseNotFound,
    Http404,
)
from django.views.decorators.csrf import csrf_exempt

from ietf.doc.factories import WgDraftFactory  # DO NOT MERGE INTO MAIN
from ietf.doc.models import Document, DocHistory
from ietf.person.factories import PersonFactory  # DO NOT MERGE INTO MAIN
from ietf.person.models import Person
from .ietf_utils import requires_api_token


class PersonSerializer(serializers.ModelSerializer):
    """Serializer for a Person in a response"""
    plain_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Person
        fields = ["id", "plain_name"]
    
    def get_plain_name(self, person) -> str:
        return person.plain_name()


class PersonLookupSerializer(serializers.ModelSerializer):
    """Serializer for a request looking up a person"""
    class Meta:
        model = Person
        fields = ["id"]

    def to_internal_value(self, data):
        return super().to_internal_value(data)

    def to_representation(self, instance):
        # when serializing, use the regular PersonSerializer so we get full records
        return PersonSerializer(context=self.context).to_representation(instance)


@extend_schema_view(
    retrieve=extend_schema(
        operation_id="get_person_by_id",
        summary="Find person by ID",
        description="Returns a single person",
    ),
)
class PersonViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Person.objects.all()
    serializer_class = PersonSerializer
    api_key_endpoint = "ietf.api.views_rpc"
    lookup_url_kwarg = "person_id"


class SubjectPersonView(APIView):
    api_key_endpoint = "ietf.api.views_rpc"

    @extend_schema(
        operation_id="get_subject_person_by_id",
        summary="Find person for OIDC subject by ID",
        description="Returns a single person",
        responses=PersonSerializer,
        parameters=[
            OpenApiParameter(
                name="subject_id",
                type=str,
                description="subject ID of person to return",
                location="path",
            ),
        ],
    )
    def get(self, request, subject_id: str):
        try:
            user_id = int(subject_id)
        except ValueError:
            raise serializers.ValidationError({"subject_id": "This field must be an integer value."})
        person = Person.objects.filter(user__pk=user_id).first()
        if person:
            return Response(PersonSerializer(person).data)
        raise Http404


class RpcPersonsView(APIView):
    api_key_endpoint = "ietf.api.views_rpc"
    @extend_schema(
        operation_id="get_persons",
        summary="Get a batch of persons",
        description="returns a dict of person pks to person names",
        request=list[int],
        responses=dict[str, str],
    )
    def post(self, request):
        """Get a batch of rpc person names"""
        pks = json.loads(request.body)
        response = dict()
        for p in Person.objects.filter(pk__in=pks):
            response[str(p.pk)] = p.plain_name()
        return Response(response)


def _document_source_format(doc):
    submission = doc.submission()
    if submission is None:
        return "unknown"
    if ".xml" in submission.file_types:
        if submission.xml_version == "3":
            return "xml-v3"
        else:
            return "xml-v2"
    elif ".txt" in submission.file_types:
        return "txt"
    return "unknown"

    
@csrf_exempt
@requires_api_token("ietf.api.views_rpc")
def rpc_draft(request, doc_id):
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])

    try:
        d = Document.objects.get(pk=doc_id, type_id="draft")
    except Document.DoesNotExist:
        return HttpResponseNotFound()
    return JsonResponse(
        {
            "id": d.pk,
            "name": d.name,
            "rev": d.rev,
            "stream": d.stream.slug,
            "title": d.title,
            "pages": d.pages,
            "source_format": _document_source_format(d),
            "authors": [
                {
                    "id": p.pk,
                    "plain_name": p.person.plain_name(),
                }
                for p in d.documentauthor_set.all()
            ],
            "shepherd": d.shepherd.formatted_ascii_email() if d.shepherd else "",
            "intended_std_level": (
                d.intended_std_level.slug if d.intended_std_level else ""
            ),
        }
    )

@csrf_exempt
@requires_api_token("ietf.api.views_rpc")
def drafts_by_names(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    try:
        names = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest()
    docs = Document.objects.filter(type_id="draft", name__in=names)
    response = dict()
    for doc in docs:
        response[doc.name] = {
            "id": doc.pk,
            "name": doc.name,
            "rev": doc.rev,
            "stream": doc.stream.slug if doc.stream else "none",
            "title": doc.title,
            "pages": doc.pages,
            "source_format": _document_source_format(doc),
            "authors": [
                {
                    "id": p.pk,
                    "plain_name": p.person.plain_name(),
                }
                for p in doc.documentauthor_set.all()
            ],
        }
    return JsonResponse(response)


@csrf_exempt
@requires_api_token("ietf.api.views_rpc")
def submitted_to_rpc(request):
    """Return documents in datatracker that have been submitted to the RPC but are not yet in the queue

    Those queries overreturn - there may be things, particularly not from the IETF stream that are already in the queue.
    """
    ietf_docs = Q(states__type_id="draft-iesg", states__slug__in=["ann"])
    irtf_iab_ise_docs = Q(
        states__type_id__in=[
            "draft-stream-iab",
            "draft-stream-irtf",
            "draft-stream-ise",
        ],
        states__slug__in=["rfc-edit"],
    )
    # TODO: Need a way to talk about editorial stream docs
    docs = Document.objects.filter(type_id="draft").filter(
        ietf_docs | irtf_iab_ise_docs
    )
    response = {"submitted_to_rpc": []}
    for doc in docs:
        response["submitted_to_rpc"].append(
            {
                "name": doc.name,
                "id": doc.pk,
                "stream": doc.stream_id,
                "submitted": f"{doc.sent_to_rfc_editor_event().time.isoformat()}",
            }
        )
    return JsonResponse(response)


@csrf_exempt
@requires_api_token("ietf.api.views_rpc")
def rfc_original_stream(request):
    """Return the stream that an rfc was first published into for all rfcs"""
    rfcs = Document.objects.filter(type="rfc").annotate(
        orig_stream_id=Subquery(
            DocHistory.objects.filter(doc=OuterRef("pk"))
            .exclude(stream__isnull=True)
            .order_by("time")
            .values_list("stream_id", flat=True)[:1]
        )
    )
    response = {"original_stream": []}
    for rfc in rfcs:
        response["original_stream"].append(
            {
                "rfc_number": rfc.rfc_number,
                "stream": (
                    rfc.orig_stream_id
                    if rfc.orig_stream_id is not None
                    else rfc.stream_id
                ),
            }
        )
    return JsonResponse(response)


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
