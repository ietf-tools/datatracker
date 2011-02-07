from django.db import models

class IdSubmissionStatus(models.Model):
    status_id = models.IntegerField(primary_key=True)
    status_value = models.CharField(blank=True, max_length=255)

    class Meta:
        db_table = 'id_submission_status'
