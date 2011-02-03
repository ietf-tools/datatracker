from django.db import models

class IdSubmissionStatus(models.Model):
    status_id = models.IntegerField(primary_key=True)
    status_value = models.CharField(blank=True, max_length=255)

    class Meta:
        db_table = 'id_submission_status'


class IdSubmitDateConfig(models.Model):
    id = models.IntegerField(primary_key=True)
    id_date = models.DateField(null=True, blank=True)
    date_name = models.CharField(blank=True, max_length=255)
    f_name = models.CharField(blank=True, max_length=255)

    class Meta:
        db_table = 'id_dates'

    @classmethod
    def get_first_cut_off(cls):
        return cls.objects.get(id=1).id_date

    @classmethod
    def get_second_cut_off(cls):
        return cls.objects.get(id=2).id_date

    @classmethod
    def get_ietf_monday(cls):
        return cls.objects.get(id=3).id_date

    @classmethod
    def get_processed_ids_date(cls):
        return cls.objects.get(id=4).id_date

    @classmethod
    def get_monday_after_ietf(cls):
        return cls.objects.get(id=5).id_date

    @classmethod
    def get_list_aproved_date(cls):
        return cls.objects.get(id=6).id_date
