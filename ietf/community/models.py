from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.db import models

from redesign.doc.models import Document
from redesign.group.models import Group

from ietf.community.rules import TYPES_OF_RULES


class CommunityList(models.Model):

    user = models.ForeignKey(User, blank=True, null=True)
    group = models.ForeignKey(Group, blank=True, null=True)
    added_ids = models.ManyToManyField(Document)

    def check_manager(self, user):
        if user == self.user:
            return True
        if not self.group or self.group.type.slug not in ('area', 'wg'):
            return False
        try:
            person = user.get_profile()
        except:
            return False
        if self.group.type.slug == 'area':
            return bool(Role.objects.filter(name__slug='ad', email__in=person.email_set.all()).count(), group=self.group)
        elif self.group.type.slug == 'wg':
            return bool(Role.objects.filter(name__slug='chair', email__in=person.email_set.all()).count(), group=self.group)
        return False

    def short_name(self):
        if self.user:
            return 'Personal list'
        else:
            return '%s list' % self.group.acronym

    def long_name(self):
        if self.user:
            return 'Personal ID list of %s' % self.user.username
        else:
            return 'ID list for %s' % self.group.name

    def __unicode__(self):
        return self.long_name()

    def get_manage_url(self):
        if self.user:
            return reverse('manage_personal_list', None, args=(self.user.username, ))
        else:
            return reverse('manage_group_list', None, args=(self.group.acronym, ))

class Rule(models.Model):

    community_list = models.ForeignKey(CommunityList)
    cached_ids = models.ManyToManyField(Document)

    rule_type = models.CharField(
        max_length=30,
        choices=TYPES_OF_RULES)
    value = models.CharField(
        max_length=255)

    last_updated = models.DateTimeField(
        auto_now=True)
