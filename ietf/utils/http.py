# Copyright The IETF Trust 2023-2024, All Rights Reserved
# -*- coding: utf-8 -*-

from django.urls import resolve as urlresolve, Resolver404

def is_ajax(request):
    """Checks whether a request was an AJAX call

    See https://docs.djangoproject.com/en/3.1/releases/3.1/#id2 - this implements the
    exact reproduction of the deprecated method suggested there.
    """
    return request.headers.get("x-requested-with") == "XMLHttpRequest"

def validate_return_to_path(path, get_default_path, allowed_path_handlers):
    if path is None:
        path = get_default_path()

    # we need to ensure the path isn't used for attacks (eg phishing).
    # `path` can be used in HttpResponseRedirect() which could redirect to Datatracker or offsite.
    # Eg http://datatracker.ietf.org/...?ballot_edit_return_point=https://example.com/phish
    # offsite links could be phishing attempts so let's reject them all, and require valid Datatracker
    # routes
    try:
        # urlresolve will throw if the url doesn't match a route known to Django
        match = urlresolve(path)                
        # further restrict by whether it's in the list of valid routes to prevent
        # (eg) redirecting to logout
        if match.url_name not in allowed_path_handlers:
            raise ValueError("Invalid return to path not among valid matches")
        pass
    except Resolver404:
        raise ValueError("Invalid return to path doesn't match a route")

    return path
