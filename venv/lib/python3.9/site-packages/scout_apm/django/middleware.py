# coding=utf-8

from django.conf import settings
from django.urls import get_urlconf

from scout_apm.core.config import scout_config
from scout_apm.core.queue_time import track_request_queue_time
from scout_apm.core.tracked_request import TrackedRequest
from scout_apm.core.web_requests import create_filtered_path, ignore_path
from scout_apm.django.request import get_controller_name


def track_request_view_data(request, tracked_request):
    path = request.path
    tracked_request.tag(
        "path",
        create_filtered_path(
            path, [(k, v) for k, vs in request.GET.lists() for v in vs]
        ),
    )
    if ignore_path(path):
        tracked_request.tag("ignore_transaction", True)

    if scout_config.value("collect_remote_ip"):
        try:
            # Determine a remote IP to associate with the request. The value is
            # spoofable by the requester so this is not suitable to use in any
            # security sensitive context.
            user_ip = (
                request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0]
                or request.META.get("HTTP_CLIENT_IP", "").split(",")[0]
                or request.META.get("REMOTE_ADDR", None)
            )
            tracked_request.tag("user_ip", user_ip)
        except Exception:
            pass

    # Django's request.user caches in this attribute on first access. We only
    # want to track the user if the application code has touched request.user
    # because touching it causes session access, which adds "Cookie" to the
    # "Vary" header.
    user = getattr(request, "_cached_user", None)
    if user is not None:
        try:
            tracked_request.tag("username", user.get_username())
        except Exception:
            pass

    tracked_request.tag("urlconf", get_urlconf(settings.ROOT_URLCONF))


class MiddlewareTimingMiddleware(object):
    """
    Insert as early into the Middleware stack as possible (outermost layers),
    so that other middlewares called after can be timed.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not scout_config.value("monitor"):
            return self.get_response(request)

        tracked_request = TrackedRequest.instance()

        queue_time = request.META.get("HTTP_X_QUEUE_START") or request.META.get(
            "HTTP_X_REQUEST_START", ""
        )
        track_request_queue_time(queue_time, tracked_request)

        with tracked_request.span(
            operation="Middleware",
            should_capture_backtrace=False,
        ):
            return self.get_response(request)


class ViewTimingMiddleware(object):
    """
    Insert as deep into the middleware stack as possible, ideally wrapping no
    other middleware. Designed to time the View itself
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        """
        Wrap a single incoming request with start and stop calls.
        This will start timing, but relies on the process_view callback to
        capture more details about what view was really called, and other
        similar info.

        If process_view isn't called, then the request will not
        be recorded.  This can happen if a middleware further along the stack
        doesn't call onward, and instead returns a response directly.
        """
        if not scout_config.value("monitor"):
            return self.get_response(request)

        tracked_request = TrackedRequest.instance()

        # This operation name won't be recorded unless changed later in
        # process_view
        with tracked_request.span(operation="Unknown", should_capture_backtrace=False):
            response = self.get_response(request)
            track_request_view_data(request, tracked_request)
            if 500 <= response.status_code <= 599:
                tracked_request.tag("error", "true")
            return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        """
        Capture details about the view_func that is about to execute
        """
        if not scout_config.value("monitor"):
            return
        tracked_request = TrackedRequest.instance()
        tracked_request.is_real_request = True

        span = tracked_request.current_span()
        if span is not None:
            span.operation = get_controller_name(request)
            tracked_request.operation = span.operation

    def process_exception(self, request, exception):
        """
        Mark this request as having errored out

        Does not modify or catch or otherwise change the exception thrown
        """
        if not scout_config.value("monitor"):
            return
        TrackedRequest.instance().tag("error", "true")


class OldStyleMiddlewareTimingMiddleware(object):
    """
    Insert as early into the Middleware stack as possible (outermost layers),
    so that other middlewares called after can be timed.
    """

    def process_request(self, request):
        if not scout_config.value("monitor"):
            return
        tracked_request = TrackedRequest.instance()
        request._scout_tracked_request = tracked_request

        queue_time = request.META.get("HTTP_X_QUEUE_START") or request.META.get(
            "HTTP_X_REQUEST_START", ""
        )
        track_request_queue_time(queue_time, tracked_request)

        tracked_request.start_span(
            operation="Middleware", should_capture_backtrace=False
        )

    def process_response(self, request, response):
        # Only stop span if there's a request, but presume we are balanced,
        # i.e. that custom instrumentation within the application is not
        # causing errors
        tracked_request = getattr(request, "_scout_tracked_request", None)
        if tracked_request is not None:
            if 500 <= response.status_code <= 599:
                tracked_request.tag("error", "true")
            tracked_request.stop_span()
        return response


class OldStyleViewMiddleware(object):
    def process_view(self, request, view_func, view_func_args, view_func_kwargs):
        tracked_request = getattr(request, "_scout_tracked_request", None)
        if tracked_request is None:
            # Looks like OldStyleMiddlewareTimingMiddleware didn't run, so
            # don't do anything
            return

        tracked_request.is_real_request = True

        span = tracked_request.start_span(
            operation=get_controller_name(request), should_capture_backtrace=False
        )
        # Save the span into the request, so we can check
        # if we're matched up when stopping
        request._scout_view_span = span

    def process_response(self, request, response):
        tracked_request = getattr(request, "_scout_tracked_request", None)
        if tracked_request is None:
            # Looks like OldStyleMiddlewareTimingMiddleware didn't run, so
            # don't do anything
            return response

        track_request_view_data(request, tracked_request)

        # Only stop span if we started, but presume we are balanced, i.e. that
        # custom instrumentation within the application is not causing errors
        span = getattr(request, "_scout_view_span", None)
        if span is not None:
            tracked_request.stop_span()
        return response

    def process_exception(self, request, exception):
        tracked_request = getattr(request, "_scout_tracked_request", None)
        if tracked_request is None:
            # Looks like OldStyleMiddlewareTimingMiddleware didn't run, so
            # don't do anything
            return

        tracked_request.tag("error", "true")
