# Copyright The IETF Trust 2026, All Rights Reserved

import datetime
import subprocess

from pathlib import Path

from django.conf import settings
from ietf.utils import log
from ietf.doc.models import Document
from ietf.doc.storage_utils import AlreadyExistsError, store_bytes


def rsync_helper(subprocess_arg_array: list[str]):
    subprocess.run(["/usr/bin/rsync"]+subprocess_arg_array)

def build_from_file_content(rfc_numbers: list[int]) -> str:
    types_to_sync = settings.RFC_FILE_TYPES + ("json",)
    lines = []
    lines.append("prerelease/")
    for num in rfc_numbers:
        for ext in types_to_sync:
            lines.append(f"rfc{num}.{ext}")
        lines.append(f"prerelease/rfc{num}.notprepped.xml")
    return "\n".join(lines)+"\n"

def load_rfcs_into_blobdb(numbers: list[int]):
    types_to_load = settings.RFC_FILE_TYPES + ("json",)
    rfc_docs = Document.objects.filter(type="rfc", rfc_number__in=numbers).values_list("rfc_number", flat=True)
    for num in numbers:
        if num in rfc_docs:
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
                            doc_rev="",
                            # Not setting content_type
                            mtime=datetime.datetime.fromtimestamp(
                                mtime, tz=datetime.UTC
                            ),
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
                        doc_rev="",
                        # Not setting content_type
                        mtime=datetime.datetime.fromtimestamp(mtime, tz=datetime.UTC),
                    )
                except AlreadyExistsError as e:
                    log.log(str(e))
        else:
            log.log(
                f"Skipping loading rfc{num} into blobdb as no matching Document exists"
            )
