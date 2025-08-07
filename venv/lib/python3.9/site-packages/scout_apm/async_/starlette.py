# coding=utf-8

import wrapt
from starlette.background import BackgroundTask

import scout_apm.core
from scout_apm.core.tracked_request import TrackedRequest
from scout_apm.core.web_requests import asgi_track_request_data


class ScoutMiddleware:
    def __init__(self, app):
        self.app = app
        installed = scout_apm.core.install()
        self._do_nothing = not installed
        if installed:
            install_background_instrumentation()

    async def __call__(self, scope, receive, send):
        if self._do_nothing or scope["type"] != "http":
            return await self.app(scope, receive, send)

        tracked_request = TrackedRequest.instance()
        # Assume the request is real until we determine it's not. This is useful
        # when the asyncio instrumentation is determining if a new Task should
        # reuse the existing tracked request.
        tracked_request.is_real_request = True
        # Can't name controller until post-routing - see final clause
        controller_span = tracked_request.start_span(operation="Controller/Unknown")

        asgi_track_request_data(scope, tracked_request)

        def grab_extra_data():
            if "endpoint" in scope:
                # Rename top span
                endpoint = scope["endpoint"]
                if not hasattr(endpoint, "__qualname__"):
                    endpoint = endpoint.__class__
                controller_span.operation = "Controller/{}.{}".format(
                    endpoint.__module__,
                    endpoint.__qualname__,
                )
                tracked_request.operation = controller_span.operation
            else:
                # Mark the request as not real
                tracked_request.is_real_request = False

            # From AuthenticationMiddleware - bypass request.user because it
            # throws AssertionError if 'user' is not in Scope, and we need a
            # try/except already
            try:
                username = scope["user"].display_name
            except (KeyError, AttributeError):
                pass
            else:
                tracked_request.tag("username", username)

        async def wrapped_send(data):
            type_ = data.get("type", None)
            if type_ == "http.response.start" and 500 <= data.get("status", 200) <= 599:
                tracked_request.tag("error", "true")
            elif type_ == "http.response.body" and not data.get("more_body", False):
                # Finish HTTP span when body finishes sending, not later (e.g.
                # after background tasks)
                grab_extra_data()
                tracked_request.stop_span()
            return await send(data)

        try:
            await self.app(scope, receive, wrapped_send)
        except Exception as exc:
            tracked_request.tag("error", "true")
            raise exc
        finally:
            if tracked_request.end_time is None:
                grab_extra_data()
                tracked_request.stop_span()


background_instrumentation_installed = False


def install_background_instrumentation():
    global background_instrumentation_installed
    if background_instrumentation_installed:
        return
    background_instrumentation_installed = True

    @wrapt.decorator
    async def wrapped_background_call(wrapped, instance, args, kwargs):
        tracked_request = TrackedRequest.instance()
        tracked_request.is_real_request = True

        operation = "Job/{}.{}".format(
            instance.func.__module__, instance.func.__qualname__
        )
        tracked_request.operation = operation
        with tracked_request.span(operation=operation):
            return await wrapped(*args, **kwargs)

    BackgroundTask.__call__ = wrapped_background_call(BackgroundTask.__call__)
