# Copyright The IETF Trust 2012-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import email.utils

from django.forms import TextInput
from django.db import models
from django.utils import timezone

import debug                            # pyflakes:ignore

from ietf.person.models import Person
from ietf.group.models import Group
from ietf.doc.models import Document
from ietf.name.models import RoleName
from ietf.utils.models import ForeignKey
from ietf.utils.mail import get_email_addresses_from_text


class HeaderField(models.TextField):
    """TextField that defaults to a TextInput widget"""
    def formfield(self, **kwargs):
        return super().formfield(**{'widget': TextInput, **kwargs})


class Message(models.Model):
    time = models.DateTimeField(default=timezone.now)
    by = ForeignKey(Person)

    subject = HeaderField()
    frm = HeaderField()
    to = HeaderField()
    cc = HeaderField(blank=True)
    bcc = HeaderField(blank=True)
    reply_to = HeaderField(blank=True)
    body = models.TextField()
    content_type = models.CharField(default="text/plain", max_length=255, blank=True)
    msgid = HeaderField(blank=True, null=True, default=email.utils.make_msgid)

    related_groups = models.ManyToManyField(Group, blank=True)
    related_docs = models.ManyToManyField(Document, blank=True)

    sent = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['time']
        indexes = [
            models.Index(fields=['time',]),
        ]

    def __str__(self):
        return "'%s' %s -> %s" % (self.subject, self.frm, self.to)

    def get(self, field):
        r = getattr(self, field)
        return r if isinstance(r, list) else get_email_addresses_from_text(r)
            

class MessageAttachment(models.Model):
    message = ForeignKey(Message)
    filename = models.CharField(max_length=255, db_index=True, blank=True)
    content_type = models.CharField(max_length=255, blank=True)
    encoding = models.CharField(max_length=255, blank=True)
    removed = models.BooleanField(default=False)
    body = models.TextField()

    def __str__(self):
        return self.filename


class SendQueue(models.Model):
    time = models.DateTimeField(default=timezone.now)
    by = ForeignKey(Person)
    
    message = ForeignKey(Message)
    
    send_at = models.DateTimeField(blank=True, null=True)
    sent_at = models.DateTimeField(blank=True, null=True)

    note = models.TextField(blank=True)
    
    class Meta:
        ordering = ['time']
        indexes = [
            models.Index(fields=['time',]),
        ]

    def __str__(self):
        return "'%s' %s -> %s (sent at %s)" % (self.message.subject, self.message.frm, self.message.to, self.sent_at or "<not yet>")


class AnnouncementFrom(models.Model):
    name = ForeignKey(RoleName)
    group = ForeignKey(Group)
    address = models.CharField(max_length=255)

    def __str__(self):
        return self.address

    class Meta:
        verbose_name_plural='Announcement From addresses'
        
