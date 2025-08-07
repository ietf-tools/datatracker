# coding=utf-8

import logging

import urllib3
import wrapt

from scout_apm.core.config import scout_config
from scout_apm.core.tracked_request import TrackedRequest

try:
    from urllib3 import HTTPConnectionPool
except ImportError:  # pragma: no cover
    HTTPConnectionPool = None

# Try except separately because _url_from_pool is explicitly imported for urllib3 >= 2.
# HTTPConnectionPool is always required.
try:
    from urllib3.connectionpool import _url_from_pool
except ImportError:  # pragma: no cover

    def _url_from_pool(pool, path):
        pass


logger = logging.getLogger(__name__)

have_patched_pool_urlopen = False


def ensure_installed():
    global have_patched_pool_urlopen

    logger.debug("Instrumenting urllib3.")

    if HTTPConnectionPool is None:
        logger.debug(
            "Couldn't import urllib3.HTTPConnectionPool - probably not installed."
        )
        return False
    elif not have_patched_pool_urlopen:
        try:
            HTTPConnectionPool.urlopen = wrapped_urlopen(HTTPConnectionPool.urlopen)
        except Exception as exc:
            logger.warning(
                "Failed to instrument for Urllib3 HTTPConnectionPool.urlopen: %r",
                exc,
                exc_info=exc,
            )
        else:
            have_patched_pool_urlopen = True


@wrapt.decorator
def wrapped_urlopen(wrapped, instance, args, kwargs):
    def _extract_method(method, *args, **kwargs):
        return method

    try:
        method = _extract_method(*args, **kwargs)
    except TypeError:
        method = "Unknown"

    try:
        if int(urllib3.__version__.split(".")[0]) < 2:
            url = str(instance._absolute_url("/"))
        else:
            url = str(_url_from_pool(instance, "/"))
    except Exception:
        logger.exception("Could not get URL for HTTPConnectionPool")
        url = "Unknown"

    # Don't instrument ErrorMonitor calls
    if str(url).startswith(scout_config.value("errors_host")):
        return wrapped(*args, **kwargs)

    tracked_request = TrackedRequest.instance()
    with tracked_request.span(operation="HTTP/{}".format(method)) as span:
        span.tag("url", str(url))
        return wrapped(*args, **kwargs)
