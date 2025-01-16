# Copyright The IETF Trust 2025, All Rights Reserved

import debug # pyflakes ignore

from django.core.files.base import ContentFile
from django.core.files.storage import storages, Storage

from ietf.utils.log import log

def _get_storage(kind: str) -> Storage:
    if kind in [
        "bofreq",
        "charter",
        "conflrev",
        "draft",
        "draft",
        "draft",
    ]:
        return storages[kind]
    else:
        debug.say(f"Got into not-implemented looking for {kind}")
        raise NotImplementedError(f"Don't know how to store {kind}")


def store_bytes(kind: str, name: str, content: bytes, allow_overwrite: bool = False) -> None:
    store = _get_storage(kind)
    if not allow_overwrite:
        try:
            new_name = store.save(name, ContentFile(content))
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
    else:
        try:
            with store.open(name) as f:
                f.write(content)
        except Exception as e:
            # Log and then swallow the exception while we're learning.
            # Don't let failure pass so quietly when these are the autoritative bits.
            log(f"Failed to save {kind}:{name}", e)
            return None
        raise NotImplementedError()


def retrieve_bytes(kind: str, name: str) -> bytes:
    store = _get_storage(kind)
    with store.open(name) as f:
        content = f.read()
    return content

def store_str(kind: str, name: str, content: str, allow_overwrite: bool = False) -> None:
    content_bytes = content.encode("utf-8")
    store_bytes(kind, name, content_bytes, allow_overwrite)

def retrieve_str(kind: str, name: str) -> str:
    content_bytes = retrieve_bytes(kind, name)
    return content_bytes.decode("utf-8")
