# Copyright The IETF Trust 2025, All Rights Reserved
from django.apps import AppConfig


class BlobdbConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ietf.blobdb"

    def ready(self):
        """Initialize app once the registries / settings are populated"""
        from django.conf import settings

        # Validate that the DB is set up
        db = get_blobdb()  # depends on settings.BLOBDB_DATABASE
        if db is not None and db not in settings.DATABASES:
            raise RuntimeError(
                f"settings.BLOBDB_DATABASE is '{db}' but that is not present in settings.DATABASES"
            )

        # Validate replication settings
        from .replication import validate_replication_settings

        validate_replication_settings()


def get_blobdb():
    """Retrieve the blobdb setting from Django's settings"""
    from django.conf import settings

    return getattr(settings, "BLOBDB_DATABASE", None)
