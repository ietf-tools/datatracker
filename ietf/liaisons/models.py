# Copyright The IETF Trust 2007, All Rights Reserved

from django.db import models
from django.utils.text import slugify

from ietf.name.models import LiaisonStatementPurposeName
from ietf.doc.models import Document
from ietf.person.models import Email
from ietf.group.models import Group
    
class LiaisonStatement(models.Model):
    title = models.CharField(blank=True, max_length=255)
    purpose = models.ForeignKey(LiaisonStatementPurposeName)
    body = models.TextField(blank=True)
    deadline = models.DateField(null=True, blank=True)

    related_to = models.ForeignKey('LiaisonStatement', blank=True, null=True)

    from_group = models.ForeignKey(Group, related_name="liaisonstatement_from_set", null=True, blank=True, help_text="Sender group, if it exists.")
    from_name = models.CharField(max_length=255, help_text="Name of the sender body.")
    from_contact = models.ForeignKey(Email, blank=True, null=True)
    to_group = models.ForeignKey(Group, related_name="liaisonstatement_to_set", null=True, blank=True, help_text="Recipient group, if it exists.")
    to_name = models.CharField(max_length=255, help_text="Name of the recipient body.")
    to_contact = models.CharField(blank=True, max_length=255, help_text="Contacts at recipient body.")

    reply_to = models.CharField(blank=True, max_length=255)

    response_contact = models.CharField(blank=True, max_length=255)
    technical_contact = models.CharField(blank=True, max_length=255)
    cc = models.TextField(blank=True)

    submitted = models.DateTimeField(null=True, blank=True)
    modified = models.DateTimeField(null=True, blank=True)
    approved = models.DateTimeField(null=True, blank=True)

    action_taken = models.BooleanField(default=False)

    attachments = models.ManyToManyField(Document, blank=True)

    def name(self):
        if self.from_group:
            frm = self.from_group.acronym or self.from_group.name
        else:
            frm = self.from_name
        if self.to_group:
            to = self.to_group.acronym or self.to_group.name
        else:
            to = self.to_name
        return slugify("liaison" + " " + self.submitted.strftime("%Y-%m-%d") + " " + frm[:50] + " " + to[:50] + " " + self.title[:115])

    def __unicode__(self):
        return self.title
