# Copyright The IETF Trust 2007, All Rights Reserved

from django.db import models
from django.core.urlresolvers import reverse as urlreverse
from django.conf import settings

from redesign.group.models import *
from redesign.name.models import *
from redesign.person.models import Email, Person
from redesign.util import admin_link

import datetime, os

class StateType(models.Model):
    slug = models.CharField(primary_key=True, max_length=30) # draft, draft_iesg, charter, ...
    label = models.CharField(max_length=255) # State, IESG state, WG state, ...

    def __unicode__(self):
        return self.label

class State(models.Model):
    type = models.ForeignKey(StateType)
    slug = models.SlugField()
    name = models.CharField(max_length=255)
    used = models.BooleanField(default=True)
    desc = models.TextField(blank=True)
    order = models.IntegerField(default=0)

    next_states = models.ManyToManyField('State', related_name="previous_states")

    def __unicode__(self):
        return self.name
    
    class Meta:
        ordering = ["type", "order"]

class DocumentInfo(models.Model):
    """Any kind of document.  Draft, RFC, Charter, IPR Statement, Liaison Statement"""
    time = models.DateTimeField(default=datetime.datetime.now) # should probably have auto_now=True

    type = models.ForeignKey(DocTypeName, blank=True, null=True) # Draft, Agenda, Minutes, Charter, Discuss, Guideline, Email, Review, Issue, Wiki, External ...
    title = models.CharField(max_length=255)

    states = models.ManyToManyField(State, blank=True) # plain state (Active/Expired/...), IESG state, stream state
    tags = models.ManyToManyField(DocTagName, blank=True, null=True) # Revised ID Needed, ExternalParty, AD Followup, ...
    stream = models.ForeignKey(DocStreamName, blank=True, null=True) # IETF, IAB, IRTF, Independent Submission
    group = models.ForeignKey(Group, blank=True, null=True) # WG, RG, IAB, IESG, Edu, Tools

    abstract = models.TextField()
    rev = models.CharField(verbose_name="revision", max_length=16, blank=True)
    pages = models.IntegerField(blank=True, null=True)
    order = models.IntegerField(default=1)
    intended_std_level = models.ForeignKey(IntendedStdLevelName, blank=True, null=True)
    std_level = models.ForeignKey(StdLevelName, blank=True, null=True)
    ad = models.ForeignKey(Person, verbose_name="area director", related_name='ad_%(class)s_set', blank=True, null=True)
    shepherd = models.ForeignKey(Person, related_name='shepherd_%(class)s_set', blank=True, null=True)
    notify = models.CharField(max_length=255, blank=True)
    external_url = models.URLField(blank=True) # Should be set for documents with type 'External'.
    note = models.TextField(blank=True)
    internal_comments = models.TextField(blank=True)

    def get_file_path(self):
        if self.type_id == "draft":
            return settings.INTERNET_DRAFT_PATH
        elif self.type_id in ("agenda", "minutes", "slides"):
            meeting = self.name.split("-")[1]
            return os.path.join(settings.AGENDA_PATH, meeting, self.type_id) + "/"
        else:
            raise NotImplemented

    def set_state(self, state):
        """Switch state type implicit in state to state. This just
        sets the state, doesn't log the change."""
        already_set = self.states.filter(type=state.type)
        others = [s for s in already_set if s != state]
        if others:
            self.states.remove(*others)
        if state not in already_set:
            self.states.add(state)

    def unset_state(self, state_type):
        """Unset state of type so no state of that type is any longer set."""
        self.states.remove(*self.states.filter(type=state_type))

    def get_state(self, state_type=None):
        """Get state of type, or default state for document type if not specified."""
        if state_type == None:
            state_type = self.type_id

        try:
            return self.states.get(type=state_type)
        except State.DoesNotExist:
            return None

    def get_state_slug(self, state_type=None):
        """Get state of type, or default if not specified, returning
        the slug of the state or None. This frees the caller of having
        to check against None before accessing the slug for a
        comparison."""
        s = self.get_state(state_type)
        if s:
            return s.slug
        else:
            return None

    def author_list(self):
        return ", ".join(email.address for email in self.authors.all())

    class Meta:
        abstract = True

class RelatedDocument(models.Model):
    source = models.ForeignKey('Document')
    target = models.ForeignKey('DocAlias')
    relationship = models.ForeignKey(DocRelationshipName)
    def action(self):
        return self.relationship.name
    def inverse_action():
        infinitive = self.relationship.name[:-1]
        return u"%sd by" % infinitive
    def __unicode__(self):
        return u"%s %s %s" % (self.source.name, self.relationship.name.lower(), self.target.name)

class DocumentAuthor(models.Model):
    document = models.ForeignKey('Document')
    author = models.ForeignKey(Email, help_text="Email address used by author for submission")
    order = models.IntegerField(default=1)

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
        if self.get_state_slug() == "rfc":
            aliases = self.docalias_set.filter(name__startswith="rfc")
            if aliases:
                name = aliases[0].name
        return urlreverse('doc_view', kwargs={ 'name': name })

    def file_tag(self):
        return u"<%s>" % self.filename_with_rev()

    def filename_with_rev(self):
        # FIXME: compensate for tombstones?
        return u"%s-%s.txt" % (self.name, self.rev)
    
    def latest_event(self, *args, **filter_args):
        """Get latest event of optional Python type and with filter
        arguments, e.g. d.latest_event(type="xyz") returns an DocEvent
        while d.latest_event(WriteupDocEvent, type="xyz") returns a
        WriteupDocEvent event."""
        model = args[0] if args else DocEvent
        e = model.objects.filter(doc=self).filter(**filter_args).order_by('-time', '-id')[:1]
        return e[0] if e else None

    def canonical_name(self):
        name = self.name
        if self.type_id == "draft" and self.get_state_slug() == "rfc":
            a = self.docalias_set.filter(name__startswith="rfc")
            if a:
                name = a[0].name
        return name

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
    doc = models.ForeignKey(Document, related_name="history_set")
    # Django 1.2 won't let us define these in the base class, so we have
    # to repeat them
    related = models.ManyToManyField('DocAlias', through=RelatedDocHistory, blank=True)
    authors = models.ManyToManyField(Email, through=DocHistoryAuthor, blank=True)
    def __unicode__(self):
        return unicode(self.doc.name)
    class Meta:
        verbose_name = "document history"
        verbose_name_plural = "document histories"

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

class DocReminder(models.Model):
    event = models.ForeignKey('DocEvent')
    type = models.ForeignKey(DocReminderTypeName)
    due = models.DateTimeField()
    active = models.BooleanField(default=True)


EVENT_TYPES = [
    # core events
    ("new_revision", "Added new revision"),
    ("changed_document", "Changed document metadata"),
    ("added_comment", "Added comment"),

    ("uploaded", "Uploaded document"),
    ("deleted", "Deleted document"),

    # misc draft/RFC events
    ("changed_stream", "Changed document stream"),
    ("expired_document", "Expired document"),
    ("requested_resurrect", "Requested resurrect"),
    ("completed_resurrect", "Completed resurrect"),
    ("published_rfc", "Published RFC"),

    # WG events
    ("changed_group", "Changed group"),
    ("changed_protocol_writeup", "Changed protocol writeup"),
    
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

class DocEvent(models.Model):
    """An occurrence for a document, used for tracking who, when and what."""
    time = models.DateTimeField(default=datetime.datetime.now, help_text="When the event happened")
    type = models.CharField(max_length=50, choices=EVENT_TYPES)
    by = models.ForeignKey(Person)
    doc = models.ForeignKey('doc.Document')
    desc = models.TextField()

    def __unicode__(self):
        return u"%s %s at %s" % (self.by.name, self.get_type_display().lower(), self.time)

    class Meta:
        ordering = ['-time', '-id']
        
class NewRevisionDocEvent(DocEvent):
    rev = models.CharField(max_length=16)
   
# IESG events
class BallotPositionDocEvent(DocEvent):
    ad = models.ForeignKey(Person)
    pos = models.ForeignKey(BallotPositionName, verbose_name="position", default="norecord")
    discuss = models.TextField(help_text="Discuss text if position is discuss", blank=True)
    discuss_time = models.DateTimeField(help_text="Time discuss text was written", blank=True, null=True)
    comment = models.TextField(help_text="Optional comment", blank=True)
    comment_time = models.DateTimeField(help_text="Time optional comment was written", blank=True, null=True)
    
class WriteupDocEvent(DocEvent):
    text = models.TextField(blank=True)

class StatusDateDocEvent(DocEvent):
    date = models.DateField(blank=True, null=True)

class LastCallDocEvent(DocEvent):
    expires = models.DateTimeField(blank=True, null=True)
    
class TelechatDocEvent(DocEvent):
    telechat_date = models.DateField(blank=True, null=True)
    returning_item = models.BooleanField(default=False)

