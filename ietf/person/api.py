# Copyright The IETF Trust 2024, All Rights Reserved
"""DRF API Views"""
from rest_framework import mixins, viewsets

from ietf.api.permissions import BelongsToOwnPerson, IsOwnPerson

from .models import Email, Person
from .serializers import EmailSerializer, PersonSerializer


class EmailViewSet(mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Email viewset
    
    Only allows updating an existing email for now.
    """
    permission_classes = [BelongsToOwnPerson]
    queryset = Email.objects.all()
    serializer_class = EmailSerializer
    lookup_value_regex = '.+@.+'  # allow @-sign in the pk


class PersonViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Person viewset"""
    permission_classes = [IsOwnPerson]
    queryset = Person.objects.all()
    serializer_class = PersonSerializer
