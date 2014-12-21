# Copyright The IETF Trust 2007, All Rights Reserved

from django.db import models

from ietf.doc.models import DocAlias


LICENSE_CHOICES = (
    (0, ''),
    (1, 'a) No License Required for Implementers.'),
    (2, 'b) Royalty-Free, Reasonable and Non-Discriminatory License to All Implementers.'),
    (3, 'c) Reasonable and Non-Discriminatory License to All Implementers with Possible Royalty/Fee.'),
    (4, 'd) Licensing Declaration to be Provided Later (implies a willingness'
        ' to commit to the provisions of a), b), or c) above to all implementers;'
        ' otherwise, the next option "Unwilling to Commit to the Provisions of'
        ' a), b), or c) Above". - must be selected).'),
    (5, 'e) Unwilling to Commit to the Provisions of a), b), or c) Above.'),
    (6, 'f) See Text Below for Licensing Declaration.'),
)
STDONLY_CHOICES = (
    (0, ""),
    (1,  "The licensing declaration is limited solely to standards-track IETF documents."),
)
SELECT_CHOICES = (
    (0, 'NO'),
    (1, 'YES'),
    (2, 'NO'),
)
STATUS_CHOICES = (
    ( 0, "Waiting for approval" ), 
    ( 1, "Approved and Posted" ), 
    ( 2, "Rejected by Administrator" ), 
    ( 3, "Removed by Request" ), 
)

class IprDetail(models.Model):
    ipr_id = models.AutoField(primary_key=True)
    title = models.CharField(blank=True, db_column="document_title", max_length=255)

    # Legacy information fieldset
    legacy_url_0 = models.CharField(blank=True, null=True, db_column="old_ipr_url", max_length=255)
    legacy_url_1 = models.CharField(blank=True, null=True, db_column="additional_old_url1", max_length=255)
    legacy_title_1 = models.CharField(blank=True, null=True, db_column="additional_old_title1", max_length=255)
    legacy_url_2 = models.CharField(blank=True, null=True, db_column="additional_old_url2", max_length=255)
    legacy_title_2 = models.CharField(blank=True, null=True, db_column="additional_old_title2", max_length=255)

    # Patent holder fieldset
    legal_name = models.CharField("Legal Name", db_column="p_h_legal_name", max_length=255)

    # Patent Holder Contact fieldset
    # self.contact.filter(contact_type=1)

    # IETF Contact fieldset
    # self.contact.filter(contact_type=3)
    
    # Related IETF Documents fieldset
    rfc_number = models.IntegerField(null=True, editable=False, blank=True)	# always NULL
    id_document_tag = models.IntegerField(null=True, editable=False, blank=True)	# always NULL
    other_designations = models.CharField(blank=True, max_length=255)
    document_sections = models.TextField("Specific document sections covered", blank=True, max_length=255, db_column='disclouser_identify')

    # Patent Information fieldset
    patents = models.TextField("Patent Applications", db_column="p_applications", max_length=255)
    date_applied = models.CharField(max_length=255)
    country = models.CharField(max_length=255)
    notes = models.TextField("Additional notes", db_column="p_notes", blank=True)
    is_pending = models.IntegerField("Unpublished Pending Patent Application", blank=True, null=True, choices=SELECT_CHOICES, db_column="selecttype")
    applies_to_all = models.IntegerField("Applies to all IPR owned by Submitter", blank=True, null=True, choices=SELECT_CHOICES, db_column="selectowned")

    # Licensing Declaration fieldset
    licensing_option = models.IntegerField(null=True, blank=True, choices=LICENSE_CHOICES)
    lic_opt_a_sub = models.IntegerField(null=True, editable=False, choices=STDONLY_CHOICES)
    lic_opt_b_sub = models.IntegerField(null=True, editable=False, choices=STDONLY_CHOICES)
    lic_opt_c_sub = models.IntegerField(null=True, editable=False, choices=STDONLY_CHOICES)
    comments = models.TextField("Licensing Comments", blank=True)
    lic_checkbox = models.BooleanField("All terms and conditions has been disclosed", default=False)


    # Other notes fieldset
    other_notes = models.TextField(blank=True)

    # Generated fields, not part of the submission form
    # Hidden fields
    third_party = models.BooleanField(default=False)
    generic = models.BooleanField(default=False)
    comply = models.BooleanField(default=False)

    status = models.IntegerField(null=True, blank=True, choices=STATUS_CHOICES)
    submitted_date = models.DateField(blank=True)
    update_notified_date = models.DateField(null=True, blank=True)

    def __unicode__(self):
        return self.title

    @models.permalink
    def get_absolute_url(self):
        return ('ietf.ipr.views.show', [str(self.ipr_id)])

    def get_submitter(self):
	try:
	    return self.contact.get(contact_type=3)
	except IprContact.DoesNotExist:
	    return None
        except IprContact.MultipleObjectsReturned:
            return self.contact.filter(contact_type=3)[0]

    def docs(self):
        return self.iprdocalias_set.select_related("doc_alias", "doc_alias__document").order_by("id")

class IprContact(models.Model):
    TYPE_CHOICES = (
	(1, 'Patent Holder Contact'),
	(2, 'IETF Participant Contact'),
	(3, 'Submitter Contact'),
    )
    contact_id = models.AutoField(primary_key=True)
    ipr = models.ForeignKey(IprDetail, related_name="contact")
    contact_type = models.IntegerField(choices=TYPE_CHOICES)
    name = models.CharField(max_length=255)
    title = models.CharField(blank=True, max_length=255)
    department = models.CharField(blank=True, max_length=255)
    address1 = models.CharField(blank=True, max_length=255)
    address2 = models.CharField(blank=True, max_length=255)
    telephone = models.CharField(blank=True, max_length=25)
    fax = models.CharField(blank=True, max_length=25)
    email = models.EmailField(max_length=255)
    def __str__(self):
	return self.name or '<no name>'


class IprNotification(models.Model):
    ipr = models.ForeignKey(IprDetail)
    notification = models.TextField(blank=True)
    date_sent = models.DateField(null=True, blank=True)
    time_sent = models.CharField(blank=True, max_length=25)
    def __str__(self):
	return "IPR notification for %s sent %s %s" % (self.ipr, self.date_sent, self.time_sent)

class IprUpdate(models.Model):
    ipr = models.ForeignKey(IprDetail, related_name='updates')
    updated = models.ForeignKey(IprDetail, db_column='updated', related_name='updated_by')
    status_to_be = models.IntegerField(null=True, blank=True)
    processed = models.IntegerField(null=True, blank=True)


class IprDocAlias(models.Model):
    ipr = models.ForeignKey(IprDetail)
    doc_alias = models.ForeignKey(DocAlias)
    rev = models.CharField(max_length=2, blank=True)

    def formatted_name(self):
        name = self.doc_alias.name
        if name.startswith("rfc"):
            return name.upper()
        elif self.rev:
            return "%s-%s" % (name, self.rev)
        else:
            return name

    def __unicode__(self):
        if self.rev:
            return u"%s which applies to %s-%s" % (self.ipr, self.doc_alias.name, self.rev)
        else:
            return u"%s which applies to %s" % (self.ipr, self.doc_alias.name)

    class Meta:
        verbose_name = "IPR document alias"
        verbose_name_plural = "IPR document aliases"

# ===================================
# New Models
# ===================================

import datetime

from django.conf import settings
from django.core.urlresolvers import reverse

from ietf.name.models import DocRelationshipName,IprDisclosureStateName,IprLicenseTypeName,IprEventTypeName
from ietf.person.models import Person
from ietf.message.models import Message

class IprDisclosureBase(models.Model):
    by                  = models.ForeignKey(Person) # who was logged in, or System if nobody was logged in
    compliant           = models.BooleanField(default=True) # complies to RFC3979
    docs                = models.ManyToManyField(DocAlias, through='IprDocRel')
    holder_legal_name   = models.CharField(max_length=255)
    notes               = models.TextField(blank=True)
    other_designations  = models.CharField(blank=True, max_length=255)
    rel                 = models.ManyToManyField('self', through='RelatedIpr', symmetrical=False)
    state               = models.ForeignKey(IprDisclosureStateName)
    submitter_name      = models.CharField(max_length=255)
    submitter_email     = models.EmailField()
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

class HolderIprDisclosure(IprDisclosureBase):
    ietfer_name              = models.CharField(max_length=255, blank=True) # "Whose Personal Belief Triggered..."
    ietfer_contact_email     = models.EmailField(blank=True)
    ietfer_contact_info      = models.TextField(blank=True)
    patent_info              = models.TextField()
    has_patent_pending       = models.BooleanField(default=False)
    holder_contact_email     = models.EmailField()
    holder_contact_name      = models.CharField(max_length=255)
    holder_contact_info      = models.TextField(blank=True)
    licensing                = models.ForeignKey(IprLicenseTypeName)
    licensing_comments       = models.TextField(blank=True)
    submitter_claims_all_terms_disclosed = models.BooleanField(default=False)

class ThirdPartyIprDisclosure(IprDisclosureBase):
    ietfer_name              = models.CharField(max_length=255) # "Whose Personal Belief Triggered..."
    ietfer_contact_email     = models.EmailField()
    ietfer_contact_info      = models.TextField(blank=True)
    patent_info              = models.TextField()
    has_patent_pending       = models.BooleanField(default=False)

class NonDocSpecificIprDisclosure(IprDisclosureBase):
    '''A Generic IPR Disclosure w/ patent information'''
    holder_contact_name      = models.CharField(max_length=255)
    holder_contact_email     = models.EmailField()
    holder_contact_info      = models.TextField(blank=True)
    patent_info              = models.TextField()
    has_patent_pending       = models.BooleanField(default=False)
    statement                = models.TextField() # includes licensing info

class GenericIprDisclosure(IprDisclosureBase):
    holder_contact_name      = models.CharField(max_length=255)
    holder_contact_email     = models.EmailField()
    holder_contact_info      = models.TextField(blank=True)
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
