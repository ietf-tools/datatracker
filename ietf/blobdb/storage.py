# Copyright The IETF Trust 2025, All Rights Reserved
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.db.models.functions import Length
from django.utils.deconstruct import deconstructible
from django.utils import timezone

from .models import Blob

# TODO-BLOBSTORE should this be the same / sibling class as StagedBlobStorage speaks? Sort out inheritance
class BlobFile(ContentFile):

    def __init__(self, content, name=None, mtime=None, content_type=None):
        super().__init__(content, name)
        self.mtime = mtime
        self.content_type = content_type


@deconstructible
class BlobdbStorage(Storage):

    def __init__(self, bucket_name=None):
        self.bucket_name = bucket_name

    def get_queryset(self):
        return Blob.objects.filter(bucket=self.bucket_name)

    def delete(self, name):
        self.get_queryset().filter(name=name).delete()

    def exists(self, name):
        return self.get_queryset().filter(name=name).exists()

    def size(self, name):
        sizes = (
            self.get_queryset()
            .filter(name=name)
            .annotate(object_size=Length("content"))
            .values_list("object_size", flat=True)
        )
        if len(sizes) == 0:
            raise FileNotFoundError(
                f"No object '{name}' exists in bucket '{self.bucket_name}'"
            )
        return sizes[0]  # unique constraint guarantees 0 or 1 entry

    def _open(self, name, mode="rb"):
        try:
            blob = self.get_queryset().get(name=name)
        except Blob.DoesNotExist:
            raise FileNotFoundError(
                f"No object '{name}' exists in bucket '{self.bucket_name}'"
            )
        return BlobFile(
            content=blob.content,
            name=blob.name,
            mtime=blob.mtime or blob.modified,  # fall back to modified time
            content_type=blob.content_type,
        )

    def _save(self, name, content):
        Blob.objects.update_or_create(
            name=name,
            bucket=self.bucket_name,
            defaults={
                "content": content.read(),
                "modified": timezone.now(),
                "mtime": getattr(content, "mtime", None),
                "content_type": getattr(content, "content_type", ""),
            },
        )
        return name
