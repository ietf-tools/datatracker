# Copyright The IETF Trust 2024, All Rights Reserved
"""DRF API Views"""

from rest_framework import mixins, permissions, viewsets

from .models import Email, Person
from .serializers import EmailSerializer, PersonSerializer


class EmailViewSet(mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Email viewset
    
    Only allows updating an existing email for now.
    """
    permission_classes = [permissions.IsAuthenticated]

    queryset = Email.objects.all()
    lookup_value_regex = '.+@.+'  # allow @-sign in the pk
    serializer_class = EmailSerializer

    def get_queryset(self):
        """Get the queryset for a specific request
        
        Limits access to Emails belonging to the current User.
        """
        if not (self.request.user.is_authenticated and hasattr(self.request.user, "person")):
            return self.queryset.none()
        return self.queryset.filter(person=self.request.user.person)


class PersonViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Person viewset"""
    permission_classes = [permissions.IsAuthenticated]

    queryset = Person.objects.all()
    serializer_class = PersonSerializer

    def get_queryset(self):
        """Get the queryset for a specific request

        Limits access to the Person belonging to the current User.
        """
        if not hasattr(self.request.user, "person"):
            return self.queryset.none()
        return self.queryset.filter(pk=self.request.user.person.pk)
