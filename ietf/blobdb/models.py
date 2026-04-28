# Copyright The IETF Trust 2025-2026, All Rights Reserved
from hashlib import sha384

from django.db import models, transaction
from django.utils import timezone

from .apps import get_blobdb
from .utils import queue_for_replication


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

    def __str__(self):
        return f"{self.bucket}:{self.name}"

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

    def _emit_blob_change_event(self, using: str | None=None):
        queue_for_replication(self.bucket, self.name, using=using)


class ResolvedMaterial(models.Model):
    # A Document name can be 255 characters; allow this name to be a bit longer
    name = models.CharField(max_length=300, help_text="Name to resolve")
    meeting_number = models.CharField(
        max_length=64, help_text="Meeting material is related to"
    )
    bucket = models.CharField(max_length=255, help_text="Resolved bucket name")
    blob = models.CharField(max_length=300, help_text="Resolved blob name")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["name", "meeting_number"], name="unique_name_per_meeting"
            )
        ]
    
    def __str__(self):
        return f"{self.name}@{self.meeting_number} -> {self.bucket}:{self.blob}"
