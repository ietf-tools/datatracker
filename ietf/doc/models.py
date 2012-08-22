# Copyright The IETF Trust 2007, All Rights Reserved

from django.db import models
from django.core.urlresolvers import reverse as urlreverse
from django.conf import settings

from ietf.group.models import *
from ietf.name.models import *
from ietf.person.models import Email, Person
from ietf.utils.admin import admin_link

import datetime, os

class StateType(models.Model):
    slug = models.CharField(primary_key=True, max_length=30) # draft, draft-iesg, charter, ...
    label = models.CharField(max_length=255, help_text="Label that should be used (e.g. in admin) for state drop-down for this type of state") # State, IESG state, WG state, ...

    def __unicode__(self):
        return self.slug

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
    stream = models.ForeignKey(StreamName, blank=True, null=True) # IETF, IAB, IRTF, Independent Submission
    group = models.ForeignKey(Group, blank=True, null=True) # WG, RG, IAB, IESG, Edu, Tools

    abstract = models.TextField(blank=True)
    rev = models.CharField(verbose_name="revision", max_length=16, blank=True)
    pages = models.IntegerField(blank=True, null=True)
    order = models.IntegerField(default=1, blank=True)
    intended_std_level = models.ForeignKey(IntendedStdLevelName, verbose_name="Intended standardization level", blank=True, null=True)
    std_level = models.ForeignKey(StdLevelName, verbose_name="Standardization level", blank=True, null=True)
    ad = models.ForeignKey(Person, verbose_name="area director", related_name='ad_%(class)s_set', blank=True, null=True)
    shepherd = models.ForeignKey(Person, related_name='shepherd_%(class)s_set', blank=True, null=True)
    expires = models.DateTimeField(blank=True, null=True)
    notify = models.CharField(max_length=255, blank=True)
    external_url = models.URLField(blank=True) # Should be set for documents with type 'External'.
    note = models.TextField(blank=True)
    internal_comments = models.TextField(blank=True)

    def file_extension(self):
        _,ext = os.path.splitext(self.external_url)
        return ext.lstrip(".").lower()

    def get_file_path(self):
        if self.type_id == "draft":
            return settings.INTERNET_DRAFT_PATH
        elif self.type_id in ("agenda", "minutes", "slides"):
            meeting = self.name.split("-")[1]
            return os.path.join(settings.AGENDA_PATH, meeting, self.type_id) + "/"
        elif self.type_id == "charter":
            return settings.CHARTER_PATH
        elif self.type_id == "conflrev": 
            return settings.CONFLICT_REVIEW_PATH
        else:
            raise NotImplemented

    def href(self):
        try:
            format = settings.DOC_HREFS[self.type_id]
        except KeyError:
            if len(self.external_url):
                return self.external_url
            return None
        meeting = None
        if self.type_id in ("agenda", "minutes", "slides"):
            meeting = self.name.split("-")[1]
        return format.format(doc=self,meeting=meeting)

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
        if self.type_id == "draft" and self.get_state_slug() == "rfc":
            aliases = self.docalias_set.filter(name__startswith="rfc")
            if aliases:
                name = aliases[0].name
        elif self.type_id in ('slides','agenda','minutes'):
            session = self.session_set.all()[0]
            meeting = session.meeting
            if self.type_id in ('agenda','minutes'):
                filename = os.path.splitext(self.external_url)[0]
            else:
                filename = self.external_url
            if meeting.type_id == 'ietf':
                url = '%s/proceedings/%s/%s/%s' % (settings.MEDIA_URL,meeting.number,self.type_id,filename)
            elif meeting.type_id == 'interim':
                url = "%s/proceedings/interim/%s/%s/%s/%s" % (
                    settings.MEDIA_URL,
                    meeting.date.strftime('%Y/%m/%d'),
                    session.group.acronym,
                    self.type_id,
                    filename)
            return url
        return urlreverse('doc_view', kwargs={ 'name': name }, urlconf="ietf.urls")


    def file_tag(self):
        return u"<%s>" % self.filename_with_rev()

    def filename_with_rev(self):
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
        elif self.type_id == "charter":
            return "charter-ietf-%s" % self.chartered_group.acronym
        return name

    def display_name(self):
        name = self.canonical_name()
        if name.startswith('rfc'):
            name = name.upper()
        return name

    #TODO can/should this be a function instead of a property? Currently a view uses it as a property
    @property
    def telechat_date(self):
        e = self.latest_event(TelechatDocEvent, type="scheduled_for_telechat")
        return e.telechat_date if e else None

    def area_acronym(self):
        g = self.group
        if g:
            if g.type_id == "area":
                return g.acronym
            elif g.type_id != "individ":
                return g.parent.acronym
        else:
            return None
    
    def group_acronym(self):
        g = self.group
        if g and g.type_id != "area":
            return g.acronym
        else:
            return "none"

    def on_upcoming_agenda(self):
        e = self.latest_event(TelechatDocEvent, type="scheduled_for_telechat")
        return bool(e and e.telechat_date and e.telechat_date >= datetime.date.today())

    def returning_item(self):
        e = self.latest_event(TelechatDocEvent, type="scheduled_for_telechat")
        return e.returning_item if e else None

    # This is brittle. Resist the temptation to make it more brittle by combining the search against those description
    # strings to one command. It is coincidence that those states have the same description - one might change.
    # Also, this needs further review - is it really the case that there would be no other changed_document events
    # between when the state was changed to defer and when some bit of code wants to know if we are deferred? Why
    # isn't this just returning whether the state is currently a defer state for that document type?
    def active_defer_event(self):
        if self.type_id == "draft" and self.get_state_slug("draft-iesg") == "defer":
            return self.latest_event(type="changed_document", desc__startswith="State changed to <b>IESG Evaluation - Defer</b>")
        elif self.type_id == "conflrev" and self.get_state_slug("conflrev") == "defer":
            return self.latest_event(type="changed_document", desc__startswith="State changed to <b>IESG Evaluation - Defer</b>")
        return None

# This, and several other ballot related functions here, assume that there is only one active ballot for a document at any point in time.
# If that assumption is violated, they will only expose the most recently created ballot
    def ballot_open(self, ballot_type_slug):
        e = self.latest_event(BallotDocEvent, ballot_type__slug=ballot_type_slug)
        return e and not e.type == "closed_ballot"

    def active_ballot(self):
        """Returns the most recently created ballot if it isn't closed."""
        ballot = self.latest_event(BallotDocEvent, type="created_ballot")
        open = self.ballot_open(ballot.ballot_type.slug) if ballot else False
        return ballot if open else None

    def most_recent_ietflc(self):
        """Returns the most recent IETF LastCallDocEvent for this document"""
        return self.latest_event(LastCallDocEvent,type="sent_last_call")

    def displayname_with_link(self):
        return '<a href="%s">%s-%s</a>' % (self.get_absolute_url(), self.name , self.rev)

    def rfc_number(self):
        qs = self.docalias_set.filter(name__startswith='rfc')
        return qs[0].name[3:] if qs else None

    def replaced_by(self):
        return [ rel.source for alias in self.docalias_set.all() for rel in alias.relateddocument_set.filter(relationship='replaces') ]

    def friendly_state(self):
        """ Return a concise text description of the document's current state """
        if self.type_id=='draft':
            # started_iesg_process is is how the redesigned database schema (as of May2012) captured what 
            # used to be "has an IDInternal", aka *Wrapper.in_ietf_process()=True
            in_iesg_process = self.latest_event(type='started_iesg_process')
            iesg_state_summary=None
            if in_iesg_process:
                iesg_state = self.states.get(type='draft-iesg')
                # This knowledge about which tags are reportable IESG substate tags is duplicated in idrfc
                IESG_SUBSTATE_TAGS = ('point', 'ad-f-up', 'need-rev', 'extpty')
                iesg_substate = self.tags.filter(slug__in=IESG_SUBSTATE_TAGS)
                # There really shouldn't be more than one tag in iesg_substate, but this will do something sort-of-sensible if there is
                iesg_state_summary = iesg_state.name
                if iesg_substate:
                     iesg_state_summary = iesg_state_summary + "::"+"::".join(tag.name for tag in iesg_substate)
             
            if self.get_state_slug() == "rfc":
                return "<a href=\"%s\">RFC %d</a>" % (urlreverse('doc_view', args=['rfc%d' % self.rfc_number]), self.rfc_number)
            elif self.get_state_slug() == "repl":
                rs = self.replaced_by()
                if rs:
                    return "Replaced by "+", ".join("<a href=\"%s\">%s</a>" % (urlreverse('doc_view', args=[name]),name) for name in rs)
                else:
                    return "Replaced"
            elif self.get_state_slug() == "active":
                if in_iesg_process:
                    if iesg_state.slug == "dead":
                        # Many drafts in the draft-iesg "Dead" state are not dead
                        # in other state machines; they're just not currently under 
                        # IESG processing. Show them as "I-D Exists (IESG: Dead)" instead...
                        return "I-D Exists (IESG: "+iesg_state_summary+")"
                    elif iesg_state.slug == "lc":
                        expiration_date = str(self.latest_event(LastCallDocEvent,type="sent_last_call").expires.date())
                        return iesg_state_summary + " (ends "+expiration_date+")"
                    else:
                        return iesg_state_summary
                else:
                    return "I-D Exists"
            else:
                if in_iesg_process  and iesg_state.slug == "dead":
                    return self.get_state().name +" (IESG: "+iesg_state_summary+")"
                # Expired/Withdrawn by Submitter/IETF
                return self.get_state().name
        else:
           return self.get_state().name

    def ipr(self):
        """Returns the IPR disclosures against this document (as a queryset over IprDocAlias)."""
        from ietf.ipr.models import IprDocAlias
        return IprDocAlias.objects.filter(doc_alias__document=self)



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
    name = models.CharField(max_length=255) # WG charter canonical names can change if the group acronym changes
    related = models.ManyToManyField('DocAlias', through=RelatedDocHistory, blank=True)
    authors = models.ManyToManyField(Email, through=DocHistoryAuthor, blank=True)
    def __unicode__(self):
        return unicode(self.doc.name)

    def canonical_name(self):
        return self.name

    def latest_event(self, *args, **kwargs):
        kwargs["time__lte"] = self.time
        return self.doc.latest_event(*args, **kwargs)

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
    fields["name"] = doc.canonical_name()
    
    dochist = DocHistory(**fields)
    dochist.save()

    # copy many to many
    for field in doc._meta.many_to_many:
        if field.rel.through and field.rel.through._meta.auto_created:
            setattr(dochist, field.name, getattr(doc, field.name).all())

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

    ("deleted", "Deleted document"),

    # misc draft/RFC events
    ("changed_stream", "Changed document stream"),
    ("expired_document", "Expired document"),
    ("extended_expiry", "Extended expiry of document"),
    ("requested_resurrect", "Requested resurrect"),
    ("completed_resurrect", "Completed resurrect"),
    ("published_rfc", "Published RFC"),

    # WG events
    ("changed_group", "Changed group"),
    ("changed_protocol_writeup", "Changed protocol writeup"),

    # charter events
    ("initial_review", "Set initial review time"),
    ("changed_review_announcement", "Changed WG Review text"),
    ("changed_action_announcement", "Changed WG Action text"),

    # IESG events
    ("started_iesg_process", "Started IESG process on document"),

    ("created_ballot", "Created ballot"),
    ("closed_ballot", "Closed ballot"),
    ("sent_ballot_announcement", "Sent ballot announcement"),
    ("changed_ballot_position", "Changed ballot position"),
    
    ("changed_ballot_approval_text", "Changed ballot approval text"),
    ("changed_ballot_writeup_text", "Changed ballot writeup text"),

    ("changed_last_call_text", "Changed last call text"),
    ("requested_last_call", "Requested last call"),
    ("sent_last_call", "Sent last call"),
    
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
        return u"%s %s by %s at %s" % (self.doc.name, self.get_type_display().lower(), self.by.plain_name(), self.time)

    class Meta:
        ordering = ['-time', '-id']
        
class NewRevisionDocEvent(DocEvent):
    rev = models.CharField(max_length=16)
   
# IESG events
class BallotType(models.Model):
    doc_type = models.ForeignKey(DocTypeName, blank=True, null=True)
    slug = models.SlugField()
    name = models.CharField(max_length=255)
    question = models.TextField(blank=True)
    used = models.BooleanField(default=True)
    order = models.IntegerField(default=0)
    positions = models.ManyToManyField(BallotPositionName, blank=True)

    def __unicode__(self):
        return self.name
    
    class Meta:
        ordering = ['order']

class BallotDocEvent(DocEvent):
    ballot_type = models.ForeignKey(BallotType)

    def active_ad_positions(self):
        """Return dict mapping each active AD to a current ballot position (or None if they haven't voted)."""
        active_ads = list(Person.objects.filter(role__name="ad", role__group__state="active"))
        res = {}
    
        if self.doc.latest_event(BallotDocEvent, type="created_ballot") == self:
        
            positions = BallotPositionDocEvent.objects.filter(type="changed_ballot_position",ad__in=active_ads, ballot=self).select_related('ad', 'pos').order_by("-time", "-id")
   
            for pos in positions:
                if pos.ad not in res:
                    res[pos.ad] = pos
    
            for ad in active_ads:
                if ad not in res:
                    res[ad] = None
        return res

    def all_positions(self):
        """Return array holding the current and past positions per AD"""

        positions = []
        seen = {}
        active_ads = list(Person.objects.filter(role__name="ad", role__group__state="active").distinct())
        for e in BallotPositionDocEvent.objects.filter(type="changed_ballot_position", ballot=self).select_related('ad', 'pos').order_by("-time", '-id'):
            if e.ad not in seen:
                e.old_ad = e.ad not in active_ads
                e.old_positions = []
                positions.append(e)
                seen[e.ad] = e
            else:
                latest = seen[e.ad]
                if latest.old_positions:
                    prev = latest.old_positions[-1]
                else:
                    prev = latest.pos
    
                if e.pos != prev:
                    latest.old_positions.append(e.pos)
    
        # add any missing ADs through fake No Record events
        norecord = BallotPositionName.objects.get(slug="norecord")
        for ad in active_ads:
            if ad not in seen:
                e = BallotPositionDocEvent(type="changed_ballot_position", doc=self.doc, ad=ad)
                e.pos = norecord
                e.old_ad = False
                e.old_positions = []
                positions.append(e)

        positions.sort(key=lambda p: (p.old_ad, p.ad.last_name()))
        return positions

class BallotPositionDocEvent(DocEvent):
    ballot = models.ForeignKey(BallotDocEvent, null=True, default=None) # default=None is a temporary migration period fix, should be removed when charter branch is live
    ad = models.ForeignKey(Person)
    pos = models.ForeignKey(BallotPositionName, verbose_name="position", default="norecord")
    discuss = models.TextField(help_text="Discuss text if position is discuss", blank=True)
    discuss_time = models.DateTimeField(help_text="Time discuss text was written", blank=True, null=True)
    comment = models.TextField(help_text="Optional comment", blank=True)
    comment_time = models.DateTimeField(help_text="Time optional comment was written", blank=True, null=True)
    
class WriteupDocEvent(DocEvent):
    text = models.TextField(blank=True)

class LastCallDocEvent(DocEvent):
    expires = models.DateTimeField(blank=True, null=True)
    
class TelechatDocEvent(DocEvent):
    telechat_date = models.DateField(blank=True, null=True)
    returning_item = models.BooleanField(default=False)

# charter events
class InitialReviewDocEvent(DocEvent):
    expires = models.DateTimeField(blank=True, null=True)
