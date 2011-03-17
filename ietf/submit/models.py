from django.db import models

from ietf.idtracker.models import IETFWG


class IdSubmissionStatus(models.Model):
    status_id = models.IntegerField(primary_key=True)
    status_value = models.CharField(blank=True, max_length=255)

    class Meta:
        db_table = 'id_submission_status'


class IdSubmissionDetail(models.Model):
    submission_id = models.AutoField(primary_key=True)
    temp_id_document_tag = models.IntegerField(null=True, blank=True)
    status = models.ForeignKey(IdSubmissionStatus, db_column='status_id', null=True, blank=True)
    last_updated_date = models.DateField(null=True, blank=True)
    last_updated_time = models.CharField(null=True, blank=True, max_length=25)
    id_document_name = models.CharField(null=True, blank=True, max_length=255)
    group_acronym = models.ForeignKey(IETFWG, null=True, blank=True)
    filename = models.CharField(null=True, blank=True, max_length=255)
    creation_date = models.DateField(null=True, blank=True)
    submission_date = models.DateField(null=True, blank=True)
    remote_ip = models.CharField(null=True, blank=True, max_length=100)
    revision = models.CharField(null=True, blank=True, max_length=3)
    submitter_tag = models.IntegerField(null=True, blank=True)
    auth_key = models.CharField(null=True, blank=True, max_length=255)
    idnits_message = models.TextField(null=True, blank=True)
    file_type = models.CharField(null=True, blank=True, max_length=50)
    comment_to_sec = models.TextField(null=True, blank=True)
    abstract = models.TextField(null=True, blank=True)
    txt_page_count = models.IntegerField(null=True, blank=True)
    error_message = models.CharField(null=True, blank=True, max_length=255)
    warning_message = models.TextField(null=True, blank=True)
    wg_submission = models.IntegerField(null=True, blank=True)
    filesize = models.IntegerField(null=True, blank=True)
    man_posted_date = models.DateField(null=True, blank=True)
    man_posted_by = models.CharField(null=True, blank=True, max_length=255)
    first_two_pages = models.TextField(null=True, blank=True)
    sub_email_priority = models.IntegerField(null=True, blank=True)
    invalid_version = models.IntegerField(null=True, blank=True)
    idnits_failed = models.IntegerField(null=True, blank=True)
    submission_hash = models.CharField(null=True, blank=True, max_length=255)

    class Meta:
        db_table = 'id_submission_detail'


class IdApprovedDetail(models.Model):
    id = models.AutoField(primary_key=True)
    filename = models.CharField(null=True, blank=True, max_length=255)
    approved_status = models.IntegerField(null=True, blank=True)
    approved_person_tag = models.IntegerField(null=True, blank=True)
    approved_date = models.DateField(null=True, blank=True)
    recorded_by = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'id_approved_detail'


class TempIdAuthors(models.Model):
    id = models.AutoField(primary_key=True)
    id_document_tag = models.IntegerField()
    first_name = models.CharField(blank=True, max_length=255)
    last_name = models.CharField(blank=True, max_length=255)
    email_address = models.CharField(blank=True, max_length=255)
    last_modified_date = models.DateField(null=True, blank=True)
    last_modified_time = models.CharField(blank=True, max_length=100)
    author_order = models.IntegerField(null=True, blank=True)
    submission = models.ForeignKey(IdSubmissionDetail)

    class Meta:
        db_table = 'temp_id_authors'

    def email(self):
        return ('%s %s' % (self.first_name, self.last_name), self.email_address)
