# Copyright The IETF Trust 2026, All Rights Reserved
"""Search indexing utilities

Where this module refers to "document," it is a Typesense / other search provider
record. I.e., it is the thing that is indexed. That should not be confused with the
Datatracker Document model.
"""

import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from itertools import batched
from typing import Any, Literal, TypeVar, cast
from urllib.parse import urljoin

import httpx  # just for exceptions
import requests
import typesense
import typesense.exceptions
from django.conf import settings
from typesense.types.collection import CollectionCreateSchema
from typesense.types.document import (
    DocumentWriteParameters,
    ImportResponseFail,
    ImportResponseSuccess,
)

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


@dataclass
class WriteFailure:
    document: Mapping[str, Any]
    error: str


@dataclass
class WriteResult:
    written: int = 0
    failures: list[WriteFailure] = field(default_factory=list)


@dataclass(frozen=True)
class SearchIndex:
    """A search index definition and the operations on it"""

    name: str
    schema: dict[str, Any]
    presets: dict[str, dict[str, Any]] = field(default_factory=dict)

    def create(self):
        log(f"Creating '{self.name}' collection")
        client = _get_client()
        client.collections.create(
            cast(CollectionCreateSchema, {"name": self.name} | self.schema)
        )

    def delete(self):
        log(f"Deleting '{self.name}' collection")
        client = _get_client()
        try:
            client.collections[self.name].delete()
        except typesense.exceptions.ObjectNotFound:
            pass

    def upsert_presets(self):
        # typesense-python does not support presets, so use requests
        _settings = get_settings()
        api_base = _settings["TYPESENSE_API_URL"]
        api_key = _settings["TYPESENSE_API_KEY"]
        for preset_name, payload in self.presets.items():
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

    def upsert_document(self, document: Mapping[str, Any]):
        """Create or replace one document"""
        client = _get_client()
        state = _get_index_state(client, self.name)
        _write_to_targets(
            client,
            state.write_targets or [self.name],
            state.collections,
            lambda collection: client.collections[collection].documents.upsert(
                document
            ),
        )

    def upsert_documents(
        self, documents: Iterable[Mapping[str, Any]], *, batchsize: int | None = None
    ) -> WriteResult:
        """Create or replace documents in bulk"""
        return _import_documents(self.name, documents, "upsert", batchsize)

    def update_documents(
        self,
        partial_documents: Iterable[Mapping[str, Any]],
        *,
        batchsize: int | None = None,
    ) -> WriteResult:
        """Update fields of existing documents in bulk

        Each partial document must include the id of the document it updates.
        """
        return _import_documents(self.name, partial_documents, "update", batchsize)


@dataclass
class _IndexState:
    """Collections and alias for an index as listed at one point in time"""

    name: str
    alias_target: str | None
    collections: set[str]  # names of all collections, not just this index's

    @property
    def live(self) -> str | None:
        """Collection that searches use

        This is the alias target. Before the alias is created, it is a collection
        named like the index, if there is one.
        """
        if self.alias_target is not None:
            return self.alias_target
        return self.name if self.name in self.collections else None

    @property
    def versioned(self) -> list[str]:
        """Collections named {name}_{number}, in numeric order"""
        numbered = []
        for collection in self.collections:
            number = _collection_number(self.name, collection)
            if number is not None:
                numbered.append((number, collection))
        return [collection for _, collection in sorted(numbered)]

    @property
    def others(self) -> list[str]:
        """Versioned collections that are not live (rebuilds in progress)"""
        return [c for c in self.versioned if c != self.live]

    @property
    def write_targets(self) -> list[str]:
        live = self.live
        return ([] if live is None else [live]) + self.others


def _collection_number(name: str, collection: str) -> int | None:
    """Number of a collection named {name}_{number}, or None"""
    match = re.fullmatch(rf"{re.escape(name)}_(\d+)", collection)
    return None if match is None else int(match[1])


def _list_collections(client: typesense.Client) -> set[str]:
    return {collection["name"] for collection in client.collections.retrieve()}


def _get_index_state(client: typesense.Client, name: str) -> _IndexState:
    try:
        alias_target = client.aliases[name].retrieve()["collection_name"]
    except typesense.exceptions.ObjectNotFound:
        alias_target = None
    return _IndexState(name, alias_target, _list_collections(client))


T = TypeVar("T")


def _write_to_targets(
    client: typesense.Client,
    targets: list[str],
    listed_collections: set[str],
    write: Callable[[str], T],
) -> dict[str, T]:
    """Call write(collection) for each target collection

    A rebuild that finishes or fails deletes a collection, so a target collection may
    vanish between listing and writing. If a target collection was deleted, failure to
    write to it does not create inconsistent data; such a failure is logged and
    otherwise ignored. Other write failures do indicate that data may be inconsistent.
    These are caught so they do not stop the remaining target collections from being
    written; afterward, the first one is raised so that the caller can retry on a
    retryable error.

    Returns the write results of the targets that succeeded.
    """
    results = {}
    first_error = None
    for collection in targets:
        try:
            results[collection] = write(collection)
        except Exception as err:
            vanished = collection in listed_collections and (
                collection not in _list_collections(client)
            )
            if vanished:
                log(
                    f"Ignoring failed write to deleted collection {collection} ({err!r})"
                )
            else:
                log(f"Write to collection {collection} failed ({err!r})")
                if first_error is None:
                    first_error = err
    if first_error is not None:
        raise first_error
    return results


ImportOutcome = tuple[
    Mapping[str, Any], ImportResponseSuccess | ImportResponseFail[Mapping[str, Any]]
]


def _import_batch(
    client: typesense.Client,
    collection: str,
    batch: list[Mapping[str, Any]],
    action: Literal["upsert", "update"],
) -> list[ImportOutcome]:
    params: DocumentWriteParameters = {"action": action}
    return list(
        zip(batch, client.collections[collection].documents.import_(batch, params))
    )


def _import_documents(
    name: str,
    documents: Iterable[Mapping[str, Any]],
    action: Literal["upsert", "update"],
    batchsize: int | None,
) -> WriteResult:
    """Import documents in bulk into all write targets of the index

    If batchsize is set, consumes documents in batches of batchsize and imports each
    batch with one API call per target. Otherwise, imports all documents with a
    single API call per target.

    The result describes the live collection. Failures in other collections are
    logged.

    N.b. that typesense has a server-side batch size that defaults to 40, which should
    "almost never be changed from the default." This does not change that. Further,
    the python client library's import_ method has a batch_size parameter that does
    client-side batching. We don't use that, either.
    """
    result = WriteResult()
    client = _get_client()
    state = _get_index_state(client, name)
    targets = state.write_targets or [name]
    batches = [documents] if batchsize is None else batched(documents, batchsize)
    for batch in batches:
        doc_batch = list(batch)
        batch_outcomes = _write_to_targets(
            client,
            targets,
            state.collections,
            lambda collection: _import_batch(client, collection, doc_batch, action),
        )
        # Drop deleted targets. If a finished rebuild deleted the live collection,
        # its replacement becomes the first target and the one reported.
        targets = [t for t in targets if t in batch_outcomes]
        for index, collection in enumerate(targets):
            if index == 0:
                _add_outcomes(result, batch_outcomes[collection])
            else:
                _log_other_outcomes(collection, batch_outcomes[collection], action)
    return result


def _add_outcomes(result: WriteResult, outcomes: list[ImportOutcome]):
    for document, outcome in outcomes:
        if outcome["success"]:
            result.written += 1
        else:
            result.failures.append(WriteFailure(document, outcome["error"]))


def _log_other_outcomes(
    collection: str,
    outcomes: list[ImportOutcome],
    action: Literal["upsert", "update"],
):
    not_found = 0
    for document, outcome in outcomes:
        if outcome["success"]:
            continue
        if action == "update" and outcome["code"] == 404:
            # the rebuild in progress has not created this document yet
            not_found += 1
        else:
            log(
                f"Write of {document.get('id')} to in-progress collection "
                f"{collection} failed: {outcome['error']}"
            )
    if not_found > 0:
        log(
            f"{not_found} documents not yet in in-progress collection {collection}, "
            "not updated there"
        )
