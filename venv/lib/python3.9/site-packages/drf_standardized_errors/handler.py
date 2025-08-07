import sys
from typing import Optional

import django
from django.conf import settings
from django.core import signals
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.utils.log import log_response
from rest_framework import exceptions
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.status import is_server_error
from rest_framework.views import set_rollback

from .formatter import ExceptionFormatter
from .settings import package_settings
from .types import ExceptionHandlerContext


def exception_handler(
    exc: Exception, context: ExceptionHandlerContext
) -> Optional[Response]:
    exception_handler_class = package_settings.EXCEPTION_HANDLER_CLASS
    msg = "`EXCEPTION_HANDLER_CLASS` should be a subclass of ExceptionHandler."
    assert issubclass(exception_handler_class, ExceptionHandler), msg
    return exception_handler_class(exc, context).run()


class ExceptionHandler:
    def __init__(self, exc: Exception, context: ExceptionHandlerContext):
        self.exc = exc
        self.context = context

    def run(self) -> Optional[Response]:
        """entrypoint for handling an exception"""
        exc = self.convert_known_exceptions(self.exc)
        if self.should_not_handle(exc):
            return None

        exc = self.convert_unhandled_exceptions(exc)
        data = self.format_exception(exc)
        self.set_rollback()
        response = self.get_response(exc, data)
        self.report_exception(exc, response)
        return response

    def convert_known_exceptions(self, exc: Exception) -> Exception:
        """
        By default, Django's built-in `Http404` and `PermissionDenied` are converted
        to their DRF equivalent.
        """
        if isinstance(exc, Http404):
            return exceptions.NotFound()
        elif isinstance(exc, PermissionDenied):
            return exceptions.PermissionDenied()
        else:
            return exc

    def should_not_handle(self, exc: Exception) -> bool:
        """
        By default, don't handle non-DRF errors in DEBUG mode. That's because
        handling the exception means the developer will not see the exception
        traceback.
        """
        return (
            getattr(settings, "DEBUG", False)
            and not package_settings.ENABLE_IN_DEBUG_FOR_UNHANDLED_EXCEPTIONS
            and not isinstance(exc, exceptions.APIException)
        )

    def convert_unhandled_exceptions(self, exc: Exception) -> exceptions.APIException:
        """
        Any non-DRF unhandled exception is converted to an APIException which
        has a 500 status code.
        """
        if not isinstance(exc, exceptions.APIException):
            # return a generic error message to avoid potentially leaking sensitive
            # data and match DRF/django behavior (same generic error message returned
            # by django.views.defaults.server_error)
            return exceptions.APIException(detail="Server Error (500)")
        else:
            return exc

    def format_exception(self, exc: exceptions.APIException) -> dict:
        exception_formatter_class = package_settings.EXCEPTION_FORMATTER_CLASS
        msg = "`EXCEPTION_FORMATTER_CLASS` should be a subclass of ExceptionFormatter."
        assert issubclass(exception_formatter_class, ExceptionFormatter), msg
        return exception_formatter_class(exc, self.context, self.exc).run()

    def set_rollback(self) -> None:
        set_rollback()

    def get_response(self, exc: exceptions.APIException, data: dict) -> Response:
        headers = self.get_headers(exc)
        return Response(data, status=exc.status_code, headers=headers)

    def get_headers(self, exc: exceptions.APIException) -> dict:
        headers = {}
        if getattr(exc, "auth_header", None):
            headers["WWW-Authenticate"] = exc.auth_header
        if getattr(exc, "wait", None):
            headers["Retry-After"] = "%d" % exc.wait
        return headers

    def report_exception(
        self, exc: exceptions.APIException, response: Response
    ) -> None:
        """
        Normally, when an exception is unhandled (non-DRF exception), DRF delegates
        handling it to Django. Django, then, takes care of returning the appropriate
        response. That is done in: django.core.handlers.exception.convert_exception_to_response

        However, this package handles all exceptions. So, to stay in line with Django's
        default behavior, the got_request_exception signal is sent and the response is
        also logged. Sending the signal should allow error monitoring tools (like Sentry)
        to work as usual (error is captured and sent to their servers).
        """
        if is_server_error(exc.status_code):
            try:
                drf_request: Request = self.context["request"]
                request = drf_request._request
            except AttributeError:
                request = None
            signals.got_request_exception.send(sender=None, request=request)
            if django.VERSION < (4, 1):
                log_response(
                    "%s: %s",
                    exc.detail,
                    getattr(request, "path", ""),
                    response=response,
                    request=request,
                    exc_info=sys.exc_info(),
                )
            else:
                log_response(
                    "%s: %s",
                    exc.detail,
                    getattr(request, "path", ""),
                    response=response,
                    request=request,
                    exception=self.exc,
                )
