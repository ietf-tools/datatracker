# Copyright The IETF Trust 2024, All Rights Reserved
"""DRF API Views"""

from rest_framework import mixins, permissions, viewsets

from .models import Email, Person
from .serializers import EmailSerializer, PersonSerializer


class EmailViewSet(mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Email viewset
    
    Only allows updating an existing email for now.
    """
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    
    queryset = Email.objects.all()
    serializer_class = EmailSerializer


class PersonViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Person viewset
    
    Mostly demo for now. Only allows retrieving single instances. Think hard about permissions before
    allowing write or list access.
    """
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    queryset = Person.objects.all()
    serializer_class = PersonSerializer
