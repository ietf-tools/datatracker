from django.contrib.auth.models import User
from django.db import models
from django.db.models import signals
from django.core.urlresolvers import reverse as urlreverse

from ietf.doc.models import Document, DocEvent, State
from ietf.group.models import Group
from ietf.person.models import Person, Email

class CommunityList(models.Model):
    user = models.ForeignKey(User, blank=True, null=True)
    group = models.ForeignKey(Group, blank=True, null=True)
    added_docs = models.ManyToManyField(Document)

    def long_name(self):
        if self.user:
            return 'Personal ID list of %s' % self.user.username
        elif self.group:
            return 'ID list for %s' % self.group.name
        else:
            return 'ID list'

    def __unicode__(self):
        return self.long_name()

    def get_absolute_url(self):
        import ietf.community.views
        if self.user:
            return urlreverse(ietf.community.views.view_list, kwargs={ 'username': self.user.username })
        elif self.group:
            return urlreverse("group_docs", kwargs={ 'acronym': self.group.acronym })
        return ""


class SearchRule(models.Model):
    # these types define the UI for setting up the rule, and also
    # helps when interpreting the rule and matching documents
    RULE_TYPES = [
        ('group', 'All I-Ds associated with a particular group'),
        ('area', 'All I-Ds associated with all groups in a particular Area'),
        ('group_rfc', 'All RFCs associated with a particular group'),
        ('area_rfc', 'All RFCs associated with all groups in a particular Area'),

        ('state_iab', 'All I-Ds that are in a particular IAB state'),
        ('state_iana', 'All I-Ds that are in a particular IANA state'),
        ('state_iesg', 'All I-Ds that are in a particular IESG state'),
        ('state_irtf', 'All I-Ds that are in a particular IRTF state'),
        ('state_ise', 'All I-Ds that are in a particular ISE state'),
        ('state_rfceditor', 'All I-Ds that are in a particular RFC Editor state'),
        ('state_ietf', 'All I-Ds that are in a particular Working Group state'),

        ('author', 'All I-Ds with a particular author'),
        ('author_rfc', 'All RFCs with a particular author'),

        ('ad', 'All I-Ds with a particular responsible AD'),

        ('shepherd', 'All I-Ds with a particular document shepherd'),

        ('name_contains', 'All I-Ds with particular text/regular expression in the name'),
    ]

    community_list = models.ForeignKey(CommunityList)
    rule_type = models.CharField(max_length=30, choices=RULE_TYPES)

    # these are filled in depending on the type
    state = models.ForeignKey(State, blank=True, null=True)
    group = models.ForeignKey(Group, blank=True, null=True)
    person = models.ForeignKey(Person, blank=True, null=True)
    text = models.CharField(verbose_name="Text/RegExp", max_length=255, blank=True, default="")

    # store a materialized view/index over which documents are matched
    # by the name_contains rule to avoid having to scan the whole
    # database - we update this manually when the rule is changed and
    # when new documents are submitted
    name_contains_index = models.ManyToManyField(Document)


class EmailSubscription(models.Model):
    community_list = models.ForeignKey(CommunityList)
    email = models.ForeignKey(Email)

    NOTIFICATION_CHOICES = [
        ("all", "All changes"),
        ("significant", "Only significant state changes")
    ]
    notify_on = models.CharField(max_length=30, choices=NOTIFICATION_CHOICES, default="all")

    def __unicode__(self):
        return u"%s to %s (%s changes)" % (self.email, self.community_list, self.notify_on)


def notify_events(sender, instance, **kwargs):
    if not isinstance(instance, DocEvent):
        return

    if instance.doc.type_id != 'draft':
        return

    from ietf.community.utils import notify_event_to_subscribers
    notify_event_to_subscribers(instance)


signals.post_save.connect(notify_events)
