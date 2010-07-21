from django.db import models

class MigrationHistory(models.Model):
    app_name = models.CharField(max_length=255)
    migration = models.CharField(max_length=255)
    applied = models.DateTimeField(blank=True, null=True)

    @classmethod
    def for_migration(cls, app_name, migration):
        try:
            return cls.objects.get(
                app_name = app_name,
                migration = migration,
            )
        except cls.DoesNotExist:
            return cls(
                app_name = app_name,
                migration = migration,
            )