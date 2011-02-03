# Copyright The IETF Trust 2007, All Rights Reserved

from django.db import models
from redesign.name.models import *
from redesign.person.models import Email

class Group(models.Model):
    name = models.CharField(max_length=80)
    acronym = models.CharField(max_length=16)
    state = models.ForeignKey(GroupStateName, null=True)
    type = models.ForeignKey(GroupTypeName, null=True)
    charter = models.OneToOneField('doc.Document', related_name='chartered_group', blank=True, null=True)
    parent = models.ForeignKey('Group', blank=True, null=True)
    list_email = models.CharField(max_length=64, blank=True)
    list_pages = models.CharField(max_length=64, blank=True)
    comments = models.TextField(blank=True)
    def __unicode__(self):
        return self.name

# This will actually be extended from Groups, but that requires Django 1.0
# This will record the new state and the date it occurred for any changes
# to a group.  The group acronym must be unique and is the invariant used
# to select group history from this table.
class GroupHistory(models.Model):
    group = models.ForeignKey('Group', related_name='group_history')
    # Event related
    time = models.DateTimeField()
    comment = models.TextField()
    who = models.ForeignKey(Email, related_name='group_changes')
    # inherited from Group:
    name = models.CharField(max_length=64)
    acronym = models.CharField(max_length=16)
    state = models.ForeignKey(GroupStateName)
    type = models.ForeignKey(GroupTypeName)
    charter = models.ForeignKey('doc.Document', related_name='chartered_group_history')
    parent = models.ForeignKey('Group')
    chairs = models.ManyToManyField(Email, related_name='chaired_groups_history')
    list_email = models.CharField(max_length=64)
    list_pages = models.CharField(max_length=64)
    comments = models.TextField(blank=True)
    def __unicode__(self):
        return self.group.name
    class Meta:
        verbose_name_plural="Doc histories"

class Role(models.Model):
    name = models.ForeignKey(RoleName)
    group = models.ForeignKey(Group)
    email = models.ForeignKey(Email)
    auth = models.CharField(max_length=255, blank=True)
    def __unicode__(self):
        return u"%s is %s in %s" % (self.email.get_name(), self.name.name, self.grop.acronym)
    
