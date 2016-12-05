# Copyright The IETF Trust 2007, All Rights Reserved

from django.conf import settings
from django.core.urlresolvers import reverse as urlreverse
from django.db import models
from django.utils.text import slugify

from ietf.person.models import Email, Person
from ietf.name.models import (LiaisonStatementPurposeName, LiaisonStatementState,
                              LiaisonStatementEventTypeName, LiaisonStatementTagName,
                              DocRelationshipName)
from ietf.doc.models import Document
from ietf.group.models import Group

# maps (previous state id, new state id) to event type id
STATE_EVENT_MAPPING = {
    (u'pending','approved'):'approved',
    (u'pending','dead'):'killed',
    (u'pending','posted'):'posted',
    (u'approved','posted'):'posted',
    (u'dead','pending'):'resurrected',
    (u'pending','pending'):'submitted'
}


class LiaisonStatement(models.Model):
    title = models.CharField(max_length=255)
    from_groups = models.ManyToManyField(Group, blank=True, related_name='liaisonstatement_from_set')
    from_contact = models.ForeignKey(Email, blank=True, null=True)
    to_groups = models.ManyToManyField(Group, blank=True, related_name='liaisonstatement_to_set')
    to_contacts = models.CharField(max_length=2000, help_text="Contacts at recipient group")

    response_contacts = models.CharField(blank=True, max_length=255, help_text="Where to send a response") # RFC4053
    technical_contacts = models.CharField(blank=True, max_length=255, help_text="Who to contact for clarification") # RFC4053
    action_holder_contacts = models.CharField(blank=True, max_length=255, help_text="Who makes sure action is completed")  # incoming only?
    cc_contacts = models.TextField(blank=True)

    purpose = models.ForeignKey(LiaisonStatementPurposeName)
    deadline = models.DateField(null=True, blank=True)
    other_identifiers = models.TextField(blank=True, null=True) # Identifiers from other bodies
    body = models.TextField(blank=True)

    tags = models.ManyToManyField(LiaisonStatementTagName, blank=True)
    attachments = models.ManyToManyField(Document, through='LiaisonStatementAttachment', blank=True)
    state = models.ForeignKey(LiaisonStatementState, default='pending')

    def __unicode__(self):
        return self.title or u"<no title>"

    def change_state(self,state_id=None,person=None):
        '''Helper function to change state of liaison statement and create appropriate
        event'''
        previous_state_id = self.state_id
        self.set_state(state_id)
        event_type_id = STATE_EVENT_MAPPING[(previous_state_id,state_id)]
        LiaisonStatementEvent.objects.create(
            type_id=event_type_id,
            by=person,
            statement=self,
            desc='Statement {}'.format(event_type_id.capitalize())
        )

    def get_absolute_url(self):
        return settings.IDTRACKER_BASE_URL + urlreverse('ietf.liaisons.views.liaison_detail',kwargs={'object_id':self.id})

    def is_outgoing(self):
        return self.to_groups.first().type_id == 'sdo'

    def latest_event(self, *args, **filter_args):
        """Get latest event of optional Python type and with filter
        arguments, e.g. d.latest_event(type="xyz") returns an LiaisonStatementEvent
        while d.latest_event(WriteupDocEvent, type="xyz") returns a
        WriteupDocEvent event."""
        model = args[0] if args else LiaisonStatementEvent
        e = model.objects.filter(statement=self).filter(**filter_args).order_by('-time', '-id')[:1]
        return e[0] if e else None

    def name(self):
        if self.from_groups.count():
            frm = ', '.join([i.acronym or i.name for i in self.from_groups.all()])
        else:
            frm = self.from_name
        if self.to_groups.count():
            to = ', '.join([i.acronym or i.name for i in self.to_groups.all()])
        else:
            to = self.to_name
        return slugify("liaison" + " " + self.submitted.strftime("%Y-%m-%d") + " " + frm[:50] + " " + to[:50] + " " + self.title[:115])

    @property
    def posted(self):
        if hasattr(self,'prefetched_posted_events') and self.prefetched_posted_events:
            return self.prefetched_posted_events[0].time
        else:
            event = self.latest_event(type='posted')
            if event:
                return event.time
        return None

    @property
    def submitted(self):
        event = self.latest_event(type='submitted')
        if event:
            return event.time
        return None

    @property
    def sort_date(self):
        """Returns the date to use for sorting, for posted statements this is post date,
        for pending statements this is submitted date"""
        if self.state_id == 'posted':
            return self.posted
        else:
            return self.submitted

    @property
    def modified(self):
        event = self.liaisonstatementevent_set.all().order_by('-time').first()
        if event:
            return event.time
        return None

    @property
    def approved(self):
        return self.state_id in ('approved','posted')

    @property
    def action_taken(self):
        if hasattr(self,'prefetched_tags'):
            return bool(self.prefetched_tags)
        else:
            return self.tags.filter(slug='taken').exists()
        
    def active_attachments(self):
        '''Returns attachments with removed ones filtered out'''
        return self.attachments.exclude(liaisonstatementattachment__removed=True)

    @property
    def awaiting_action(self):
        if getattr(self, '_awaiting_action', None) != None:
            return bool(self._awaiting_action)
        return self.tags.filter(slug='awaiting').exists()

    def _get_group_display(self, groups):
        '''Returns comma separated string of group acronyms, non-wg are uppercase'''
        acronyms = []
        for group in groups:
            if group.type.slug == 'wg':
                acronyms.append(group.acronym)
            else:
                acronyms.append(group.acronym.upper())
        return ', '.join(acronyms)
        
    @property
    def from_groups_display(self):
        '''Returns comma separated list of from_group names'''
        if hasattr(self, 'prefetched_from_groups'):
            return self._get_group_display(self.prefetched_from_groups)
        else:
            return self._get_group_display(self.from_groups.order_by('acronym'))

    @property
    def to_groups_display(self):
        '''Returns comma separated list of to_group names'''
        if hasattr(self, 'prefetched_to_groups'):
            return self._get_group_display(self.prefetched_to_groups)
        else:
            return self._get_group_display(self.to_groups.order_by('acronym'))

    def from_groups_short_display(self):
        '''Returns comma separated list of from_group acronyms.  For use in admin
        interface'''
        groups = self.to_groups.order_by('acronym').values_list('acronym',flat=True)
        return ', '.join(groups)
    from_groups_short_display.short_description = 'From Groups'

    def set_state(self,slug):
        try:
            state = LiaisonStatementState.objects.get(slug=slug)
        except LiaisonStatementState.DoesNotExist:
            return
        self.state = state
        self.save()

    def approver_emails(self):
        '''Send mail requesting approval of pending liaison statement.  Send mail to
        the intersection of approvers for all from_groups
        '''
        approval_set = set()
        if self.from_groups.first():
            approval_set.update(self.from_groups.first().liaison_approvers())
        if self.from_groups.count() > 1:
            for group in self.from_groups.all():
                approval_set.intersection_update(group.liaison_approvers())
        return list(set([ r.email.address for r in approval_set ]))

class LiaisonStatementAttachment(models.Model):
    statement = models.ForeignKey(LiaisonStatement)
    document = models.ForeignKey(Document)
    removed = models.BooleanField(default=False)

    def __unicode__(self):
        return self.document.name


class RelatedLiaisonStatement(models.Model):
    source = models.ForeignKey(LiaisonStatement, related_name='source_of_set')
    target = models.ForeignKey(LiaisonStatement, related_name='target_of_set')
    relationship = models.ForeignKey(DocRelationshipName)

    def __unicode__(self):
        return u"%s %s %s" % (self.source.title, self.relationship.name.lower(), self.target.title)


class LiaisonStatementGroupContacts(models.Model):
    group = models.ForeignKey(Group, unique=True, null=True)
    contacts = models.CharField(max_length=255,blank=True)
    cc_contacts = models.CharField(max_length=255,blank=True)

    def __unicode__(self):
        return u"%s" % self.group.name


class LiaisonStatementEvent(models.Model):
    time = models.DateTimeField(auto_now_add=True)
    type = models.ForeignKey(LiaisonStatementEventTypeName)
    by = models.ForeignKey(Person)
    statement = models.ForeignKey(LiaisonStatement)
    desc = models.TextField()

    def __unicode__(self):
        return u"%s %s by %s at %s" % (self.statement.title, self.type.slug, self.by.plain_name(), self.time)

    class Meta:
        ordering = ['-time', '-id']
