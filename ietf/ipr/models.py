# Copyright The IETF Trust 2007-2023, All Rights Reserved
# -*- coding: utf-8 -*-


from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone

from ietf.doc.models import Document, DocEvent
from ietf.name.models import DocRelationshipName,IprDisclosureStateName,IprLicenseTypeName,IprEventTypeName
from ietf.person.models import Person
from ietf.message.models import Message
from ietf.utils.models import ForeignKey

class IprDisclosureBase(models.Model):
    by                  = ForeignKey(Person) # who was logged in, or System if nobody was logged in
    compliant           = models.BooleanField("Complies to RFC3979", default=True)
    docs                = models.ManyToManyField(Document, through='ipr.IprDocRel')
    holder_legal_name   = models.CharField(max_length=255)
    notes               = models.TextField("Additional notes", blank=True)
    other_designations  = models.CharField("Designations for other contributions", blank=True, max_length=255)
    rel                 = models.ManyToManyField('self', through='ipr.RelatedIpr', symmetrical=False)
    state               = ForeignKey(IprDisclosureStateName)
    submitter_name      = models.CharField(max_length=255,blank=True)
    submitter_email     = models.EmailField(blank=True)
    time                = models.DateTimeField(auto_now_add=True)
    title               = models.CharField(blank=True, max_length=255)

    class Meta:
        ordering = ['-time', '-id']
        indexes = [
            models.Index(fields=['-time', '-id']),
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return settings.IDTRACKER_BASE_URL + reverse('ietf.ipr.views.show',kwargs={'id':self.id})

    def get_child(self):
        """Returns the child instance"""
        for child_class in ('genericiprdisclosure',
                            'holderiprdisclosure',
                            'nondocspecificiprdisclosure',
                            'thirdpartyiprdisclosure'):
            try:
                return getattr(self,child_class)
            except IprDisclosureBase.DoesNotExist:
                pass

    def get_latest_event_msgout(self):
        """Returns the latest IprEvent of type msgout.  For use in templates."""
        return self.latest_event(type='msgout')

    def get_latest_event_submitted(self):
        return self.latest_event(type='submitted')

    def get_latest_event_posted(self):
        return self.latest_event(type='posted')

    def has_legacy_event(self):
        """Returns True if there is one or more LegacyMigrationIprEvents
        for this disclosure"""
        if LegacyMigrationIprEvent.objects.filter(disclosure=self):
            return True
        else:
            return False

    def latest_event(self, *args, **filter_args):
        """Get latest event of optional Python type and with filter
        arguments, e.g. d.latest_event(type="xyz") returns an IprEvent
        while d.latest_event(WriteupDocEvent, type="xyz") returns a
        WriteupDocEvent event."""
        model = args[0] if args else IprEvent
        e = model.objects.filter(disclosure=self).filter(**filter_args).order_by('-time', '-id')[:1]
        return e[0] if e else None

    def set_state(self, state):
        """This just sets the state, doesn't log the change.  Takes a string"""
        try:
            statename = IprDisclosureStateName.objects.get(slug=state)
        except IprDisclosureStateName.DoesNotExist:
            return
        self.state = statename
        self.save()

    @property
    def updates(self):
        """Shortcut for disclosures this disclosure updates"""
        return self.relatedipr_source_set.filter(relationship__slug='updates')
    
    @property
    def updated_by(self):
        """Shortcut for disclosures this disclosure is updated by"""
        return self.relatedipr_target_set.filter(relationship__slug='updates')

    @property
    def update_notified_date(self):
        """Returns the date when the submitters of the IPR that this IPR updates
        were notified"""
        e = self.latest_event(type='update_notify')
        if e:
            return e.time
        else:
            return None

    def recursively_updates(self,disc_set=None):
        """Returns the set of disclosures updated directly or transitively by this disclosure"""
        if disc_set == None:
            disc_set = set()
        new_candidates = set([y.target.get_child() for y in self.updates])
        unseen = new_candidates - disc_set
        disc_set.update(unseen)
        for disc in unseen:
            disc_set.update(disc.recursively_updates(disc_set))
        return disc_set

    def is_thirdparty(self):
        """Returns True if this disclosure is a Third Party disclosure"""
        ipr = self.get_child() if self.__class__ is IprDisclosureBase else self
        return ipr.__class__ is ThirdPartyIprDisclosure


class HolderIprDisclosure(IprDisclosureBase):
    ietfer_name = models.CharField(
        max_length=255, blank=True
    )  # "Whose Personal Belief Triggered..."
    ietfer_contact_email = models.EmailField(blank=True)
    ietfer_contact_info = models.TextField(blank=True)
    patent_info = models.TextField()
    has_patent_pending = models.BooleanField(default=False)
    holder_contact_email = models.EmailField()
    holder_contact_name = models.CharField(max_length=255)
    holder_contact_info = models.TextField(blank=True, help_text="Address, phone, etc.")
    licensing = ForeignKey(IprLicenseTypeName)
    licensing_comments = models.TextField(blank=True)
    submitter_claims_all_terms_disclosed = models.BooleanField(default=False)
    is_blanket_disclosure = models.BooleanField(default=False)
    
    def clean(self):
        if self.is_blanket_disclosure:
            # If the IprLicenseTypeName does not exist, we have a serious problem and a 500 response is ok,
            # so not handling failure of the `get()`
            royalty_free_licensing = IprLicenseTypeName.objects.get(slug="royalty-free")
            if self.licensing_id != royalty_free_licensing.pk:
                raise ValidationError(
                    f'Must select "{royalty_free_licensing.desc}" for a blanket IPR disclosure.')


class ThirdPartyIprDisclosure(IprDisclosureBase):
    ietfer_name              = models.CharField(max_length=255) # "Whose Personal Belief Triggered..."
    ietfer_contact_email     = models.EmailField()
    ietfer_contact_info      = models.TextField(blank=True, help_text="Address, phone, etc.")
    patent_info              = models.TextField()
    has_patent_pending       = models.BooleanField(default=False)

class NonDocSpecificIprDisclosure(IprDisclosureBase):
    '''A Generic IPR Disclosure w/ patent information'''
    holder_contact_name      = models.CharField(max_length=255)
    holder_contact_email     = models.EmailField()
    holder_contact_info      = models.TextField(blank=True, help_text="Address, phone, etc.")
    patent_info              = models.TextField()
    has_patent_pending       = models.BooleanField(default=False)
    statement                = models.TextField() # includes licensing info

class GenericIprDisclosure(IprDisclosureBase):
    holder_contact_name      = models.CharField(max_length=255)
    holder_contact_email     = models.EmailField()
    holder_contact_info      = models.TextField(blank=True, help_text="Address, phone, etc.")
    statement                = models.TextField() # includes licensing info

class IprDocRel(models.Model):
    disclosure = ForeignKey(IprDisclosureBase)
    document   = ForeignKey(Document)
    sections   = models.TextField(blank=True)
    revisions  = models.CharField(max_length=16,blank=True) # allows strings like 01-07
    originaldocumentaliasname = models.CharField(max_length=255, null=True, blank=True)

    def doc_type(self):
        name = self.document.name
        if name.startswith("rfc"):
            return "RFC"
        if name.startswith("draft"):
            return "Internet-Draft"
        if name.startswith("slide"):
            return "Meeting Slide"

    def formatted_name(self):
        name = self.document.name
        if len(name) >= 3 and name[:3] in ("rfc", "bcp", "fyi", "std"):
            return name.upper()
        #elif self.revisions:
        #    return "%s-%s" % (name, self.revisions)
        else:
            return name

    def __str__(self):
        if self.revisions:
            return "%s which applies to %s-%s" % (self.disclosure, self.document.name, self.revisions)
        else:
            return "%s which applies to %s" % (self.disclosure, self.document.name)

class RelatedIpr(models.Model):
    source       = ForeignKey(IprDisclosureBase,related_name='relatedipr_source_set')
    target       = ForeignKey(IprDisclosureBase,related_name='relatedipr_target_set')
    relationship = ForeignKey(DocRelationshipName) # Re-use; change to a dedicated RelName if needed

    def __str__(self):
        return "%s %s %s" % (self.source.title, self.relationship.name.lower(), self.target.title)

class IprEvent(models.Model):
    time        = models.DateTimeField(auto_now_add=True)
    type        = ForeignKey(IprEventTypeName)
    by          = ForeignKey(Person)
    disclosure  = ForeignKey(IprDisclosureBase)
    desc        = models.TextField()
    message     = ForeignKey(Message, null=True, blank=True,related_name='msgevents')
    in_reply_to = ForeignKey(Message, null=True, blank=True,related_name='irtoevents')
    response_due= models.DateTimeField(blank=True,null=True)

    def __str__(self):
        return "%s %s by %s at %s" % (self.disclosure.title, self.type.name.lower(), self.by.plain_name(), self.time)

    def save(self, *args, **kwargs):
        created = not self.pk
        super(IprEvent, self).save(*args, **kwargs)
        if created:
            self.create_doc_events()
        
    def response_past_due(self):
        """Returns true if it's beyond the response_due date and no response has been
        received"""
        qs = IprEvent.objects.filter(disclosure=self.disclosure,in_reply_to=self.message)
        if not qs and timezone.now().date() > self.response_due.date():
            return True
        else:
            return False
        
    def create_doc_events(self):
        """Create DocEvents for documents affected by an IprEvent"""
        # Map from self.type_id to DocEvent.EVENT_TYPES for types that
        # should be logged as DocEvents
        event_type_map = {
            'posted': 'posted_related_ipr',
            'removed': 'removed_related_ipr',
            'removed_objfalse': 'removed_objfalse_related_ipr',
        }
        if self.type_id in event_type_map:
            for doc in self.disclosure.docs.distinct():
                DocEvent.objects.create(
                    type=event_type_map[self.type_id],
                    time=self.time,
                    by=self.by,
                    doc=doc,
                    rev='',
                    desc='%s related IPR disclosure <b>%s</b>' % (self.type.name, 
                                                                  self.disclosure.title),
                )
                    
    class Meta:
        ordering = ['-time', '-id']
        indexes = [
            models.Index(fields=['-time', '-id']),
        ]

class LegacyMigrationIprEvent(IprEvent):
    """A subclass of IprEvent specifically for capturing contents of legacy_url_0,
    the text of a disclosure submitted by email"""
    pass
