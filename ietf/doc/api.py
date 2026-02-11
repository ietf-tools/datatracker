# Copyright The IETF Trust 2024-2026, All Rights Reserved
"""Doc API implementations"""

from django.db.models import (
    BooleanField,
    Count,
    JSONField,
    OuterRef,
    Prefetch,
    Q,
    QuerySet,
    Subquery,
    Value,
)
from django.db.models.functions import TruncDate
from django_filters import rest_framework as filters
from rest_framework import filters as drf_filters
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.viewsets import GenericViewSet

from ietf.group.models import Group
from ietf.name.models import StreamName, DocTypeName
from ietf.utils.timezone import RPC_TZINFO
from .models import (
    Document,
    DocEvent,
    RelatedDocument,
    DocumentAuthor,
    SUBSERIES_DOC_TYPE_IDS,
)
from .serializers import (
    RfcMetadataSerializer,
    RfcStatus,
    RfcSerializer,
    SubseriesDocSerializer,
)


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


class PrefetchRelatedDocument(Prefetch):
    """Prefetch via a RelatedDocument

    Prefetches following RelatedDocument relationships to other docs. By default, includes
    those for which the current RFC is the `source`. If `reverse` is True, includes those
    for which it is the `target` instead. Defaults to only "rfc" documents.
    """

    @staticmethod
    def _get_queryset(relationship_id, reverse, doc_type_ids):
        """Get queryset to use for the prefetch"""
        if isinstance(doc_type_ids, str):
            doc_type_ids = (doc_type_ids,)

        return RelatedDocument.objects.filter(
            **{
                "relationship_id": relationship_id,
                f"{'source' if reverse else 'target'}__type_id__in": doc_type_ids,
            }
        ).select_related("source" if reverse else "target")

    def __init__(self, to_attr, relationship_id, reverse=False, doc_type_ids="rfc"):
        super().__init__(
            lookup="targets_related" if reverse else "relateddocument_set",
            queryset=self._get_queryset(relationship_id, reverse, doc_type_ids),
            to_attr=to_attr,
        )


def augment_rfc_queryset(queryset: QuerySet[Document]):
    return (
        queryset.select_related("std_level", "stream")
        .prefetch_related(
            Prefetch(
                "group",
                Group.objects.select_related("parent"),
            ),
            Prefetch(
                "documentauthor_set",
                DocumentAuthor.objects.select_related("email", "person"),
            ),
            PrefetchRelatedDocument(
                to_attr="drafts",
                relationship_id="became_rfc",
                doc_type_ids="draft",
                reverse=True,
            ),
            PrefetchRelatedDocument(to_attr="obsoletes", relationship_id="obs"),
            PrefetchRelatedDocument(
                to_attr="obsoleted_by", relationship_id="obs", reverse=True
            ),
            PrefetchRelatedDocument(to_attr="updates", relationship_id="updates"),
            PrefetchRelatedDocument(
                to_attr="updated_by", relationship_id="updates", reverse=True
            ),
            PrefetchRelatedDocument(
                to_attr="subseries",
                relationship_id="contains",
                reverse=True,
                doc_type_ids=SUBSERIES_DOC_TYPE_IDS,
            ),
        )
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
        .annotate(
            # Count of "verified-errata" tags will be 1 or 0, convert to Boolean
            has_errata=Count(
                "tags",
                filter=Q(
                    tags__slug="verified-errata",
                ),
                output_field=BooleanField(),
            )
        )
        .annotate(
            # TODO implement these fake fields for real
            see_also=Value([], output_field=JSONField()),
            keywords=Value(["keyword"], output_field=JSONField()),
        )
    )


class RfcViewSet(ListModelMixin, RetrieveModelMixin, GenericViewSet):
    api_key_endpoint = "ietf.api.red_api"  # matches prefix in ietf/api/urls.py
    lookup_field = "rfc_number"
    queryset = augment_rfc_queryset(
        Document.objects.filter(type_id="rfc", rfc_number__isnull=False)
    ).order_by("-rfc_number")

    pagination_class = RfcLimitOffsetPagination
    filter_backends = [filters.DjangoFilterBackend, drf_filters.SearchFilter]
    filterset_class = RfcFilter
    search_fields = ["title", "abstract"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return RfcSerializer
        return RfcMetadataSerializer


class PrefetchSubseriesContents(Prefetch):
    def __init__(self, to_attr):
        super().__init__(
            lookup="relateddocument_set",
            queryset=RelatedDocument.objects.filter(
                relationship_id="contains",
                target__type_id="rfc",
            ).prefetch_related(
                Prefetch(
                    "target",
                    queryset=augment_rfc_queryset(Document.objects.all()),
                )
            ),
            to_attr=to_attr,
        )


class SubseriesFilter(filters.FilterSet):
    type = filters.ModelMultipleChoiceFilter(
        queryset=DocTypeName.objects.filter(pk__in=SUBSERIES_DOC_TYPE_IDS)
    )


class SubseriesViewSet(ListModelMixin, RetrieveModelMixin, GenericViewSet):
    api_key_endpoint = "ietf.api.red_api"  # matches prefix in ietf/api/urls.py
    lookup_field = "name"
    serializer_class = SubseriesDocSerializer
    queryset = Document.objects.subseries_docs().prefetch_related(
        PrefetchSubseriesContents(to_attr="contents")
    )
    filter_backends = [filters.DjangoFilterBackend]
    filterset_class = SubseriesFilter
