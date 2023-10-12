# Copyright The IETF Trust 2023, All Rights Reserved

# This is not utils.py because Tastypie implicitly consumes ietf.api.utils.
# See ietf.api.__init__.py for details.

import debug # pyflakes: ignore

from functools import wraps
from typing import Callable, Optional, Union

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


def requires_api_token(func_or_endpoint: Optional[Union[Callable, str]] = None):
    """Validate API token before executing the wrapped method

    Usage:
        * Basic: endpoint defaults to the qualified name of the wrapped method. E.g., in ietf.api.views,

                @requires_api_token
                def my_view(request):
                    ...

            will require a token for "ietf.api.views.my_view"

        * Custom endpoint: specify the endpoint explicitly

                @requires_api_token("ietf.api.views.some_other_thing")
                def my_view(request):
                    ...

            will require a token for "ietf.api.views.some_other_thing"
    """

    def decorate(f):
        if _endpoint is None:
            fname = getattr(f, "__qualname__", None)
            if fname is None:
                raise TypeError("Cannot automatically decorate function that does not support __qualname__. Explicitly set the endpoint.")
            endpoint = "{}.{}".format(f.__module__, fname)
        else:
            endpoint = _endpoint

        @wraps(f)
        def wrapped(request, *args, **kwargs):
            authtoken = request.META.get("HTTP_X_API_KEY", None)
            if authtoken is None or not is_valid_token(endpoint, authtoken):
                return HttpResponseForbidden()
            return f(request, *args, **kwargs)

        return wrapped

    # Magic to allow decorator to be used with or without parentheses
    if callable(func_or_endpoint):
        func = func_or_endpoint
        _endpoint = None
        return decorate(func)
    else:
        _endpoint = func_or_endpoint
        return decorate
