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


def upsert_presets(presets: Mapping[str, Mapping[str, Any]]):
    """Upsert search presets

    For Typesense, search preset names are global. Watch out for conflicts.
    """
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


@dataclass
class WriteFailure:
    document: Mapping[str, Any]
    error: str


@dataclass
class WriteResult:
    written: int = 0
    failures: list[WriteFailure] = field(default_factory=list)


@dataclass
class RebuildResult:
    loaded: int = 0
    skipped: int = 0  # already written by a concurrent update
    failures: list[WriteFailure] = field(default_factory=list)


class IndexStateError(Exception):
    """The index's collections and alias are not in a state that allows the operation"""


class RebuildFailedError(Exception):
    """Documents failed to load during a rebuild; the live index is unchanged"""

    def __init__(self, message: str, result: RebuildResult):
        super().__init__(message)
        self.result = result


@dataclass(frozen=True)
class SearchIndex:
    """A search index definition and the operations on it"""

    name: str
    schema: dict[str, Any]

    def upsert_document(self, document: Mapping[str, Any]):
        """Create or replace one document

        To ensure a concurrent rebuild() does not lose data, ensure data this adds to
        the index are already readable from the data source. E.g., do not call this
        method until after a transaction writing its data has committed.
        """
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
        """Create or replace documents in bulk

        To ensure a concurrent rebuild() does not lose data, ensure data this adds to
        the index are already readable from the data source. E.g., do not call this
        method until after a transaction writing its data has committed.
        """
        return _import_documents(self.name, documents, "upsert", batchsize)

    def update_documents(
        self,
        partial_documents: Iterable[Mapping[str, Any]],
        *,
        batchsize: int | None = None,
    ) -> WriteResult:
        """Update fields of existing documents in bulk

        Each partial document must include the id of the document it updates.

        To ensure a concurrent rebuild() does not lose data, ensure data this adds to
        the index are already readable from the data source. E.g., do not call this
        method until after a transaction writing its data has committed.
        """
        return _import_documents(self.name, partial_documents, "update", batchsize)

    def rebuild(
        self,
        documents: Iterable[Mapping[str, Any]],
        *,
        batchsize: int | None = None,
        ignore_errors: bool = False,
    ) -> RebuildResult:
        """Replace the contents of the index with documents

        Loads the documents into a new collection, then switches searches to it and
        deletes the old one. Searches use the old contents until the switch.

        Consumes the documents iterable only after the new collection is created. This
        ensures that any updates via upsert_document, upsert_documents, or
        update_documents made concurrent to the rebuild call are reflected correctly
        in the rebuilt collection. The documents iterable must not read its input until
        it is consumed.

        Raises IndexStateError if the index is not in a rebuildable state (e.g., a
        rebuild is in progress or a failed rebuild left collections behind), and
        RebuildFailedError if any documents fail to load (unless ignore_errors is set).
        """
        client = _get_client()
        state = _get_index_state(client, self.name)
        if state.alias_target is None and self.name in state.collections:
            raise IndexStateError(
                f"{self.name} is a collection rather than an alias. Convert it to an "
                "alias before rebuilding."
            )
        if len(state.others) > 0:
            raise IndexStateError(
                f"Collections {', '.join(state.others)} exist besides the live "
                f"collection of {self.name}. Another rebuild may be running. If not, "
                "remove them with clean_up() and rebuild again."
            )

        # Rebuilds that start from the same live collection choose the same name for
        # the new one, so creating it succeeds for at most one of them.
        new_collection = _next_collection_name(state)
        result = _create_and_load(
            client, self, new_collection, documents, batchsize, ignore_errors
        )

        try:
            _set_alias(client, self.name, new_collection)
            # Typesense allows an alias to point at a missing collection. If ours was
            # deleted, deleting the previous one too would leave searches no data.
            if new_collection not in _list_collections(client):
                _restore_alias(client, self.name, state.alias_target)
                raise IndexStateError(
                    f"Collection {new_collection} was deleted during the rebuild of "
                    f"{self.name}, possibly by clean_up() while the rebuild was "
                    "running."
                )
        except Exception:
            _discard_collection(client, self.name, new_collection)
            raise

        # We only reach this point if the alias has been updated to point to the new
        # collection. If set, state.alias_target is still the previous live collection.
        if state.alias_target is not None:
            try:
                _delete_collection(client, state.alias_target)
            except Exception as err:
                # The rebuild succeeded; the old collection is a leftover that the
                # next rebuild reports and clean_up() removes.
                log(
                    f"Failed to delete previous collection {state.alias_target} of "
                    f"{self.name} ({err!r}). Remove it with clean_up()."
                )
        return result

    def clean_up(self) -> list[str]:
        """Delete collections left behind by failed or interrupted rebuilds

        Deletes all numbered collections of the index except the live one. Returns
        the names of collections deleted. Do not call this during a rebuild because it
        will delete the new collection!

        Raises IndexStateError without deleting anything if it cannot tell which
        collection is live.
        """
        client = _get_client()
        state = _get_index_state(client, self.name)
        if state.live is None and len(state.versioned) > 0:
            raise IndexStateError(
                f"{self.name} has no alias and no collection named {self.name}, so "
                f"none of {', '.join(state.versioned)} is known to be live. Resolve "
                "this manually."
            )
        if state.alias_target is not None and (
            state.alias_target not in state.collections
        ):
            raise IndexStateError(
                f"Alias {self.name} points to {state.alias_target}, which does not "
                "exist. Resolve this manually."
            )
        for collection in state.others:
            _delete_collection(client, collection)
        return state.others

    def build_transition_collection(
        self,
        documents: Iterable[Mapping[str, Any]],
        *,
        batchsize: int | None = None,
        ignore_errors: bool = False,
    ) -> RebuildResult:
        """Build the first numbered collection for an index stored in a plain collection

        Temporary and Typesense-specific. Converting an index stored in a collection
        named like the index to one whose name is an alias takes two steps. This is
        the first: it creates {name}_0 and loads documents into it like rebuild()
        does, leaving the existing collection alone and creating no alias. Then an
        operator deletes the existing collection and creates the alias.
        """
        client = _get_client()
        state = _get_index_state(client, self.name)
        if state.alias_target is not None:
            raise IndexStateError(f"{self.name} is already an alias")
        if self.name not in state.collections:
            raise IndexStateError(f"There is no collection named {self.name}")
        if len(state.versioned) > 0:
            raise IndexStateError(
                f"Collections {', '.join(state.versioned)} already exist"
            )
        return _create_and_load(
            client, self, f"{self.name}_0", documents, batchsize, ignore_errors
        )


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
                    f"Ignoring failed write to deleted collection {collection} "
                    f"({err!r})"
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
    action: Literal["create", "upsert", "update"],
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


def _next_collection_name(state: _IndexState) -> str:
    """Name for a collection to replace the live one

    One more than the live collection's number, or 0 if there is no live collection.
    """
    if state.live is None:
        return f"{state.name}_0"
    number = _collection_number(state.name, state.live)
    if number is None:
        raise IndexStateError(
            f"Live collection {state.live} of {state.name} is not named "
            f"{state.name}_<number>"
        )
    return f"{state.name}_{number + 1}"


def _set_alias(client: typesense.Client, name: str, collection: str):
    client.aliases.upsert(name, {"collection_name": collection})
    log(f"Pointed alias {name} at collection {collection}")


def _restore_alias(client: typesense.Client, name: str, collection: str | None):
    """Point the alias back at collection, or remove it if collection is None

    Errors are logged rather than raised so they do not hide the rebuild's error.
    """
    try:
        if collection is None:
            client.aliases[name].delete()
            log(f"Removed alias {name}")
        else:
            _set_alias(client, name, collection)
    except Exception as err:
        log(f"Failed to restore alias {name} ({err!r})")


def _delete_collection(client: typesense.Client, collection: str):
    try:
        client.collections[collection].delete()
    except typesense.exceptions.ObjectNotFound:
        return
    log(f"Deleted collection {collection}")


def _discard_collection(client: typesense.Client, name: str, collection: str):
    """Delete a collection a failed rebuild created, unless it went live

    Errors are logged rather than raised so they do not hide the rebuild's error.
    """
    try:
        if _get_index_state(client, name).alias_target == collection:
            # The alias update took effect although it raised an error
            log(f"Not discarding collection {collection}: alias {name} points to it")
            return
        _delete_collection(client, collection)
    except Exception as err:
        log(f"Failed to discard collection {collection} ({err!r})")


def _create_and_load(
    client: typesense.Client,
    index: SearchIndex,
    collection: str,
    documents: Iterable[Mapping[str, Any]],
    batchsize: int | None,
    ignore_errors: bool,
) -> RebuildResult:
    """Create a collection for an index and load documents into it

    Discards the collection if loading fails.
    """
    try:
        client.collections.create(
            cast(CollectionCreateSchema, {"name": collection} | index.schema)
        )
    except typesense.exceptions.ObjectAlreadyExists:
        raise IndexStateError(
            f"Collection {collection} already exists. Another rebuild of "
            f"{index.name} is running or has just finished, or one failed and left "
            "it behind. If no rebuild is running, remove it with clean_up() and "
            "rebuild again."
        )
    log(f"Created collection {collection} to rebuild {index.name}")

    try:
        result = _load_documents(client, collection, documents, batchsize)
        log(
            f"Loaded {result.loaded} documents into {collection}, skipped "
            f"{result.skipped} already written by updates, "
            f"{len(result.failures)} failed"
        )
        if len(result.failures) > 0 and not ignore_errors:
            raise RebuildFailedError(
                f"{len(result.failures)} documents failed to load. Discarding "
                f"{collection}; {index.name} is unchanged.",
                result,
            )
    except Exception:
        _discard_collection(client, index.name, collection)
        raise
    return result


def _load_documents(
    client: typesense.Client,
    collection: str,
    documents: Iterable[Mapping[str, Any]],
    batchsize: int | None,
) -> RebuildResult:
    """Create documents in a new collection

    A document that already exists was written by a concurrent update, which has
    newer data, so it is counted as skipped.
    """
    result = RebuildResult()
    batches = [documents] if batchsize is None else batched(documents, batchsize)
    for batch in batches:
        for document, outcome in _import_batch(
            client, collection, list(batch), "create"
        ):
            if outcome["success"]:
                result.loaded += 1
            elif outcome["code"] == 409:
                result.skipped += 1
            else:
                result.failures.append(WriteFailure(document, outcome["error"]))
    return result
