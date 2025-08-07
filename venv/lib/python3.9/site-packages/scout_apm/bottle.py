# coding=utf-8

import wrapt
from bottle import request, response

import scout_apm.core
from scout_apm.core.config import scout_config
from scout_apm.core.queue_time import track_request_queue_time
from scout_apm.core.tracked_request import TrackedRequest
from scout_apm.core.web_requests import create_filtered_path, ignore_path


class ScoutPlugin(object):
    def __init__(self):
        self.name = "scout"
        self.api = 2

    def set_config_from_bottle(self, app):
        bottle_configs = {}
        prefix = "scout."
        prefix_len = len(prefix)
        for key, value in app.config.items():
            if key.startswith(prefix) and len(key) > prefix_len:
                scout_key = key[prefix_len:]
                bottle_configs[scout_key] = value
        scout_config.set(**bottle_configs)

    def setup(self, app):
        self.set_config_from_bottle(app)
        installed = scout_apm.core.install()
        self._do_nothing = not installed

    def apply(self, callback, context):
        if self._do_nothing:
            return callback
        return wrap_callback(callback)


@wrapt.decorator
def wrap_callback(wrapped, instance, args, kwargs):
    tracked_request = TrackedRequest.instance()
    tracked_request.is_real_request = True

    path = request.path
    # allitems() is an undocumented bottle internal
    tracked_request.tag("path", create_filtered_path(path, request.query.allitems()))
    if ignore_path(path):
        tracked_request.tag("ignore_transaction", True)

    if request.route.name is not None:
        controller_name = request.route.name
    else:
        controller_name = request.route.rule
    if controller_name == "/":
        controller_name = "/home"
    if not controller_name.startswith("/"):
        controller_name = "/" + controller_name

    if scout_config.value("collect_remote_ip"):
        # Determine a remote IP to associate with the request. The
        # value is spoofable by the requester so this is not suitable
        # to use in any security sensitive context.
        user_ip = (
            request.headers.get("x-forwarded-for", "").split(",")[0]
            or request.headers.get("client-ip", "").split(",")[0]
            or request.environ.get("REMOTE_ADDR")
        )
        tracked_request.tag("user_ip", user_ip)

    queue_time = request.headers.get("x-queue-start", "") or request.headers.get(
        "x-request-start", ""
    )
    track_request_queue_time(queue_time, tracked_request)
    operation = "Controller{}".format(controller_name)

    with tracked_request.span(operation=operation):
        tracked_request.operation = operation
        try:
            value = wrapped(*args, **kwargs)
        except Exception:
            tracked_request.tag("error", "true")
            raise
        else:
            if 500 <= response.status_code <= 599:
                tracked_request.tag("error", "true")
            return value
