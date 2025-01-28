# Copyright The IETF Trust 2025, All Rights Reserved

from io import BufferedReader
from typing import Union
import debug  # pyflakes ignore

from django.conf import settings
from django.core.files.base import ContentFile, File
from django.core.files.storage import storages, Storage

from ietf.utils.log import log


def _get_storage(kind: str) -> Storage:
    if kind in settings.MORE_STORAGE_NAMES:
        return storages[kind]
    else:
        debug.say(f"Got into not-implemented looking for {kind}")
        raise NotImplementedError(f"Don't know how to store {kind}")


def exists_in_storage(kind: str, name: str) -> bool:
    store = _get_storage(kind)
    try:
        # open is realized with a HEAD
        # See https://github.com/jschneier/django-storages/blob/b79ea310201e7afd659fe47e2882fe59aae5b517/storages/backends/s3.py#L528
        with store.open(name):
            return True
    except FileNotFoundError:
        return False


def remove_from_storage(kind: str, name: str) -> None:
    store = _get_storage(kind)
    try:
        with store.open(name):
            pass
        store.delete(name)
        # debug.show('f"deleted {name} from {kind} storage"')
    except FileNotFoundError:
        complaint = f"WARNING: Asked to delete non-existant {name} from {kind} storage"
        log(complaint)
        # debug.show("complaint")


def store_file(kind: str, name: str, file: Union[File,BufferedReader], allow_overwrite: bool = False) -> None:
    # debug.show('f"asked to store {name} into {kind}"')
    store = _get_storage(kind)
    if not allow_overwrite and store.exists(name):
        log(f"Failed to save {kind}:{name} - name already exists in store")
        debug.show('f"Failed to save {kind}:{name} - name already exists in store"')
    else:
        try:
            new_name = store.save(name, file)
        except Exception as e:
            # Log and then swallow the exception while we're learning.
            # Don't let failure pass so quietly when these are the autoritative bits.
            log(f"Failed to save {kind}:{name}", e)
            debug.show("e")
            return None
        if new_name != name:
            complaint = f"Error encountered saving '{name}' - results stored in '{new_name}' instead."
            log(complaint)
            debug.show("complaint")
        return None


def store_bytes(
    kind: str, name: str, content: bytes, allow_overwrite: bool = False
) -> None:
    return store_file(kind, name, ContentFile(content), allow_overwrite)


def store_str(
    kind: str, name: str, content: str, allow_overwrite: bool = False
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
