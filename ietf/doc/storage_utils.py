# Copyright The IETF Trust 2025, All Rights Reserved

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


def store_file(kind: str, name: str, file: File, allow_overwrite: bool = False) -> None:
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
            log(
                f"Conflict encountered saving {name} - results stored in {new_name} instead."
            )
            debug.show('f"Conflict encountered saving {name} - results stored in {new_name} instead."')
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
