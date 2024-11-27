# Copyright The IETF Trust 2024, All Rights Reserved
"""DRF API Views"""
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ietf.api.permissions import BelongsToOwnPerson, IsOwnPerson
from ietf.ietfauth.utils import send_new_email_confirmation_request

from .models import Email, Person
from .serializers import NewEmailSerializer, EmailSerializer, PersonSerializer


class EmailViewSet(mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Email viewset
    
    Only allows updating an existing email for now.
    """
    permission_classes = [IsAuthenticated & BelongsToOwnPerson]
    queryset = Email.objects.all()
    serializer_class = EmailSerializer
    lookup_value_regex = '.+@.+'  # allow @-sign in the pk


class PersonViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Person viewset"""
    permission_classes = [IsAuthenticated & IsOwnPerson]
    queryset = Person.objects.all()
    serializer_class = PersonSerializer

    @action(detail=True, methods=["post"], serializer_class=NewEmailSerializer)
    def email(self, request, pk=None):
        """Add an email address for this Person
        
        Always succeeds if the email address is valid. Causes a confirmation email to be sent to the
        requested address and completion of that handshake will actually add the email address. If the
        address already exists, an alert will be sent instead of the confirmation email.
        """
        person = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # This may or may not actually send a confirmation, but doesn't reveal that to the user.
        send_new_email_confirmation_request(person, serializer.validated_data["address"])
        return Response(serializer.data)
