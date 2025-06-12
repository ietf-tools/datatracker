# Copyright The IETF Trust 2025, All Rights Reserved
import json
from functools import partial
from hashlib import sha384

from django.db import models, transaction
from django.utils import timezone

from .apps import get_blobdb
from .replication import replication_enabled
from .tasks import pybob_the_blob_replicator_task


class BlobQuerySet(models.QuerySet):
    """QuerySet customized for Blob management

    Operations that bypass save() / delete() won't correctly notify watchers of changes
    to the blob contents. Disallow them.
    """

    def delete(self):
        raise NotImplementedError("Only deleting individual Blobs is supported")

    def bulk_create(self, *args, **kwargs):
        raise NotImplementedError("Only creating individual Blobs is supported")

    def update(self, *args, **kwargs):
        # n.b., update_or_create() _does_ call save()
        raise NotImplementedError("Updating BlobQuerySets is not supported")

    def bulk_update(self, *args, **kwargs):
        raise NotImplementedError("Updating Blobs in bulk is not supported")


class Blob(models.Model):
    objects = BlobQuerySet.as_manager()
    name = models.CharField(max_length=1024, help_text="Name of the blob")
    bucket = models.CharField(
        max_length=1024, help_text="Name of the bucket containing this blob"
    )
    modified = models.DateTimeField(
        default=timezone.now, help_text="Last modification time of the blob"
    )
    content = models.BinaryField(help_text="Content of the blob")
    checksum = models.CharField(
        max_length=96, help_text="SHA-384 digest of the content", editable=False
    )
    mtime = models.DateTimeField(
        default=None,
        blank=True,
        null=True,
        help_text="mtime associated with the blob as a filesystem object",
    )
    content_type = models.CharField(
        max_length=1024,
        blank=True,
        help_text="content-type header value for the blob contents",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["bucket", "name"], name="unique_name_per_bucket"
            ),
        ]

    def save(self, **kwargs):
        db = get_blobdb()
        with transaction.atomic(using=db):
            self.checksum = sha384(self.content, usedforsecurity=False).hexdigest()
            super().save(**kwargs)
            self._emit_blob_change_event(using=db)

    def delete(self, **kwargs):
        db = get_blobdb()
        with transaction.atomic(using=db):
            retval = super().delete(**kwargs)
            self._emit_blob_change_event(using=db)
        return retval

    def _emit_blob_change_event(self, using=None):
        if not replication_enabled(self.bucket):
            return

        # For now, fire a celery task we've arranged to guarantee in-order processing.
        # Later becomes pushing an event onto a queue to a dedicated worker.
        transaction.on_commit(
            partial(
                pybob_the_blob_replicator_task.delay,
                json.dumps(
                    {
                        "name": self.name,
                        "bucket": self.bucket,
                    }
                )
            ),
            using=using,
        )
