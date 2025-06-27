# Copyright The IETF Trust 2023-2025, All Rights Reserved

from drf_spectacular.utils import extend_schema_view, extend_schema
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from ietf.doc.factories import WgDraftFactory
from ietf.doc.models import Document
from ietf.person.factories import PersonFactory
from ietf.person.models import Person


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
        return Response(DemoPersonSerializer(person).data)

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
