# Copyright The IETF Trust 2007, All Rights Reserved

from django.db import models
from django.core.urlresolvers import reverse as urlreverse

from redesign.group.models import *
from redesign.name.models import *
from redesign.person.models import Email
from redesign.util import admin_link

import datetime

class DocumentInfo(models.Model):
    """Any kind of document.  Draft, RFC, Charter, IPR Statement, Liaison Statement"""
    time = models.DateTimeField(default=datetime.datetime.now) # should probably have auto_now=True
    # Document related
    type = models.ForeignKey(DocTypeName, blank=True, null=True) # Draft, Agenda, Minutes, Charter, Discuss, Guideline, Email, Review, Issue, Wiki, External ...
    title = models.CharField(max_length=255)
    # State
    state = models.ForeignKey(DocStateName, blank=True, null=True) # Active/Expired/RFC/Replaced/Withdrawn
    tags = models.ManyToManyField(DocInfoTagName, blank=True, null=True) # Revised ID Needed, ExternalParty, AD Followup, ...
    stream = models.ForeignKey(DocStreamName, blank=True, null=True) # IETF, IAB, IRTF, Independent Submission
    group = models.ForeignKey(Group, blank=True, null=True) # WG, RG, IAB, IESG, Edu, Tools
    wg_state  = models.ForeignKey(WgDocStateName, verbose_name="WG state", blank=True, null=True) # Not/Candidate/Active/Parked/LastCall/WriteUp/Submitted/Dead
    iesg_state = models.ForeignKey(IesgDocStateName, verbose_name="IESG state", blank=True, null=True) # 
    iana_state = models.ForeignKey(IanaDocStateName, verbose_name="IANA state", blank=True, null=True)
    rfc_state = models.ForeignKey(RfcDocStateName, verbose_name="RFC state", blank=True, null=True)
    # Other
    abstract = models.TextField()
    rev = models.CharField(verbose_name="revision", max_length=16)
    pages = models.IntegerField(blank=True, null=True)
    intended_std_level = models.ForeignKey(IntendedStdLevelName, blank=True, null=True)
    std_level = models.ForeignKey(StdLevelName, blank=True, null=True)
    ad = models.ForeignKey(Email, verbose_name="area director", related_name='ad_%(class)s_set', blank=True, null=True)
    shepherd = models.ForeignKey(Email, related_name='shepherd_%(class)s_set', blank=True, null=True)
    notify = models.CharField(max_length=255, blank=True)
    external_url = models.URLField(blank=True) # Should be set for documents with type 'External'.
    note = models.TextField(blank=True)
    internal_comments = models.TextField(blank=True)

    class Meta:
        abstract = True
    def author_list(self):
        return ", ".join(email.address for email in self.authors.all())
    def latest_event(self, *args, **filter_args):
        """Get latest event of optional Python type and with filter
        arguments, e.g. d.latest_event(type="xyz") returns an Event
        while d.latest_event(Status, type="xyz") returns a Status
        event."""
        model = args[0] if args else Event
        e = model.objects.filter(doc=self).filter(**filter_args).order_by('-time', '-id')[:1]
        return e[0] if e else None

class RelatedDocument(models.Model):
    source = models.ForeignKey('Document')
    target = models.ForeignKey('DocAlias')
    relationship = models.ForeignKey(DocRelationshipName)
    def __unicode__(self):
        return u"%s %s %s" % (self.source.name, self.relationship.name.lower(), self.target.name)

class DocumentAuthor(models.Model):
    document = models.ForeignKey('Document')
    author = models.ForeignKey(Email)
    order = models.IntegerField()

    def __unicode__(self):
        return u"%s %s (%s)" % (self.document.name, self.author.get_name(), self.order)

    class Meta:
        ordering = ["document", "order"]
    
class Document(DocumentInfo):
    name = models.CharField(max_length=255, primary_key=True)           # immutable
    related = models.ManyToManyField('DocAlias', through=RelatedDocument, blank=True, related_name="reversely_related_document_set")
    authors = models.ManyToManyField(Email, through=DocumentAuthor, blank=True)

    def __unicode__(self):
        return self.name

    def get_absolute_url(self):
        name = self.name
        if self.state == "rfc":
            aliases = self.docalias_set.filter(name__startswith="rfc")
            if aliases:
                name = aliases[0].name
        return urlreverse('doc_view', kwargs={ 'name': name })

    def file_tag(self):
        # FIXME: compensate for tombstones?
        return u"<%s-%s.txt>" % (self.name, self.rev)

class RelatedDocHistory(models.Model):
    source = models.ForeignKey('DocHistory')
    target = models.ForeignKey('DocAlias', related_name="reversely_related_document_history_set")
    relationship = models.ForeignKey(DocRelationshipName)
    def __unicode__(self):
        return u"%s %s %s" % (self.source.doc.name, self.relationship.name.lower(), self.target.name)

class DocHistoryAuthor(models.Model):
    document = models.ForeignKey('DocHistory')
    author = models.ForeignKey(Email)
    order = models.IntegerField()

    def __unicode__(self):
        return u"%s %s (%s)" % (self.document.doc.name, self.author.get_name(), self.order)

    class Meta:
        ordering = ["document", "order"]

class DocHistory(DocumentInfo):
    doc = models.ForeignKey(Document)   # ID of the Document this relates to
    # Django won't let us define these in the base class, so we have
    # to repeat them
    related = models.ManyToManyField('DocAlias', through=RelatedDocHistory, blank=True)
    authors = models.ManyToManyField(Email, through=DocHistoryAuthor, blank=True)
    def __unicode__(self):
        return unicode(self.doc.name)

def save_document_in_history(doc):
    def get_model_fields_as_dict(obj):
        return dict((field.name, getattr(obj, field.name))
                    for field in obj._meta.fields
                    if field is not obj._meta.pk)

    # copy fields
    fields = get_model_fields_as_dict(doc)
    fields["doc"] = doc
    
    dochist = DocHistory(**fields)
    dochist.save()

    # copy many to many
    for field in doc._meta.many_to_many:
        if not field.rel.through:
            # just add the attributes
            rel = getattr(dochist, field.name)
            for item in getattr(doc, field.name).all():
                rel.add(item)

    # copy remaining tricky many to many
    def transfer_fields(obj, HistModel):
        mfields = get_model_fields_as_dict(item)
        # map doc -> dochist
        for k, v in mfields.iteritems():
            if v == doc:
                mfields[k] = dochist
        HistModel.objects.create(**mfields)

    for item in RelatedDocument.objects.filter(source=doc):
        transfer_fields(item, RelatedDocHistory)

    for item in DocumentAuthor.objects.filter(document=doc):
        transfer_fields(item, DocHistoryAuthor)
                
    return dochist
        
class DocAlias(models.Model):
    """This is used for documents that may appear under multiple names,
    and in particular for RFCs, which for continuity still keep the
    same immutable Document.name, in the tables, but will be referred
    to by RFC number, primarily, after achieving RFC status.
    """
    document = models.ForeignKey(Document)
    name = models.CharField(max_length=255, db_index=True)
    def __unicode__(self):
        return "%s-->%s" % (self.name, self.document.name)
    document_link = admin_link("document")
    class Meta:
        verbose_name = "document alias"
        verbose_name_plural = "document aliases"

class SendQueue(models.Model):
    time = models.DateTimeField()       # Scheduled at this time
    agent  = models.ForeignKey(Email)     # Scheduled by this person
    comment = models.TextField()
    # 
    msg  = models.ForeignKey('Message')
    to   = models.ForeignKey(Email, related_name='to_messages')
    cc   = models.ManyToManyField(Email, related_name='cc_messages')
    send = models.DateTimeField()       # Send message at this time

# class Ballot(models.Model):             # A collection of ballot positions
#     """A collection of ballot positions, and the actions taken during the
#     lifetime of the ballot.

#     The actual ballot positions are found by searching Messages for
#     BallotPositions for this document between the dates indicated by
#     self.initiated.time and (self.closed.time or now)
#     """
#     initiated = models.ForeignKey(Message,                        related_name="initiated_ballots")
#     deferred  = models.ForeignKey(Message, null=True, blank=True, related_name="deferred_ballots")
#     last_call = models.ForeignKey(Message, null=True, blank=True, related_name="lastcalled_ballots")
#     closed    = models.ForeignKey(Message, null=True, blank=True, related_name="closed_ballots")
#     announced = models.ForeignKey(Message, null=True, blank=True, related_name="announced_ballots")


EVENT_TYPES = [
    # core events
    ("new_revision", "Added new revision"),
    ("changed_document", "Changed document metadata"),
    
    # misc document events
    ("added_comment", "Added comment"),
    ("added_tombstone", "Added tombstone"),
    ("expired_document", "Expired document"),
    ("requested_resurrect", "Requested resurrect"),
    ("completed_resurrect", "Completed resurrect"),
    ("published_rfc", "Published RFC"),
    
    # IESG events
    ("started_iesg_process", "Started IESG process on document"),

    ("sent_ballot_announcement", "Sent ballot announcement"),
    ("changed_ballot_position", "Changed ballot position"),
    
    ("changed_ballot_approval_text", "Changed ballot approval text"),
    ("changed_ballot_writeup_text", "Changed ballot writeup text"),

    ("changed_last_call_text", "Changed last call text"),
    ("requested_last_call", "Requested last call"),
    ("sent_last_call", "Sent last call"),
    
    ("changed_status_date", "Changed status date"),
    
    ("scheduled_for_telechat", "Scheduled for telechat"),

    ("iesg_approved", "IESG approved document (no problem)"),
    ("iesg_disapproved", "IESG disapproved document (do not publish)"),
    
    ("approved_in_minute", "Approved in minute"),
    ]

class Event(models.Model):
    """An occurrence in connection with a document."""
    time = models.DateTimeField(default=datetime.datetime.now, help_text="When the event happened")
    type = models.CharField(max_length=50, choices=EVENT_TYPES)
    by = models.ForeignKey(Email, blank=True, null=True) # FIXME: make NOT NULL?
    doc = models.ForeignKey('doc.Document')
    desc = models.TextField()

    def __unicode__(self):
        return u"%s %s at %s" % (self.by.get_name(), self.get_type_display().lower(), self.time)

    class Meta:
        ordering = ['-time', 'id']
        
class Message(Event):
    subj = models.CharField(max_length=255)
    body = models.TextField()

class Text(Event):
    content = models.TextField(blank=True)

class NewRevision(Event):
    rev = models.CharField(max_length=16)
   
# IESG events
class BallotPosition(Event):
    ad = models.ForeignKey(Email)
    pos = models.ForeignKey(BallotPositionName, verbose_name="position", default="norecord")
    discuss = models.TextField(help_text="Discuss text if position is discuss", blank=True)
    discuss_time = models.DateTimeField(help_text="Time discuss text was written", blank=True, null=True)
    comment = models.TextField(help_text="Optional comment", blank=True)
    comment_time = models.DateTimeField(help_text="Time optional comment was written", blank=True, null=True)
    
class Status(Event):
    date = models.DateField(blank=True, null=True)

class Expiration(Event):
    expires = models.DateTimeField(blank=True, null=True)
    
class Telechat(Event):
    telechat_date = models.DateField(blank=True, null=True)
    returning_item = models.BooleanField(default=False)

    
    
