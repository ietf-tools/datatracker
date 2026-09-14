# Copyright The IETF Trust 2024, All Rights Reserved
#
from rest_framework import authentication
from django.contrib.auth.models import AnonymousUser


class ApiKeyAuthentication(authentication.BaseAuthentication):
    """API-Key header authentication"""

    def authenticate(self, request):
        """Extract the authentication token, if present
        
        This does not validate the token, it just arranges for it to be available in request.auth.
        It's up to a Permissions class to validate it for the appropriate endpoint.
        """
        token = request.META.get("HTTP_X_API_KEY", None)
        if token is None:
            return None
        return AnonymousUser(), token  # available as request.user and request.auth


class BearerTokenAuthentication(authentication.BaseAuthentication):
    """`Authorization: Token <token>` header authentication

    Same contract as ApiKeyAuthentication - the token is made available, not validated -
    for callers that were built against that header instead of X-Api-Key.

    Deliberately no authenticate_header(): supplying one would make DRF answer every
    permission failure with 401 instead of the 403 the rest of this API returns.
    """

    keyword = "Token"

    def authenticate(self, request):
        scheme, _, token = request.META.get("HTTP_AUTHORIZATION", "").partition(" ")
        if scheme.lower() != self.keyword.lower() or not token.strip():
            return None
        return AnonymousUser(), token.strip()  # available as request.user and request.auth
