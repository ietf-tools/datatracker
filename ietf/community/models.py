from django.conf import settings
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.db import models
from django.db.models import signals, Q

from ietf.utils.mail import send_mail
from redesign.doc.models import Document
from redesign.group.models import Group, Role

from ietf.community.rules import TYPES_OF_RULES, RuleManager
from ietf.community.display import (TYPES_OF_SORT, DisplayField,
                                    SortMethod)


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
            return bool(Role.objects.filter(name__slug='ad', email__in=person.email_set.all(), group=self.group).count())
        elif self.group.type.slug == 'wg':
            return bool(Role.objects.filter(name__slug='chair', email__in=person.email_set.all(), group=self.group).count())
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

    def get_public_url(self):
        if self.user:
            return reverse('view_personal_list', None, args=(self.user.username, ))
        else:
            return reverse('view_group_list', None, args=(self.group.acronym, ))

    def get_manage_url(self):
        if self.user:
            return reverse('manage_personal_list', None, args=(self.user.username, ))
        else:
            return reverse('manage_group_list', None, args=(self.group.acronym, ))

    def get_display_config(self):
        dconfig = getattr(self, '_cached_dconfig', None)
        if not dconfig:
            self._cached_dconfig = DisplayConfiguration.objects.get_or_create(community_list=self)[0]
            return self._cached_dconfig
        return self._cached_dconfig

    def get_documents(self):
        docs = self.added_ids.all().distinct()
        for rule in self.rule_set.all():
            docs = docs | rule.cached_ids.all().distinct()
        sort_field = self.get_display_config().get_sort_method().get_sort_field()
        docs = docs.distinct().order_by(sort_field)
        return docs

    def add_subscriptor(self, email, significant):
        self.emailsubscription_set.get_or_create(email=email, significant=significant)


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

    def get_callable_rule(self):
        for i in RuleManager.__subclasses__():
            if i.codename == self.rule_type:
                return i(self.value)
        return RuleManager(self.value)

    def save(self, *args, **kwargs):
        super(Rule, self).save(*args, **kwargs)
        rule = self.get_callable_rule()
        self.cached_ids = rule.get_documents()


class DisplayConfiguration(models.Model):

    community_list = models.ForeignKey(CommunityList)
    sort_method = models.CharField(
        max_length=100,
        choices=TYPES_OF_SORT,
        default='by_filename',
        blank=False,
        null=False)
    display_fields = models.TextField(
        default='filename,title,date')

    def get_display_fields_config(self):
        fields = self.display_fields and self.display_fields.split(',') or []
        config = []
        for i in DisplayField.__subclasses__():
            config.append({
                'codename': i.codename,
                'description': i.description,
                'active': i.codename in fields,
            })
        return config

    def get_active_fields(self):
        fields = self.display_fields and self.display_fields.split(',') or ''
        active_fields = [i for i in DisplayField.__subclasses__() if i.codename in fields]
        return active_fields

    def get_sort_method(self):
        for i in SortMethod.__subclasses__():
            if i.codename == self.sort_method:
                return i()
        return SortMethod()


class ExpectedChange(models.Model):

    community_list = models.ForeignKey(CommunityList)
    document = models.ForeignKey(Document)
    expected_date = models.DateField(
        verbose_name='Expected date'
        )


class EmailSubscription(models.Model):
    community_list = models.ForeignKey(CommunityList)
    email = models.CharField(max_length=200)
    significant = models.BooleanField(default=False)


class ListNotification(models.Model):

    document = models.ForeignKey(Document)
    notification_date = models.DateTimeField(auto_now=True)
    desc = models.TextField()
    significant = models.BooleanField(default=False)

    def notify_by_email(self):
        clists = CommunityList.objects.filter(
            Q(added_ids=self.document) | Q(rule__cached_ids=self.document)).distinct()
        from_email = settings.DEFAULT_FROM_EMAIL
        for l in clists:
            subject = '%s notification: Changes on %s' % (l.long_name(), self.document.name)
            context = {'notification': self,
                       'clist': l}
            to_email = ''
            filter_subscription = {'community_list': l}
            if not self.significant:
                filter_subscription['significant'] = False
            bcc = ','.join(list(set([i.email for i in EmailSubscription.objects.filter(**filter_subscription)])))
            send_mail(None, to_email, from_email, subject, 'community/public/notification_email.txt', context, bcc=bcc)

    def save(self, *args, **kwargs):
        super(ListNotification, self).save(*args, **kwargs)
        (changes, created) = DocumentChangeDates.objects.get_or_create(document=self.document)
        if self.significant:
            changes.significant_change_date = self.notification_date
            changes.normal_change_date = self.notification_date
        else:
            changes.normal_change_date = self.notification_date
        changes.save()
        self.notify_by_email()


def save_previous_states(sender, instance, **kwargs):
    if isinstance(instance, Document) and not instance.pk:
        instance.new_document = True
    elif isinstance(instance, Document):
        original = Document.objects.get(pk=instance.pk)
        instance.prev_state = original.state
        instance.prev_wg_state = original.wg_state
        instance.prev_iesg_state = original.iesg_state
        instance.prev_iana_state = original.iana_state
        instance.prev_rfc_state = original.rfc_state


def create_notifications(sender, instance, **kwargs):
    if not isinstance(instance, Document):
        return
    if getattr(instance, 'new_document', False):
        ListNotification.objects.create(
            document=instance,
            significant=True,
            desc='New document created %s: %s' % (instance.name, instance.title)
        )
        return
    if getattr(instance, 'prev_state', False) != False:
        desc = ''
        significant = False
        if instance.prev_state != instance.state:
            desc += 'State changed from %s to %s\n' % (instance.prev_state, instance.state)
        if instance.prev_wg_state != instance.wg_state:
            desc += 'WG state changed from %s to %s\n' % (instance.prev_wg_state, instance.wg_state)
            if instance.iesg_state.name in ['Adopted by a WG', 'In WG Last Call',
                                            'WG Consensus: Waiting for Write-up',
                                            'Parked WG document', 'Dead WG document']:
                significant = True
        if instance.prev_iesg_state != instance.iesg_state:
            desc += 'IESG state changed from %s to %s\n' % (instance.prev_iesg_state, instance.iesg_state)
            if instance.iesg_state.name in ['RFC Published', 'Dead', 'Approved-announcement sent',
                                            'Publication Requested', 'In Last Call', 'IESG Evaluation',
                                            'Sent to the RFC Editor']:
                significant = True
        if instance.prev_iana_state != instance.iana_state:
            desc += 'Iana state changed from %s to %s\n' % (instance.prev_iana_state, instance.iana_state)
        if instance.prev_rfc_state != instance.rfc_state:
            desc += 'RFC state changed from %s to %s\n' % (instance.prev_rfc_state, instance.rfc_state)
        if desc:
            ListNotification.objects.create(
                document=instance,
                significant=significant,
                desc=desc
            )
signals.pre_save.connect(save_previous_states)
signals.post_save.connect(create_notifications)


class DocumentChangeDates(models.Model):

    document = models.ForeignKey(Document)
    new_version_date = models.DateTimeField(blank=True, null=True)
    normal_change_date = models.DateTimeField(blank=True, null=True)
    significant_change_date = models.DateTimeField(blank=True, null=True)
