# Copyright The IETF Trust 2023-2026, All Rights Reserved

# This is not utils.py because Tastypie implicitly consumes ietf.api.utils.
# See ietf.api.__init__.py for details.
from functools import wraps
from typing import Callable, Optional, Union

from django.conf import settings
from django.core.cache import caches
from django.http import HttpResponseForbidden

from .models import AppApiToken


def cached_hashed_token_store(force_update=False):
    cache = caches["default"]
    cache_key = "ietf.api.ietf_utils.cached_hashed_token_store"
    cached_value = None if force_update else cache.get(cache_key)
    if cached_value is None:
        cached_value = AppApiToken.objects.as_hashed_token_dict()
        cache.set(cache_key, cached_value, 86400)
    return cached_value


def is_valid_token(endpoint, token):
    if token is None or token == "":
        return False

    hashed_token_store = cached_hashed_token_store()
    hashed_token = AppApiToken.hash(token)
    if endpoint in hashed_token_store and hashed_token in hashed_token_store[endpoint]:
        return True

    # Settings-based tokens
    if hasattr(settings, "APP_API_TOKENS"):
        token_store = settings.APP_API_TOKENS
        if endpoint in token_store:
            endpoint_tokens = token_store[endpoint]
            # Be sure endpoints is a list or tuple so we don't accidentally use
            # substring matching!
            if not isinstance(endpoint_tokens, (list, tuple)):
                endpoint_tokens = [endpoint_tokens]
            if token in endpoint_tokens:
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
                raise TypeError(
                    "Cannot automatically decorate function that does not support __qualname__. "
                    "Explicitly set the endpoint."
                )
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
