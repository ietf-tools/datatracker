# Copyright The IETF Trust 2025, All Rights Reserved
from django.apps import AppConfig


class BlobdbConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ietf.blobdb"

    def ready(self):
        from django.conf import settings  # settings should be ready now

        # Validate that the DB is set up
        db = getattr(settings, "BLOBDB_DATABASE", None)
        if db is not None and db not in settings.DATABASES:
            raise RuntimeError(
                f"settings.BLOBDB_DATABASE is '{db}' but that is not present in settings.DATABASES"
            )

        # Validate replication settings
        from .replication import validate_replication_settings

        validate_replication_settings()
