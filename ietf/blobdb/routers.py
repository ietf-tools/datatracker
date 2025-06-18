# Copyright The IETF Trust 2025, All Rights Reserved
from django.apps import apps

from .apps import BlobdbConfig, get_blobdb


class BlobdbStorageRouter:
    """Database router for the Blobdb"""

    _app_label = None

    @property
    def app_label(self):
        if self._app_label is None:
            for app in apps.get_app_configs():
                if isinstance(app, BlobdbConfig):
                    self._app_label = app.label
                    break
            if self._app_label is None:
                raise RuntimeError(
                    f"{BlobdbConfig.name} is not present in the Django app registry"
                )
        return self._app_label

    @property
    def db(self):
        return get_blobdb()

    def db_for_read(self, model, **hints):
        """Suggest the database that should be used for read operations for objects of type model

        Returns None if there is no suggestion.
        """
        if model._meta.app_label == self.app_label:
            return self.db
        return None  # no suggestion

    def db_for_write(self, model, **hints):
        """Suggest the database that should be used for write of objects of type model

        Returns None if there is no suggestion.
        """
        if model._meta.app_label == self.app_label:
            return self.db
        return None  # no suggestion

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """Determine if the migration operation is allowed to run on the database with alias db

        Return True if the operation should run, False if it shouldn’t run, or
        None if the router has no opinion.
        """
        if self.db is None:
            return None  # no opinion, use the default db
        is_our_app = app_label == self.app_label
        is_our_db = db == self.db
        if is_our_app or is_our_db:
            return is_our_app and is_our_db
