# Copyright The IETF Trust 2010-2023, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime
import logging
import io
import os

import django.db
import rfc2html

from pathlib import Path
from lxml import etree
from typing import Optional, TYPE_CHECKING
from weasyprint import HTML as wpHTML
from weasyprint.text.fonts import FontConfiguration

from django.db import models
from django.core import checks
from django.core.cache import caches
from django.core.validators import URLValidator, RegexValidator
from django.urls import reverse as urlreverse
from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.html import mark_safe # type:ignore
from django.contrib.staticfiles import finders

import debug                            # pyflakes:ignore

from ietf.group.models import Group
from ietf.name.models import ( DocTypeName, DocTagName, StreamName, IntendedStdLevelName, StdLevelName,
    DocRelationshipName, DocReminderTypeName, BallotPositionName, ReviewRequestStateName, ReviewAssignmentStateName, FormalLanguageName,
    DocUrlTagName, ExtResourceName)
from ietf.person.models import Email, Person
from ietf.person.utils import get_active_balloters
from ietf.utils import log
from ietf.utils.decorators import memoize
from ietf.utils.validators import validate_no_control_chars
from ietf.utils.mail import formataddr
from ietf.utils.models import ForeignKey
from ietf.utils.timezone import date_today, RPC_TZINFO, DEADLINE_TZINFO
if TYPE_CHECKING:
    # importing other than for type checking causes errors due to cyclic imports
    from ietf.meeting.models import ProceedingsMaterial, Session

logger = logging.getLogger('django')

class StateType(models.Model):
    slug = models.CharField(primary_key=True, max_length=30) # draft, draft-iesg, charter, ...
    label = models.CharField(max_length=255, help_text="Label that should be used (e.g. in admin) for state drop-down for this type of state") # State, IESG state, WG state, ...

    def __str__(self):
        return self.slug

@checks.register('db-consistency')
def check_statetype_slugs(app_configs, **kwargs):
    errors = []
    try:
        state_type_slugs = [ t.slug for t in StateType.objects.all() ]
    except django.db.ProgrammingError:
        # When running initial migrations on an empty DB, attempting to retrieve StateType will raise a
        # ProgrammingError. Until Django 3, there is no option to skip the checks.
        return []
    else:
        for type in DocTypeName.objects.all():
            if not type.slug in state_type_slugs:
                errors.append(checks.Error(
                    "The document type '%s (%s)' does not have a corresponding entry in the doc.StateType table" % (type.name, type.slug),
                    hint="You should add a doc.StateType entry with a slug '%s' to match the DocTypeName slug."%(type.slug),
                    obj=type,
                    id='datatracker.doc.E0015',
                ))
        return errors

class State(models.Model):
    type = ForeignKey(StateType)
    slug = models.SlugField()
    name = models.CharField(max_length=255)
    used = models.BooleanField(default=True)
    desc = models.TextField(blank=True)
    order = models.IntegerField(default=0)

    next_states = models.ManyToManyField('doc.State', related_name="previous_states", blank=True)

    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ["type", "order"]

IESG_BALLOT_ACTIVE_STATES = ("lc", "writeupw", "goaheadw", "iesg-eva", "defer")
IESG_CHARTER_ACTIVE_STATES = ("intrev", "extrev", "iesgrev")
IESG_STATCHG_CONFLREV_ACTIVE_STATES = ("iesgeval", "defer")
IESG_SUBSTATE_TAGS = ('ad-f-up', 'need-rev', 'extpty')

class DocumentInfo(models.Model):
    """Any kind of document.  Draft, RFC, Charter, IPR Statement, Liaison Statement"""
    time = models.DateTimeField(default=timezone.now) # should probably have auto_now=True

    type = ForeignKey(DocTypeName, blank=True, null=True) # Draft, Agenda, Minutes, Charter, Discuss, Guideline, Email, Review, Issue, Wiki, External ...
    title = models.CharField(max_length=255, validators=[validate_no_control_chars, ])

    states = models.ManyToManyField(State, blank=True) # plain state (Active/Expired/...), IESG state, stream state
    tags = models.ManyToManyField(DocTagName, blank=True) # Revised ID Needed, ExternalParty, AD Followup, ...
    stream = ForeignKey(StreamName, blank=True, null=True) # IETF, IAB, IRTF, Independent Submission, Editorial
    group = ForeignKey(Group, blank=True, null=True) # WG, RG, IAB, IESG, Edu, Tools

    abstract = models.TextField(blank=True)
    rev = models.CharField(verbose_name="revision", max_length=16, blank=True)
    pages = models.IntegerField(blank=True, null=True)
    words = models.IntegerField(blank=True, null=True)
    formal_languages = models.ManyToManyField(FormalLanguageName, blank=True, help_text="Formal languages used in document")
    intended_std_level = ForeignKey(IntendedStdLevelName, verbose_name="Intended standardization level", blank=True, null=True)
    std_level = ForeignKey(StdLevelName, verbose_name="Standardization level", blank=True, null=True)
    ad = ForeignKey(Person, verbose_name="area director", related_name='ad_%(class)s_set', blank=True, null=True)
    shepherd = ForeignKey(Email, related_name='shepherd_%(class)s_set', blank=True, null=True)
    expires = models.DateTimeField(blank=True, null=True)
    notify = models.TextField(max_length=1023, blank=True)
    external_url = models.URLField(blank=True)
    uploaded_filename = models.TextField(blank=True)
    note = models.TextField(blank=True)
    rfc_number = models.PositiveIntegerField(blank=True, null=True)  # only valid for type="rfc"

    def file_extension(self):
        if not hasattr(self, '_cached_extension'):
            if self.uploaded_filename:
                _, ext= os.path.splitext(self.uploaded_filename)
                self._cached_extension = ext.lstrip(".").lower()
            else:
                self._cached_extension = "txt"
        return self._cached_extension

    def get_file_path(self):
        if not hasattr(self, '_cached_file_path'):
            if self.type_id == "rfc":
                self._cached_file_path = settings.RFC_PATH
            elif self.type_id == "draft":
                if self.is_dochistory():
                    self._cached_file_path = settings.INTERNET_ALL_DRAFTS_ARCHIVE_DIR
                else:
                    # This could be simplified since anything in INTERNET_DRAFT_PATH is also already in INTERNET_ALL_DRAFTS_ARCHIVE_DIR
                    draft_state = self.get_state('draft')
                    if draft_state and draft_state.slug == 'active':
                        self._cached_file_path = settings.INTERNET_DRAFT_PATH
                    else:
                        self._cached_file_path = settings.INTERNET_ALL_DRAFTS_ARCHIVE_DIR
            elif self.meeting_related() and self.type_id in (
                    "agenda", "minutes", "narrativeminutes", "slides", "bluesheets", "procmaterials", "chatlog", "polls"
            ):
                meeting = self.get_related_meeting()
                if meeting is not None:
                    self._cached_file_path = os.path.join(meeting.get_materials_path(), self.type_id) + "/"
                else:
                    self._cached_file_path = ""
            elif self.type_id == "charter":
                self._cached_file_path = settings.CHARTER_PATH
            elif self.type_id == "conflrev": 
                self._cached_file_path = settings.CONFLICT_REVIEW_PATH
            elif self.type_id == "statchg":
                self._cached_file_path = settings.STATUS_CHANGE_PATH
            elif self.type_id == "bofreq": # TODO: This is probably unneeded, as is the separate path setting
                self._cached_file_path = settings.BOFREQ_PATH
            else:
                self._cached_file_path = settings.DOCUMENT_PATH_PATTERN.format(doc=self)
        return self._cached_file_path

    def get_base_name(self):
        if not hasattr(self, '_cached_base_name'):
            if self.uploaded_filename:
                self._cached_base_name = self.uploaded_filename
            elif self.type_id == 'rfc':
                self._cached_base_name = "%s.txt" % self.name  
            elif self.type_id == 'draft':
                if self.is_dochistory():
                    self._cached_base_name = "%s-%s.txt" % (self.doc.name, self.rev)
                else:
                    self._cached_base_name = "%s-%s.txt" % (self.name, self.rev)
            elif self.type_id in ["slides", "agenda", "minutes", "bluesheets", "procmaterials", ] and self.meeting_related():
                ext = 'pdf' if self.type_id == 'procmaterials' else 'txt'
                self._cached_base_name = f'{self.name}-{self.rev}.{ext}'
            elif self.type_id == 'review':
                # TODO: This will be wrong if a review is updated on the same day it was created (or updated more than once on the same day)
                self._cached_base_name = "%s.txt" % self.name
            elif self.type_id in ['bofreq', 'statement']:
                self._cached_base_name = "%s-%s.md" % (self.name, self.rev)
            else:
                if self.rev:
                    self._cached_base_name = "%s-%s.txt" % (self.name, self.rev)
                else:
                    self._cached_base_name = "%s.txt" % (self.name, )
        return self._cached_base_name

    def get_file_name(self):
        if not hasattr(self, '_cached_file_name'):
            self._cached_file_name = os.path.join(self.get_file_path(), self.get_base_name())
        return self._cached_file_name


    def revisions_by_dochistory(self):
        revisions = []
        if self.type_id != "rfc":
            for h in self.history_set.order_by("time", "id"):
                if h.rev and not h.rev in revisions:
                    revisions.append(h.rev)
            if not self.rev in revisions:
                revisions.append(self.rev)
        return revisions

    def revisions_by_newrevisionevent(self):
        revisions = []
        if self.type_id != "rfc":
            doc = self.doc if isinstance(self, DocHistory) else self
            for e in doc.docevent_set.filter(type='new_revision').distinct():
                if e.rev and not e.rev in revisions:
                    revisions.append(e.rev)
            if not doc.rev in revisions:
                revisions.append(doc.rev)
            revisions.sort()
        return revisions

    def get_href(self, meeting=None):
        return self._get_ref(meeting=meeting,meeting_doc_refs=settings.MEETING_DOC_HREFS)


    def get_versionless_href(self, meeting=None):
        return self._get_ref(meeting=meeting,meeting_doc_refs=settings.MEETING_DOC_GREFS)


    def _get_ref(self, meeting=None, meeting_doc_refs=settings.MEETING_DOC_HREFS):
        """
        Returns an url to the document text.  This differs from .get_absolute_url(),
        which returns an url to the datatracker page for the document.   
        """
        # If self.external_url truly is an url, use it.  This is a change from
        # the earlier resolution order, but there's at the moment one single
        # instance which matches this (with correct results), so we won't
        # break things all over the place.
        if not hasattr(self, '_cached_href'):
            validator = URLValidator()
            if self.external_url and self.external_url.split(':')[0] in validator.schemes:
                validator(self.external_url)
                return self.external_url

            if self.type_id in settings.DOC_HREFS and self.type_id in meeting_doc_refs:
                if self.meeting_related():
                    self.is_meeting_related = True
                    format = meeting_doc_refs[self.type_id]
                else:
                    self.is_meeting_related = False
                    format = settings.DOC_HREFS[self.type_id]
            elif self.type_id in settings.DOC_HREFS:
                self.is_meeting_related = False
                if self.type_id == "rfc":
                    format = settings.DOC_HREFS['rfc']
                else:
                    format = settings.DOC_HREFS[self.type_id]
            elif self.type_id in meeting_doc_refs:
                self.is_meeting_related = True
            else:
                return None

            if self.is_meeting_related:
                if not meeting:
                    meeting = self.get_related_meeting()
                    if meeting is None:
                        return ''

                # After IETF 96, meeting materials acquired revision
                # handling, and the document naming changed.
                if meeting.proceedings_format_version == 1:
                    format = settings.MEETING_DOC_OLD_HREFS[self.type_id]
                else:
                    # This branch includes interims
                    format = meeting_doc_refs[self.type_id]
                info = dict(doc=self, meeting=meeting)
            else:
                info = dict(doc=self)

            href = format.format(**info)

            # For slides that are not meeting-related, we need to know the file extension.
            # Assume we have access to the same files as settings.DOC_HREFS["slides"] and
            # see what extension is available
            if  self.type_id == "slides" and not self.meeting_related() and not href.endswith("/"):
                filepath = Path(self.get_file_path()) / self.get_base_name()  # start with this
                if not filepath.exists():
                    # Look for other extensions - grab the first one, sorted for stability
                    for existing in sorted(filepath.parent.glob(f"{filepath.stem}.*")):
                        filepath = filepath.with_suffix(existing.suffix)
                        break
                href += filepath.suffix  # tack on the extension

            if href.startswith('/'):
                href = settings.IDTRACKER_BASE_URL + href
            self._cached_href = href
        return self._cached_href

    def set_state(self, state):
        """Switch state type implicit in state to state. This just
        sets the state, doesn't log the change."""
        already_set = self.states.filter(type=state.type)
        others = [s for s in already_set if s != state]
        if others:
            self.states.remove(*others)
        if state not in already_set:
            self.states.add(state)
        if state.type and state.type.slug == 'draft-iesg':
            iesg_state = self.states.get(type_id="draft-iesg") # pyflakes:ignore
            log.assertion('iesg_state', note="A document's 'draft-iesg' state should never be unset'.  Failed for %s"%self.name)
        self.state_cache = None # invalidate cache
        self._cached_state_slug = {}

    def unset_state(self, state_type):
        """Unset state of type so no state of that type is any longer set."""
        log.assertion('state_type != "draft-iesg"')
        self.states.remove(*self.states.filter(type=state_type))
        self.state_cache = None # invalidate cache
        self._cached_state_slug = {}

    def get_state(self, state_type=None):
        """Get state of type, or default state for document type if
        not specified. Uses a local cache to speed multiple state
        reads up."""
        if self.pk == None: # states is many-to-many so not in database implies no state
            return None

        if state_type == None:
            state_type = self.type_id

        if not hasattr(self, "state_cache") or self.state_cache == None:
            state_cache = {}
            for s in self.states.all():
                state_cache[s.type_id] = s
            self.state_cache = state_cache

        return self.state_cache.get(state_type, None)

    def get_state_slug(self, state_type=None):
        """Get state of type, or default if not specified, returning
        the slug of the state or None. This frees the caller of having
        to check against None before accessing the slug for a
        comparison."""
        if not hasattr(self, '_cached_state_slug'):
            self._cached_state_slug = {}
        if not state_type in self._cached_state_slug:
            s = self.get_state(state_type)
            self._cached_state_slug[state_type] = s.slug if s else None
        return self._cached_state_slug[state_type]

    def friendly_state(self):
        """ Return a concise text description of the document's current state."""
        state = self.get_state()
        if not state:
            return "Unknown state"
    
        if self.type_id == "rfc":
            return f"RFC {self.rfc_number} ({self.std_level})"
        elif self.type_id == 'draft':
            iesg_state = self.get_state("draft-iesg")
            iesg_state_summary = None
            if iesg_state:
                iesg_substate = [t for t in self.tags.all() if t.slug in IESG_SUBSTATE_TAGS]
                # There really shouldn't be more than one tag in iesg_substate, but this will do something sort-of-sensible if there is
                iesg_state_summary = iesg_state.name
                if iesg_substate:
                     iesg_state_summary = iesg_state_summary + "::"+"::".join(tag.name for tag in iesg_substate)

            rfc = self.became_rfc()
            if rfc:
                return f"Became RFC {rfc.rfc_number} ({rfc.std_level})"

            elif state.slug == "repl":
                rs = self.related_that("replaces")
                if rs:
                    return mark_safe("Replaced by " + ", ".join("<a href=\"%s\">%s</a>" % (urlreverse('ietf.doc.views_doc.document_main', kwargs=dict(name=related.name)), related) for related in rs))
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
                            return iesg_state_summary + " (ends %s)" % e.expires.astimezone(DEADLINE_TZINFO).date().isoformat()
    
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
        best_addresses = []
        for author in self.documentauthor_set.all():
            if author.email:
                if author.email.active or not author.email.person:
                    best_addresses.append(author.email.address)
                else:
                    best_addresses.append(author.email.person.email_address())
        return ", ".join(best_addresses)

    def authors(self):
        return [ a.person for a in self.documentauthor_set.all() ]

    # This, and several other ballot related functions here, assume that there is only one active ballot for a document at any point in time.
    # If that assumption is violated, they will only expose the most recently created ballot
    def ballot_open(self, ballot_type_slug):
        e = self.latest_event(BallotDocEvent, ballot_type__slug=ballot_type_slug)
        return e if e and not e.type == "closed_ballot" else None

    def latest_ballot(self):
        """Returns the most recently created ballot"""
        ballot = self.latest_event(BallotDocEvent, type__in=("created_ballot", "closed_ballot"))
        return ballot

    def active_ballot(self):
        """Returns the most recently created ballot if it isn't closed."""
        ballot = self.latest_ballot()
        if ballot and ballot.type == "created_ballot":
            return ballot
        else:
            return None

    def has_rfc_editor_note(self):
        e = self.latest_event(WriteupDocEvent, type="changed_rfc_editor_note_text")
        return e != None and (e.text != "")

    def meeting_related(self):
        if self.type_id in ("agenda","minutes", "narrativeminutes", "bluesheets","slides","recording","procmaterials","chatlog","polls"):
             return self.type_id != "slides" or self.get_state_slug('reuse_policy')=='single'
        return False

    def get_related_session(self) -> Optional['Session']:
        """Get the meeting session related to this document

        Return None if there is no related session.
        Must define this in DocumentInfo subclasses.
        """
        raise NotImplementedError(f'Class {self.__class__} must define get_related_session()')

    def get_related_proceedings_material(self) -> Optional['ProceedingsMaterial']:
        """Get the proceedings material related to this document

        Return None if there is no related proceedings material.
        Must define this in DocumentInfo subclasses.
        """
        raise NotImplementedError(f'Class {self.__class__} must define get_related_proceedings_material()')

    def get_related_meeting(self):
        """Get the meeting this document relates to"""
        if not self.meeting_related():
            return None  # no related meeting if not meeting_related!
        # get an item that links this doc to a meeting
        item = self.get_related_session() or self.get_related_proceedings_material()
        return getattr(item, 'meeting', None)

    def relations_that(self, relationship):
        """Return the related-document objects that describe a given relationship targeting self."""
        if isinstance(relationship, str):
            relationship = ( relationship, )
        if not isinstance(relationship, tuple):
            raise TypeError("Expected a string or tuple, received %s" % type(relationship))
        if isinstance(self, Document):
            return RelatedDocument.objects.filter(target=self, relationship__in=relationship).select_related('source')
        elif isinstance(self, DocHistory):
            return RelatedDocHistory.objects.filter(target=self.doc, relationship__in=relationship).select_related('source')
        else:
            raise TypeError("Expected method called on Document or DocHistory")

    def all_relations_that(self, relationship, related=None):
        if not related:
            related = tuple([])
        rels = self.relations_that(relationship)
        for r in rels:
            if not r in related:
                related += ( r, )
                related = r.source.all_relations_that(relationship, related)
        return related

    def relations_that_doc(self, relationship):
        """Return the related-document objects that describe a given relationship from self to other documents."""
        if isinstance(relationship, str):
            relationship = ( relationship, )
        if not isinstance(relationship, tuple):
            raise TypeError("Expected a string or tuple, received %s" % type(relationship))
        if isinstance(self, Document):
            return RelatedDocument.objects.filter(source=self, relationship__in=relationship).select_related('target')
        elif isinstance(self, DocHistory):
            return RelatedDocHistory.objects.filter(source=self, relationship__in=relationship).select_related('target')
        else:
            raise TypeError("Expected method called on Document or DocHistory")

    def all_relations_that_doc(self, relationship, related=None):
        if not related:
            related = tuple([])
        rels = self.relations_that_doc(relationship)
        for r in rels:
            if not r in related:
                related += ( r, )
                related = r.target.all_relations_that_doc(relationship, related)
        return related

    def related_that(self, relationship):
        return list(set([x.source for x in self.relations_that(relationship)]))

    def all_related_that(self, relationship, related=None):
        return list(set([x.source for x in self.all_relations_that(relationship)]))

    def related_that_doc(self, relationship):
        return list(set([x.target for x in self.relations_that_doc(relationship)]))

    def all_related_that_doc(self, relationship, related=None):
        return list(set([x.target for x in self.all_relations_that_doc(relationship)]))

    def replaces(self):
        return self.related_that_doc("replaces")

    def replaced_by(self):
        return set([ r.document for r in self.related_that("replaces") ])

    def text(self, size = -1):
        path = self.get_file_name()
        root, ext =  os.path.splitext(path)
        txtpath = root+'.txt'
        if ext != '.txt' and os.path.exists(txtpath):
            path = txtpath
        try:
            with io.open(path, 'rb') as file:
                raw = file.read(size)
        except IOError:
            return None
        text = None
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError:
            for back in range(1,4):
                try:
                    text = raw[:-back].decode('utf-8')
                    break
                except UnicodeDecodeError:
                    pass
            if text is None:
                text = raw.decode('latin-1')
        return text

    def text_or_error(self):
        return self.text() or "Error; cannot read '%s'"%self.get_base_name()

    def html_body(self, classes=""):
        if self.type_id == "rfc":
            try:
                html = Path(
                    os.path.join(settings.RFC_PATH, self.name + ".html")
                ).read_text()
            except (IOError, UnicodeDecodeError):
                return None
        else:
            try:
                html = Path(
                    os.path.join(
                        settings.INTERNET_ALL_DRAFTS_ARCHIVE_DIR,
                        self.name + "-" + self.rev + ".html",
                    )
                ).read_text()
            except (IOError, UnicodeDecodeError):
                return None

        # If HTML was generated by rfc2html, do not return it. Caller
        # will use htmlize() to use a more current rfc2html to
        # generate an HTMLized version. TODO: There should be a
        # better way to determine how an HTML format was generated.
        if html.startswith("<pre>"):
            return None

        # get body
        etree_html = etree.HTML(html)
        if etree_html is None:
            return None
        body = etree_html.xpath("//body")[0]
        body.tag = "div"
        if classes:
            body.attrib["class"] = classes

        # remove things
        for tag in ["script"]:
            for t in body.xpath(f"//{tag}"):
                t.getparent().remove(t)
        html = etree.tostring(body, encoding=str, method="html")

        return html

    def htmlized(self):
        name = self.get_base_name()
        text = self.text()
        if name.endswith('.html'):
            return text
        if not name.endswith('.txt'):
            return None
        html = ""
        if text:
            cache = caches['htmlized']
            cache_key = name.split('.')[0]
            try:
                html = cache.get(cache_key)
            except EOFError:
                html = None
            if not html:
                # The path here has to match the urlpattern for htmlized
                # documents in order to produce correct intra-document links
                html = rfc2html.markup(text, path=settings.HTMLIZER_URL_PREFIX)
                html = f'<div class="rfcmarkup">{html}</div>'
                if html:
                    cache.set(cache_key, html, settings.HTMLIZER_CACHE_TIME)
        return html

    def pdfized(self):
        name = self.get_base_name()
        text = self.html_body(classes="rfchtml")
        stylesheets = [finders.find("ietf/css/document_html_referenced.css")]
        if text:
            stylesheets.append(finders.find("ietf/css/document_html_txt.css"))
        else:
            text = self.htmlized()
        stylesheets.append(f'{settings.STATIC_IETF_ORG_INTERNAL}/fonts/noto-sans-mono/import.css')

        cache = caches["pdfized"]
        cache_key = name.split(".")[0]
        try:
            pdf = cache.get(cache_key)
        except EOFError:
            pdf = None
        if not pdf:
            try:
                font_config = FontConfiguration()
                pdf = wpHTML(
                    string=text, base_url=settings.IDTRACKER_BASE_URL
                ).write_pdf(
                    stylesheets=stylesheets,
                    font_config=font_config,
                    presentational_hints=True,
                    optimize_images=True,
                )
            except AssertionError:
                pdf = None
            except Exception as e:
                log.log('weasyprint failed:'+str(e))
                raise
            if pdf:
                cache.set(cache_key, pdf, settings.PDFIZER_CACHE_TIME)
        return pdf

    def references(self):
        return self.relations_that_doc(('refnorm','refinfo','refunk','refold'))

    def referenced_by(self):
        return self.relations_that(("refnorm", "refinfo", "refunk", "refold")).filter(
            models.Q(
                source__type__slug="draft",
                source__states__type__slug="draft",
                source__states__slug="active",
            )
            | models.Q(source__type__slug="rfc")
        ).distinct()
    
    def referenced_by_rfcs(self):
        """Get refs to this doc from RFCs"""
        return self.relations_that(("refnorm", "refinfo", "refunk", "refold")).filter(
            source__type__slug="rfc"
        )

    def became_rfc(self):
        if not hasattr(self, "_cached_became_rfc"):
            doc = self if isinstance(self, Document) else self.doc
            self._cached_became_rfc = next(iter(doc.related_that_doc("became_rfc")), None)
        return self._cached_became_rfc

    def came_from_draft(self):
        if not hasattr(self, "_cached_came_from_draft"):
            doc = self if isinstance(self, Document) else self.doc
            self._cached_came_from_draft = next(iter(doc.related_that("became_rfc")), None)
        return self._cached_came_from_draft
    
    def contains(self):
        return self.related_that_doc("contains")
    
    def part_of(self):
        return self.related_that("contains")

    def referenced_by_rfcs_as_rfc_or_draft(self):
        """Get refs to this doc, or a draft/rfc it came from, from an RFC"""
        refs_to = self.referenced_by_rfcs()
        if self.type_id == "rfc" and self.came_from_draft():
            refs_to |= self.came_from_draft().referenced_by_rfcs()
        return refs_to

    class Meta:
        abstract = True

STATUSCHANGE_RELATIONS = ('tops','tois','tohist','toinf','tobcp','toexp')

class RelatedDocument(models.Model):
    source = ForeignKey('Document')
    target = ForeignKey('Document', related_name='targets_related')
    relationship = ForeignKey(DocRelationshipName)
    originaltargetaliasname = models.CharField(max_length=255, null=True, blank=True)
    def action(self):
        return self.relationship.name
    def __str__(self):
        return u"%s %s %s" % (self.source.name, self.relationship.name.lower(), self.target.name)

    def is_downref(self):
        if self.source.type_id not in ["draft","rfc"] or self.relationship.slug not in [
            "refnorm",
            "refold",
            "refunk",
        ]:
            return None

        if self.source.type_id == "rfc":
            source_lvl = self.source.std_level_id
        elif self.source.type_id in ["bcp","std"]:
            source_lvl = self.source.type_id
        else:
            source_lvl = self.source.intended_std_level_id

        if source_lvl not in ["bcp", "ps", "ds", "std", "unkn"]:
            return None

        if self.target.type_id == 'rfc':
            if not self.target.std_level:
                target_lvl = 'unkn'
            else:
                target_lvl = self.target.std_level_id
        elif self.target.type_id in ["bcp", "std"]:
            target_lvl = self.target.type_id
        else:
            if not self.target.intended_std_level:
                target_lvl = 'unkn'
            else:
                target_lvl = self.target.intended_std_level_id

        if self.relationship.slug not in ["refnorm", "refunk"]:
            return None

        if source_lvl in ["inf", "exp"]:
            return None

        pos_downref = (
            "Downref" if self.relationship_id != "refunk" else "Possible Downref"
        )

        if source_lvl in ["bcp", "ps", "ds", "std"] and target_lvl in ["inf", "exp"]:
            return pos_downref

        if source_lvl == "ds" and target_lvl == "ps":
            return pos_downref

        if source_lvl == "std" and target_lvl in ["ps", "ds"]:
            return pos_downref

        if source_lvl not in ["inf", "exp"] and target_lvl == "unkn":
            return "Possible Downref"

        if source_lvl == "unkn" and target_lvl in ["ps", "ds"]:
            return "Possible Downref"

        return None

    def is_approved_downref(self):

        if self.target.type_id == 'rfc':
           if RelatedDocument.objects.filter(relationship_id='downref-approval', target=self.target).exists():
              return "Approved Downref"

        return False

class DocumentAuthorInfo(models.Model):
    person = ForeignKey(Person)
    # email should only be null for some historic documents
    email = ForeignKey(Email, help_text="Email address used by author for submission", blank=True, null=True)
    affiliation = models.CharField(max_length=100, blank=True, help_text="Organization/company used by author for submission")
    country = models.CharField(max_length=255, blank=True, help_text="Country used by author for submission")
    order = models.IntegerField(default=1)

    def formatted_email(self):

        if self.email:
            return formataddr((self.person.plain_ascii(), self.email.address))
        else:
            return ""

    class Meta:
        abstract = True
        ordering = ["document", "order"]
        indexes = [
            models.Index(fields=['document', 'order']),
        ]

class DocumentAuthor(DocumentAuthorInfo):
    document = ForeignKey('Document')

    def __str__(self):
        return u"%s %s (%s)" % (self.document.name, self.person, self.order)


class DocumentActionHolder(models.Model):
    """Action holder for a document"""
    document = ForeignKey('Document')
    person = ForeignKey(Person)
    time_added = models.DateTimeField(default=timezone.now)

    CLEAR_ACTION_HOLDERS_STATES = ['approved', 'ann', 'rfcqueue', 'pub', 'dead']  # draft-iesg state slugs
    GROUP_ROLES_OF_INTEREST = ['chair', 'techadv', 'editor', 'secr']

    def __str__(self):
        return str(self.person)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['document', 'person'], name='unique_action_holder')
        ]

    def role_for_doc(self):
        """Brief string description of this person's relationship to the doc"""
        roles = []
        if self.person in self.document.authors():
            roles.append('Author')
        if self.person == self.document.ad:
            roles.append('Responsible AD')
        if self.document.shepherd and self.person == self.document.shepherd.person:
            roles.append('Shepherd')
        if self.document.group:
            roles.extend([
                'Group %s' % role.name.name 
                for role in self.document.group.role_set.filter(
                    name__in=self.GROUP_ROLES_OF_INTEREST,
                    person=self.person,
                )
            ])

        if not roles:
            roles.append('Action Holder')
        return ', '.join(roles) 

validate_docname = RegexValidator(
    r'^[-a-z0-9]+$',
    "Provide a valid document name consisting of lowercase letters, numbers and hyphens.",
    'invalid'
)

class Document(DocumentInfo):
    name = models.CharField(max_length=255, validators=[validate_docname,], unique=True)           # immutable
    
    action_holders = models.ManyToManyField(Person, through=DocumentActionHolder, blank=True)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        """
        Returns an url to the document view.  This differs from .get_href(),
        which returns an url to the document content.
        """
        if not hasattr(self, '_cached_absolute_url'):
            name = self.name
            url = None
            if self.type_id == "draft" and self.get_state_slug() == "rfc":
                name = self.name
                url = urlreverse('ietf.doc.views_doc.document_main', kwargs={ 'name': name }, urlconf="ietf.urls")
            elif self.type_id in ('slides','bluesheets','recording'):
                session = self.session_set.first()
                if session:
                    meeting = session.meeting
                    if self.type_id == 'recording':
                        url = self.external_url
                    else:
                        filename = self.uploaded_filename
                        url = '%sproceedings/%s/%s/%s' % (settings.IETF_HOST_URL,meeting.number,self.type_id,filename)
            else:
                url = urlreverse('ietf.doc.views_doc.document_main', kwargs={ 'name': name }, urlconf="ietf.urls")
            self._cached_absolute_url = url
        return self._cached_absolute_url

    def get_related_session(self):
        sessions = self.session_set.all()
        return sessions.first()

    def get_related_proceedings_material(self):
        return self.proceedingsmaterial_set.first()

    def file_tag(self):
        return "<%s>" % self.filename_with_rev()

    def filename_with_rev(self):
        return "%s-%s.txt" % (self.name, self.rev)
    
    def latest_event(self, *args, **filter_args):
        """Get latest event of optional Python type and with filter
        arguments, e.g. d.latest_event(type="xyz") returns a DocEvent
        while d.latest_event(WriteupDocEvent, type="xyz") returns a
        WriteupDocEvent event."""
        model = args[0] if args else DocEvent
        e = model.objects.filter(doc=self).filter(**filter_args).order_by('-time', '-id').first()
        return e

    def display_name(self):
        name = self.name
        if name.startswith('rfc'):
            name = name.upper()
        return name

    def save_with_history(self, events):
        """Save document and put a snapshot in the history models where they
        can be retrieved later. You must pass in at least one event
        with a description of what happened."""

        assert events, "You must always add at least one event to describe the changes in the history log"
        self.time = max(self.time, events[0].time)

        self._has_an_event_so_saving_is_allowed = True
        self.save()
        del self._has_an_event_so_saving_is_allowed

        from ietf.doc.utils import save_document_in_history
        save_document_in_history(self)

    def save(self, *args, **kwargs):
        # if there's no primary key yet, we can allow the save to go
        # through to break the cycle between the document and any
        # events
        assert kwargs.get("force_insert", False) or getattr(self, "_has_an_event_so_saving_is_allowed", None), "Use .save_with_history to save documents"
        super(Document, self).save(*args, **kwargs)

    def telechat_date(self, e=None):
        if not e:
            e = self.latest_event(TelechatDocEvent, type="scheduled_for_telechat")
        return e.telechat_date if e and e.telechat_date and e.telechat_date >= date_today(settings.TIME_ZONE) else None

    def past_telechat_date(self):
        "Return the latest telechat date if it isn't in the future; else None"
        e = self.latest_event(TelechatDocEvent, type="scheduled_for_telechat")
        return e.telechat_date if e and e.telechat_date and e.telechat_date < date_today(settings.TIME_ZONE) else None

    def previous_telechat_date(self):
        "Return the most recent telechat date in the past, if any (even if there's another in the future)"
        e = self.latest_event(
            TelechatDocEvent,
            type="scheduled_for_telechat",
            telechat_date__lt=date_today(settings.TIME_ZONE),
        )
        return e.telechat_date if e else None

    def request_closed_time(self, review_req):
        e = self.latest_event(ReviewRequestDocEvent, type="closed_review_request", review_request=review_req)
        return e.time if e and e.time else None

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

    @memoize
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

    def ipr(self,states=settings.PUBLISH_IPR_STATES):
        """Returns the IPR disclosures against this document (as a queryset over IprDocRel)."""
        # from ietf.ipr.models import IprDocRel
        # return IprDocRel.objects.filter(document__docs=self, disclosure__state__in=states) # TODO - clear these comments away
        return self.iprdocrel_set.filter(disclosure__state__in=states)

    def related_ipr(self):
        """Returns the IPR disclosures against this document and those documents this
        document directly or indirectly obsoletes or replaces
        """
        from ietf.ipr.models import IprDocRel
        iprs = (
            IprDocRel.objects.filter(
                document__in=[self]
                + self.all_related_that_doc(("obs", "replaces"))
            )
            .filter(disclosure__state__in=settings.PUBLISH_IPR_STATES)
            .values_list("disclosure", flat=True)
            .distinct()
        )
        return iprs


    def future_presentations(self):
        """ returns related SessionPresentation objects for meetings that
            have not yet ended. This implementation allows for 2 week meetings """
        candidate_presentations = self.presentations.filter(
            session__meeting__date__gte=date_today() - datetime.timedelta(days=15)
        )
        return sorted(
            [pres for pres in candidate_presentations
             if pres.session.meeting.end_date() >= date_today()],
            key=lambda x:x.session.meeting.date,
        )

    def last_presented(self):
        """ returns related SessionPresentation objects for the most recent meeting in the past"""
        # Assumes no two meetings have the same start date - if the assumption is violated, one will be chosen arbitrarily
        today = date_today()
        candidate_presentations = self.presentations.filter(session__meeting__date__lte=today)
        candidate_meetings = set([p.session.meeting for p in candidate_presentations if p.session.meeting.end_date()<today])
        if candidate_meetings:
            mtg = sorted(list(candidate_meetings),key=lambda x:x.date,reverse=True)[0]
            return self.presentations.filter(session__meeting=mtg)
        else:
            return None

    def submission(self):
        s = self.submission_set.filter(rev=self.rev)
        s = s.first()
        return s

    def pub_date(self):
        """Get the publication date for this document

        This is the rfc publication date for RFCs, and the new-revision date for other documents.
        """
        if self.type_id == "rfc":
            # As of Sept 2022, in ietf.sync.rfceditor.update_docs_from_rfc_index() `published_rfc` events are
            # created with a timestamp whose date *in the PST8PDT timezone* is the official publication date
            # assigned by the RFC editor.
            event = self.latest_event(type='published_rfc')
        else:
            event = self.latest_event(type='new_revision')
        return event.time.astimezone(RPC_TZINFO).date() if event else None

    def is_dochistory(self):
        return False

    def fake_history_obj(self, rev):
        """
        Mock up a fake DocHistory object with the given revision, for
        situations where we need an entry but there is none in the DocHistory
        table.
        XXX TODO: Add missing objects to DocHistory instead
        """
        history = DocHistory.objects.filter(doc=self, rev=rev).order_by("time")
        if history.exists():
            return history.first()
        else:
            # fake one
            events = self.docevent_set.order_by("time", "id")
            rev_events = events.filter(rev=rev)
            new_rev_events = rev_events.filter(type='new_revision')
            if new_rev_events.exists():
                time = new_rev_events.first().time
            elif rev_events.exists():
                time = rev_events.first().time
            else:
                time = datetime.datetime.fromtimestamp(0, datetime.timezone.utc)
            dh = DocHistory(name=self.name, rev=rev, doc=self, time=time, type=self.type, title=self.title,
                             stream=self.stream, group=self.group)

        return dh

    def action_holders_enabled(self):
        """Is the action holder list active for this document?"""
        iesg_state = self.get_state('draft-iesg')
        return iesg_state and iesg_state.slug != 'idexists'

class DocumentURL(models.Model):
    doc  = ForeignKey(Document)
    tag  = ForeignKey(DocUrlTagName)
    desc = models.CharField(max_length=255, default='', blank=True)
    url  = models.URLField(max_length=2083) # 2083 is the legal max for URLs

class ExtResource(models.Model):
    name = models.ForeignKey(ExtResourceName, on_delete=models.CASCADE)
    display_name = models.CharField(max_length=255, default='', blank=True)
    value = models.CharField(max_length=2083) # 2083 is the maximum legal URL length
    def __str__(self):
        priority = self.display_name or self.name.name
        return u"%s (%s) %s" % (priority, self.name.slug, self.value)

    class Meta:
        abstract = True
        
    # The to_form_entry_str() and matching from_form_entry_str() class method are
    # defined here to ensure that change request emails suggest resources in the
    # correct format to cut-and-paste into the current textarea on the external
    # resource form. If that is changed to a formset or other non-text entry field,
    # these methods really should not be needed.
    def to_form_entry_str(self):
        """Serialize as a string suitable for entry in a form"""
        if self.display_name:
            return "%s %s (%s)" % (self.name.slug, self.value, self.display_name.strip('()'))
        else:
            return "%s %s" % (self.name.slug, self.value)

    @classmethod
    def from_form_entry_str(cls, s):
        """Create an instance from the form_entry_str format

        Expected format is "<tag> <value>[ (<display name>)]"
        Any text after the value is treated as the display name, with whitespace replaced by
        spaces and leading/trailing parentheses stripped.
        """
        parts = s.split(None, 2)
        display_name = ' '.join(parts[2:]).strip('()')
        kwargs = dict(name_id=parts[0], value=parts[1])
        if display_name:
            kwargs['display_name'] = display_name
        return cls(**kwargs)

    @classmethod
    def from_sibling_class(cls, sib):
        """Create an instance with same base attributes as another subclass instance"""
        kwargs = dict()
        for field in ExtResource._meta.get_fields():
            value = getattr(sib, field.name, None)
            if value:
                kwargs[field.name] = value
        return cls(**kwargs)

class DocExtResource(ExtResource):
    doc = ForeignKey(Document) # Should this really be to DocumentInfo rather than Document?

class RelatedDocHistory(models.Model):
    source = ForeignKey('DocHistory')
    target = ForeignKey('Document', related_name="reversely_related_document_history_set")
    relationship = ForeignKey(DocRelationshipName)
    originaltargetaliasname = models.CharField(max_length=255, null=True, blank=True)
    def __str__(self):
        return u"%s %s %s" % (self.source.doc.name, self.relationship.name.lower(), self.target.name)

class DocHistoryAuthor(DocumentAuthorInfo):
    # use same naming convention as non-history version to make it a bit
    # easier to write generic code
    document = ForeignKey('DocHistory', related_name="documentauthor_set")

    def __str__(self):
        return u"%s %s (%s)" % (self.document.doc.name, self.person, self.order)

class DocHistory(DocumentInfo):
    doc = ForeignKey(Document, related_name="history_set")

    name = models.CharField(max_length=255)

    def __str__(self):
        return force_str(self.doc.name)

    def get_related_session(self):
        return self.doc.get_related_session()

    def get_related_proceedings_material(self):
        return self.doc.get_related_proceedings_material()

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

    def is_dochistory(self):
        return True

    def related_ipr(self):
        return self.doc.related_ipr()

    @property
    def documenturl_set(self):
        return self.doc.documenturl_set

    def filename_with_rev(self):
        return self.doc.filename_with_rev()
    
    class Meta:
        verbose_name = "document history"
        verbose_name_plural = "document histories"


class DocReminder(models.Model):
    event = ForeignKey('DocEvent')
    type = ForeignKey(DocReminderTypeName)
    due = models.DateTimeField()
    active = models.BooleanField(default=True)


EVENT_TYPES = [
    # core events
    ("new_revision", "Added new revision"),
    ("new_submission", "Uploaded new revision"),
    ("changed_document", "Changed document metadata"),
    ("added_comment", "Added comment"),
    ("added_message", "Added message"),
    ("edited_authors", "Edited the documents author list"),

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
    ("changed_action_holders", "Changed action holders for document"),

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
    ("requested_publication", "Publication at RFC Editor requested"),
    ("sync_from_rfc_editor", "Received updated information from RFC Editor"),

    # review
    ("requested_review", "Requested review"),
    ("assigned_review_request", "Assigned review request"),
    ("closed_review_request", "Closed review request"),
    ("closed_review_assignment", "Closed review assignment"),

    # downref
    ("downref_approved", "Downref approved"),
    
    # IPR events
    ("posted_related_ipr", "Posted related IPR"),
    ("removed_related_ipr", "Removed related IPR"),
    ("removed_objfalse_related_ipr", "Removed Objectively False related IPR"),

    # Bofreq Editor events
    ("changed_editors", "Changed BOF Request editors"),

    # Statement events
    ("published_statement", "Published statement"),

    # Slide events
    ("approved_slides", "Slides approved"),
    
    ]

class DocEvent(models.Model):
    """An occurrence for a document, used for tracking who, when and what."""
    time = models.DateTimeField(default=timezone.now, help_text="When the event happened", db_index=True)
    type = models.CharField(max_length=50, choices=EVENT_TYPES)
    by = ForeignKey(Person)
    doc = ForeignKey(Document)
    rev = models.CharField(verbose_name="revision", max_length=16, null=True, blank=True)
    desc = models.TextField()

    def for_current_revision(self):
        e = self.doc.latest_event(NewRevisionDocEvent,type='new_revision')
        return not e or (self.time, self.pk) >= (e.time, e.pk)

    def get_dochistory(self):
        return DocHistory.objects.filter(time__lte=self.time,doc__name=self.doc.name).order_by('-time', '-pk').first()

    def __str__(self):
        return u"%s %s by %s at %s" % (self.doc.name, self.get_type_display().lower(), self.by.plain_name(), self.time)
    
    class Meta:
        ordering = ['-time', '-id']
        indexes = [
            models.Index(fields=['type', 'doc']),
            models.Index(fields=['-time', '-id']),
        ]
        
class NewRevisionDocEvent(DocEvent):
    pass

class IanaExpertDocEvent(DocEvent):
    pass

class StateDocEvent(DocEvent):
    state_type = ForeignKey(StateType)
    state = ForeignKey(State, blank=True, null=True)

class ConsensusDocEvent(DocEvent):
    consensus = models.BooleanField(null=True, default=None)

# IESG events
class BallotType(models.Model):
    doc_type = ForeignKey(DocTypeName, blank=True, null=True)
    slug = models.SlugField()
    name = models.CharField(max_length=255)
    question = models.TextField(blank=True)
    used = models.BooleanField(default=True)
    order = models.IntegerField(default=0)
    positions = models.ManyToManyField(BallotPositionName, blank=True)

    def __str__(self):
        return u"%s: %s" % (self.name, self.doc_type.name)
    
    class Meta:
        ordering = ['order']

class BallotDocEvent(DocEvent):
    ballot_type = ForeignKey(BallotType)

    def active_balloter_positions(self):
        """Return dict mapping each active member of the balloting body to a current ballot position (or None if they haven't voted)."""
        res = {}
    
        active_balloters = get_active_balloters(self.ballot_type)
        positions = BallotPositionDocEvent.objects.filter(type="changed_ballot_position",balloter__in=active_balloters, ballot=self).select_related('balloter', 'pos').order_by("-time", "-id")

        for pos in positions:
            if pos.balloter not in res:
                res[pos.balloter] = pos

        for balloter in active_balloters:
            if balloter not in res:
                res[balloter] = None
        return res

    def all_positions(self):
        """Return array holding the current and past positions per AD"""

        positions = []
        seen = {}
        active_balloters = get_active_balloters(self.ballot_type)
        for e in BallotPositionDocEvent.objects.filter(type="changed_ballot_position", ballot=self).select_related('balloter', 'pos').order_by("-time", '-id'):
            if e.balloter not in seen:
                e.is_old_pos = e.balloter not in active_balloters
                e.old_positions = []
                positions.append(e)
                seen[e.balloter] = e
            else:
                latest = seen[e.balloter]
                if latest.old_positions:
                    prev = latest.old_positions[-1]
                else:
                    prev = latest.pos
    
                if e.pos != prev:
                    latest.old_positions.append(e.pos)

        # get rid of trailing "No record" positions, some old ballots
        # have plenty of these
        for p in positions:
            while p.old_positions and p.old_positions[-1].slug == "norecord":
                p.old_positions.pop()

        # add any missing balloters through fake No Record events
        if self.doc.active_ballot() == self:
            norecord = BallotPositionName.objects.get(slug="norecord")
            for balloter in active_balloters:
                if balloter not in seen:
                    e = BallotPositionDocEvent(type="changed_ballot_position", doc=self.doc, rev=self.doc.rev, balloter=balloter)
                    e.by = balloter
                    e.pos = norecord
                    e.is_old_pos = False
                    e.old_positions = []
                    positions.append(e)

        positions.sort(key=lambda p: (p.is_old_pos, p.balloter.last_name()))
        return positions

class IRSGBallotDocEvent(BallotDocEvent):
    duedate = models.DateTimeField(blank=True, null=True)

class BallotPositionDocEvent(DocEvent):
    ballot = ForeignKey(BallotDocEvent, null=True, default=None) # default=None is a temporary migration period fix, should be removed when charter branch is live
    balloter = ForeignKey(Person)
    pos = ForeignKey(BallotPositionName, verbose_name="position", default="norecord")
    discuss = models.TextField(help_text="Discuss text if position is discuss", blank=True)
    discuss_time = models.DateTimeField(help_text="Time discuss text was written", blank=True, null=True)
    comment = models.TextField(help_text="Optional comment", blank=True)
    comment_time = models.DateTimeField(help_text="Time optional comment was written", blank=True, null=True)
    send_email = models.BooleanField(null=True, default=None)

    @memoize
    def any_email_sent(self):
        # When the send_email field is introduced, old positions will have it
        # set to None.  We still essentially return True, False, or don't know:
        sent_list = BallotPositionDocEvent.objects.filter(
            ballot=self.ballot,
            time__lte=self.time,
            balloter=self.balloter,
        ).values_list('send_email', flat=True)
        false = any( s==False for s in sent_list )
        true  = any( s==True for s in sent_list )
        return True if true else False if false else None


class WriteupDocEvent(DocEvent):
    text = models.TextField(blank=True)

class LastCallDocEvent(DocEvent):
    expires = models.DateTimeField(blank=True, null=True)
    
class TelechatDocEvent(DocEvent):
    telechat_date = models.DateField(blank=True, null=True)
    returning_item = models.BooleanField(default=False)

class ReviewRequestDocEvent(DocEvent):
    review_request = ForeignKey('review.ReviewRequest')
    state = ForeignKey(ReviewRequestStateName, blank=True, null=True)

class ReviewAssignmentDocEvent(DocEvent):
    review_assignment = ForeignKey('review.ReviewAssignment')
    state = ForeignKey(ReviewAssignmentStateName, blank=True, null=True)

# charter events
class InitialReviewDocEvent(DocEvent):
    expires = models.DateTimeField(blank=True, null=True)

class AddedMessageEvent(DocEvent):
    import ietf.message.models
    message     = ForeignKey(ietf.message.models.Message, null=True, blank=True,related_name='doc_manualevents')
    msgtype     = models.CharField(max_length=25)
    in_reply_to = ForeignKey(ietf.message.models.Message, null=True, blank=True,related_name='doc_irtomanual')


class SubmissionDocEvent(DocEvent):
    import ietf.submit.models
    submission = ForeignKey(ietf.submit.models.Submission)

# dumping store for removed events
class DeletedEvent(models.Model):
    content_type = ForeignKey(ContentType)
    json = models.TextField(help_text="Deleted object in JSON format, with attribute names chosen to be suitable for passing into the relevant create method.")
    by = ForeignKey(Person)
    time = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return u"%s by %s %s" % (self.content_type, self.by, self.time)

class EditedAuthorsDocEvent(DocEvent):
    """ Capture the reasoning or authority for changing a document author list.
        Allows programs to recognize and not change lists that have been manually verified and corrected.
        Example 'basis' values might be from ['manually adjusted','recomputed by parsing document', etc.]
    """
    basis = models.CharField(help_text="What is the source or reasoning for the changes to the author list",max_length=255)

class BofreqEditorDocEvent(DocEvent):
    """ Capture the proponents of a BOF Request."""
    editors = models.ManyToManyField('person.Person', blank=True)

class BofreqResponsibleDocEvent(DocEvent):
    """ Capture the responsible leadership (IAB and IESG members) for a BOF Request """
    responsible = models.ManyToManyField('person.Person', blank=True)
