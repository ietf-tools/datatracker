from django.db import models

import datetime

from ietf.person.models import Person
from ietf.group.models import Group
from ietf.doc.models import Document

class Message(models.Model):
    time = models.DateTimeField(default=datetime.datetime.now)
    by = models.ForeignKey(Person)

    subject = models.CharField(max_length=255)
    frm = models.CharField(max_length=255)
    to = models.CharField(max_length=1024)
    cc = models.CharField(max_length=1024, blank=True)
    bcc = models.CharField(max_length=255, blank=True)
    reply_to = models.CharField(max_length=255, blank=True)
    body = models.TextField()
    content_type = models.CharField(default="text/plain", max_length=255, blank=True)

    related_groups = models.ManyToManyField(Group, blank=True)
    related_docs = models.ManyToManyField(Document, blank=True)

    class Meta:
        ordering = ['time']

    def __unicode__(self):
        return "'%s' %s -> %s" % (self.subject, self.frm, self.to)


class MessageAttachment(models.Model):
    message = models.ForeignKey(Message)
    filename = models.CharField(max_length=255, db_index=True, blank=True)
    content_type = models.CharField(max_length=255, blank=True)
    encoding = models.CharField(max_length=255, blank=True)
    removed = models.BooleanField(default=False)
    body = models.TextField()

    def __unicode__(self):
        return self.filename


class SendQueue(models.Model):
    time = models.DateTimeField(default=datetime.datetime.now)
    by = models.ForeignKey(Person)
    
    message = models.ForeignKey(Message)
    
    send_at = models.DateTimeField(blank=True, null=True)
    sent_at = models.DateTimeField(blank=True, null=True)

    note = models.TextField(blank=True)
    
    class Meta:
        ordering = ['time']

    def __unicode__(self):
        return u"'%s' %s -> %s (sent at %s)" % (self.message.subject, self.message.frm, self.message.to, self.sent_at or "<not yet>")
