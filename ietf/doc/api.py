# Copyright The IETF Trust 2024, All Rights Reserved
"""Doc API implementations"""
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from rest_framework.viewsets import GenericViewSet

from .models import Document
from .serializers import RfcMetadataSerializer


class RfcViewSet(ListModelMixin, RetrieveModelMixin, GenericViewSet):
    permission_classes = []
    queryset = Document.objects.filter(type_id="rfc")
    serializer_class = RfcMetadataSerializer
