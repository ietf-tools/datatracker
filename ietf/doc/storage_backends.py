# Copyright The IETF Trust 2025, All Rights Reserved
from django.core.files.storage import Storage, storages

import debug  # pyflakes:ignore
import json

from contextlib import contextmanager
from hashlib import sha384
from io import BufferedReader
from storages.backends.s3 import S3Storage
from typing import Optional, Union, Protocol

from django.core.files.base import File

from ietf.doc.models import StoredObject
from ietf.doc.tasks import commit_staged_storageobject_task
from ietf.utils.log import log
from ietf.utils.timezone import timezone


class MetadataFile(File):
    def __init__(self, name, file, doc_name=None, doc_rev=None):
        super().__init__(file, name)
        self.doc_name = doc_name
        self.doc_rev = doc_rev
        self._custom_metadata = None 

    @property
    def custom_metadata(self):
        if self._custom_metadata is None:
            try:
                self.file.seek(0)
            except AttributeError:  # TODO-BLOBSTORE
                debug.say("Encountered Non-Seekable content")
                raise NotImplementedError("cannot handle unseekable content")
            content_bytes = self.file.read()
            if not isinstance(
                content_bytes, bytes
            ):  # TODO-BLOBSTORE: This is sketch-development only -remove before committing
                raise Exception(f"Expected bytes - got {type(content_bytes)}")
            self.file.seek(0)
            self._custom_metadata = {
                "len": f"{len(content_bytes)}",
                "sha384": f"{sha384(content_bytes).hexdigest()}",
            }
        return self._custom_metadata


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
class StorageObjectStorageMixin: #(BucketStorageProtocol):
    commit_on_save = True  # if True, blobs are immediately treated as committed

    def commit(self, name):
        now = timezone.now()
        obj = StoredObject.objects.filter(
            store=self.bucket_name,
            name=name,
            committed__isnull=True
        ).first()
        obj.committed = now
        obj.save()

    def store_file(
        self,
        kind: str,
        name: str,
        file: Union[File, BufferedReader],
        allow_overwrite: bool = False,
        doc_name: Optional[str] = None,
        doc_rev: Optional[str] = None,
    ):
        if kind != self.bucket_name:
            raise RuntimeError(f"Called store_file() for {kind} against the {self.bucket_name} Storage")
        is_new = not self.exists_in_storage(kind, name)
        # debug.show('f"Asked to store {name} in {kind}: is_new={is_new}, allow_overwrite={allow_overwrite}"')
        if not allow_overwrite and not is_new:
            log(f"Failed to save {kind}:{name} - name already exists in store")
            debug.show('f"Failed to save {kind}:{name} - name already exists in store"')
            # raise Exception("Not ignoring overwrite attempts while testing")
        else:
            content = MetadataFile(
                name=name,
                file=file,
                doc_name=doc_name,
                doc_rev=doc_rev,
            )
            try:
                new_name = self.save(name, content)
                now = timezone.now()
                record, created = StoredObject.objects.get_or_create(
                    store=kind,
                    name=name,
                    defaults=dict(
                        sha384=content.custom_metadata["sha384"],
                        len=int(content.custom_metadata["len"]),
                        store_created=now,
                        created=now,
                        modified=now,
                        committed=now if self.commit_on_save else None,
                        doc_name=content.doc_name,  # Note that these are assumed to be invariant
                        doc_rev=content.doc_rev,  # for a given name
                    ),
                )
                if not created:
                    record.sha384 = content.custom_metadata["sha384"]
                    record.len = int(content.custom_metadata["len"])
                    record.modified = now
                    record.deleted = None
                    record.committed = None
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


class CustomS3Storage(StorageObjectStorageMixin, S3Storage):
    def get_default_settings(self):
        # add a default for the ietf_log_blob_timing boolean
        return super().get_default_settings() | {"ietf_log_blob_timing": False}

    def _save(self, name, content: File):
        with maybe_log_timing(
            self.ietf_log_blob_timing, "_save", bucket_name=self.bucket_name, name=name
        ):
            if not isinstance(content, MetadataFile):
                raise NotImplementedError("Only handle MetadataFile so far")
                return new_name

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

    def _get_write_parameters(self, name, content=None):
        # debug.show('f"getting write parameters for {name}"')
        params = super()._get_write_parameters(name, content)
        if "Metadata" not in params:
            params["Metadata"] = {}
        if not isinstance(content, MetadataFile):
            raise NotImplementedError("Can only handle content of type MetadataFile")
        params["Metadata"].update(content.custom_metadata)
        return params


class StagedBlobStorage(Storage):
    """Storage using an intermediate staging step"""

    def __init__(self, staging_storage: Union[str, Storage], final_storage: Union[str, Storage]):
        self._staging_storage = staging_storage
        self._final_storage = final_storage

    @property
    def staging_storage(self) -> Storage:
        if isinstance(self._staging_storage, str):
            return storages[self._staging_storage]
        return self._staging_storage 

    @property
    def final_storage(self) -> Storage:
        if isinstance(self._final_storage, str):
            return storages[self._final_storage]
        return self._final_storage 

    @property
    def bucket_name(self):
        return self.final_storage.bucket_name

    def _open(self, name, mode="rb"):
        try:
            return self.staging_storage.open(name, mode)
        except FileNotFoundError:
            pass
        return self.final_storage.open(name, mode)

    def _save(self, name, content):
        return self.staging_storage.save(name, content)

    def exists(self, name):        
        return False  # TODO-BLOBSTORE implement this


class StorageObjectStagedBlogStorage(StorageObjectStorageMixin, StagedBlobStorage):
    commit_on_save = False  # files not committed until they're moved to the final_storage
    ietf_log_blob_timing = True

    def _save(self, name, content):
        new_name = super()._save(name, content)
        commit_staged_storageobject_task.delay(self.bucket_name, name)
        return new_name

    def commit(self, name):
        with self.staging_storage.open(name) as staged:
            self.final_storage.save(
                name=name,
                content=staged,
            )
        super().commit(name)
        self.staging_storage.delete(name)
