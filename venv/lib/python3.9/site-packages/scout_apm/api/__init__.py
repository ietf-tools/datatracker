# coding=utf-8

import sys

import scout_apm.core
from scout_apm.compat import ContextDecorator, text
from scout_apm.core.config import ScoutConfig
from scout_apm.core.error import ErrorMonitor
from scout_apm.core.tracked_request import TrackedRequest

# The async_ module can only be shipped on Python 3.6+
try:
    from scout_apm.async_.api import AsyncDecoratorMixin
except ImportError:

    class AsyncDecoratorMixin(object):
        pass


__all__ = [
    "BackgroundTransaction",
    "Config",
    "Context",
    "Error",
    "WebTransaction",
    "install",
    "instrument",
]


class Context(object):
    @classmethod
    def add(self, key, value):
        """Adds context to the currently executing request.

        :key: Any String identifying the request context.
              Example: "user_ip", "plan", "alert_count"
        :value: Any json-serializable type.
              Example: "1.1.1.1", "free", 100
        :returns: nothing.
        """
        TrackedRequest.instance().tag(key, value)


class Config(ScoutConfig):
    pass


install = scout_apm.core.install


def ignore_transaction():
    TrackedRequest.instance().tag("ignore_transaction", True)


class instrument(AsyncDecoratorMixin, ContextDecorator):
    def __init__(self, operation, kind="Custom", tags=None):
        self.operation = text(kind) + "/" + text(operation)
        if tags is None:
            self.tags = {}
        else:
            self.tags = tags

    def __enter__(self):
        tracked_request = TrackedRequest.instance()
        self.span = tracked_request.start_span(operation=self.operation)
        for key, value in self.tags.items():
            self.tag(key, value)
        return self

    def __exit__(self, *exc):
        tracked_request = TrackedRequest.instance()
        tracked_request.stop_span()
        return False

    def tag(self, key, value):
        if self.span is not None:
            self.span.tag(key, value)


class Transaction(AsyncDecoratorMixin, ContextDecorator):
    """
    This Class is not meant to be used directly.
    Use one of the subclasses
    (WebTransaction or BackgroundTransaction)
    """

    def __init__(self, name, tags=None):
        self.name = text(name)
        if tags is None:
            self.tags = {}
        else:
            self.tags = tags

    @classmethod
    def start(cls, kind, name, tags=None):
        operation = text(kind) + "/" + text(name)

        tracked_request = TrackedRequest.instance()
        tracked_request.operation = operation
        tracked_request.is_real_request = True
        span = tracked_request.start_span(
            operation=operation, should_capture_backtrace=False
        )
        if tags is not None:
            for key, value in tags.items():
                tracked_request.tag(key, value)
        return span

    @classmethod
    def stop(cls):
        tracked_request = TrackedRequest.instance()
        tracked_request.stop_span()
        return True

    # __enter__ must be defined by child classes.

    # *exc is any exception raised. Ignore that
    def __exit__(self, *exc):
        WebTransaction.stop()
        return False

    def tag(self, key, value):
        if self.span is not None:
            self.span.tag(key, value)


class WebTransaction(Transaction):
    @classmethod
    def start(cls, name, tags=None):
        super(WebTransaction, cls).start("Controller", text(name), tags)

    def __enter__(self):
        super(WebTransaction, self).start("Controller", self.name, self.tags)


class BackgroundTransaction(Transaction):
    @classmethod
    def start(cls, name, tags=None):
        super(BackgroundTransaction, cls).start("Job", text(name), tags)

    def __enter__(self):
        super(BackgroundTransaction, self).start("Job", self.name, self.tags)


def rename_transaction(name):
    if name is not None:
        tracked_request = TrackedRequest.instance()
        tracked_request.tag("transaction.name", name)


class Error(object):
    @classmethod
    def capture(
        cls,
        exception,
        request_path=None,
        request_params=None,
        session=None,
        custom_controller=None,
        custom_params=None,
    ):
        """
        Capture the exception manually.

        Utilizes sys.exc_info to gather the traceback. This has the side
        effect that if another exception is raised before calling
        ``Error.capture``, the traceback will match the most recently
        raised exception.

        Includes any context added for the TrackedRequest.

        :exception: Any exception.
        :request_path: Any String identifying the relative path of the request.
              Example: "/hello-world/"
        :request_params: Any json-serializable dict representing the
              querystring parameters.
              Example: {"page": 1}
        :session: Any json-serializable dict representing the
              request session.
              Example: {"step": 0}
        :custom_controller: Any String identifying the controller or job.
              Example: "send_email"
        :custom_params: Any json-serializable dict.
              Example: {"to": "scout@test.com", "from": "no-reply@test.com"}
        :returns: nothing.
        """
        if isinstance(exception, Exception):
            exc_info = (exception.__class__, exception, sys.exc_info()[2])
            ErrorMonitor.send(
                exc_info,
                request_path=request_path,
                request_params=request_params,
                session=session,
                custom_controller=custom_controller,
                custom_params=custom_params,
            )
