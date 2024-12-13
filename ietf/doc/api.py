# Copyright The IETF Trust 2024, All Rights Reserved
"""Doc API implementations"""
from django.db.models import OuterRef, Subquery, Prefetch
from django.db.models.functions import TruncDate
from django_filters import rest_framework as filters
from rest_framework import filters as drf_filters
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import BasePermission
from rest_framework.viewsets import GenericViewSet

from ietf.group.models import Group
from ietf.name.models import StreamName
from ietf.utils.timezone import RPC_TZINFO
from .models import Document, DocEvent, RelatedDocument
from .serializers import RfcMetadataSerializer, RfcStatus


class RfcLimitOffsetPagination(LimitOffsetPagination):
    default_limit = 10
    max_limit = 500


class RfcFilter(filters.FilterSet):
    published = filters.DateFromToRangeFilter()
    stream = filters.ModelMultipleChoiceFilter(
        queryset=StreamName.objects.filter(used=True)
    )
    group = filters.ModelMultipleChoiceFilter(
        queryset=Group.objects.wgs(),
        field_name="group__acronym",
        to_field_name="acronym",
    )
    area = filters.ModelMultipleChoiceFilter(
        queryset=Group.objects.areas(),
        field_name="group__parent__acronym",
        to_field_name="acronym",
    )
    status = filters.MultipleChoiceFilter(
        choices=[(slug, slug) for slug in RfcStatus.status_slugs],
        method=RfcStatus.filter,
    )
    sort = filters.OrderingFilter(
        fields=(
            ("rfc_number", "number"),  # ?sort=number / ?sort=-number
            ("published", "published"),  # ?sort=published / ?sort=-published
        ),
    )


class RfcViewSet(ListModelMixin, RetrieveModelMixin, GenericViewSet):
    permission_classes: list[BasePermission] = []
    queryset = (
        Document.objects.filter(type_id="rfc")
        .annotate(
            published_datetime=Subquery(
                DocEvent.objects.filter(
                    doc_id=OuterRef("pk"),
                    type="published_rfc",
                )
                .order_by("-time")
                .values("time")[:1]
            ),
        )
        .annotate(published=TruncDate("published_datetime", tzinfo=RPC_TZINFO))
        .order_by("-rfc_number")
        .prefetch_related(
            Prefetch(
                "targets_related",  # relationship to follow
                queryset=RelatedDocument.objects.filter(
                    source__type_id="rfc", relationship_id="obs"
                ),
                to_attr="obsoleted_by",  # attr to add to queryset instances
            ),
            Prefetch(
                "targets_related",  # relationship to follow
                queryset=RelatedDocument.objects.filter(
                    source__type_id="rfc", relationship_id="updates"
                ),
                to_attr="updated_by",  # attr to add to queryset instances
            ),
        )
    )  # default ordering - RfcFilter may override

    serializer_class = RfcMetadataSerializer
    pagination_class = RfcLimitOffsetPagination
    filter_backends = [filters.DjangoFilterBackend, drf_filters.SearchFilter]
    filterset_class = RfcFilter
    search_fields = ["title", "abstract"]
