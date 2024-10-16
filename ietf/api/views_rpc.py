# Copyright The IETF Trust 2023, All Rights Reserved

import datetime
import json
from typing import Literal, Optional

from dill import extend
from django.db.models.functions import Coalesce
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_view, extend_schema, OpenApiParameter, extend_schema_field
from rest_framework import serializers, viewsets, mixins
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.response import Response

from django.db.models import OuterRef, Subquery, Q, CharField
from django.http import (
    HttpResponse,
    JsonResponse,
    HttpResponseNotAllowed,
    Http404,
)
from django.views.decorators.csrf import csrf_exempt

from ietf.doc.factories import WgDraftFactory  # DO NOT MERGE INTO MAIN
from ietf.doc.models import Document, DocHistory, DocumentAuthor
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
    batch=extend_schema(
        operation_id="get_persons",
        summary="Get a batch of persons",
        description="returns a dict of person pks to person names",
        request=list[int],
        responses=PersonSerializer(many=True),
    )
)
class PersonViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Person.objects.all()
    serializer_class = PersonSerializer
    api_key_endpoint = "ietf.api.views_rpc"
    lookup_url_kwarg = "person_id"

    @action(detail=False, methods=["post"], serializer_class=PersonSerializer)
    def batch(self, request):
        """Get a batch of rpc person names"""
        pks = json.loads(request.data)
        return Response(self.get_serializer(Person.objects.filter(pk__in=pks), many=True).data)


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


class DocumentAuthorSerializer(serializers.ModelSerializer):
    """Serializer for a Person in a response"""
    plain_name = serializers.SerializerMethodField()

    class Meta:
        model = DocumentAuthor
        fields = ["person", "plain_name"]

    def get_plain_name(self, document_author: DocumentAuthor) -> str:
        return document_author.person.plain_name()
        

class FullDraftSerializer(serializers.ModelSerializer):
    source_format = serializers.SerializerMethodField()
    authors = DocumentAuthorSerializer(many=True, source="documentauthor_set")
    shepherd = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            "id",
            "name",
            "rev",
            "stream",
            "title",
            "pages",
            "source_format",
            "authors",
            "shepherd",
            "intended_std_level",
        ]

    def get_source_format(self, doc: Document) -> Literal["unknown", "xml-v2", "xml-v3", "txt"]:
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

    @extend_schema_field(OpenApiTypes.EMAIL)
    def get_shepherd(self, doc: Document) -> str:
        if doc.shepherd:
           return doc.shepherd.formatted_ascii_email()
        return ""


class DraftSerializer(FullDraftSerializer):
    class Meta:
        model = Document
        fields = [
            "id",
            "name",
            "rev",
            "stream",
            "title",
            "pages",
            "source_format",
            "authors",
        ]


class SubmittedToQueueSerializer(FullDraftSerializer):
    submitted = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            "id",
            "name",
            "stream",
            "submitted",
        ]


    def get_submitted(self, doc) -> Optional[datetime.datetime]:
        event = doc.sent_to_rfc_editor_event()
        return None if event is None else event.time


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
    )
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
        docs = self.get_queryset().filter(type_id="draft").filter(
            ietf_docs | irtf_iab_ise_docs
        )
        serializer = self.get_serializer(docs, many=True)
        return Response(serializer.data)


class OriginalStreamSerializer(serializers.ModelSerializer):
    stream = serializers.CharField(read_only=True, source="orig_stream_id")

    class Meta:
        model = Document
        fields = ["rfc_number", "stream"]


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
        responses=DraftSerializer(many=True)
    )
    def post(self, request):
        names = request.data
        docs = Document.objects.filter(type_id="draft", name__in=names)
        return Response(DraftSerializer(docs, many=True).data)


class DemoPersonCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)


class DemoPersonSerializer(serializers.ModelSerializer):
    person_pk = serializers.IntegerField(source="pk")

    class Meta:
        model = Person
        fields = ["user_id", "person_pk"]


class DemoDraftCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=True)
    stream_id = serializers.CharField(default="ietf")
    rev = serializers.CharField(default=None)
    states = serializers.DictField(child=serializers.CharField(), default=None)


class DemoDraftSerializer(serializers.ModelSerializer):
    doc_id = serializers.IntegerField(source="pk")

    class Meta:
        model = Document
        fields = ["doc_id", "name"]

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
            event_type = "iesg_approved" if stream_id == "ietf" else "requested_publication"
            if not doc.docevent_set.filter(
                type=event_type
            ).exists():  # Not using get_or_create here on purpose - these are wobbly facades we're creating
                doc.docevent_set.create(
                    type=event_type, by_id=1, desc="Sent off to the RPC"
                )
        return Response(DemoDraftSerializer(doc).data)
