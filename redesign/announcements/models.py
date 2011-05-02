from django.db import models

import datetime

from person.models import Email
from group.models import Group

class Message(models.Model):
    time = models.DateTimeField(default=datetime.datetime.now)
    by = models.ForeignKey(Email)

    subject = models.CharField(max_length=255)
    frm = models.CharField(max_length=255)
    to = models.CharField(max_length=255)
    cc = models.CharField(max_length=255, blank=True)
    bcc = models.CharField(max_length=255, blank=True)
    reply_to = models.CharField(max_length=255, blank=True)
    text = models.TextField()

    related_groups = models.ManyToManyField(Group, blank=True)

    class Meta:
        ordering = ['time']

    def __unicode__(self):
        return "'%s' %s -> %s" % (self.subject, self.frm, self.to)

class SendQueue(models.Model):
    time = models.DateTimeField(default=datetime.datetime.now)
    by = models.ForeignKey(Email)
    comment = models.TextField()
    message = models.ForeignKey(Message)
    send_at = models.DateTimeField(blank=True, null=True)
    sent_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['time']
