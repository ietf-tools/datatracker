# coding=utf-8

import logging

import wrapt

from scout_apm.core.tracked_request import TrackedRequest

try:
    import pymongo
    from pymongo.collection import Collection
except ImportError:
    pymongo = None
    Collection = None

logger = logging.getLogger(__name__)

have_patched_collection = False


def ensure_installed():
    global have_patched_collection

    logger.debug("Instrumenting pymongo.")

    if Collection is None:
        logger.debug("Couldn't import pymongo.Collection - probably not installed.")
    elif not have_patched_collection:
        methods = COLLECTION_METHODS
        if pymongo.version_tuple < (4, 0):
            methods = COLLECTION_METHODS_V3
        for name in methods:
            try:
                setattr(
                    Collection, name, wrap_collection_method(getattr(Collection, name))
                )
            except Exception as exc:
                logger.warning(
                    "Failed to instrument pymongo.Collection.%s: %r",
                    name,
                    exc,
                    exc_info=exc,
                )
        have_patched_collection = True


COLLECTION_METHODS = [
    "aggregate",
    "aggregate_raw_batches",
    "bulk_write",
    "count_documents",
    "create_index",
    "create_indexes",
    "delete_many",
    "delete_one",
    "distinct",
    "drop",
    "drop_index",
    "drop_indexes",
    "estimated_document_count",
    "find",
    "find_one",
    "find_one_and_delete",
    "find_one_and_replace",
    "find_one_and_update",
    "find_raw_batches",
    "index_information",
    "insert_many",
    "insert_one",
    "list_indexes",
    "rename",
    "replace_one",
    "update_many",
    "update_one",
    "drop_search_index",
    "create_search_indexes",
    "create_search_index",
    "list_search_indexes",
    "update_search_index",
]

COLLECTION_METHODS_V3 = COLLECTION_METHODS + [
    "count",
    "ensure_index",
    "find_and_modify",
    "group",
    "inline_map_reduce",
    "insert",
    "map_reduce",
    "parallel_scan",
    "reindex",
    "remove",
    "save",
    "update",
]


@wrapt.decorator
def wrap_collection_method(wrapped, instance, args, kwargs):
    tracked_request = TrackedRequest.instance()
    camel_name = "".join(c.title() for c in wrapped.__name__.split("_"))
    operation = "MongoDB/{}.{}".format(instance.name, camel_name)
    with tracked_request.span(operation=operation, ignore_children=True) as span:
        span.tag("name", instance.name)
        return wrapped(*args, **kwargs)
