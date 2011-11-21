# Copyright The IETF Trust 2007, All Rights Reserved

from django.db import models
from redesign.name.models import *
from redesign.person.models import Email, Person

import datetime

class GroupInfo(models.Model):
    time = models.DateTimeField(default=datetime.datetime.now)
    name = models.CharField(max_length=80)
    acronym = models.CharField(max_length=16, blank=True, db_index=True)
    state = models.ForeignKey(GroupStateName, null=True)
    type = models.ForeignKey(GroupTypeName, null=True)
    parent = models.ForeignKey('Group', blank=True, null=True)
    iesg_state = models.ForeignKey(IesgGroupStateName, verbose_name="IESG state", blank=True, null=True)
    ad = models.ForeignKey(Person, blank=True, null=True)
    list_email = models.CharField(max_length=64, blank=True)
    list_subscribe = models.CharField(max_length=255, blank=True)
    list_archive = models.CharField(max_length=255, blank=True)
    comments = models.TextField(blank=True)

    unused_states = models.ManyToManyField('doc.State', help_text="Document states that have been disabled for the group")
    unused_tags = models.ManyToManyField(DocTagName, help_text="Document tags that have been disabled for the group")

    def __unicode__(self):
        return self.name

    class Meta:
        abstract = True

class Group(GroupInfo):
    # we keep charter separate
    charter = models.OneToOneField('doc.Document', related_name='chartered_group', blank=True, null=True)
    
    def latest_event(self, *args, **filter_args):
        """Get latest group event with filter arguments, e.g.
        d.latest_event(type="xyz")."""
        e = GroupEvent.objects.filter(group=self).filter(**filter_args).order_by('-time', '-id')[:1]
        return e[0] if e else None
    
# This will record the new state and the date it occurred for any changes
# to a group.  The group acronym must be unique and is the invariant used
# to select group history from this table.
class GroupHistory(GroupInfo):
    group = models.ForeignKey(Group, related_name='history_set')
    charter = models.ForeignKey('doc.Document', related_name='chartered_group_history_set', blank=True, null=True)
    
    class Meta:
        verbose_name_plural="group histories"

class GroupURL(models.Model):
    group = models.ForeignKey(Group)
    name = models.CharField(max_length=255)
    url = models.URLField(verify_exists=False)

class GroupMilestone(models.Model):
    group = models.ForeignKey(Group)
    desc = models.TextField()
    expected_due_date = models.DateField()
    done = models.BooleanField()
    done_date = models.DateField(null=True, blank=True)
    time = models.DateTimeField(auto_now=True)
    def __unicode__(self):
	return self.desc[:20] + "..."
    class Meta:
	ordering = ['expected_due_date']

class GroupStateTransitions(models.Model):
    """Captures that a group has overriden the default available
    document state transitions for a certain state."""
    group = models.ForeignKey(Group)
    state = models.ForeignKey('doc.State', help_text="State for which the next states should be overridden")
    next_states = models.ManyToManyField('doc.State', related_name='previous_groupstatetransitions_states')

GROUP_EVENT_CHOICES = [("proposed", "Proposed group"),
                       ("started", "Started group"),
                       ("concluded", "Concluded group"),
                       ]
    
class GroupEvent(models.Model):
    """An occurrence for a group, used for tracking who, when and what."""
    group = models.ForeignKey(Group)
    time = models.DateTimeField(default=datetime.datetime.now, help_text="When the event happened")
    type = models.CharField(max_length=50, choices=GROUP_EVENT_CHOICES)
    by = models.ForeignKey(Person)
    desc = models.TextField()

    def __unicode__(self):
        return u"%s %s at %s" % (self.by.name, self.get_type_display().lower(), self.time)

    class Meta:
        ordering = ['-time', 'id']

class Role(models.Model):
    name = models.ForeignKey(RoleName)
    group = models.ForeignKey(Group)
    person = models.ForeignKey(Person)
    email = models.ForeignKey(Email, help_text="Email address used by person for this role")
    def __unicode__(self):
        return u"%s is %s in %s" % (self.email.get_name(), self.name.name, self.group.acronym or self.group.name)

    def formatted_email(self):
        return u'"%s" <%s>' % (self.person.name, self.email.address)

class RoleHistory(models.Model):
    # RoleHistory doesn't have a time field as it's not supposed to be
    # used on its own - there should always be a GroupHistory
    # accompanying a change in roles, so lookup the appropriate
    # GroupHistory instead
    name = models.ForeignKey(RoleName)
    group = models.ForeignKey(GroupHistory)
    person = models.ForeignKey(Person)
    email = models.ForeignKey(Email, help_text="Email address used by person for this role")
    def __unicode__(self):
        return u"%s is %s in %s" % (self.email.get_name(), self.name.name, self.group.acronym)

    class Meta:
        verbose_name_plural = "role histories"
