from django.db import models

class TelechatMinutes(models.Model):
    telechat_date = models.DateField(null=True, blank=True)
    telechat_minute = models.TextField(blank=True)
    exported = models.IntegerField(null=True, blank=True)
    class Meta:
        db_table = 'telechat_minutes'

