# Copyright The IETF Trust 2023, All Rights Reserved

# This is not utils.py because Tastypie implicitly consumes ietf.api.utils.
# See ietf.api.__init__.py for details.

from functools import wraps

from django.conf import settings
from django.http import HttpResponseForbidden


def is_valid_token(endpoint, token):
    # This is where we would consider integration with vault
    # Settings implementation for now.
    if hasattr(settings, "APP_API_TOKENS"):
        token_store = settings.APP_API_TOKENS
        if endpoint in token_store and token in token_store[endpoint]:
            return True
    return False

def requires_api_token(endpoint):
    def decorate(f):
        @wraps(f)
        def wrapped(request, *args, **kwargs):
            authtoken = request.META.get("HTTP_X_API_KEY", None)
            if authtoken is None or not is_valid_token(endpoint, authtoken):
                return HttpResponseForbidden()
            return f(request, *args, **kwargs)
        return wrapped
    return decorate
