# Copyright The IETF Trust 2025, All Rights Reserved
import debug  # pyflakes:ignore
import json

from contextlib import contextmanager
from functools import cached_property
from hashlib import sha384
from io import BufferedReader
from storages.backends.s3 import S3Storage
from typing import Optional, Union,  Any

from django.core.files.base import File
from django.core.files.storage import Storage, storages
from django.db import transaction

from ietf.doc.models import StoredObject
from ietf.doc.tasks import commit_saved_staged_storedobject_task, commit_deleted_staged_storedobject_task
from ietf.utils.log import log
from ietf.utils.timezone import timezone


class MetadataFile(File):
    """Django storage File object that carries custom metadata"""
    def __init__(self, file, name):
        super().__init__(file, name)
        self._custom_metadata = None 

    @property
    def custom_metadata(self):
        if self._custom_metadata is None:
            self._custom_metadata = self._compute_custom_metadata()
        return self._custom_metadata

    def _compute_custom_metadata(self):
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
        return {
            "len": f"{len(content_bytes)}",
            "sha384": f"{sha384(content_bytes).hexdigest()}",
        }


class StoredObjectFile(MetadataFile):
    """Django storage File object that represents a StoredObject"""
    def __init__(self, file, name, store, doc_name=None, doc_rev=None):
        super().__init__(file, name)
        self.store = store
        self.doc_name = doc_name
        self.doc_rev = doc_rev

    @classmethod
    def from_storedobject(cls, file, name, store):
        """Alternate constructor for objects that already exist in the StoredObject table"""
        stored_object = StoredObject.objects.filter(store=store, name=name, deleted__isnull=True).first()
        if stored_object is None:
            raise FileNotFoundError(f"StoredObject for {store}:{name} does not exist or was deleted")
        file = cls(file, name, store, doc_name=stored_object.doc_name, doc_rev=stored_object.doc_rev)
        if int(file.custom_metadata["len"]) != stored_object.len:
            raise RuntimeError(f"File length changed unexpectedly for {store}:{name}")
        if file.custom_metadata["sha384"] != stored_object.sha384:
            raise RuntimeError(f"SHA-384 hash changed unexpectedly for {store}:{name}")
        return file


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
class StoredObjectStorageMixin:
    commit_on_save = True  # if True, blobs are immediately treated as committed

    def record_committed_save(self, name):
        debug.say(f"StoredObjectStorageMixin.record_committed_save('{name}') called")
        now = timezone.now()
        obj = StoredObject.objects.filter(
            store=self.kind,
            name=name,
            deleted__isnull=True,  # don't "commit" a deleted file on save
            committed__isnull=True,
        ).first()
        if obj is not None:
            obj.committed = now
            obj.save()

    def record_committed_delete(self, name):
        debug.say(f"StoredObjectStorageMixin.record_committed_delete('{name}') called")
        now = timezone.now()
        obj = StoredObject.objects.filter(
            store=self.kind,
            name=name,
            deleted__isnull=False,  # only "commit" a deleted file on delete
            committed__isnull=True,
        ).first()
        if obj is not None:
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
        if kind != self.kind:
            raise RuntimeError(f"Called store_file() for {kind} against the {self.kind} Storage")
        is_new = not self.exists_in_storage(kind, name)
        # debug.show('f"Asked to store {name} in {kind}: is_new={is_new}, allow_overwrite={allow_overwrite}"')
        if not allow_overwrite and not is_new:
            log(f"Failed to save {kind}:{name} - name already exists in store")
            debug.show('f"Failed to save {kind}:{name} - name already exists in store"')
            # raise Exception("Not ignoring overwrite attempts while testing")
        else:
            content = StoredObjectFile(
                file=file,
                name=name,
                store=self.kind,
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
            complaint = f"WARNING: Asked to delete {name} from {kind} storage, but there was no matching StoredObject"
            log(complaint)
            debug.show("complaint")
        else:
            # Note that existing_record is a queryset that will have one matching object
            existing_record.filter(deleted__isnull=True).update(
                deleted=now,
                committed=now if self.commit_on_save else None,
            )


class MetadataS3Storage(S3Storage):
    def get_default_settings(self):
        # add a default for the ietf_log_blob_timing boolean
        return super().get_default_settings() | {"ietf_log_blob_timing": False}

    def _save(self, name, content: File):
        with maybe_log_timing(
            self.ietf_log_blob_timing, "_save", bucket_name=self.bucket_name, name=name
        ):
            if not isinstance(content, MetadataFile):
                raise NotImplementedError("Only handle MetadataFile so far")
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

    def _get_write_parameters(self, name, content=None):
        # debug.show('f"getting write parameters for {name}"')
        params = super()._get_write_parameters(name, content)
        if "Metadata" not in params:
            params["Metadata"] = {}
        if not isinstance(content, MetadataFile):
            raise NotImplementedError("Can only handle content of type MetadataFile")
        params["Metadata"].update(content.custom_metadata)
        return params


class CustomS3Storage(StoredObjectStorageMixin, MetadataS3Storage):
    @cached_property
    def kind(self):
        return self.bucket_name  # teach StoredObjectStorageMixin our kind


class StagedBlobStorage(Storage):
    """Storage using an intermediate staging step"""

    def __init__(
        self,
        kind: str,
        staging_storage: Union[str, Storage, dict[str, Any]],
        final_storage: Union[str, Storage, dict[str, Any]],
    ):
        self.kind = kind
        self._staging_storage = staging_storage
        self._final_storage = final_storage

    @cached_property
    def staging_storage(self) -> Storage:
        if isinstance(self._staging_storage, str):
            return storages[self._staging_storage]  # str = alias of another STORAGES entry
        elif isinstance(self._staging_storage, Storage):
            return self._staging_storage  # Storage = actual storage instance
        else:
            return storages.create_storage(params=self._staging_storage)  # dict = def of another Storage

    @cached_property
    def final_storage(self) -> Storage:
        if isinstance(self._final_storage, str):
            return storages[self._final_storage]  # str = alias of another STORAGES entry
        elif isinstance(self._final_storage, Storage):
            return self._final_storage  # Storage = actual storage instance
        else:
            return storages.create_storage(params=self._final_storage)  # dict = def of another Storage

    def _open(self, name, mode="rb"):
        try:
            return self.staging_storage.open(name, mode)
        except FileNotFoundError:
            pass
        return self.final_storage.open(name, mode)

    def _save(self, name, content):
        # Save to staging immediately
        new_name = self.staging_storage.save(name, content)
        # Queue a task to delete from final storage later
        transaction.on_commit(
            lambda: commit_saved_staged_storedobject_task.delay(self.kind, name)
        )
        return new_name

    def commit_save(self, name):
        debug.say(f"StagedBlobStorage.commit_save('{name}') called")
        try:
            with self.staging_storage.open(name) as staged:
                new_name = self.final_storage.save(
                    name=name,
                    content=StoredObjectFile.from_storedobject(
                        file=staged,
                        name=name,
                        store=self.kind,
                    ),
                )
        except FileNotFoundError:
            log(f"Failed to commit save of {self.kind}:{name} due to FileNotFoundError from staging storage")
        else:
            if new_name != name:
                log(f"Staged file {self.kind}:{name} was committed as {self.kind}:{new_name}")
            self.staging_storage.delete(name)


    def exists(self, name):        
        return False  # TODO-BLOBSTORE implement this

    def delete(self, name):
        # Immediately delete from staging, if possible
        try:
            self.staging_storage.delete(name)
        except NotImplementedError:
            log(f"Staging storage does not implement delete() for {self.kind}:{name}")
        # Queue a task to delete from final storage later
        transaction.on_commit(
            lambda: commit_deleted_staged_storedobject_task.delay(self.kind, name)
        )

    def commit_delete(self, name):
        debug.say(f"StagedBlobStorage.commit_delete('{name}') called")
        try:
            self.final_storage.delete(name)
        except NotImplementedError:
            log(f"Final storage does not implement delete() for {self.kind}:{name}")


class StoredObjectStagedBlobStorage(StoredObjectStorageMixin, StagedBlobStorage):
    commit_on_save = False  # files not committed until they're moved to the final_storage
    ietf_log_blob_timing = True

    def commit_save(self, name):
        debug.say(f"StoredObjectStagedBlobStorage.commit_save('{name}') called")
        super().commit_save(name)
        super().record_committed_save(name)

    def commit_delete(self, name):
        debug.say(f"StoredObjectStagedBlobStorage.commit_delete('{name}') called")
        super().commit_delete(name)
        super().record_committed_delete(name)
