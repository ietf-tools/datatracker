import hashlib

from django.conf import settings
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.db import models
from django.db.models import signals, Q

from ietf.utils.mail import send_mail
from ietf.doc.models import Document, DocEvent
from ietf.group.models import Group, Role

from ietf.community.rules import TYPES_OF_RULES, RuleManager
from ietf.community.display import (TYPES_OF_SORT, DisplayField,
                                    SortMethod)
from ietf.community.constants import SIGNIFICANT_STATES


class CommunityList(models.Model):

    user = models.ForeignKey(User, blank=True, null=True)
    group = models.ForeignKey(Group, blank=True, null=True)
    added_ids = models.ManyToManyField(Document)
    secret = models.CharField(max_length=255, null=True, blank=True)
    cached = models.TextField(null=True, blank=True)

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
            return 'mine'
        else:
            return '%s' % self.group.acronym

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
            return reverse('manage_personal_list', None, args=())
        else:
            return reverse('manage_group_list', None, args=(self.group.acronym, ))

    def get_display_config(self):
        dconfig = getattr(self, '_cached_dconfig', None)
        if not dconfig:
            self._cached_dconfig = DisplayConfiguration.objects.get_or_create(community_list=self)[0]
            return self._cached_dconfig
        return self._cached_dconfig

    def get_documents(self):
        if hasattr(self, '_cached_documents'):
            return self._cached_documents
        docs = self.added_ids.all().distinct().select_related('type', 'group', 'ad')
        for rule in self.rule_set.all():
            docs = docs | rule.cached_ids.all().distinct()
        sort_field = self.get_display_config().get_sort_method().get_sort_field()
        docs = docs.distinct().order_by(sort_field)
        self._cached_documents = docs
        return self._cached_documents

    def get_rfcs_and_drafts(self):
        if hasattr(self, '_cached_rfcs_and_drafts'):
            return self._cached_rfcs_and_drafts
        docs = self.get_documents()
        sort_method = self.get_display_config().get_sort_method()
        sort_field = sort_method.get_sort_field()
        if hasattr(sort_method, 'get_full_rfc_sort'):
            rfcs = sort_method.get_full_rfc_sort(docs.filter(states__name='rfc').distinct())
        else:
            rfcs = docs.filter(states__name='rfc').distinct().order_by(sort_field)
        if hasattr(sort_method, 'get_full_draft_sort'):
            drafts = sort_method.get_full_draft_sort(docs.exclude(pk__in=rfcs).distinct())
        else:
            drafts = docs.exclude(pk__in=rfcs).distinct().order_by(sort_field)
        self._cached_rfcs_and_drafts = (rfcs, drafts)
        return self._cached_rfcs_and_drafts

    def add_subscriptor(self, email, significant):
        self.emailsubscription_set.get_or_create(email=email, significant=significant)

    def save(self, *args, **kwargs):
        super(CommunityList, self).save(*args, **kwargs)
        if not self.secret:
            self.secret = hashlib.md5('%s%s%s%s' % (settings.SECRET_KEY, self.id, self.user and self.user.id or '', self.group and self.group.id or '')).hexdigest()
            self.save()

    def update(self):
        self.cached=None
        self.save()


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
        self.community_list.update()

    def delete(self):
        self.community_list.update()
        super(Rule, self).delete()


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

    def get_all_fields(self):
        all_fields = [i for i in DisplayField.__subclasses__()]
        return all_fields

    def get_sort_method(self):
        for i in SortMethod.__subclasses__():
            if i.codename == self.sort_method:
                return i()
        return SortMethod()

    def save(self, *args, **kwargs):
        super(DisplayConfiguration, self).save(*args, **kwargs)
        self.community_list.update()

    def delete(self):
        self.community_list.update()
        super(DisplayConfiguration, self).delete()


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

    event = models.ForeignKey(DocEvent)
    significant = models.BooleanField(default=False)

    def notify_by_email(self):
        clists = CommunityList.objects.filter(
            Q(added_ids=self.event.doc) | Q(rule__cached_ids=self.event.doc)).distinct()
        from_email = settings.DEFAULT_FROM_EMAIL
        for l in clists:
            subject = '%s notification: Changes on %s' % (l.long_name(), self.event.doc.name)
            context = {'notification': self.event,
                       'clist': l}
            to_email = ''
            filter_subscription = {'community_list': l}
            if not self.significant:
                filter_subscription['significant'] = False
            bcc = ','.join(list(set([i.email for i in EmailSubscription.objects.filter(**filter_subscription)])))
            send_mail(None, to_email, from_email, subject, 'community/public/notification_email.txt', context, bcc=bcc)


def notify_events(sender, instance, **kwargs):
    if not isinstance(instance, DocEvent):
        return
    if instance.doc.type.slug != 'draft' or instance.type == 'added_comment':
        return
    (changes, created) = DocumentChangeDates.objects.get_or_create(document=instance.doc)
    changes.normal_change_date = instance.time
    significant = False
    if instance.type == 'changed_document' and 'tate changed' in instance.desc:
        for i in SIGNIFICANT_STATES:
            if ('<b>%s</b>' % i) in instance.desc:
                significant = True
                changes.significant_change_date = instance.time
                break
    elif instance.type == 'new_revision':
        changes.new_version_date = instance.time
    changes.save()
    notification = ListNotification.objects.create(
        event=instance,
        significant=significant,
    )
    notification.notify_by_email()
signals.post_save.connect(notify_events)


class DocumentChangeDates(models.Model):

    document = models.ForeignKey(Document)
    new_version_date = models.DateTimeField(blank=True, null=True)
    normal_change_date = models.DateTimeField(blank=True, null=True)
    significant_change_date = models.DateTimeField(blank=True, null=True)
