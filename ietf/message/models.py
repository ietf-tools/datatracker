from django.db import models

import datetime

from ietf.person.models import Email, Person
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

class SendQueue(models.Model):
    time = models.DateTimeField(default=datetime.datetime.now)
    by = models.ForeignKey(Person)
    
    message = models.ForeignKey(Message)
    
    send_at = models.DateTimeField(blank=True, null=True)
    sent_at = models.DateTimeField(blank=True, null=True)

    note = models.TextField(blank=True)
    
    class Meta:
        ordering = ['time']
