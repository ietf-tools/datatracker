# coding=utf-8

import logging
import os

from scout_apm.core.backtrace import capture_stacktrace
from scout_apm.core.config import scout_config
from scout_apm.core.error_service import ErrorServiceThread
from scout_apm.core.tracked_request import TrackedRequest
from scout_apm.core.web_requests import RequestComponents, filter_element

logger = logging.getLogger(__name__)


class ErrorMonitor(object):
    @classmethod
    def send(
        cls,
        exc_info,
        request_components=None,
        request_path=None,
        request_params=None,
        session=None,
        environment=None,
        custom_controller=None,
        custom_params=None,
    ):
        if not scout_config.value("errors_enabled"):
            return

        exc_class, exc_value, traceback = exc_info

        ignore_exceptions = scout_config.value("errors_ignored_exceptions")
        if ignore_exceptions and isinstance(exc_value, tuple(ignore_exceptions)):
            return

        tracked_request = TrackedRequest.instance()

        context = {}
        context.update(tracked_request.tags)

        if custom_params:
            context["custom_params"] = custom_params

        if custom_controller:
            if request_components:
                request_components.controller = custom_controller
            else:
                request_components = RequestComponents(
                    module=None, controller=custom_controller, action=None
                )

        scm_subdirectory = scout_config.value("scm_subdirectory")
        error = {
            "exception_class": exc_class.__name__,
            "message": str(exc_value),
            "request_id": tracked_request.request_id,
            "request_uri": request_path,
            "request_params": filter_element("", request_params)
            if request_params
            else None,
            "request_session": filter_element("", session) if session else None,
            "environment": filter_element("", environment) if environment else None,
            "trace": [
                "{file}:{line}:in {function}".format(
                    file=os.path.join(scm_subdirectory, frame["file"])
                    if scm_subdirectory
                    else frame["file"],
                    line=frame["line"],
                    function=frame["function"],
                )
                for frame in capture_stacktrace(traceback)
            ],
            "request_components": {
                "module": request_components.module,
                "controller": request_components.controller,
                "action": request_components.action,
            }
            if request_components
            else None,
            "context": context,
            "host": scout_config.value("hostname"),
            "revision_sha": scout_config.value("revision_sha"),
        }

        if scout_config.value("log_payload_content"):
            logger.debug(
                "Sending error for request: %s. Payload: %r",
                tracked_request.request_id,
                error,
            )
        else:
            logger.debug("Sending error for request: %s.", tracked_request.request_id)

        ErrorServiceThread.send(error=error)
