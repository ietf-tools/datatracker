# Copyright The IETF Trust 2025, All Rights Reserved

from io import BufferedReader
from typing import Optional, Union
import debug  # pyflakes ignore

from django.conf import settings
from django.core.files.base import ContentFile, File
from django.core.files.storage import storages


# TODO-BLOBSTORE (Future, maybe after leaving 3.9) : add a return type
def _get_storage(kind: str):

    if kind in settings.MORE_STORAGE_NAMES:
        # TODO-BLOBSTORE - add a checker that verifies configuration will only return CustomS3Storages
        return storages[kind]
    else:
        debug.say(f"Got into not-implemented looking for {kind}")
        raise NotImplementedError(f"Don't know how to store {kind}")


def exists_in_storage(kind: str, name: str) -> bool:
    store = _get_storage(kind)
    return store.exists_in_storage(kind, name)


def remove_from_storage(kind: str, name: str, warn_if_missing: bool = True) -> None:
    store = _get_storage(kind)
    store.remove_from_storage(kind, name, warn_if_missing)
    return None


# TODO-BLOBSTORE: Try to refactor `kind` out of the signature of the methods already on the custom store (which knows its kind)
def store_file(
    kind: str,
    name: str,
    file: Union[File, BufferedReader],
    allow_overwrite: bool = False,
    doc_name: Optional[str] = None,
    doc_rev: Optional[str] = None,
) -> None:
    # debug.show('f"asked to store {name} into {kind}"')
    store = _get_storage(kind)
    store.store_file(kind, name, file, allow_overwrite, doc_name, doc_rev)
    return None


def store_bytes(
    kind: str,
    name: str,
    content: bytes,
    allow_overwrite: bool = False,
    doc_name: Optional[str] = None,
    doc_rev: Optional[str] = None,
) -> None:
    return store_file(kind, name, ContentFile(content), allow_overwrite)


def store_str(
    kind: str,
    name: str,
    content: str,
    allow_overwrite: bool = False,
    doc_name: Optional[str] = None,
    doc_rev: Optional[str] = None,
) -> None:
    content_bytes = content.encode("utf-8")
    return store_bytes(kind, name, content_bytes, allow_overwrite)


def retrieve_bytes(kind: str, name: str) -> bytes:
    store = _get_storage(kind)
    with store.open(name) as f:
        content = f.read()
    return content


def retrieve_str(kind: str, name: str) -> str:
    content_bytes = retrieve_bytes(kind, name)
    # TODO: try to decode all the different ways doc.text() does
    return content_bytes.decode("utf-8")
