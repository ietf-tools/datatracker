# Copyright The IETF Trust 2024, All Rights Reserved
"""Doc API implementations"""
from django.db.models import OuterRef, Subquery
from django.db.models.functions import TruncDate
from django_filters import rest_framework as filters
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.viewsets import GenericViewSet

from ietf.utils.timezone import RPC_TZINFO
from .models import Document, DocEvent
from .serializers import RfcMetadataSerializer
from ..name.models import StreamName


class RfcLimitOffsetPagination(LimitOffsetPagination):
    default_limit = 10
    max_limit = 500


class RfcFilter(filters.FilterSet):
    published = filters.DateFromToRangeFilter()
    stream = filters.ModelMultipleChoiceFilter(queryset=StreamName.objects.filter(used=True))


class RfcViewSet(ListModelMixin, RetrieveModelMixin, GenericViewSet):
    permission_classes = []
    queryset = Document.objects.filter(
        type_id="rfc"
    ).annotate(
        published_datetime=Subquery(
            DocEvent.objects.filter(
                doc_id=OuterRef("pk"),
                type="published_rfc",
            ).order_by("-time").values("time")[:1]
        ),
    ).annotate(
        published=TruncDate("published_datetime", tzinfo=RPC_TZINFO)
    ).order_by("-rfc_number")

    serializer_class = RfcMetadataSerializer
    pagination_class = RfcLimitOffsetPagination
    filter_backends = [filters.DjangoFilterBackend]
    filterset_class = RfcFilter
