# Copyright The IETF Trust 2025, All Rights Reserved
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.db.models.functions import Length
from django.utils.deconstruct import deconstructible
from django.utils import timezone

from .models import Blob


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
        return ContentFile(content=blob.content, name=blob.name)

    def _save(self, name, content):
        Blob.objects.update_or_create(
            name=name,
            bucket=self.bucket_name,
            defaults={"content": content.read(), "modified": timezone.now()},
        )
        return name
