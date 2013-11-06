import re, datetime, hashlib

from django.conf import settings
from django.db import models

from ietf.person.models import Person
from ietf.group.models import Group


class IdSubmissionStatus(models.Model):
    status_id = models.IntegerField(primary_key=True)
    status_value = models.CharField(blank=True, max_length=255)

    def __unicode__(self):
        return self.status_value

class IdSubmissionDetail(models.Model):
    submission_id = models.AutoField(primary_key=True)
    temp_id_document_tag = models.IntegerField(null=True, blank=True)
    status = models.ForeignKey(IdSubmissionStatus, db_column='status_id', null=True, blank=True)
    last_updated_date = models.DateField(null=True, blank=True)
    last_updated_time = models.CharField(null=True, blank=True, max_length=25)
    id_document_name = models.CharField(null=True, blank=True, max_length=255)
    group_acronym = models.ForeignKey(Group, null=True, blank=True)
    filename = models.CharField(null=True, blank=True, max_length=255, db_index=True)
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

    def __unicode__(self):
        return u"%s-%s" % (self.filename, self.revision)

    def create_hash(self):
        self.submission_hash = hashlib.md5(settings.SECRET_KEY + self.filename).hexdigest()

    def get_hash(self):
        if not self.submission_hash:
            self.create_hash()
            self.save()
        return self.submission_hash

def create_submission_hash(sender, instance, **kwargs):
    instance.create_hash()

models.signals.pre_save.connect(create_submission_hash, sender=IdSubmissionDetail)

class Preapproval(models.Model):
    """Pre-approved draft submission name."""
    name = models.CharField(max_length=255, db_index=True)
    by = models.ForeignKey(Person)
    time = models.DateTimeField(default=datetime.datetime.now)

    def __unicode__(self):
        return self.name

class TempIdAuthors(models.Model):
    id_document_tag = models.IntegerField()
    first_name = models.CharField(blank=True, max_length=255) # with new schema, this contains the full name while the other name fields are empty to avoid loss of information
    last_name = models.CharField(blank=True, max_length=255)
    email_address = models.CharField(blank=True, max_length=255)
    last_modified_date = models.DateField(null=True, blank=True)
    last_modified_time = models.CharField(blank=True, max_length=100)
    author_order = models.IntegerField(null=True, blank=True)
    submission = models.ForeignKey(IdSubmissionDetail)
    middle_initial = models.CharField(blank=True, max_length=255, null=True)
    name_suffix = models.CharField(blank=True, max_length=255, null=True)

    def email(self):
        return (self.get_full_name(), self.email_address)

    def get_full_name(self):
        parts = (self.first_name or '', self.middle_initial or '', self.last_name or '', self.name_suffix or '')
        return u" ".join(x.strip() for x in parts if x.strip())

    def __unicode__(self):
        return u"%s <%s>" % self.email()
