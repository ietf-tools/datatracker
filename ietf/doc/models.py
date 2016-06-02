# Copyright The IETF Trust 2007, All Rights Reserved

import datetime, os

from django.db import models
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse as urlreverse
from django.core.validators import URLValidator
from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from django.utils.html import mark_safe

import debug                            # pyflakes:ignore

from ietf.group.models import Group
from ietf.name.models import ( DocTypeName, DocTagName, StreamName, IntendedStdLevelName, StdLevelName,
    DocRelationshipName, DocReminderTypeName, BallotPositionName )
from ietf.person.models import Email, Person
from ietf.utils.admin import admin_link


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

    next_states = models.ManyToManyField('State', related_name="previous_states", blank=True)

    def __unicode__(self):
        return self.name
    
    class Meta:
        ordering = ["type", "order"]

IESG_BALLOT_ACTIVE_STATES = ("lc", "writeupw", "goaheadw", "iesg-eva", "defer")
IESG_SUBSTATE_TAGS = ('point', 'ad-f-up', 'need-rev', 'extpty')

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
    shepherd = models.ForeignKey(Email, related_name='shepherd_%(class)s_set', blank=True, null=True)
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
        elif self.type_id in ("agenda", "minutes", "slides", "bluesheets") and self.meeting_related():
            meeting = self.session_set.first().meeting
            return os.path.join(meeting.get_materials_path(), self.type_id) + "/"
        elif self.type_id == "charter":
            return settings.CHARTER_PATH
        elif self.type_id == "conflrev": 
            return settings.CONFLICT_REVIEW_PATH
        elif self.type_id == "statchg":
            return settings.STATUS_CHANGE_PATH
        else:
            return settings.DOCUMENT_PATH_PATTERN.format(doc=self)

    def href(self):
        # If self.external_url truly is an url, use it.  This is a change from
        # the earlier resulution order, but there's at the moment one single
        # instance which matches this (with correct results), so we won't
        # break things all over the place.
        # XXX TODO: move all non-URL 'external_url' values into a field which is
        # better named, or regularize the filename based on self.name
        validator = URLValidator()
        try:
            validator(self.external_url)
            return self.external_url
        except ValidationError:
            pass

        meeting_related = self.meeting_related()

        settings_var = settings.DOC_HREFS
        if meeting_related:
            settings_var = settings.MEETING_DOC_HREFS

        try:
            format = settings_var[self.type_id]
        except KeyError:
            if len(self.external_url):
                return self.external_url
            return None

        meeting = None
        if meeting_related:
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
        self.state_cache = None # invalidate cache

    def unset_state(self, state_type):
        """Unset state of type so no state of that type is any longer set."""
        self.states.remove(*self.states.filter(type=state_type))
        self.state_cache = None # invalidate cache

    def get_state(self, state_type=None):
        """Get state of type, or default state for document type if
        not specified. Uses a local cache to speed multiple state
        reads up."""
        if self.pk == None: # states is many-to-many so not in database implies no state
            return None

        if state_type == None:
            state_type = self.type_id

        if not hasattr(self, "state_cache") or self.state_cache == None:
            self.state_cache = {}
            for s in self.states.all():
                self.state_cache[s.type_id] = s

        return self.state_cache.get(state_type, None)

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

    def friendly_state(self):
        """ Return a concise text description of the document's current state."""
        state = self.get_state()
        if not state:
            return "Unknown state"
    
        if self.type_id == 'draft':
            iesg_state = self.get_state("draft-iesg")
            iesg_state_summary = None
            if iesg_state:
                iesg_substate = [t for t in self.tags.all() if t.slug in IESG_SUBSTATE_TAGS]
                # There really shouldn't be more than one tag in iesg_substate, but this will do something sort-of-sensible if there is
                iesg_state_summary = iesg_state.name
                if iesg_substate:
                     iesg_state_summary = iesg_state_summary + "::"+"::".join(tag.name for tag in iesg_substate)
             
            if state.slug == "rfc":
                return "RFC %s (%s)" % (self.rfc_number(), self.std_level)
            elif state.slug == "repl":
                rs = self.related_that("replaces")
                if rs:
                    return mark_safe("Replaced by " + ", ".join("<a href=\"%s\">%s</a>" % (urlreverse('doc_view', kwargs=dict(name=alias.document)), alias.document) for alias in rs))
                else:
                    return "Replaced"
            elif state.slug == "active":
                if iesg_state:
                    if iesg_state.slug == "dead":
                        # Many drafts in the draft-iesg "Dead" state are not dead
                        # in other state machines; they're just not currently under 
                        # IESG processing. Show them as "I-D Exists (IESG: Dead)" instead...
                        return "I-D Exists (IESG: %s)" % iesg_state_summary
                    elif iesg_state.slug == "lc":
                        e = self.latest_event(LastCallDocEvent, type="sent_last_call")
                        if e:
                            return iesg_state_summary + " (ends %s)" % e.expires.date().isoformat()
    
                    return iesg_state_summary
                else:
                    return "I-D Exists"
            else:
                if iesg_state and iesg_state.slug == "dead":
                    return state.name + " (IESG: %s)" % iesg_state_summary
                # Expired/Withdrawn by Submitter/IETF
                return state.name
        else:
            return state.name

    def author_list(self):
        return ", ".join(email.address for email in self.authors.all())

    # This, and several other ballot related functions here, assume that there is only one active ballot for a document at any point in time.
    # If that assumption is violated, they will only expose the most recently created ballot
    def ballot_open(self, ballot_type_slug):
        e = self.latest_event(BallotDocEvent, ballot_type__slug=ballot_type_slug)
        return e and not e.type == "closed_ballot"

    def active_ballot(self):
        """Returns the most recently created ballot if it isn't closed."""
        ballot = self.latest_event(BallotDocEvent, type__in=("created_ballot", "closed_ballot"))
        if ballot and ballot.type == "created_ballot":
            return ballot
        else:
            return None

    def has_rfc_editor_note(self):
        e = self.latest_event(WriteupDocEvent, type="changed_rfc_editor_note_text")
        return e != None and (e.text != "")

    def meeting_related(self):
        answer = False
        if self.type_id in ("agenda","minutes","bluesheets","slides","recording"):
            answer =  (self.name.split("-")[1] == "interim"
                       or (self if isinstance(self, Document) else self.doc).session_set.exists())
            if self.type_id in ("slides",):
                answer =  answer and self.get_state_slug('reuse_policy')=='single'
        return answer

    def relations_that(self, relationship):
        """Return the related-document objects that describe a given relationship targeting self."""
        if isinstance(relationship, str):
            relationship = [ relationship ]
        if isinstance(relationship, tuple):
            relationship = list(relationship)
        if not isinstance(relationship, list):
            raise TypeError("Expected a string, tuple or list, received %s" % type(relationship))
        if isinstance(self, Document):
            return RelatedDocument.objects.filter(target__document=self, relationship__in=relationship).select_related('source')
        elif isinstance(self, DocHistory):
            return RelatedDocHistory.objects.filter(target__document=self, relationship__in=relationship).select_related('source')
        else:
            return RelatedDocument.objects.none()

    def all_relations_that(self, relationship, related=None):
        if not related:
            related = []
        rels = self.relations_that(relationship)
        for r in rels:
            if not r in related:
                related += [ r ]
                related = r.source.all_relations_that(relationship, related)
        return related

    def relations_that_doc(self, relationship):
        """Return the related-document objects that describe a given relationship from self to other documents."""
        if isinstance(relationship, str):
            relationship = [ relationship ]
        if isinstance(relationship, tuple):
            relationship = list(relationship)
        if not isinstance(relationship, list):
            raise TypeError("Expected a string, tuple or list, received %s" % type(relationship))
        if isinstance(self, Document):
            return RelatedDocument.objects.filter(source=self, relationship__in=relationship).select_related('target__document')
        elif isinstance(self, DocHistory):
            return RelatedDocHistory.objects.filter(source=self, relationship__in=relationship).select_related('target__document')
        else:
            return RelatedDocument.objects.none()
 

    def all_relations_that_doc(self, relationship, related=None):
        if not related:
            related = []
        rels = self.relations_that_doc(relationship)
        for r in rels:
            if not r in related:
                related += [ r ]
                related = r.target.document.all_relations_that_doc(relationship, related)
        return related

    def related_that(self, relationship):
        return list(set([x.source.docalias_set.get(name=x.source.name) for x in self.relations_that(relationship)]))

    def all_related_that(self, relationship, related=None):
        return list(set([x.source.docalias_set.get(name=x.source.name) for x in self.all_relations_that(relationship)]))

    def related_that_doc(self, relationship):
        return list(set([x.target for x in self.relations_that_doc(relationship)]))

    def all_related_that_doc(self, relationship, related=None):
        return list(set([x.target for x in self.all_relations_that_doc(relationship)]))

    class Meta:
        abstract = True

STATUSCHANGE_RELATIONS = ('tops','tois','tohist','toinf','tobcp','toexp')

class RelatedDocument(models.Model):
    source = models.ForeignKey('Document')
    target = models.ForeignKey('DocAlias')
    relationship = models.ForeignKey(DocRelationshipName)
    def action(self):
        return self.relationship.name
    def __unicode__(self):
        return u"%s %s %s" % (self.source.name, self.relationship.name.lower(), self.target.name)

    def is_downref(self):

        if self.source.type.slug!='draft' or self.relationship.slug not in ['refnorm','refold','refunk']:
            return None

        if self.source.get_state().slug == 'rfc':
            source_lvl = self.source.std_level.slug
        elif self.source.intended_std_level:
            source_lvl = self.source.intended_std_level.slug
        else:
            source_lvl = None

        if source_lvl not in ['bcp','ps','ds','std']:
            return None

        if self.target.document.get_state().slug == 'rfc':
            if not self.target.document.std_level:
                target_lvl = 'unkn'
            else:
                target_lvl = self.target.document.std_level.slug
        else:
            if not self.target.document.intended_std_level:
                target_lvl = 'unkn'
            else:
                target_lvl = self.target.document.intended_std_level.slug

        rank = { 'ps':1, 'ds':2, 'std':3, 'bcp':3 }

        if ( target_lvl not in rank ) or ( rank[target_lvl] < rank[source_lvl] ):
            if self.relationship.slug == 'refnorm' and target_lvl!='unkn':
                return "Downref"
            else:
                return "Possible Downref"

        return None

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
    authors = models.ManyToManyField(Email, through=DocumentAuthor, blank=True)

    def __unicode__(self):
        return self.name

    def get_absolute_url(self):
        name = self.name
        if self.type_id == "draft" and self.get_state_slug() == "rfc":
            name = self.canonical_name()
        elif self.type_id in ('slides','agenda','minutes','bluesheets'):
            session = self.session_set.first()
            if session:
                meeting = session.meeting
                if self.type_id in ('agenda','minutes'):
                    filename = os.path.splitext(self.external_url)[0]
                else:
                    filename = self.external_url
                if meeting.type_id == 'ietf':
                    url = '%sproceedings/%s/%s/%s' % (settings.IETF_HOST_URL,meeting.number,self.type_id,filename)
                elif meeting.type_id == 'interim':
                    url = "%sproceedings/interim/%s/%s/%s/%s" % (
                        settings.IETF_HOST_URL,
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
            from ietf.doc.utils_charter import charter_name_for_group
            return charter_name_for_group(self.chartered_group)
        return name

    def canonical_docalias(self):
        return self.docalias_set.get(name=self.name)

    def display_name(self):
        name = self.canonical_name()
        if name.startswith('rfc'):
            name = name.upper()
        return name


    def telechat_date(self, e=None):
        if not e:
            e = self.latest_event(TelechatDocEvent, type="scheduled_for_telechat")
        return e.telechat_date if e and e.telechat_date and e.telechat_date >= datetime.date.today() else None

    def area_acronym(self):
        g = self.group
        if g:
            if g.type_id == "area":
                return g.acronym
            elif g.type_id != "individ" and g.parent:
                return g.parent.acronym
        else:
            return None
    
    def group_acronym(self):
        g = self.group
        if g and g.type_id != "area":
            return g.acronym
        else:
            return "none"

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
            return self.latest_event(type="changed_state", desc__icontains="State changed to <b>IESG Evaluation - Defer</b>")
        elif self.type_id == "conflrev" and self.get_state_slug("conflrev") == "defer":
            return self.latest_event(type="changed_state", desc__icontains="State changed to <b>IESG Evaluation - Defer</b>")
        elif self.type_id == "statchg" and self.get_state_slug("statchg") == "defer":
            return self.latest_event(type="changed_state", desc__icontains="State changed to <b>IESG Evaluation - Defer</b>")
        return None

    def most_recent_ietflc(self):
        """Returns the most recent IETF LastCallDocEvent for this document"""
        return self.latest_event(LastCallDocEvent,type="sent_last_call")

    def displayname_with_link(self):
        return mark_safe('<a href="%s">%s-%s</a>' % (self.get_absolute_url(), self.name , self.rev))

    def rfc_number(self):
        n = self.canonical_name()
        return n[3:] if n.startswith("rfc") else None

    def ipr(self,states=('posted','removed')):
        """Returns the IPR disclosures against this document (as a queryset over IprDocRel)."""
        from ietf.ipr.models import IprDocRel
        return IprDocRel.objects.filter(document__document=self,disclosure__state__in=states)

    def related_ipr(self):
        """Returns the IPR disclosures against this document and those documents this
        document directly or indirectly obsoletes or replaces
        """
        from ietf.ipr.models import IprDocRel
        iprs = IprDocRel.objects.filter(document__in=list(self.docalias_set.all())+self.all_related_that_doc(['obs','replaces'])).filter(disclosure__state__in=['posted','removed']).values_list('disclosure', flat=True).distinct()
        return iprs

    def future_presentations(self):
        """ returns related SessionPresentation objects for meetings that
            have not yet ended. This implementation allows for 2 week meetings """
        candidate_presentations = self.sessionpresentation_set.filter(session__meeting__date__gte=datetime.date.today()-datetime.timedelta(days=15))
        return sorted([pres for pres in candidate_presentations if pres.session.meeting.end_date()>=datetime.date.today()], key=lambda x:x.session.meeting.date)

    def last_presented(self):
        """ returns related SessionPresentation objects for the most recent meeting in the past"""
        # Assumes no two meetings have the same start date - if the assumption is violated, one will be chosen arbitrariy
        candidate_presentations = self.sessionpresentation_set.filter(session__meeting__date__lte=datetime.date.today())
        candidate_meetings = set([p.session.meeting for p in candidate_presentations if p.session.meeting.end_date()<datetime.date.today()])
        if candidate_meetings:
            mtg = sorted(list(candidate_meetings),key=lambda x:x.date,reverse=True)[0]
            return self.sessionpresentation_set.filter(session__meeting=mtg)
        else:
            return None

    def submission(self):
        s = self.submission_set.filter(rev=self.rev)
        s = s.first()
        return s

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
    # the name here is used to capture the canonical name at the time
    # - it would perhaps be more elegant to simply call the attribute
    # canonical_name and replace the function on Document with a
    # property
    name = models.CharField(max_length=255)
    authors = models.ManyToManyField(Email, through=DocHistoryAuthor, blank=True)
    def __unicode__(self):
        return unicode(self.doc.name)

    def canonical_name(self):
        return self.name

    def latest_event(self, *args, **kwargs):
        kwargs["time__lte"] = self.time
        return self.doc.latest_event(*args, **kwargs)

    def future_presentations(self):
        return self.doc.future_presentations()

    def last_presented(self):
        return self.doc.last_presented()

    @property
    def groupmilestone_set(self):
        return self.doc.groupmilestone_set

    @property
    def docalias_set(self):
        return self.doc.docalias_set

    class Meta:
        verbose_name = "document history"
        verbose_name_plural = "document histories"

def save_document_in_history(doc):
    """This should be called before saving changes to a Document instance,
    so that the DocHistory entries contain all previous states, while
    the Group entry contain the current state.  XXX TODO: Call this
    directly from Document.save(), and add event listeners for save()
    on related objects so we can save as needed when they change, too.
    """
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
    name = models.CharField(max_length=255, primary_key=True)
    document = models.ForeignKey(Document)
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

    ("changed_state", "Changed state"),

    # misc draft/RFC events
    ("changed_stream", "Changed document stream"),
    ("expired_document", "Expired document"),
    ("extended_expiry", "Extended expiry of document"),
    ("requested_resurrect", "Requested resurrect"),
    ("completed_resurrect", "Completed resurrect"),
    ("changed_consensus", "Changed consensus"),
    ("published_rfc", "Published RFC"),
    ("added_suggested_replaces", "Added suggested replacement relationships"),
    ("reviewed_suggested_replaces", "Reviewed suggested replacement relationships"),

    # WG events
    ("changed_group", "Changed group"),
    ("changed_protocol_writeup", "Changed protocol writeup"),
    ("changed_charter_milestone", "Changed charter milestone"),

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
    ("changed_rfc_editor_note_text", "Changed RFC Editor Note text"),

    ("changed_last_call_text", "Changed last call text"),
    ("requested_last_call", "Requested last call"),
    ("sent_last_call", "Sent last call"),

    ("scheduled_for_telechat", "Scheduled for telechat"),

    ("iesg_approved", "IESG approved document (no problem)"),
    ("iesg_disapproved", "IESG disapproved document (do not publish)"),
    
    ("approved_in_minute", "Approved in minute"),

    # IANA events
    ("iana_review", "IANA review comment"),
    ("rfc_in_iana_registry", "RFC is in IANA registry"),

    # RFC Editor
    ("rfc_editor_received_announcement", "Announcement was received by RFC Editor"),
    ("requested_publication", "Publication at RFC Editor requested")
    ]

class DocEvent(models.Model):
    """An occurrence for a document, used for tracking who, when and what."""
    time = models.DateTimeField(default=datetime.datetime.now, help_text="When the event happened", db_index=True)
    type = models.CharField(max_length=50, choices=EVENT_TYPES)
    by = models.ForeignKey(Person)
    doc = models.ForeignKey('doc.Document')
    desc = models.TextField()

    def for_current_revision(self):
        return self.time >= self.doc.latest_event(NewRevisionDocEvent,type='new_revision').time

    def get_dochistory(self):
        return DocHistory.objects.filter(time__lte=self.time,doc__name=self.doc.name).order_by('-time').first()

    def __unicode__(self):
        return u"%s %s by %s at %s" % (self.doc.name, self.get_type_display().lower(), self.by.plain_name(), self.time)

    class Meta:
        ordering = ['-time', '-id']
        
class NewRevisionDocEvent(DocEvent):
    rev = models.CharField(max_length=16)

class StateDocEvent(DocEvent):
    state_type = models.ForeignKey(StateType)
    state = models.ForeignKey(State, blank=True, null=True)

class ConsensusDocEvent(DocEvent):
    consensus = models.NullBooleanField(default=None)

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
        active_ads = list(Person.objects.filter(role__name="ad", role__group__state="active", role__group__type="area"))
        res = {}
    
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
        active_ads = list(Person.objects.filter(role__name="ad", role__group__state="active", role__group__type="area").distinct())
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

        # get rid of trailling "No record" positions, some old ballots
        # have plenty of these
        for p in positions:
            while p.old_positions and p.old_positions[-1].slug == "norecord":
                p.old_positions.pop()

        # add any missing ADs through fake No Record events
        if self.doc.active_ballot() == self:
            norecord = BallotPositionName.objects.get(slug="norecord")
            for ad in active_ads:
                if ad not in seen:
                    e = BallotPositionDocEvent(type="changed_ballot_position", doc=self.doc, ad=ad)
                    e.by = ad
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


# dumping store for removed events
class DeletedEvent(models.Model):
    content_type = models.ForeignKey(ContentType)
    json = models.TextField(help_text="Deleted object in JSON format, with attribute names chosen to be suitable for passing into the relevant create method.")
    by = models.ForeignKey(Person)
    time = models.DateTimeField(default=datetime.datetime.now)

    def __unicode__(self):
        return u"%s by %s %s" % (self.content_type, self.by, self.time)
