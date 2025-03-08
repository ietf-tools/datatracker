from django.apps import AppConfig


class BlobdbConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ietf.blobdb"

    def ready(self):
        from django.conf import settings  # settings should be ready now
        db = getattr(settings, "BLOBDB_DATABASE", None)
        if db is not None and db not in settings.DATABASES:
            raise RuntimeError(f"settings.BLOBDB_DATABASE is '{db}' but that is not present in settings.DATABASES")
