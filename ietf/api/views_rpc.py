# Copyright The IETF Trust 2023-2024, All Rights Reserved

from collections import defaultdict
import json
from django.db.models.functions import Coalesce
from drf_spectacular.utils import extend_schema_view, extend_schema, OpenApiParameter
from rest_framework import serializers, viewsets, mixins
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.response import Response

from django.db.models import OuterRef, Subquery, Q, CharField
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    JsonResponse,
    HttpResponseNotAllowed,
    HttpResponseNotFound,
)
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User

from ietf.api.ietf_utils import requires_api_token
from ietf.doc.factories import WgDraftFactory  # DO NOT MERGE INTO MAIN
from ietf.doc.models import Document, DocHistory
from ietf.person.factories import PersonFactory  # DO NOT MERGE INTO MAIN
from ietf.person.models import Email, Person
from .serializers_rpc import (
    PersonBatchSerializer,
    PersonSerializer,
    FullDraftSerializer,
    DraftSerializer,
    SubmittedToQueueSerializer,
    OriginalStreamSerializer,
    DemoPersonCreateSerializer,
    DemoPersonSerializer,
    DemoDraftCreateSerializer,
    DemoDraftSerializer,
)


@extend_schema_view(
    retrieve=extend_schema(
        operation_id="get_person_by_id",
        summary="Find person by ID",
        description="Returns a single person",
    ),
    batch=extend_schema(
        operation_id="get_persons",
        summary="Get a batch of persons",
        description="returns a dict of person pks to person names",
        request=PersonBatchSerializer,
        responses=PersonSerializer(many=True),
    ),
)
class PersonViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Person.objects.all()
    serializer_class = PersonSerializer
    api_key_endpoint = "ietf.api.views_rpc"
    lookup_url_kwarg = "person_id"

    @action(detail=False, methods=["post"], serializer_class=PersonSerializer)
    def batch(self, request):
        """Get a batch of rpc person names"""
        pks = PersonBatchSerializer(request.data).data["person_ids"]
        return Response(
            self.get_serializer(Person.objects.filter(pk__in=pks), many=True).data
        )


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
                type=int,
                description="subject ID of person to return",
                location="path",
            ),
        ],
    )
    def get(self, request, subject_id: int):
        try:
            user_id = int(subject_id)
        except ValueError:
            raise Http404
        person = Person.objects.filter(user__pk=user_id).first()
        if person:
            return Response(PersonSerializer(person).data)
        raise Http404


@extend_schema_view(
    retrieve=extend_schema(
        operation_id="get_draft_by_id",
        summary="Get a draft",
        description="Returns the draft for the requested ID",
    ),
    submitted_to_rpc=extend_schema(
        operation_id="submitted_to_rpc",
        summary="List documents ready to enter the RFC Editor Queue",
        description="List documents ready to enter the RFC Editor Queue",
        responses=SubmittedToQueueSerializer(many=True),
    ),
)
class DraftViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Document.objects.filter(type_id="draft")
    serializer_class = FullDraftSerializer
    api_key_endpoint = "ietf.api.views_rpc"
    lookup_url_kwarg = "doc_id"

    @action(detail=False, serializer_class=SubmittedToQueueSerializer)
    def submitted_to_rpc(self, request):
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
        docs = (
            self.get_queryset()
            .filter(type_id="draft")
            .filter(ietf_docs | irtf_iab_ise_docs)
        )
        serializer = self.get_serializer(docs, many=True)
        return Response(serializer.data)


@extend_schema_view(
    rfc_original_stream=extend_schema(
        operation_id="get_rfc_original_streams",
        summary="Get the streams RFCs were originally published into",
        description="returns a list of dicts associating an RFC with its originally published stream",
        responses=OriginalStreamSerializer(many=True),
    )
)
class RfcViewSet(viewsets.GenericViewSet):
    queryset = Document.objects.filter(type_id="rfc")
    api_key_endpoint = "ietf.api.views_rpc"

    @action(detail=False, serializer_class=OriginalStreamSerializer)
    def rfc_original_stream(self, request):
        rfcs = self.get_queryset().annotate(
            orig_stream_id=Coalesce(
                Subquery(
                    DocHistory.objects.filter(doc=OuterRef("pk"))
                    .exclude(stream__isnull=True)
                    .order_by("time")
                    .values_list("stream_id", flat=True)[:1]
                ),
                "stream_id",
                output_field=CharField(),
            ),
        )
        serializer = self.get_serializer(rfcs, many=True)
        return Response(serializer.data)


class DraftsByNamesView(APIView):
    api_key_endpoint = "ietf.api.views_rpc"

    @extend_schema(
        operation_id="get_drafts_by_names",
        summary="Get a batch of drafts by draft names",
        description="returns a list of drafts with matching names",
        request=list[str],
        responses=DraftSerializer(many=True),
    )
    def post(self, request):
        names = request.data
        docs = Document.objects.filter(type_id="draft", name__in=names)
        return Response(DraftSerializer(docs, many=True).data)


@extend_schema_view(
    create_demo_person=extend_schema(
        operation_id="create_demo_person",
        summary="Build a datatracker Person for RPC demo purposes",
        description="returns a datatracker User id for a person created with the given name",
        request=DemoPersonCreateSerializer,
        responses=DemoPersonSerializer,
    ),
    create_demo_draft=extend_schema(
        operation_id="create_demo_draft",
        summary="Build a datatracker WG draft for RPC demo purposes",
        description="returns a datatracker document id for a draft created with the provided name and states. "
        "The arguments, if present, are passed directly to the WgDraftFactory",
        request=DemoDraftCreateSerializer,
        responses=DemoDraftSerializer,
    ),
)
class DemoViewSet(viewsets.ViewSet):
    """SHOULD NOT MAKE IT INTO PRODUCTION"""

    api_key_endpoint = "ietf.api.views_rpc"

    @action(detail=False, methods=["post"])
    def create_demo_person(self, request):
        """Helper for creating rpc demo objects - SHOULD NOT MAKE IT INTO PRODUCTION"""
        request_params = DemoPersonCreateSerializer(request.data)
        name = request_params.data["name"]
        person = Person.objects.filter(name=name).first() or PersonFactory(name=name)
        return DemoPersonSerializer(person).data

    @action(detail=False, methods=["post"])
    def create_demo_draft(self, request):
        """Helper for creating rpc demo objects - SHOULD NOT MAKE IT INTO PRODUCTION"""
        request_params = DemoDraftCreateSerializer(request.data)
        name = request_params.data["name"]
        rev = request_params.data["rev"]
        stream_id = request_params.data["stream_id"]
        states = request_params.data["states"]
        doc = Document.objects.filter(name=name).first()
        if not doc:
            kwargs = {"name": name, "stream_id": stream_id}
            if states:
                kwargs["states"] = states
            if rev:
                kwargs["rev"] = rev
            doc = WgDraftFactory(
                **kwargs
            )  # Yes, things may be a little strange if the stream isn't IETF, but until we need something different...
            event_type = (
                "iesg_approved" if stream_id == "ietf" else "requested_publication"
            )
            if not doc.docevent_set.filter(
                type=event_type
            ).exists():  # Not using get_or_create here on purpose - these are wobbly facades we're creating
                doc.docevent_set.create(
                    type=event_type, by_id=1, desc="Sent off to the RPC"
                )
        return Response(DemoDraftSerializer(doc).data)

@csrf_exempt
@requires_api_token("ietf.api.views_rpc")
def persons_by_email(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    try:
        emails = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest()
    response = []
    for email in Email.objects.filter(address__in=emails).exclude(person__isnull=True):
        response.append({
            "email": email.address,
            "person_pk": email.person.pk,
            "name": email.person.name,
            "last_name": email.person.last_name(),
            "initials": email.person.initials(),
        })
    return JsonResponse(response,safe=False)


@csrf_exempt
@requires_api_token("ietf.api.views_rpc")
def rfc_authors(request):
    """Gather authors of the RFCs with the given numbers"""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    try:
        rfc_numbers = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest()
    response = []
    for rfc in Document.objects.filter(type="rfc",rfc_number__in=rfc_numbers):
        item={"rfc_number": rfc.rfc_number, "authors": []}
        for author in rfc.authors():
            item_author=dict()
            item_author["person_pk"] = author.pk
            item_author["name"] = author.name
            item_author["last_name"] = author.last_name()
            item_author["initials"] = author.initials()
            item_author["email_addresses"] = [address.lower() for address in author.email_set.values_list("address", flat=True)]
            item["authors"].append(item_author)
        response.append(item)
    return JsonResponse(response, safe=False)
