# Copyright The IETF Trust 2007, All Rights Reserved

import datetime

from django.conf import settings
from django.core.urlresolvers import reverse
from django.db import models

from ietf.doc.models import DocAlias
from ietf.name.models import DocRelationshipName,IprDisclosureStateName,IprLicenseTypeName,IprEventTypeName
from ietf.person.models import Person
from ietf.message.models import Message

class IprDisclosureBase(models.Model):
    by                  = models.ForeignKey(Person) # who was logged in, or System if nobody was logged in
    compliant           = models.BooleanField("Complies to RFC3979", default=True)
    docs                = models.ManyToManyField(DocAlias, through='IprDocRel')
    holder_legal_name   = models.CharField(max_length=255)
    notes               = models.TextField("Additional notes", blank=True)
    other_designations  = models.CharField("Designations for other contributions", blank=True, max_length=255)
    rel                 = models.ManyToManyField('self', through='RelatedIpr', symmetrical=False)
    state               = models.ForeignKey(IprDisclosureStateName)
    submitter_name      = models.CharField(max_length=255,blank=True)
    submitter_email     = models.EmailField(blank=True)
    time                = models.DateTimeField(auto_now_add=True)
    title               = models.CharField(blank=True, max_length=255)

    def __unicode__(self):
        return self.title

    def get_absolute_url(self):
        return settings.IDTRACKER_BASE_URL + reverse('ipr_show',kwargs={'id':self.id})

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
        

class HolderIprDisclosure(IprDisclosureBase):
    ietfer_name              = models.CharField(max_length=255, blank=True) # "Whose Personal Belief Triggered..."
    ietfer_contact_email     = models.EmailField(blank=True)
    ietfer_contact_info      = models.TextField(blank=True)
    patent_info              = models.TextField()
    has_patent_pending       = models.BooleanField(default=False)
    holder_contact_email     = models.EmailField()
    holder_contact_name      = models.CharField(max_length=255)
    holder_contact_info      = models.TextField(blank=True, help_text="Address, phone, etc.")
    licensing                = models.ForeignKey(IprLicenseTypeName)
    licensing_comments       = models.TextField(blank=True)
    submitter_claims_all_terms_disclosed = models.BooleanField(default=False)

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
    disclosure = models.ForeignKey(IprDisclosureBase)
    document   = models.ForeignKey(DocAlias)
    sections   = models.TextField(blank=True)
    revisions  = models.CharField(max_length=16,blank=True) # allows strings like 01-07

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
        if name.startswith("rfc"):
            return name.upper()
        #elif self.revisions:
        #    return "%s-%s" % (name, self.revisions)
        else:
            return name

    def __unicode__(self):
        if self.revisions:
            return u"%s which applies to %s-%s" % (self.disclosure, self.document.name, self.revisions)
        else:
            return u"%s which applies to %s" % (self.disclosure, self.document.name)

class RelatedIpr(models.Model):
    source       = models.ForeignKey(IprDisclosureBase,related_name='relatedipr_source_set')
    target       = models.ForeignKey(IprDisclosureBase,related_name='relatedipr_target_set')
    relationship = models.ForeignKey(DocRelationshipName) # Re-use; change to a dedicated RelName if needed

    def __unicode__(self):
        return u"%s %s %s" % (self.source.title, self.relationship.name.lower(), self.target.title)

class IprEvent(models.Model):
    time        = models.DateTimeField(auto_now_add=True)
    type        = models.ForeignKey(IprEventTypeName)
    by          = models.ForeignKey(Person)
    disclosure  = models.ForeignKey(IprDisclosureBase)
    desc        = models.TextField()
    message     = models.ForeignKey(Message, null=True, blank=True,related_name='msgevents')
    in_reply_to = models.ForeignKey(Message, null=True, blank=True,related_name='irtoevents')
    response_due= models.DateTimeField(blank=True,null=True)

    def __unicode__(self):
        return u"%s %s by %s at %s" % (self.disclosure.title, self.type.name.lower(), self.by.plain_name(), self.time)

    def response_past_due(self):
        """Returns true if it's beyond the response_due date and no response has been
        received"""
        qs = IprEvent.objects.filter(disclosure=self.disclosure,in_reply_to=self.message)
        if not qs and datetime.datetime.now().date() > self.response_due.date():
            return True
        else:
            return False
        
    class Meta:
        ordering = ['-time', '-id']

class LegacyMigrationIprEvent(IprEvent):
    """A subclass of IprEvent specifically for capturing contents of legacy_url_0,
    the text of a disclosure submitted by email"""
    pass
