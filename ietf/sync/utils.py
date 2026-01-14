# Copyright The IETF Trust 2026, All Rights Reserved

import datetime
import subprocess

from pathlib import Path

from django.conf import settings

from ietf.utils import log
from ietf.doc.storage_utils import AlreadyExistsError, store_bytes


def rsync_helper(subprocess_arg_array: list[str]):
    subprocess.run(["/usr/bin/rsync"]+subprocess_arg_array)


def load_rfcs_into_blobdb(numbers: list[int]):
    types_to_load = settings.RFC_FILE_TYPES + ("json",)
    for num in numbers:
        for ext in types_to_load:
            fs_path = Path(settings.RFC_PATH) / f"rfc{num}.{ext}"
            if fs_path.is_file():
                with fs_path.open("rb") as f:
                    bytes = f.read()
                mtime = fs_path.stat().st_mtime
                try:
                    store_bytes(
                        kind="rfc",
                        name=f"{ext}/rfc{num}.{ext}",
                        content=bytes,
                        allow_overwrite=False,  # Intentionally not allowing overwrite.
                        doc_name=f"rfc{num}",
                        doc_rev=None,
                        # Not setting content_type
                        mtime=datetime.datetime.fromtimestamp(mtime, tz=datetime.UTC),
                    )
                except AlreadyExistsError as e:
                    log.log(str(e))

        # store the not-prepped xml
        name = f"rfc{num}.notprepped.xml"
        source = Path(settings.RFC_PATH) / "prerelease" / name
        if source.is_file():
            with open(source, "rb") as f:
                bytes = f.read()
            mtime = source.stat().st_mtime
            try:
                store_bytes(
                    kind="rfc",
                    name=f"notprepped/{name}",
                    content=bytes,
                    allow_overwrite=False,  # Intentionally not allowing overwrite.
                    doc_name=f"rfc{num}",
                    doc_rev=None,
                    # Not setting content_type
                    mtime=datetime.datetime.fromtimestamp(mtime, tz=datetime.UTC),
                )
            except AlreadyExistsError as e:
                log.log(str(e))
