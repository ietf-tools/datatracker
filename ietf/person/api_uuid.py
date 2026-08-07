# Copyright The IETF Trust 2026, All Rights Reserved
"""Person UUID resolution API

Lets an authorized application ask about a Person UUID it holds and learn the Person's
current identifier set. Responses carry identifiers only - no name, address or database
key.
"""
from drf_spectacular.utils import (
    OpenApiExample,
    PolymorphicProxySerializer,
    extend_schema,
)
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from ietf.person.models import Person, PersonUUID

MAX_BATCH = 500


def uuid_sets_for(person_ids):
    """Map each person_id to its (primary_uuid, [prior_uuids]) in a single query

    Keeps the batch endpoints' query count independent of the batch size: reading
    Person.primary_uuid and Person.prior_uuid per row would be two queries per Person.
    Ordering matches those accessors.
    """
    sets = {pid: (None, []) for pid in person_ids}
    rows = (
        PersonUUID.objects.filter(person_id__in=person_ids)
        .order_by("time", "uuid")
        .values_list("person_id", "uuid", "primary")
    )
    for pid, value, is_primary in rows:
        primary, priors = sets[pid]
        if is_primary:
            sets[pid] = (value, priors)
        else:
            priors.append(value)
    return sets


class PersonUUIDResolutionSerializer(serializers.Serializer):
    """A PersonUUID together with its Person's whole identifier set"""

    uuid = serializers.UUIDField(read_only=True)
    is_primary = serializers.BooleanField(source="primary", read_only=True)
    primary_uuid = serializers.UUIDField(source="person.primary_uuid", read_only=True)
    prior_uuids = serializers.ListField(
        source="person.prior_uuids", child=serializers.UUIDField(), read_only=True
    )


class ResolvedEntrySerializer(PersonUUIDResolutionSerializer):
    status = serializers.ChoiceField(choices=["resolved"], read_only=True)


class UnknownEntrySerializer(serializers.Serializer):
    uuid = serializers.UUIDField(read_only=True)
    status = serializers.ChoiceField(choices=["unknown"], read_only=True)


class PersonUUIDBatchRequestSerializer(serializers.Serializer):
    uuids = serializers.ListField(
        child=serializers.UUIDField(), allow_empty=False, max_length=MAX_BATCH
    )


class PersonUUIDBatchResponseSerializer(serializers.Serializer):
    results = serializers.ListField(
        child=PolymorphicProxySerializer(
            component_name="PersonUUIDBatchEntry",
            serializers={
                "resolved": ResolvedEntrySerializer,
                "unknown": UnknownEntrySerializer,
            },
            resource_type_field_name="status",
        ),
        read_only=True,
    )


class PersonPkBatchRequestSerializer(serializers.Serializer):
    person_pks = serializers.ListField(
        child=serializers.IntegerField(), allow_empty=False, max_length=MAX_BATCH
    )


class PersonPkResolvedEntrySerializer(serializers.Serializer):
    person_pk = serializers.IntegerField(read_only=True)
    status = serializers.ChoiceField(choices=["resolved"], read_only=True)
    primary_uuid = serializers.UUIDField(read_only=True)
    prior_uuids = serializers.ListField(child=serializers.UUIDField(), read_only=True)


class PersonPkUnknownEntrySerializer(serializers.Serializer):
    person_pk = serializers.IntegerField(read_only=True)
    status = serializers.ChoiceField(choices=["unknown"], read_only=True)


class PersonPkBatchResponseSerializer(serializers.Serializer):
    results = serializers.ListField(
        child=PolymorphicProxySerializer(
            component_name="PersonPkBatchEntry",
            serializers={
                "resolved": PersonPkResolvedEntrySerializer,
                "unknown": PersonPkUnknownEntrySerializer,
            },
            resource_type_field_name="status",
        ),
        read_only=True,
    )


@extend_schema(
    tags=["person"],
    parameters=[],
)
class PersonUUIDViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Resolve Person UUIDs to their Person's current identifier set"""

    api_key_endpoint = "ietf.person.api_uuid"
    queryset = PersonUUID.objects.select_related("person")
    serializer_class = PersonUUIDResolutionSerializer
    lookup_field = "uuid"
    lookup_url_kwarg = "uuid"
    lookup_value_converter = "anycase_uuid"

    @extend_schema(
        operation_id="person_uuid_retrieve",
        summary="Resolve a Person UUID",
        description=(
            "Resolve any UUID the datatracker has issued for a Person to that Person's "
            "current identifier set. A UUID that stopped being primary because of a "
            "merge still resolves, and the response carries the current primary. A 200 "
            "whose primary_uuid differs from the requested uuid means \"same person, new "
            "identifier\" - it is not an error.\n\n"
            "A 404 means no Person has this UUID. It does not distinguish a UUID the "
            "datatracker never issued from one it issued to a Person that has since been "
            "deleted, because deleting a Person deletes its UUIDs.\n\n"
            "primary_uuid is the person's current primary. Re-read it; do not assume it "
            "is unchanged from a previous response, and do not assume a UUID you hold "
            "remains primary.\n\n"
            "Responses contain identifiers only. No name, address or database key is "
            "returned."
        ),
        responses=PersonUUIDResolutionSerializer,
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        operation_id="person_uuid_lookup",
        summary="Resolve a batch of Person UUIDs",
        description=(
            f"Resolve up to {MAX_BATCH} UUIDs in one call. Always returns 200 with one "
            "results entry per distinct requested UUID - no entry is ever omitted and no "
            "unresolvable UUID fails the request.\n\n"
            "Each entry carries a status of resolved or unknown, corresponding to the "
            "200 and 404 outcomes of the single-UUID endpoint, and the entry's remaining "
            "fields follow from it. Switch on status; do not infer the outcome from "
            "which fields are present. Duplicate inputs produce one entry. Entry order "
            "is not significant - match on uuid."
        ),
        request=PersonUUIDBatchRequestSerializer,
        responses=PersonUUIDBatchResponseSerializer,
    )
    @action(detail=False, methods=["post"])
    def lookup(self, request):
        serializer = PersonUUIDBatchRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        requested = list(dict.fromkeys(serializer.validated_data["uuids"]))

        found = {
            row.uuid: row for row in PersonUUID.objects.filter(uuid__in=requested)
        }
        sets = uuid_sets_for({row.person_id for row in found.values()})

        results = []
        for value in requested:
            row = found.get(value)
            if row is None:
                results.append({"uuid": value, "status": "unknown"})
                continue
            primary, priors = sets[row.person_id]
            results.append(
                {
                    "uuid": value,
                    "status": "resolved",
                    "is_primary": row.primary,
                    "primary_uuid": primary,
                    "prior_uuids": priors,
                }
            )
        # Rendered as plain dicts: PersonUUIDBatchResponseSerializer is an annotation
        # helper (PolymorphicProxySerializer) and cannot serialize real responses.
        return Response({"results": results})


@extend_schema(tags=["person"])
class PersonUUIDByPersonPkViewSet(viewsets.GenericViewSet):
    """Transitional pk-to-UUID conversion, for consumers migrating off Person.pk

    Batch-only on purpose: the one legitimate use is a single bulk conversion, and a
    convenient per-request lookup would become a permanent pk-to-UUID service. Its own
    api_key_endpoint so its tokens can be withdrawn without touching the resolution API.
    """

    api_key_endpoint = "ietf.person.api_uuid_by_pk"
    queryset = Person.objects.none()
    serializer_class = PersonPkBatchRequestSerializer

    @extend_schema(
        deprecated=True,
        operation_id="person_uuid_by_person_pk",
        summary="TRANSITIONAL: resolve Person database keys to UUIDs",
        description=(
            "DEPRECATED FROM FIRST RELEASE, AND WILL BE WITHDRAWN. Resolves up to "
            f"{MAX_BATCH} Person.pk values to their UUID sets, so an application that "
            "keyed its records on the datatracker database key can convert them to "
            "UUIDs once and stop using the key. Person.pk is the identifier this whole "
            "feature exists to stop exporting: it does not survive a Person merge, "
            "which is why holding it is unsafe.\n\n"
            "Intended to be called once per consuming application, to migrate a table. "
            "Do not call it at request time and do not build anything that keeps "
            "needing it."
        ),
        request=PersonPkBatchRequestSerializer,
        responses=PersonPkBatchResponseSerializer,
        examples=[
            OpenApiExample(
                "Two pks, one of them unknown",
                value={
                    "results": [
                        {
                            "person_pk": 12345,
                            "status": "resolved",
                            "primary_uuid": "6f9a1c30-6c7e-4f0a-9a3f-2f1d0b8a4e11",
                            "prior_uuids": ["0b21f8d4-1a55-4c9e-8f77-9c2b4a6e3d02"],
                        },
                        {"person_pk": 999999, "status": "unknown"},
                    ]
                },
                response_only=True,
            )
        ],
    )
    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        requested = list(dict.fromkeys(serializer.validated_data["person_pks"]))

        existing = set(
            Person.objects.filter(pk__in=requested).values_list("pk", flat=True)
        )
        sets = uuid_sets_for(existing)

        results = []
        for pk in requested:
            if pk not in existing:
                results.append({"person_pk": pk, "status": "unknown"})
                continue
            primary, priors = sets[pk]
            results.append(
                {
                    "person_pk": pk,
                    "status": "resolved",
                    "primary_uuid": primary,
                    "prior_uuids": priors,
                }
            )
        return Response({"results": results})  # see the note in lookup() above
