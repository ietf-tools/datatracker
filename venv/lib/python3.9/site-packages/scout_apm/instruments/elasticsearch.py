# coding=utf-8

import logging
from collections import namedtuple

import wrapt

from scout_apm.compat import get_pos_args, unwrap_decorators
from scout_apm.core.tracked_request import TrackedRequest

try:
    from elasticsearch import VERSION as ELASTICSEARCH_VERSION
    from elasticsearch import Elasticsearch
except ImportError:  # pragma: no cover
    Elasticsearch = None
    ELASTICSEARCH_VERSION = (0, 0, 0)

try:
    # Transport was moved to elastic_transport as of v8.0.0
    from elastic_transport import Transport
except ImportError:  # pragma: no cover
    try:
        from elasticsearch import Transport
    except ImportError:  # pragma: no cover
        Transport = None

logger = logging.getLogger(__name__)


def ensure_installed():
    logger.debug("Instrumenting elasticsearch.")

    if Elasticsearch is None or Transport is None:
        if Elasticsearch is None:
            logger.debug(
                "Couldn't import elasticsearch.Elasticsearch "
                "- probably not installed."
            )
        if Transport is None:
            logger.debug(
                "Couldn't import elasticsearch.Transport or "
                "elastic_transport.Transport - probably not installed."
            )
    else:
        ensure_client_instrumented()
        ensure_transport_instrumented()


ClientMethod = namedtuple("ClientMethod", ["name", "takes_index_argument"])

VERSIONED_CLIENT_METHODS = {
    "v7": [
        ClientMethod("bulk", True),
        ClientMethod("clear_scroll", False),
        ClientMethod("close", False),
        ClientMethod("close_point_in_time", False),
        ClientMethod("count", True),
        ClientMethod("create", True),
        ClientMethod("delete", True),
        ClientMethod("delete_by_query", True),
        ClientMethod("delete_by_query_rethrottle", False),
        ClientMethod("delete_script", False),
        ClientMethod("exists", True),
        ClientMethod("exists_source", True),
        ClientMethod("explain", True),
        ClientMethod("field_caps", True),
        ClientMethod("get", True),
        ClientMethod("get_script", False),
        ClientMethod("get_script_context", False),
        ClientMethod("get_script_languages", False),
        ClientMethod("get_source", True),
        ClientMethod("index", True),
        ClientMethod("info", False),
        ClientMethod("mget", True),
        ClientMethod("msearch", True),
        ClientMethod("msearch_template", True),
        ClientMethod("mtermvectors", True),
        ClientMethod("open_point_in_time", True),
        ClientMethod("ping", False),
        ClientMethod("put_script", False),
        ClientMethod("rank_eval", True),
        ClientMethod("reindex", False),
        ClientMethod("reindex_rethrottle", False),
        ClientMethod("render_search_template", False),
        ClientMethod("scripts_painless_execute", False),
        ClientMethod("scroll", False),
        ClientMethod("search", True),
        ClientMethod("search_mvt", True),
        ClientMethod("search_shards", True),
        ClientMethod("search_template", True),
        ClientMethod("termvectors", True),
        ClientMethod("terms_enum", True),
        ClientMethod("update", True),
        ClientMethod("update_by_query", True),
        ClientMethod("update_by_query_rethrottle", False),
    ],
    "v8": [
        ClientMethod("knn_search", True),
        ClientMethod("health_report", False),
    ],
}

CLIENT_METHODS = VERSIONED_CLIENT_METHODS["v7"][:]
if ELASTICSEARCH_VERSION > (8, 0, 0):
    CLIENT_METHODS += VERSIONED_CLIENT_METHODS["v8"]


have_patched_client = False


def ensure_client_instrumented():
    global have_patched_client

    if not have_patched_client:
        instrumented_count = 0
        for name, takes_index_argument in CLIENT_METHODS:
            try:
                method = getattr(Elasticsearch, name)
                if takes_index_argument:
                    wrapped = wrap_client_index_method(method)
                else:
                    wrapped = wrap_client_method(method)
                setattr(Elasticsearch, name, wrapped)
                instrumented_count += 1
            except Exception as exc:
                logger.debug(
                    "Failed to instrument elasticsearch.Elasticsearch.%s: %r",
                    name,
                    exc,
                    exc_info=exc,
                )
        if instrumented_count == 0:
            logger.warning(
                "Failed to instrument any elasticsearch.Elasticsearch methods."
                " Enable debug logs to view root causes."
            )

        have_patched_client = True


@wrapt.decorator
def wrap_client_index_method(wrapped, instance, args, kwargs):
    # elasticsearch-py 7.5.1 changed the order of arguments for client methods,
    # so to be safe we need to inspect the wrapped method's positional
    # arguments to see if we should pull it from there
    if "index" in kwargs:
        index = kwargs["index"]
    else:
        unwrapped = unwrap_decorators(wrapped)
        pos_args = get_pos_args(unwrapped)
        try:
            index_index = pos_args.index("index")
        except ValueError:  # pragma: no cover
            # This guards against the method not accepting an 'index' argument
            # but they all do - for now
            index = ""
        else:
            try:
                index = args[index_index - 1]  # subtract 'self'
            except IndexError:
                index = ""

    if isinstance(index, (list, tuple)):
        index = ",".join(index)
    if index == "":
        index = "Unknown"
    index = index.title()

    camel_name = "".join(c.title() for c in wrapped.__name__.split("_"))
    operation = "Elasticsearch/{}/{}".format(index, camel_name)
    tracked_request = TrackedRequest.instance()
    with tracked_request.span(operation=operation, ignore_children=True):
        return wrapped(*args, **kwargs)


@wrapt.decorator
def wrap_client_method(wrapped, instance, args, kwargs):
    camel_name = "".join(c.title() for c in wrapped.__name__.split("_"))
    operation = "Elasticsearch/{}".format(camel_name)
    tracked_request = TrackedRequest.instance()
    with tracked_request.span(operation=operation, ignore_children=True):
        return wrapped(*args, **kwargs)


have_patched_transport = False


def ensure_transport_instrumented():
    global have_patched_transport

    if not have_patched_transport:
        try:
            Transport.perform_request = wrapped_perform_request(
                Transport.perform_request
            )
        except Exception as exc:
            logger.warning(
                "Failed to instrument elasticsearch.Transport.perform_request: %r",
                exc,
                exc_info=exc,
            )

    have_patched_transport = True


def _sanitize_name(name):
    try:
        op = name.split("/")[-1]
        op = op[1:]  # chop leading '_' from op
        known_names = (
            "bench",
            "bulk",
            "count",
            "delete_by_query",
            "execute",
            "exists",
            "explain",
            "field_caps",
            "field_stats",
            "health",
            "mget",
            "mlt",
            "mpercolate",
            "msearch",
            "mtermvectors",
            "percolate",
            "pit",
            "query",
            "rank_eval",
            "reindex",
            "script_context",
            "script_language",
            "scroll",
            "search_shards",
            "source",
            "suggest",
            "template",
            "termvectors",
            "terms_enum",
            "update",
            "update_by_query",
            "search",
        )
        if op in known_names:
            return op.title()
        return "Unknown"
    except Exception:
        return "Unknown"


@wrapt.decorator
def wrapped_perform_request(wrapped, instance, args, kwargs):
    try:
        op = _sanitize_name(args[1])
    except IndexError:
        op = "Unknown"

    tracked_request = TrackedRequest.instance()
    with tracked_request.span(
        operation="Elasticsearch/{}".format(op),
        ignore_children=True,
    ):
        return wrapped(*args, **kwargs)
