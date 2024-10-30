# Copyright The IETF Trust 2024, All Rights Reserved
"""DRF API Views"""

from rest_framework import mixins, permissions, viewsets

from .models import Person
from .serializers import PersonSerializer

class PersonViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Person viewset
    
    Mostly demo for now. Only allows retrieving single instances. Think hard about permissions before
    allowing write or list access.
    """
    permission_classes = [permissions.AllowAny]

    queryset = Person.objects.all()
    serializer_class = PersonSerializer
