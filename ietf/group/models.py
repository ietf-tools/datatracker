# Copyright The IETF Trust 2010-2021, All Rights Reserved
# -*- coding: utf-8 -*-


import email.utils
import os
import re

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.deletion import CASCADE, PROTECT
from django.dispatch import receiver
from django.utils import timezone
from django.utils.text import slugify

import debug                            # pyflakes:ignore

from ietf.name.models import (GroupStateName, GroupTypeName, DocTagName, GroupMilestoneStateName, RoleName,
                              AgendaTypeName, AgendaFilterTypeName, ExtResourceName, SessionPurposeName,
                              AppealArtifactTypeName )
from ietf.person.models import Email, Person
from ietf.utils.db import EmptyAwareJSONField
from ietf.utils.mail import formataddr, send_mail_text
from ietf.utils import log
from ietf.utils.models import ForeignKey, OneToOneField
from ietf.utils.timezone import date_today
from ietf.utils.validators import JSONForeignKeyListValidator


class GroupInfo(models.Model):
    time = models.DateTimeField(default=timezone.now)
    name = models.CharField(max_length=80)
    state = ForeignKey(GroupStateName, null=True)
    type = ForeignKey(GroupTypeName, null=True)
    parent = ForeignKey('Group', blank=True, null=True)
    description = models.TextField(blank=True)
    list_email = models.CharField(max_length=64, blank=True)
    list_subscribe = models.CharField(max_length=255, blank=True)
    list_archive = models.CharField(max_length=255, blank=True)
    comments = models.TextField(blank=True)
    meeting_seen_as_area = models.BooleanField(default=False, help_text='For meeting scheduling, should be considered an area meeting, even if the type is WG')
    

    unused_states = models.ManyToManyField('doc.State', help_text="Document states that have been disabled for the group.", blank=True)
    unused_tags = models.ManyToManyField(DocTagName, help_text="Document tags that have been disabled for the group.", blank=True)

    used_roles = models.JSONField(max_length=256, blank=True, default=list, help_text="Leave an empty list to get the group_type's default used roles")

    uses_milestone_dates = models.BooleanField(default=True)

    ACTIVE_STATE_IDS = ('active', 'bof', 'proposed')  # states considered "active"
    
    def __str__(self):
        return self.name

    def ad_role(self):
        return self.role_set.filter(name='ad').first()

    @property
    def features(self):
        if not hasattr(self, "features_cache"):
            self.features_cache = GroupFeatures.objects.get(type=self.type)
        return self.features_cache

    def about_url(self):
        # bridge gap between group-type prefixed URLs and /group/ ones
        from django.urls import reverse as urlreverse
        kwargs = { 'acronym': self.acronym }
        if self.features.acts_like_wg:
            kwargs["group_type"] = self.type_id
        return urlreverse(self.features.about_page, kwargs=kwargs)

    def is_bof(self):
        return self.state_id in ["bof", "bof-conc"]

    @property
    def is_wg(self):
        return self.type_id == 'wg'

    @property
    def is_active(self):
        # N.B., this has only been thought about for groups of type WG!
        return self.state_id in self.ACTIVE_STATE_IDS

    @property
    def is_individual(self):
        return self.acronym == 'none'

    @property
    def area(self):
        if self.type_id == 'area':
            return self
        elif not self.is_individual and self.parent:
            return self.parent
        return None

    def get_used_roles(self):
        return self.used_roles if len(self.used_roles) > 0 else self.features.default_used_roles

    class Meta:
        abstract = True

class GroupManager(models.Manager):
    def wgs(self):
        return self.get_queryset().filter(type='wg')

    def active_wgs(self):
        return self.wgs().filter(state__in=Group.ACTIVE_STATE_IDS)

    def closed_wgs(self):
        return self.wgs().exclude(state__in=Group.ACTIVE_STATE_IDS)

    def with_meetings(self):
        return self.get_queryset().filter(type__features__has_meetings=True)


class Group(GroupInfo):
    objects = GroupManager()

    acronym = models.SlugField(max_length=40, unique=True, db_index=True)
    charter = OneToOneField('doc.Document', related_name='chartered_group', blank=True, null=True)

    def latest_event(self, *args, **filter_args):
        """Get latest event of optional Python type and with filter
        arguments, e.g. g.latest_event(type="xyz") returns a GroupEvent
        while g.latest_event(ChangeStateGroupEvent, type="xyz") returns a
        ChangeStateGroupEvent event."""
        model = args[0] if args else GroupEvent
        e = model.objects.filter(group=self).filter(**filter_args).order_by('-time', '-id')[:1]
        return e[0] if e else None

    def has_role(self, user, role_names):
        if not isinstance(role_names, (list, tuple)):
            role_names = [role_names]
        return user.is_authenticated and self.role_set.filter(name__in=role_names, person__user=user).exists()

    def is_descendant_of(self, sought_parent):
        parent = self.parent
        descendants = [ self, ]
        while (parent != None) and (parent not in descendants):
            descendants = [ parent ] + descendants
            if parent.acronym == sought_parent:
                return True
            parent = parent.parent
        log.assertion('parent not in descendants')
        return False

    def get_chair(self):
        chair = self.role_set.filter(name__slug='chair')[:1]
        return chair and chair[0] or None

    @property
    def ads(self):
        return sorted(
            self.role_set.filter(name="ad").select_related("email", "person"),
            key=lambda role: role.person.name_parts()[3],  # gets last name
        )

    # these are copied to Group because it is still proxied.
    @property
    def upcase_acronym(self):
        return self.acronym.upper()

    def liaison_approvers(self):
        '''Returns roles that have liaison statement approval authority for group'''

        # a list of tuples, group query kwargs, role query kwargs
        GROUP_APPROVAL_MAPPING = [
            ({'acronym':'ietf'},{'name':'chair'}),
            ({'acronym':'iab'},{'name':'chair'}),
            ({'type':'area'},{'name':'ad'}),
            ({'type':'wg'},{'name':'ad'}), ]
        
        for group_kwargs,role_kwargs in GROUP_APPROVAL_MAPPING:
            if self in Group.objects.filter(**group_kwargs):
                # TODO is there a cleaner way?
                if self.type == 'wg':
                    return self.parent.role_set.filter(**role_kwargs)
                else:
                    return self.role_set.filter(**role_kwargs)
        return self.role_set.none()

    def status_for_meeting(self,meeting):
        previous_meeting = meeting.previous_meeting()
        status_events = self.groupevent_set.filter(
            type='status_update',
            time__lt=meeting.end_datetime(),
        ).order_by('-time')
        if previous_meeting:
            status_events = status_events.filter(
                time__gte=previous_meeting.end_datetime()
            )
        return status_events.first()

    def get_description(self):
        """
        Return self.description if set, otherwise the first paragraph of the
        charter if any, else a short error message.  Used to provide a
        fallback for self.description in group.resources.GroupResource.
        """
        desc = 'No description available'
        if self.description:
            desc = self.description
        elif self.charter:
            path = self.charter.get_file_name()
            if os.path.exists(path):
                text = self.charter.text()
                # split into paragraphs and grab the first non-empty one
                if text:
                    desc = [ p for p in re.split(r'\r?\n\s*\r?\n\s*', text) if p.strip() ][0]
        return desc

    def chat_room_url(self):
        return settings.CHAT_URL_PATTERN.format(chat_room_name=self.acronym)

    def chat_archive_url(self):
        # Zulip has no separate archive
        if 'CHAT_ARCHIVE_URL_PATTERN' in settings:
            return settings.CHAT_ARCHIVE_URL_PATTERN.format(chat_room_name=self.acronym)
        else:
            return self.chat_room_url()


validate_comma_separated_materials = RegexValidator(
    regex=r"[a-z0-9_-]+(,[a-z0-9_-]+)*",
    message="Enter a comma-separated list of material types",
    code='invalid',
)
validate_comma_separated_roles = RegexValidator(
    regex=r"[a-z0-9_-]+(,[a-z0-9_-]+)*",
    message="Enter a comma-separated list of role slugs",
    code='invalid',
)


# JSONFields need callable defaults that work with migrations to avoid sharing
# data structures between instances. These helpers provide that. 
def default_material_types():
    return ["slides"]


def default_admin_roles():
    return ["chair"]


def default_docman_roles():
    return ["ad", "chair", "delegate", "secr"]


def default_groupman_roles():
    return ["ad", "chair"]


def default_groupman_authroles():
    return ["Secretariat"]


def default_matman_roles():
    return ["ad", "chair", "delegate", "secr"]


def default_role_order():
    return ["chair", "secr", "member"]


class GroupFeatures(models.Model):
    type = OneToOneField(GroupTypeName, primary_key=True, null=False, related_name='features')
    #history = HistoricalRecords()

    #
    need_parent = models.BooleanField("Need Parent", default=False, help_text="Does this group type require a parent group?")
    parent_types = models.ManyToManyField(GroupTypeName, blank=True, related_name='child_features',
                                          help_text="Group types allowed as parent of this group type")
    default_parent = models.CharField("Default Parent", max_length=40, blank=True, default="",
                                       help_text="Default parent group acronym for this group type")

    #
    has_milestones          = models.BooleanField("Milestones", default=False)
    has_chartering_process  = models.BooleanField("Chartering", default=False)
    has_documents           = models.BooleanField("Documents",  default=False) # i.e. drafts/RFCs
    has_session_materials   = models.BooleanField("Sess Matrl.",  default=False)
    has_nonsession_materials= models.BooleanField("Other Matrl.",  default=False)
    has_meetings            = models.BooleanField("Meetings",   default=False)
    has_reviews             = models.BooleanField("Reviews",    default=False)
    has_default_chat        = models.BooleanField("Chat",     default=False)
    #
    acts_like_wg            = models.BooleanField("WG-Like",    default=False)
    create_wiki             = models.BooleanField("Wiki",       default=False)
    custom_group_roles      = models.BooleanField("Cust. Roles",default=False)
    customize_workflow      = models.BooleanField("Workflow",   default=False)
    is_schedulable          = models.BooleanField("Schedulable",default=False)
    show_on_agenda          = models.BooleanField("On Agenda",  default=False)
    agenda_filter_type      = models.ForeignKey(AgendaFilterTypeName, default='none', on_delete=PROTECT)
    req_subm_approval       = models.BooleanField("Subm. Approval",  default=False)
    #
    agenda_type             = models.ForeignKey(AgendaTypeName, null=True, default="ietf", on_delete=CASCADE)
    about_page              = models.CharField(max_length=64, blank=False, default="ietf.group.views.group_about" )
    default_tab             = models.CharField(max_length=64, blank=False, default="ietf.group.views.group_about" )
    material_types          = EmptyAwareJSONField(max_length=64, accepted_empty_values=[[], {}], blank=False, default=default_material_types)
    default_used_roles      = EmptyAwareJSONField(max_length=256, accepted_empty_values=[[], {}], blank=False, default=list)
    admin_roles             = EmptyAwareJSONField(max_length=64, accepted_empty_values=[[], {}], blank=False, default=default_admin_roles)  # Trac Admin
    docman_roles            = EmptyAwareJSONField(max_length=128, accepted_empty_values=[[], {}], blank=False, default=default_docman_roles)
    groupman_roles          = EmptyAwareJSONField(max_length=128, accepted_empty_values=[[], {}], blank=False, default=default_groupman_roles)
    groupman_authroles      = EmptyAwareJSONField(max_length=128, accepted_empty_values=[[], {}], blank=False, default=default_groupman_authroles)
    matman_roles            = EmptyAwareJSONField(max_length=128, accepted_empty_values=[[], {}], blank=False, default=default_matman_roles)
    role_order              = EmptyAwareJSONField(max_length=128, accepted_empty_values=[[], {}], blank=False, default=default_role_order,
                                            help_text="The order in which roles are shown, for instance on photo pages.  Enter valid JSON.")
    session_purposes        = EmptyAwareJSONField(max_length=256, accepted_empty_values=[[], {}], blank=False, default=list,
                                                  help_text="Allowed session purposes for this group type",
                                                  validators=[JSONForeignKeyListValidator(SessionPurposeName)])


class GroupHistory(GroupInfo):
    group = ForeignKey(Group, related_name='history_set')
    acronym = models.CharField(max_length=40)

    def ad_role(self):
        # Note - this shows current ADs, not historic ADs
        return self.group.role_set.filter(name='ad').first()

    class Meta:
        verbose_name_plural="group histories"

class GroupURL(models.Model):
    group = ForeignKey(Group)
    name = models.CharField(max_length=255)
    url = models.URLField()

    def __str__(self):
        return u"%s (%s)" % (self.url, self.name)

class GroupExtResource(models.Model):
    group = ForeignKey(Group) # Should this really be to GroupInfo?
    name = models.ForeignKey(ExtResourceName, on_delete=models.CASCADE)
    display_name = models.CharField(max_length=255, default='', blank=True)
    value = models.CharField(max_length=2083) # 2083 is the maximum legal URL length
    def __str__(self):
        priority = self.display_name or self.name.name
        return u"%s (%s) %s" % (priority, self.name.slug, self.value)
        
class GroupMilestoneInfo(models.Model):
    group = ForeignKey(Group)
    # a group has two sets of milestones, current milestones
    # (active/under review/deleted) and charter milestones (active
    # during a charter/recharter event), events for charter milestones
    # are stored on the charter document
    state = ForeignKey(GroupMilestoneStateName)
    desc = models.CharField(verbose_name="Description", max_length=500)
    due = models.DateField(blank=True, null=True)
    order = models.IntegerField(blank=True, null=True)
    resolved = models.CharField(max_length=50, blank=True, help_text="Explanation of why milestone is resolved (usually \"Done\"), or empty if still due.")

    docs = models.ManyToManyField('doc.Document', blank=True)

    def __str__(self):
        return self.desc[:20] + "..."
    class Meta:
        abstract = True
        ordering = [ 'order', 'due', 'id' ]

class GroupMilestone(GroupMilestoneInfo):
    time = models.DateTimeField(auto_now=True)

class GroupMilestoneHistory(GroupMilestoneInfo):
    time = models.DateTimeField()
    milestone = ForeignKey(GroupMilestone, related_name="history_set")

class GroupStateTransitions(models.Model):
    """Captures that a group has overridden the default available
    document state transitions for a certain state."""
    group = ForeignKey(Group)
    state = ForeignKey('doc.State', help_text="State for which the next states should be overridden")
    next_states = models.ManyToManyField('doc.State', related_name='previous_groupstatetransitions_states')

    def __str__(self):
        return u'%s "%s" -> %s' % (self.group.acronym, self.state.name, [s.name for s in self.next_states.all()])

GROUP_EVENT_CHOICES = [
    ("changed_state", "Changed state"),
    ("added_comment", "Added comment"),
    ("info_changed", "Changed metadata"),
    ("requested_close", "Requested closing group"),
    ("changed_milestone", "Changed milestone"),
    ("sent_notification", "Sent notification"),
    ("status_update", "Status update"),
    ]

class GroupEvent(models.Model):
    """An occurrence for a group, used for tracking who, when and what."""
    group = ForeignKey(Group)
    time = models.DateTimeField(default=timezone.now, help_text="When the event happened")
    type = models.CharField(max_length=50, choices=GROUP_EVENT_CHOICES)
    by = ForeignKey(Person)
    desc = models.TextField()

    def __str__(self):
        return u"%s %s at %s" % (self.by.plain_name(), self.get_type_display().lower(), self.time)

    class Meta:
        ordering = ['-time', 'id']
        indexes = [
            models.Index(fields=['-time', '-id']),
        ]

class ChangeStateGroupEvent(GroupEvent):
    state = ForeignKey(GroupStateName)

class MilestoneGroupEvent(GroupEvent):
    milestone = ForeignKey(GroupMilestone)

class Role(models.Model):
    name = ForeignKey(RoleName)
    group = ForeignKey(Group)
    person = ForeignKey(Person)
    email = ForeignKey(Email, help_text="Email address used by person for this role.")
    def __str__(self):
        return u"%s is %s in %s" % (self.person.plain_name(), self.name.name, self.group.acronym or self.group.name)

    def formatted_ascii_email(self):
        return email.utils.formataddr((self.person.plain_ascii(), self.email.address))

    def formatted_email(self):
        return formataddr((self.person.plain_name(), self.email.address))

    class Meta:
        ordering = ['name_id', ]

class RoleHistory(models.Model):
    # RoleHistory doesn't have a time field as it's not supposed to be
    # used on its own - there should always be a GroupHistory
    # accompanying a change in roles, so lookup the appropriate
    # GroupHistory instead
    name = ForeignKey(RoleName)
    group = ForeignKey(GroupHistory)
    person = ForeignKey(Person)
    email = ForeignKey(Email, help_text="Email address used by person for this role.")
    def __str__(self):
        return u"%s is %s in %s" % (self.person.plain_name(), self.name.name, self.group.acronym)

    class Meta:
        verbose_name_plural = "role histories"

class Appeal(models.Model):
    name = models.CharField(max_length=512)
    group = models.ForeignKey(Group, on_delete=models.PROTECT)
    date = models.DateField(default=date_today)

    class Meta:
        ordering = ['-date', '-id']

    def __str__(self):
        return f"{self.date} - {self.name}"

class AppealArtifact(models.Model):
    appeal = ForeignKey(Appeal)
    artifact_type = ForeignKey(AppealArtifactTypeName)
    date = models.DateField(default=date_today)
    title = models.CharField(max_length=256, blank=True, help_text="The artifact_type.name will be used if this field is blank")
    order = models.IntegerField(default=0)
    content_type = models.CharField(max_length=32)
    # "Abusing" BinaryField (see the django docs) for the small number of
    # these things we have on purpose. Later, any non-markdown content may
    # move off into statics instead.
    bits = models.BinaryField(editable=True)

    class Meta:
        ordering = ['date', 'order', 'artifact_type__order']

    def display_title(self):
        if self.title != "":
            return self.title
        else:
            return self.artifact_type.name

    def is_markdown(self):
        return self.content_type == "text/markdown;charset=utf-8"
    
    def download_name(self):
        return f"{self.date}-{slugify(self.display_title())}.{'md' if self.is_markdown() else 'pdf'}"

    def __str__(self):
        return f"{self.date} {self.display_title()} : {self.appeal.name}"

# --- Signal hooks for group models ---

@receiver(models.signals.pre_save, sender=Group)
def notify_rfceditor_of_group_name_change(sender, instance=None, **kwargs):
    if instance:
        try:
            current = Group.objects.get(pk=instance.pk)
        except Group.DoesNotExist:
            return
        addr = settings.RFC_EDITOR_GROUP_NOTIFICATION_EMAIL
        if addr and instance.name != current.name:
            msg = """
This is an automated notification of a group name change:

  acronym:  %s
  old name: %s
  new name: %s

  Regards,

    The datatracker
""" % (current.acronym, current.name, instance.name, )
            send_mail_text(None, to=addr, frm=None, subject="Group '%s' name change"%instance.acronym, txt=msg)
            log.log("Sent notification email: %s: '%s' --> '%s' to %s" % (current.acronym, current.name, instance.name, addr))

            
## Keep this code as a worked and tested example of sending signed notifies
## by HTTP POST.  (superseded for this use case by email notification)
#         url = settings.RFC_EDITOR_GROUP_NOTIFICATION_URL
#         if url and instance.name != current.name:
#             data = {
#                 'acronym': current.acronym,
#                 'old_name': current.name,
#                 'name': instance.name,
#             }
#             # Build signed data
#             key = jwk.JWK()
#             key.import_from_pem(settings.API_PRIVATE_KEY_PEM)
#             payload = json.dumps(data)
#             jwstoken = jws.JWS(payload.encode('utf-8'))
#             jwstoken.add_signature(key, None,
#                            json_encode({"alg": settings.API_KEY_TYPE}),
#                            json_encode({"kid": key.thumbprint()}))
#             sig = jwstoken.serialize()
#             # Send signed data
#             response = requests.post(url, data = { 'jws': sig, })
#             log.log("Sent notify: %s: '%s' --> '%s' to %s, result code %s" %
#                 (current.acronym, current.name, instance.name, url, response.status_code))
#             # Verify locally, to make sure we've got things right
#             key = jwk.JWK()
#             key.import_from_pem(settings.API_PUBLIC_KEY_PEM)
#             jwstoken = jws.JWS()
#             jwstoken.deserialize(sig)
#             jwstoken.verify(key)
#             log.assertion('payload == jwstoken.payload')

