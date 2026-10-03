# Copyright The IETF Trust 2026, All Rights Reserved
"""Search indexing utilities

Where this module refers to "document," it is a Typesense / other search provider
record. I.e., it is the thing that is indexed. That should not be confused with the
Datatracker Document model.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from itertools import batched
from typing import Any, Literal, cast
from urllib.parse import urljoin

import httpx  # just for exceptions
import requests
import typesense
import typesense.exceptions
from django.conf import settings
from typesense.types.collection import CollectionCreateSchema
from typesense.types.document import DocumentWriteParameters

from ietf.utils.log import log

# Error classes that might succeed just by retrying a failed attempt.
# Must be a tuple for use with isinstance()
RETRYABLE_ERROR_CLASSES = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    typesense.exceptions.Timeout,
    typesense.exceptions.ServerError,
    typesense.exceptions.ServiceUnavailable,
)

DEFAULT_SETTINGS = {
    "TYPESENSE_API_URL": "",
    "TYPESENSE_API_KEY": "",
    "TYPESENSE_COLLECTION_NAME": "docs",
    "TASK_RETRY_DELAY": 10,
    "TASK_MAX_RETRIES": 12,
}


def get_settings():
    return DEFAULT_SETTINGS | getattr(settings, "SEARCH_PROVIDER_CONFIG", {})


def enabled():
    _settings = get_settings()
    return _settings["TYPESENSE_API_URL"] != ""


def _get_client() -> typesense.Client:
    _settings = get_settings()
    client = typesense.Client(
        {
            "api_key": _settings["TYPESENSE_API_KEY"],
            "nodes": [_settings["TYPESENSE_API_URL"]],
        }
    )
    return client


def get_collection_name() -> str:
    _settings = get_settings()
    collection_name = _settings["TYPESENSE_COLLECTION_NAME"]
    assert isinstance(collection_name, str)
    return collection_name


@dataclass
class WriteFailure:
    document: Mapping[str, Any]
    error: str


@dataclass
class WriteResult:
    written: int = 0
    failures: list[WriteFailure] = field(default_factory=list)


def create_index(name: str, schema: dict[str, Any]):
    log(f"Creating '{name}' collection")
    client = _get_client()
    client.collections.create(cast(CollectionCreateSchema, {"name": name} | schema))


def delete_index(name: str):
    log(f"Deleting '{name}' collection")
    client = _get_client()
    try:
        client.collections[name].delete()
    except typesense.exceptions.ObjectNotFound:
        pass


def upsert_presets(presets: dict[str, dict[str, Any]]):
    # typesense-python does not support presets, so use requests
    _settings = get_settings()
    api_base = _settings["TYPESENSE_API_URL"]
    api_key = _settings["TYPESENSE_API_KEY"]
    for preset_name, payload in presets.items():
        log(f"Upserting '{preset_name}' preset")
        response = requests.put(
            urljoin(api_base, f"/presets/{preset_name}"),
            json={"value": payload},
            headers={
                "X-TYPESENSE-API-KEY": api_key,
            },
            timeout=3,
        )
        response.raise_for_status()


def upsert_document(name: str, document: Mapping[str, Any]):
    """Create or replace one document"""
    client = _get_client()
    client.collections[name].documents.upsert(document)


def upsert_documents(
    name: str, documents: Iterable[Mapping[str, Any]], *, batchsize: int | None = None
) -> WriteResult:
    """Create or replace documents in bulk"""
    return _import_documents(name, documents, "upsert", batchsize)


def update_documents(
    name: str,
    partial_documents: Iterable[Mapping[str, Any]],
    *,
    batchsize: int | None = None,
) -> WriteResult:
    """Update fields of existing documents in bulk

    Each partial document must include the id of the document it updates.
    """
    return _import_documents(name, partial_documents, "update", batchsize)


def _import_documents(
    name: str,
    documents: Iterable[Mapping[str, Any]],
    action: Literal["upsert", "update"],
    batchsize: int | None,
) -> WriteResult:
    """Import documents in bulk

    If batchsize is set, consumes documents in batches of batchsize and imports each
    batch with one API call. Otherwise, imports all documents with a single API call.

    N.b. that typesense has a server-side batch size that defaults to 40, which should
    "almost never be changed from the default." This does not change that. Further,
    the python client library's import_ method has a batch_size parameter that does
    client-side batching. We don't use that, either.
    """
    result = WriteResult()
    params: DocumentWriteParameters = {"action": action}
    client = _get_client()
    batches = [documents] if batchsize is None else batched(documents, batchsize)
    for batch in batches:
        doc_batch = list(batch)
        import_results = client.collections[name].documents.import_(doc_batch, params)
        for document, import_result in zip(doc_batch, import_results):
            if import_result["success"]:
                result.written += 1
            else:
                result.failures.append(WriteFailure(document, import_result["error"]))
    return result
