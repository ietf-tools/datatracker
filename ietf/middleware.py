# Copyright The IETF Trust 2007-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from django.db import connection
from django.db.utils import OperationalError
from django.shortcuts import render
from django.http import HttpResponsePermanentRedirect
from ietf.utils.log import log, exc_parts
from ietf.utils.mail import log_smtp_exception
import re
import smtplib
import unicodedata


def sql_log_middleware(get_response):
    def sql_log(request):
        response = get_response(request)
        for q in connection.queries:
            if re.match("(update|insert)", q["sql"], re.IGNORECASE):
                log(q["sql"])
        return response

    return sql_log


class SMTPExceptionMiddleware(object):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        if isinstance(exception, smtplib.SMTPException):
            (extype, value, tb) = log_smtp_exception(exception)
            return render(
                request,
                "email_failed.html",
                {"exception": extype, "args": value, "traceback": "".join(tb)},
            )
        return None


class Utf8ExceptionMiddleware(object):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        if isinstance(exception, OperationalError):
            extype, e, tb = exc_parts()
            if e.args[0] == 1366:
                log("Database 4-byte utf8 exception: %s: %s" % (extype, e))
                return render(
                    request,
                    "utf8_4byte_failed.html",
                    {"exception": extype, "args": e.args, "traceback": "".join(tb)},
                )
        return None


def redirect_trailing_period_middleware(get_response):
    def redirect_trailing_period(request):
        response = get_response(request)
        if response.status_code == 404 and request.path.endswith("."):
            return HttpResponsePermanentRedirect(request.path.rstrip("."))
        return response

    return redirect_trailing_period


def unicode_nfkc_normalization_middleware(get_response):
    def unicode_nfkc_normalization(request):
        """Do Unicode NFKC normalization to turn ligatures into individual characters.
        This was prompted by somebody actually requesting an url for /wg/ipfix/charter
        where the 'fi' was composed of an \\ufb01 ligature...

        There are probably other elements of a request which may need this normalization
        too, but let's put that in as it comes up, rather than guess ahead.
        """
        request.META["PATH_INFO"] = unicodedata.normalize(
            "NFKC", request.META["PATH_INFO"]
        )
        request.path_info = unicodedata.normalize("NFKC", request.path_info)
        response = get_response(request)
        return response

    return unicode_nfkc_normalization


def is_authenticated_header_middleware(get_response):
    """Middleware to add an is-authenticated header to the response"""
    def add_header(request):
        response = get_response(request)
        response["X-Datatracker-Is-Authenticated"] = "yes" if request.user.is_authenticated else "no"
        return response

    return add_header
