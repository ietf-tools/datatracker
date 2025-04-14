# Copyright The IETF Trust 2007, All Rights Reserved

import sys
import django
from django.conf import settings
from django.utils import timezone
from ietf import __version__, __patch__, __release_branch__, __release_hash__


def server_mode(request):
    return {"server_mode": settings.SERVER_MODE}


def rfcdiff_base_url(request):
    return {"rfcdiff_base_url": settings.RFCDIFF_BASE_URL}


def python_version():
    v = sys.version_info
    return "%s.%s.%s" % (
        v.major,
        v.minor,
        v.micro,
    )


def revision_info(request):
    return {
        "version_num": __version__,
        "patch": __patch__,
        "branch": __release_branch__,
        "git_hash": __release_hash__,
        "django_version": django.get_version(),
        "python_version": python_version(),
        "bugreport_email": settings.BUG_REPORT_EMAIL,
    }


def debug_mark_queries_from_view(request):
    "Marks the queries which has occurred so far as coming from a view."
    context_extras = {}
    if settings.DEBUG and request.META.get("REMOTE_ADDR") in settings.INTERNAL_IPS:
        from django.db import connection

        for query in connection.queries:
            query["loc"] = "V"  # V is for 'view'
    return context_extras


def sql_debug(request):
    if settings.DEBUG and request.META.get("REMOTE_ADDR") in settings.INTERNAL_IPS:
        return {"sql_debug": True}
    else:
        return {"sql_debug": False}


def settings_info(request):
    return {
        "settings": settings,
    }


def timezone_now(request):
    return {
        "timezone_now": timezone.now(),
    }
