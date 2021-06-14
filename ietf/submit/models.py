# Copyright The IETF Trust 2011-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime
import email
import jsonfield

from django.db import models

import debug                            # pyflakes:ignore

from ietf.doc.models import Document, ExtResource
from ietf.person.models import Person
from ietf.group.models import Group
from ietf.message.models import Message
from ietf.name.models import DraftSubmissionStateName, FormalLanguageName
from ietf.utils.accesstoken import generate_random_key, generate_access_token
from ietf.utils.text import parse_unicode
from ietf.utils.models import ForeignKey


def parse_email_line(line):
    """
    Split email address into name and email like
    email.utils.parseaddr() but return a dictionary
    """
    name, addr = email.utils.parseaddr(line) if '@' in line else (line, '')
    return dict(name=parse_unicode(name), email=addr)

class Submission(models.Model):
    state = ForeignKey(DraftSubmissionStateName)
    remote_ip = models.CharField(max_length=100, blank=True)

    access_key = models.CharField(max_length=255, default=generate_random_key)
    auth_key = models.CharField(max_length=255, blank=True)

    # draft metadata
    name = models.CharField(max_length=255, db_index=True)
    group = ForeignKey(Group, null=True, blank=True)
    title = models.CharField(max_length=255, blank=True)
    abstract = models.TextField(blank=True)
    rev = models.CharField(max_length=3, blank=True)
    pages = models.IntegerField(null=True, blank=True)
    words = models.IntegerField(null=True, blank=True)
    formal_languages = models.ManyToManyField(FormalLanguageName, blank=True, help_text="Formal languages used in document")

    authors = jsonfield.JSONField(default=list, help_text="List of authors with name, email, affiliation and country.")
    note = models.TextField(blank=True)
    replaces = models.CharField(max_length=1000, blank=True)

    first_two_pages = models.TextField(blank=True)
    file_types = models.CharField(max_length=50, blank=True)
    file_size = models.IntegerField(null=True, blank=True)
    document_date = models.DateField(null=True, blank=True)
    submission_date = models.DateField(default=datetime.date.today)
    xml_version = models.CharField(null=True, max_length=4, default=None)

    submitter = models.CharField(max_length=255, blank=True, help_text="Name and email of submitter, e.g. \"John Doe &lt;john@example.org&gt;\".")

    draft = ForeignKey(Document, null=True, blank=True)

    def __str__(self):
        return "%s-%s" % (self.name, self.rev)

    def submitter_parsed(self):
        return parse_email_line(self.submitter)

    def access_token(self):
        return generate_access_token(self.access_key)

    def existing_document(self):
        return Document.objects.filter(name=self.name).first()

    def latest_checks(self):
        checks = [ self.checks.filter(checker=c).latest('time') for c in self.checks.values_list('checker', flat=True).distinct() ]
        return checks

    def has_yang(self):
        return any ( [ c.checker=='yang validation' and c.passed is not None for c in self.latest_checks()] )

    @property
    def replaces_names(self):
        return self.replaces.split(',')

    @property
    def area(self):
        return self.group.area if self.group else None

    @property
    def is_individual(self):
        return self.group.is_individual if self.group else True

    @property
    def revises_wg_draft(self):
        return (
            self.rev != '00'
            and self.group
            and self.group.is_wg
        )

    @property
    def active_wg_drafts_replaced(self):
        return Document.objects.filter(
            docalias__name__in=self.replaces.split(','),
            group__in=Group.objects.active_wgs()
        )

    @property
    def closed_wg_drafts_replaced(self):
        return Document.objects.filter(
            docalias__name__in=self.replaces.split(','),
            group__in=Group.objects.closed_wgs()
        )


class SubmissionCheck(models.Model):
    time = models.DateTimeField(default=datetime.datetime.now)
    submission = ForeignKey(Submission, related_name='checks')
    checker = models.CharField(max_length=256, blank=True)
    passed = models.BooleanField(null=True, default=False)
    message = models.TextField(null=True, blank=True)
    errors = models.IntegerField(null=True, blank=True, default=None)
    warnings = models.IntegerField(null=True, blank=True, default=None)
    items = jsonfield.JSONField(null=True, blank=True, default='{}')
    symbol = models.CharField(max_length=64, default='')
    #
    def __str__(self):
        return "%s submission check: %s: %s" % (self.checker, 'Passed' if self.passed else 'Failed', self.message[:48]+'...')
    def has_warnings(self):
        return self.warnings != '[]'
    def has_errors(self):
        return self.errors != '[]'

class SubmissionEvent(models.Model):
    submission = ForeignKey(Submission)
    time = models.DateTimeField(default=datetime.datetime.now)
    by = ForeignKey(Person, null=True, blank=True)
    desc = models.TextField()

    def __str__(self):
        return "%s %s by %s at %s" % (self.submission.name, self.desc, self.by.plain_name() if self.by else "(unknown)", self.time)

    class Meta:
        ordering = ("-time", "-id")
        indexes = [
            models.Index(fields=['-time', '-id']),
        ]


class Preapproval(models.Model):
    """Pre-approved draft submission name."""
    name = models.CharField(max_length=255, db_index=True)
    by = ForeignKey(Person)
    time = models.DateTimeField(default=datetime.datetime.now)

    def __str__(self):
        return self.name

class SubmissionEmailEvent(SubmissionEvent):
    message     = ForeignKey(Message, null=True, blank=True,related_name='manualevents')
    msgtype     = models.CharField(max_length=25)
    in_reply_to = ForeignKey(Message, null=True, blank=True,related_name='irtomanual')

    def __str__(self):
        return "%s %s by %s at %s" % (self.submission.name, self.desc, self.by.plain_name() if self.by else "(unknown)", self.time)

    class Meta:
        ordering = ['-time', '-id']


class SubmissionExtResource(ExtResource):
    submission = ForeignKey(Submission, related_name='external_resources')
