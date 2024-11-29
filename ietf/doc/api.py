# Copyright The IETF Trust 2024, All Rights Reserved
"""Doc API implementations"""
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.viewsets import GenericViewSet

from .models import Document
from .serializers import RfcMetadataSerializer


class RfcLimitOffsetPagination(LimitOffsetPagination):
    default_limit = 10
    max_limit = 500


class RfcViewSet(ListModelMixin, RetrieveModelMixin, GenericViewSet):
    permission_classes = []
    pagination_class = RfcLimitOffsetPagination
    queryset = Document.objects.filter(type_id="rfc").order_by("-rfc_number")
    serializer_class = RfcMetadataSerializer
