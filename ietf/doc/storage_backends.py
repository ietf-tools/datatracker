# Copyright The IETF Trust 2025, All Rights Reserved

import debug  # pyflakes:ignore
import json

from contextlib import contextmanager
from hashlib import sha384
from io import BufferedReader
from storages.backends.s3 import S3Storage
from typing import Optional, Union

from django.core.files.base import File

from ietf.doc.models import StoredObject
from ietf.utils.log import log
from ietf.utils.timezone import timezone


@contextmanager
def maybe_log_timing(enabled, op, **kwargs):
    """If enabled, log elapsed time and additional data from kwargs

    Emits log even if an exception occurs
    """
    before = timezone.now()
    exception = None
    try:
        yield
    except Exception as err:
        exception = err
        raise
    finally:
        if enabled:
            dt = timezone.now() - before
            log(
                json.dumps(
                    {
                        "log": "S3Storage_timing",
                        "seconds": dt.total_seconds(),
                        "op": op,
                        "exception": "" if exception is None else repr(exception),
                        **kwargs,
                    }
                )
            )


# TODO-BLOBSTORE
# Consider overriding save directly so that
# we capture metadata for, e.g., ImageField objects
class CustomS3Storage(S3Storage):

    def __init__(self, **settings):
        self.in_flight_custom_metadata = {}  # type is Dict[str, Dict[str, str]]
        super().__init__(**settings)

    def get_default_settings(self):
        # add a default for the ietf_log_blob_timing boolean
        return super().get_default_settings() | {"ietf_log_blob_timing": False}

    def _save(self, name, content):
        with maybe_log_timing(
            self.ietf_log_blob_timing, "_save", bucket_name=self.bucket_name, name=name
        ):
            return super()._save(name, content)

    def _open(self, name, mode="rb"):
        with maybe_log_timing(
            self.ietf_log_blob_timing,
            "_open",
            bucket_name=self.bucket_name,
            name=name,
            mode=mode,
        ):
            return super()._open(name, mode)

    def delete(self, name):
        with maybe_log_timing(
            self.ietf_log_blob_timing, "delete", bucket_name=self.bucket_name, name=name
        ):
            super().delete(name)

    def store_file(
        self,
        kind: str,
        name: str,
        file: Union[File, BufferedReader],
        allow_overwrite: bool = False,
        doc_name: Optional[str] = None,
        doc_rev: Optional[str] = None,
    ):
        is_new = not self.exists_in_storage(kind, name)
        # debug.show('f"Asked to store {name} in {kind}: is_new={is_new}, allow_overwrite={allow_overwrite}"')
        if not allow_overwrite and not is_new:
            log(f"Failed to save {kind}:{name} - name already exists in store")
            debug.show('f"Failed to save {kind}:{name} - name already exists in store"')
            # raise Exception("Not ignoring overwrite attempts while testing")
        else:
            try:
                new_name = self.save(name, file)
                now = timezone.now()
                record, created = StoredObject.objects.get_or_create(
                    store=kind,
                    name=name,
                    defaults=dict(
                        sha384=self.in_flight_custom_metadata[name]["sha384"],
                        len=int(self.in_flight_custom_metadata[name]["len"]),
                        store_created=now,
                        created=now,
                        modified=now,
                        doc_name=doc_name,  # Note that these are assumed to be invariant
                        doc_rev=doc_rev,  # for a given name
                    ),
                )
                if not created:
                    record.sha384 = self.in_flight_custom_metadata[name]["sha384"]
                    record.len = int(self.in_flight_custom_metadata[name]["len"])
                    record.modified = now
                    record.deleted = None
                    record.save()
                if new_name != name:
                    complaint = f"Error encountered saving '{name}' - results stored in '{new_name}' instead."
                    log(complaint)
                    debug.show("complaint")
                    # Note that we are otherwise ignoring this condition - it should become an error later.
            except Exception as e:
                # Log and then swallow the exception while we're learning.
                # Don't let failure pass so quietly when these are the autoritative bits.
                complaint = f"Failed to save {kind}:{name}"
                log(complaint, e)
                debug.show('f"{complaint}: {e}"')
            finally:
                del self.in_flight_custom_metadata[name]
        return None

    def exists_in_storage(self, kind: str, name: str) -> bool:
        try:
            # open is realized with a HEAD
            # See https://github.com/jschneier/django-storages/blob/b79ea310201e7afd659fe47e2882fe59aae5b517/storages/backends/s3.py#L528
            with self.open(name):
                return True
        except FileNotFoundError:
            return False

    def remove_from_storage(
        self, kind: str, name: str, warn_if_missing: bool = True
    ) -> None:
        now = timezone.now()
        try:
            with self.open(name):
                pass
            self.delete(name)
            # debug.show('f"deleted {name} from {kind} storage"')
        except FileNotFoundError:
            if warn_if_missing:
                complaint = (
                    f"WARNING: Asked to delete non-existent {name} from {kind} storage"
                )
                log(complaint)
                debug.show("complaint")
        existing_record = StoredObject.objects.filter(store=kind, name=name)
        if not existing_record.exists() and warn_if_missing:
            complaint = f"WARNING: Asked to delete {name} from {kind} storage, but there was no matching StorageObject"
            log(complaint)
            debug.show("complaint")
        else:
            # Note that existing_record is a queryset that will have one matching object
            existing_record.filter(deleted__isnull=True).update(deleted=now)

    def _get_write_parameters(self, name, content=None):
        # debug.show('f"getting write parameters for {name}"')
        params = super()._get_write_parameters(name, content)
        if "Metadata" not in params:
            params["Metadata"] = {}
        try:
            content.seek(0)
        except AttributeError:  # TODO-BLOBSTORE
            debug.say("Encountered Non-Seekable content")
            raise NotImplementedError("cannot handle unseekable content")
        content_bytes = content.read()
        if not isinstance(
            content_bytes, bytes
        ):  # TODO-BLOBSTORE: This is sketch-development only -remove before committing
            raise Exception(f"Expected bytes - got {type(content_bytes)}")
        content.seek(0)
        metadata = {
            "len": f"{len(content_bytes)}",
            "sha384": f"{sha384(content_bytes).hexdigest()}",
        }
        params["Metadata"].update(metadata)
        self.in_flight_custom_metadata[name] = metadata
        return params
