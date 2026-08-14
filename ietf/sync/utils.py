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


def _parse_positive_int(value: str) -> int:
    """Parse a string as a positive (>= 1) integer, raising ValueError otherwise"""
    token = value.strip()
    # str.isdigit() rejects signs, whitespace, and non-digits, so anything that
    # passes is a non-negative integer literal; guard against zero separately.
    if not token.isdigit():
        raise ValueError(f"'{value}' is not a positive integer")
    number = int(token)
    if number < 1:
        raise ValueError(f"'{value}' is not a positive integer")
    return number


def expand_rfc_number_range_list(ranges: str) -> list[int]:
    """Expand a range-list string into a list of RFC numbers

    The string is a comma-separated list of tokens, optionally surrounded by a
    pair of square brackets. Each token is either a bare positive integer or a
    pair of positive integers separated by a hyphen. A hyphenated pair is
    expanded following the convention of Python's range(): the left value is
    included and the right value is excluded. For example, "[1,100,1000-1004]"
    expands to [1, 100, 1000, 1001, 1002, 1003].

    The returned list is sorted and deduplicated, so overlapping ranges do not
    produce repeated numbers.

    Raises ValueError if the input contains anything other than positive
    integers and well-formed (non-reversed) ranges.
    """
    numbers: set[int] = set()
    stripped = ranges.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        stripped = stripped[1:-1]
    for raw_token in stripped.split(","):
        token = raw_token.strip()
        if not token:
            continue
        if "-" in token:
            start_str, _, end_str = token.partition("-")
            start = _parse_positive_int(start_str)
            end = _parse_positive_int(end_str)
            if start >= end:
                raise ValueError(
                    f"'{token}' is not a valid range (start must be less than end)"
                )
            numbers.update(range(start, end))
        else:
            numbers.add(_parse_positive_int(token))
    return sorted(numbers)

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
                            doc_rev=None,
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
                        doc_rev=None,
                        # Not setting content_type
                        mtime=datetime.datetime.fromtimestamp(mtime, tz=datetime.UTC),
                    )
                except AlreadyExistsError as e:
                    log.log(str(e))
        else:
            log.log(
                f"Skipping loading rfc{num} into blobdb as no matching Document exists"
            )
