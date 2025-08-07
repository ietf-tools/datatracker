# coding=utf-8

import logging
import sys

import wrapt
from flask import current_app
from flask.globals import request, session

import scout_apm.core
from scout_apm.core.config import scout_config
from scout_apm.core.error import ErrorMonitor
from scout_apm.core.tracked_request import TrackedRequest
from scout_apm.core.web_requests import RequestComponents, werkzeug_track_request_data

logger = logging.getLogger(__name__)


class ScoutApm(object):
    def __init__(self, app):
        self.app = app
        self._attempted_install = False
        app.full_dispatch_request = self.wrapped_full_dispatch_request(
            app.full_dispatch_request
        )
        app.preprocess_request = self.wrapped_preprocess_request(app.preprocess_request)

    @wrapt.decorator
    def wrapped_full_dispatch_request(self, wrapped, instance, args, kwargs):
        if not self._attempted_install:
            self.extract_flask_settings()
            installed = scout_apm.core.install()
            self._do_nothing = not installed
            self._attempted_install = True

        if self._do_nothing:
            return wrapped(*args, **kwargs)

        # Pass on routing exceptions (normally 404's)
        if request.routing_exception is not None:
            return wrapped(*args, **kwargs)

        request_components = get_request_components(self.app, request)
        operation = "Controller/{}.{}".format(
            request_components.module, request_components.controller
        )

        tracked_request = TrackedRequest.instance()
        tracked_request.is_real_request = True
        tracked_request.operation = operation
        request._scout_tracked_request = tracked_request

        werkzeug_track_request_data(request, tracked_request)

        with tracked_request.span(
            operation=operation, should_capture_backtrace=False
        ) as span:
            request._scout_view_span = span

            try:
                response = wrapped(*args, **kwargs)
            except Exception as exc:
                tracked_request.tag("error", "true")
                if scout_config.value("errors_enabled"):
                    ErrorMonitor.send(
                        sys.exc_info(),
                        request_components=get_request_components(self.app, request),
                        request_path=request.path,
                        request_params=dict(request.args.lists()),
                        session=dict(session.items()),
                        environment=self.app.config,
                    )
                raise exc
            else:
                if 500 <= response.status_code <= 599:
                    tracked_request.tag("error", "true")
                return response

    @wrapt.decorator
    def wrapped_preprocess_request(self, wrapped, instance, args, kwargs):
        tracked_request = getattr(request, "_scout_tracked_request", None)
        if tracked_request is None:
            return wrapped(*args, **kwargs)

        # Unlike middleware in other frameworks, using request preprocessors is
        # less common in Flask, so only add a span if there is any in use
        have_before_request_funcs = (
            None in instance.before_request_funcs
            or request.blueprint in instance.before_request_funcs
        )
        if not have_before_request_funcs:
            return wrapped(*args, **kwargs)

        with tracked_request.span("PreprocessRequest", should_capture_backtrace=False):
            return wrapped(*args, **kwargs)

    def extract_flask_settings(self):
        """
        Copies SCOUT_* settings in the app into Scout's config lookup
        """
        configs = {}
        configs["application_root"] = self.app.instance_path
        for name in current_app.config:
            if name.startswith("SCOUT_"):
                value = current_app.config[name]
                clean_name = name.replace("SCOUT_", "").lower()
                configs[clean_name] = value
        scout_config.set(**configs)


def get_request_components(app, request):
    view_func = app.view_functions[request.endpoint]
    request_components = RequestComponents(
        module=view_func.__module__,
        controller=view_func.__name__,
        action=request.method,
    )
    return request_components
