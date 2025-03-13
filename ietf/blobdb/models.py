# Copyright The IETF Trust 2025, All Rights Reserved
from hashlib import sha384

from django.db import models
from django.utils import timezone


class Blob(models.Model):
    name = models.CharField(max_length=1024, help_text="Name of the blob")
    bucket = models.CharField(
        max_length=1024, help_text="Name of the bucket containing this blob"
    )
    modified = models.DateTimeField(
        default=timezone.now, help_text="Last modification time"
    )
    content = models.BinaryField(help_text="Content of the blob")
    checksum = models.CharField(
        max_length=96, help_text="SHA-384 digest of the content", editable=False
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["bucket", "name"], name="unique_name_per_bucket"
            ),
        ]

    def save(self, **kwargs):
        self.checksum = sha384(self.content, usedforsecurity=False).hexdigest()
        super().save(**kwargs)
