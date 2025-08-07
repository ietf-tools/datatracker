# coding=utf-8

import hug
from hug.interface import HTTP

from scout_apm.falcon import ScoutMiddleware as FalconMiddleware


class ScoutMiddleware(FalconMiddleware):
    """
    Hug's HTTP interface is based on Falcon. Therefore we use a subclass of our
    Falcon integration with Hug specific extras.
    """

    def __init__(self, config, hug_http_interface):
        super(ScoutMiddleware, self).__init__(config)
        self.hug_http_interface = hug_http_interface

    def process_request(self, req, resp):
        if not self._do_nothing and self.api is None:
            self.api = self.hug_http_interface.falcon
        return super(ScoutMiddleware, self).process_request(req, resp)

    def _name_operation(self, req, responder, resource):
        if isinstance(responder, HTTP):
            # Hug doesn't use functions but its custom callable classes
            return "Controller/{}.{}".format(
                responder.interface._function.__module__,
                responder.interface._function.__name__,
            )
        return super(ScoutMiddleware, self)._name_operation(req, responder, resource)


def integrate_scout(hug_module_name, config):
    http_interface = hug.API(hug_module_name).http
    scout_middleware = ScoutMiddleware(
        config=config,
        hug_http_interface=http_interface,
    )
    http_interface.add_middleware(scout_middleware)
