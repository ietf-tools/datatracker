# Copyright The IETF Trust 2023-2026, All Rights Reserved

from urllib.parse import urlsplit

from django.urls import resolve as urlresolve, Resolver404


def is_ajax(request):
    """Checks whether a request was an AJAX call

    See https://docs.djangoproject.com/en/3.1/releases/3.1/#id2 - this implements the
    exact reproduction of the deprecated method suggested there.
    """
    return request.headers.get("x-requested-with") == "XMLHttpRequest"


def is_safe_next_url(url, allowed_views=None):
    """Is url a site-relative path that is safe to redirect to?

    Query string and fragment are permitted.

    An empty url is not a usable return target, so it is rejected and the caller
    falls back to its default.

    If allowed_views is given, the path must also resolve to a URL pattern whose
    name is in it.
    """
    # Require a site-relative path. Browsers treat "//host" and "/\host" as
    # scheme-relative URLs to another site.
    if not url or not url.startswith("/") or url.startswith(("//", "/\\")):
        return False
    # Browsers remove tab, CR, and LF anywhere in a URL, so "/\t/evil.example.com"
    # becomes "//evil.example.com"
    if any(c in url for c in "\t\r\n"):
        return False
    if allowed_views is not None:
        try:
            match = urlresolve(urlsplit(url).path)
        except Resolver404:
            return False
        return match.url_name in allowed_views
    return True
