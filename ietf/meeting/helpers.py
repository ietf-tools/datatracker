# Copyright The IETF Trust 2013-2022, All Rights Reserved
# -*- coding: utf-8 -*-


from collections import defaultdict
import datetime
import io
import os
import re
from tempfile import mkstemp

from django.http import Http404
from django.db.models import F, Prefetch
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import AnonymousUser
from django.urls import reverse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone

import debug                            # pyflakes:ignore

from ietf.doc.models import Document
from ietf.group.utils import can_manage_some_groups, can_manage_group
from ietf.ietfauth.utils import has_role, user_is_person
from ietf.liaisons.utils import get_person_for_user
from ietf.mailtrigger.utils import gather_address_lists
from ietf.person.models  import Person
from ietf.meeting.models import Meeting, Schedule, TimeSlot, SchedTimeSessAssignment, ImportantDate, SchedulingEvent, Session
from ietf.meeting.utils import session_requested_by, add_event_info_to_session_qs
from ietf.name.models import ImportantDateName, SessionPurposeName
from ietf.utils import log, meetecho
from ietf.utils.mail import send_mail
from ietf.utils.pipe import pipe
from ietf.utils.text import xslugify


def get_meeting(num=None, type_in=('ietf',), days=28):
    meetings = Meeting.objects
    if type_in is not None:
        meetings = meetings.filter(type__in=type_in)
    if num is None:
        meetings = meetings.filter(
            date__gte=timezone.now() - datetime.timedelta(days=days)
        ).order_by('date')
    else:
        meetings = meetings.filter(number=num)
    if meetings.exists():
        return meetings.first()
    else:
        raise Http404("No such meeting found: %s" % num)

def get_current_ietf_meeting():
    meetings = Meeting.objects.filter(type='ietf',date__gte=timezone.now()-datetime.timedelta(days=31)).order_by('date')
    return meetings.first()

def get_current_ietf_meeting_num():
    cur = get_current_ietf_meeting()
    return cur.number if cur else None

def get_ietf_meeting(num=None):
    if num:
        meeting = Meeting.objects.filter(type='ietf', number=num).first()
    else:
        meeting = get_current_ietf_meeting()
    return meeting

def get_schedule(meeting, name=None):
    if name is None:
        schedule = meeting.schedule
    else:
        schedule = get_object_or_404(meeting.schedule_set, name=name)
    return schedule

# seems this belongs in ietf/person/utils.py?
def get_person_by_email(email):
    # email == None may actually match people who haven't set an email!
    if email is None:
        return None
    return Person.objects.filter(email__address=email).distinct().first()

def get_schedule_by_name(meeting, owner, name):
    if owner is not None:
        return meeting.schedule_set.filter(owner = owner, name = name).first()
    else:
        return meeting.schedule_set.filter(name = name).first()

def preprocess_assignments_for_agenda(assignments_queryset, meeting, extra_prefetches=()):
    """Add computed properties to assignments

    For each assignment a, adds
      a.start_timestamp
      a.end_timestamp
      a.session.rescheduled_to (if rescheduled)
      a.session.prefetched_active_materials
      a.session.order_number
    """
    assignments_queryset = assignments_queryset.prefetch_related(
            'timeslot', 'timeslot__type', 'timeslot__meeting',
            'timeslot__location', 'timeslot__location__floorplan', 'timeslot__location__urlresource_set',
            Prefetch(
                "session",
                queryset=add_event_info_to_session_qs(Session.objects.all().prefetch_related(
                    'group', 'group__charter', 'group__charter__group',
                    Prefetch('materials',
                             queryset=Document.objects.exclude(states__type=F("type"), states__slug='deleted').order_by('presentations__order').prefetch_related('states'),
                             to_attr='prefetched_active_materials'
                    )
                ))
            ),
            *extra_prefetches
        )


    # removed list(); it was consuming a very large amount of processor time
    # assignments = list(assignments_queryset) # make sure we're set in stone
    assignments = assignments_queryset

    # replace groups with historic counterparts
    groups = [ ]
    for a in assignments:
        if a.session:
            # Ensure that all Sessions refer to the same Meeting instance so they can share the
            # _groups_at_the_time() cache. The Sessions should all belong to the same meeting, but
            # check before blindly assigning to meeting just in case.
            if a.session.meeting.pk == meeting.pk:
                a.session.meeting = meeting
            a.session.order_number = a.session.order_in_meeting() if a.session.group else None

            if a.session.group and a.session.group not in groups:
                groups.append(a.session.group)

    sessions_for_groups = defaultdict(list)
    for a in assignments:
        if a.session and a.session.group:
            sessions_for_groups[(a.session.group, a.session.type_id)].append(a)

    timeslot_by_session_pk = {a.session_id: a.timeslot for a in assignments}

    for a in assignments:

        if a.session.current_status == 'resched':
            a.session.rescheduled_to = timeslot_by_session_pk.get(a.session.tombstone_for_id)

        for d in a.session.prefetched_active_materials:
            # make sure these are precomputed with the meeting instead
            # of having to look it up
            d.get_href(meeting=meeting)
            d.get_versionless_href(meeting=meeting)

        a.start_timestamp = int(a.timeslot.utc_start_time().timestamp())
        a.end_timestamp = int(a.timeslot.utc_end_time().timestamp())

    return assignments


class AgendaKeywordTool:
    """Base class for agenda keyword-related organizers

    The purpose of this class is to hold utility methods and data needed by keyword generation
    helper classes. It ensures consistency of, e.g., definitions of when to use legacy keywords or what
    timeslot types should be used to define filters.
    """
    def __init__(self, *, assignments=None, sessions=None):
        # n.b., single star argument means only keyword parameters are allowed when calling constructor
        if assignments is not None and sessions is None:
            self.assignments = assignments
            self.sessions = [a.session for a in self.assignments if a.session]
        elif sessions is not None and assignments is None:
            self.assignments = None
            self.sessions = sessions
        else:
            raise RuntimeError('Exactly one of assignments or sessions must be specified')

        self.meeting = self.sessions[0].meeting if len(self.sessions) > 0 else None

    def _use_legacy_keywords(self):
        """Should legacy keyword handling be used for this meeting?"""
        # Only IETF meetings need legacy handling. These are identified
        # by having a purely numeric meeting.number.
        return (self.meeting is not None
                and self.meeting.number.isdigit()
                and int(self.meeting.number) <= settings.MEETING_LEGACY_OFFICE_HOURS_END)

    # Helper methods
    @staticmethod
    def _get_group(s):
        """Get group of a session, handling historic groups"""
        return s.group_at_the_time()

    def _get_group_parent(self, s):
        """Get parent of a group or parent of a session's group, handling historic groups"""
        if isinstance(s, Session):
            return s.group_parent_at_the_time()
        else:
            # Assumption is that s is a group...
            return s and s.parent

    def _purpose_keyword(self, purpose):
        """Get the keyword corresponding to a session purpose"""
        return purpose.slug.lower()

    def _group_keyword(self, group):
        """Get the keyword corresponding to a session group"""
        return group.acronym.lower()

    def _session_name_keyword(self, session):
        """Get the keyword identifying a session by name"""
        return xslugify(session.name) if session.name else None

    @property
    def filterable_purposes(self):
        return SessionPurposeName.objects.exclude(slug='none').order_by('name')


class AgendaFilterOrganizer(AgendaKeywordTool):
    """Helper class to organize agenda filters given a list of assignments or sessions

    Either assignments or sessions must be specified (but not both). Keywords should be applied
    to these items before calling either of the 'get_' methods, otherwise some special filters
    may not be included (e.g., 'BoF' or 'Plenary'). If the session's group has a GroupHistory
    object active at the time of the start of the session's meeting, and/or the session's group
    parent had an active GroupHistory object active at the time, these will be used instead of 
    the group or parent.

    The organizer will process its inputs once, when one of its get_ methods is first called.

    Terminology:
      * column: group of related buttons, usually with a heading button.
      * heading: button at the top of a column, e.g. an area. Has a keyword that applies to all in its column.
      * category: a set of columns displayed as separate from other categories
      * group filters: filters whose keywords derive from the group owning the session, such as for working groups
      * non-group filters: filters whose keywords come from something other than a session's group
      * special filters: group filters of type "special" that have no heading, end up in the catch-all column
      * extra filters: ad hoc filters created based on the extra_labels list, go in the catch-all column
      * catch-all column: column with no heading where extra filters and special filters are gathered
    """
    # group acronyms in this list will never be used as filter buttons
    exclude_acronyms = ('iesg', 'ietf', 'secretariat')
    # extra keywords to include in the no-heading column if they apply to any sessions
    extra_labels = ('BoF',)
    # group types whose acronyms should be word-capitalized
    capitalized_group_types = ('team',)
    # group types whose acronyms should be all-caps
    uppercased_group_types = ('area', 'ietf', 'irtf')
    # check that the group labeling sets are disjoint
    assert(set(capitalized_group_types).isdisjoint(uppercased_group_types))
    # group acronyms that need special handling
    special_group_labels = dict(edu='EDU', iepg='IEPG')

    def __init__(self, *, single_category=False, **kwargs):
        super(AgendaFilterOrganizer, self).__init__(**kwargs)
        self.single_category = single_category
        # filled in when _organize_filters() is called
        self.filter_categories = None
        self.special_filters = None
        if self._use_legacy_keywords():
            self.extra_labels += ('Plenary',)  # need this when not using session purpose
        self.manual_extra_labels = set()

    def add_extra_filter(self, kw):
        self.manual_extra_labels.add(kw)

    def get_non_area_keywords(self):
        """Get list of any 'non-area' (aka 'special') keywords

        These are the keywords corresponding to the right-most, headingless button column.
        """
        if self.special_filters is None:
            self._organize_filters()
        return [sf['keyword'] for sf in self.special_filters['children']]

    def get_filter_categories(self):
        """Get a list of filter categories

        If single_category is True, this will be a list with one element. Otherwise it
        may have multiple elements. Each element is a list of filter columns.
        """
        if self.filter_categories is None:
            self._organize_filters()
        return self.filter_categories

    def _organize_filters(self):
        """Process inputs to construct and categorize filter lists"""
        headings, special = self._group_filter_headings()
        self.filter_categories = self._categorize_group_filters(headings)

        # Create an additional category with non-group filters and special/extra filters
        non_group_category = self._non_group_filters()

        # special filters include self.extra_labels and any 'special' group filters
        self.special_filters = self._extra_filters()
        for g in special:
            self.special_filters['children'].append(self._group_filter_entry(g))
        if len(self.special_filters['children']) > 0:
            self.special_filters['children'].sort(key=self._group_sort_key)
            non_group_category.append(self.special_filters)

        # if we have any additional filters, add them
        if len(non_group_category) > 0:
            if self.single_category:
                # if a single category is requested, just add them to that category
                self.filter_categories[0].extend(non_group_category)
            else:
                # otherwise add these as a separate category
                self.filter_categories.append(non_group_category)

    def _group_filter_headings(self):
        """Collect group-based filters

        Output is a tuple (dict(group->set), set). The dict keys are groups to be used as headings
        with sets of child groups as associated values. The set is 'special' groups that have no
        heading group.
        """
        # groups in the schedule that have a historic_parent group
        groups = set(self._get_group(s) for s in self.sessions
                     if s
                     and self._get_group(s))
        # Verify that we're not using the same acronym for more than one distinct group, accounting for
        # the possibility that some groups are GroupHistory instances. This assertion will fail if a Group
        # and GroupHistory for the same group have a different acronym - in that event, the filter will
        # not match the meeting display, so we should be alerted that this has actually occurred.
        log.assertion(
            "len(set(getattr(g, 'group_id', g.id) for g in groups)) "
            "== len(set(g.acronym for g in groups))"
        )

        group_parents = set(self._get_group_parent(g) for g in groups if self._get_group_parent(g))
        # See above for explanation of this assertion
        log.assertion(
            "len(set(getattr(gp, 'group_id', gp.id) for gp in group_parents)) "
            "== len(set(gp.acronym for gp in group_parents))"
        )

        all_groups = groups.union(group_parents)
        all_groups.difference_update([g for g in all_groups if g.acronym in self.exclude_acronyms])
        headings = {g: set()
                    for g in all_groups
                    if g.features.agenda_filter_type_id == 'heading'}
        special = set(g for g in all_groups
                      if g.features.agenda_filter_type_id == 'special')

        for g in groups:
            if g.features.agenda_filter_type_id == 'normal':
                # normal filter group with a heading parent goes in that column
                p = self._get_group_parent(g)
                if p in headings:
                    headings[p].add(g)
                else:
                    # normal filter group with no heading parent is 'special'
                    special.add(g)

        return headings, special

    def _categorize_group_filters(self, headings):
        """Categorize the group-based filters

        Returns a list of one or more categories of filter columns. When single_category is True,
        it will always be only one category.
        """
        area_category = []  # headings are area groups
        non_area_category = []  # headings are non-area groups

        for h in headings:
            if h.type_id == 'area' or self.single_category:
                area_category.append(self._group_filter_column(h, headings[h]))
            else:
                non_area_category.append(self._group_filter_column(h, headings[h]))
        area_category.sort(key=self._group_sort_key)
        if self.single_category:
            return [area_category]
        non_area_category.sort(key=self._group_sort_key)
        return [area_category, non_area_category]

    def _non_group_filters(self):
        """Get list of non-group filter columns

        Empty columns will be omitted.
        """
        if self.sessions is None:
            sessions = [a.session for a in self.assignments]
        else:
            sessions = self.sessions

        # Call legacy version for older meetings
        if self._use_legacy_keywords():
            return self._legacy_non_group_filters(sessions)

        # Not using legacy version
        filter_cols = []
        for purpose in self.filterable_purposes:
            if purpose.slug == 'regular':
                continue

            # Map label to its keyword, discarding duplicate labels.
            # This does what we want as long as sessions with the same
            # name and purpose belong to the same group.
            sessions_by_name = {
                session.name: session
                for session in sessions if session.purpose == purpose
            }
            if len(sessions_by_name) > 0:
                # keyword needs to match what's tagged in filter_keywords_for_session()
                heading_kw = self._purpose_keyword(purpose)
                children = []
                for name, session in sessions_by_name.items():
                    children.append(self._filter_entry(
                        label=name,
                        keyword=self._session_name_keyword(session),
                        toggled_by=[self._group_keyword(session.group)] if session.group else None,
                        is_bof=False,
                    ))
                column = self._filter_column(
                    label=purpose.name,
                    keyword=heading_kw,
                    children=children,
                )
                filter_cols.append(column)

        return filter_cols

    def _legacy_non_group_filters(self, sessions):
        """Get list of non-group filters for older meetings

        Returns a list of filter columns
        """
        office_hours_items = set()
        suffix = ' office hours'
        for s in sessions:
            if s.name.lower().endswith(suffix):
                office_hours_items.add((s.name[:-len(suffix)].strip(), s.group))

        headings = []
        # currently we only do office hours
        if len(office_hours_items) > 0:
            column = self._filter_column(
                label='Office Hours',
                keyword='officehours',
                children=[
                    self._filter_entry(
                        label=label,
                        keyword=f'{label.lower().replace(" ", "")}-officehours',
                        toggled_by=[self._group_keyword(group)] if group else None,
                        is_bof=False,
                    )
                    for label, group in sorted(office_hours_items, key=lambda item: item[0].upper())
                ])
            headings.append(column)
        return headings

    def _extra_filters(self):
        """Get list of filters corresponding to self.extra_labels"""
        item_source = self.assignments or self.sessions or []
        candidates = set(self.extra_labels).union(self.manual_extra_labels)
        return self._filter_column(
            label=None,
            keyword=None,
            children=[
                self._filter_entry(label=label, keyword=xslugify(label), toggled_by=[], is_bof=False)
                for label in candidates if label in self.manual_extra_labels or any(
                    # Keep only those that will affect at least one session
                    [label.lower() in item.filter_keywords for item in item_source]
                )]
        )

    @staticmethod
    def _filter_entry(label, keyword, is_bof, toggled_by=None):
        """Construct a filter entry representation"""
        # get our own copy of the list for toggled_by
        if toggled_by is None:
            toggled_by = []
        if is_bof:
            toggled_by = ['bof'] + toggled_by
        return dict(
            label=label,
            keyword=keyword,
            toggled_by=toggled_by,
            is_bof=is_bof,
        )

    def _filter_column(self, label, keyword, children):
        """Construct a filter column given a label, keyword, and list of child entries"""
        entry = self._filter_entry(label, keyword, False)  # heading
        entry['children'] = children
        # all children should be controlled by the heading keyword
        if keyword:
            for child in children:
                if keyword not in child['toggled_by']:
                    child['toggled_by'] = [keyword] + child['toggled_by']
        return entry

    def _group_label(self, group):
        """Generate a label for a group filter button"""
        label = group.acronym
        if label in self.special_group_labels:
            return self.special_group_labels[label]
        elif group.type_id in self.capitalized_group_types:
            return label.capitalize()
        elif group.type_id in self.uppercased_group_types:
            return label.upper()
        return label

    def _group_filter_entry(self, group):
        """Construct a filter_entry for a group filter button"""
        return self._filter_entry(
            label=self._group_label(group),
            keyword=self._group_keyword(group),
            toggled_by=[self._group_keyword(group.parent)] if group.parent else None,
            is_bof=group.is_bof(),
        )

    def _group_filter_column(self, heading, children):
        """Construct a filter column given a heading group and a list of its child groups"""
        return self._filter_column(
            label=None if heading is None else self._group_label(heading),
            keyword=self._group_keyword(heading),
            children=sorted([self._group_filter_entry(g) for g in children], key=self._group_sort_key),
        )

    @staticmethod
    def _group_sort_key(g):
        return 'zzzzzzzz' if g is None else g['label'].upper()  # sort blank to the end


class AgendaKeywordTagger(AgendaKeywordTool):
    """Class for applying keywords to agenda timeslot assignments.

    This is the other side of the agenda filtering: AgendaFilterOrganizer generates the
    filter buttons, this applies keywords to the entries being filtered.
    """
    def apply(self):
        """Apply tags to sessions / assignments"""
        if self.assignments is not None:
            self._tag_assignments_with_filter_keywords()
        else:
            self._tag_sessions_with_filter_keywords()

    def apply_session_keywords(self):
        """Tag each item with its session-specific keyword"""
        if self.assignments is not None:
            for a in self.assignments:
                a.session_keyword = self.filter_keyword_for_specific_session(a.session)
        else:
            for s in self.sessions:
                s.session_keyword = self.filter_keyword_for_specific_session(s)

    def _is_regular_agenda_filter_group(self, group):
        """Should this group appear in the 'regular' agenda filter button lists?"""
        parent = self._get_group_parent(group)
        return (
                group.features.agenda_filter_type_id == 'normal'
                and parent
                and parent.features.agenda_filter_type_id == 'heading'
        )

    def _tag_assignments_with_filter_keywords(self):
        """Add keywords for agenda filtering

        Keywords are all lower case.
        """
        for a in self.assignments:
            a.filter_keywords = self._filter_keywords_for_assignment(a)
            a.filter_keywords = sorted(list(a.filter_keywords))

    def _tag_sessions_with_filter_keywords(self):
        for s in self.sessions:
            s.filter_keywords = self._filter_keywords_for_session(s)
            s.filter_keywords = sorted(list(s.filter_keywords))

    @staticmethod
    def _legacy_extra_session_keywords(session):
        """Get extra keywords for a session at a legacy meeting"""
        extra = []
        if session.type_id == 'plenary':
            extra.append('plenary')
        office_hours_match = re.match(r'^ *\w+(?: +\w+)* +office hours *$', session.name, re.IGNORECASE)
        if office_hours_match is not None:
            suffix = 'officehours'
            extra.extend([
                'officehours',
                session.name.lower().replace(' ', '')[:-len(suffix)] + '-officehours',
            ])
        return extra

    def _filter_keywords_for_session(self, session):
        keywords = set()
        if session.purpose in self.filterable_purposes:
            keywords.add(self._purpose_keyword(session.purpose))

        group = self._get_group(session)
        if group is not None:
            if group.state_id == 'bof':
                keywords.add('bof')
            keywords.add(self._group_keyword(group))
        specific_kw = self.filter_keyword_for_specific_session(session)
        if specific_kw is not None:
            keywords.add(specific_kw)

        kw = self._session_name_keyword(session)
        if kw:
            keywords.add(kw)

        # Only sessions belonging to "regular" groups should respond to the
        # parent group filter keyword (often the 'area'). This must match
        # the test used by the agenda() view to decide whether a group
        # gets an area or non-area filter button.
        if self._is_regular_agenda_filter_group(group):
            area = self._get_group_parent(group)
            if area is not None:
                keywords.add(self._group_keyword(area))

        if self._use_legacy_keywords():
            keywords.update(self._legacy_extra_session_keywords(session))

        return sorted(keywords)

    def _filter_keywords_for_assignment(self, assignment):
        keywords = self._filter_keywords_for_session(assignment.session)
        return sorted(keywords)

    def filter_keyword_for_specific_session(self, session):
        """Get keyword that identifies a specific session

        Returns None if the session cannot be selected individually.
        """
        group = self._get_group(session)
        if group is None:
            return None
        kw = self._group_keyword(group)  # start with this
        token = session.docname_token_only_for_multiple()
        return kw if token is None else '{}-{}'.format(kw, token)


def read_session_file(type, num, doc):
    # XXXX FIXME: the path fragment in the code below should be moved to
    # settings.py.  The *_PATH settings should be generalized to format()
    # style python format, something like this:
    #  DOC_PATH_FORMAT = { "agenda": "/foo/bar/agenda-{meeting.number}/agenda-{meeting-number}-{doc.group}*", }
    #
    # FIXME: uploaded_filename should be replaced with a function call that computes names that are fixed
    path = os.path.join(settings.AGENDA_PATH, "%s/%s/%s" % (num, type, doc.uploaded_filename))
    if doc.uploaded_filename and os.path.exists(path):
        with io.open(path, 'rb') as f:
            return f.read(), path
    else:
        return None, path

def read_agenda_file(num, doc):
    return read_session_file('agenda', num, doc)

# TODO-BLOBSTORE: this is _yet another_ draft derived variant created when users
# ask for drafts from the meeting agenda page. Consider whether to refactor this
# now to not call out to external binaries, and consider whether we need this extra
# format at all in the draft blobstore. if so, it would probably be stored under 
# something like plainpdf/ 
def convert_draft_to_pdf(doc_name):
    inpath = os.path.join(settings.IDSUBMIT_REPOSITORY_PATH, doc_name + ".txt")
    outpath = os.path.join(settings.INTERNET_DRAFT_PDF_PATH, doc_name + ".pdf")

    try:
        infile = io.open(inpath, "r")
    except IOError:
        return

    t,tempname = mkstemp()
    os.close(t)
    tempfile = io.open(tempname, "w")

    pageend = 0;
    newpage = 0;
    formfeed = 0;
    for line in infile:
        line = re.sub("\r","",line)
        line = re.sub("[ \t]+$","",line)
        if re.search(r"\[?[Pp]age [0-9ivx]+\]?[ \t]*$",line):
            pageend=1
            tempfile.write(line)
            continue
        if re.search("^[ \t]*\f",line):
            formfeed=1
            tempfile.write(line)
            continue
        if re.search("^ *INTERNET.DRAFT.+[0-9]+ *$",line) or re.search("^ *Internet.Draft.+[0-9]+ *$",line) or re.search("^draft-[-a-z0-9_.]+.*[0-9][0-9][0-9][0-9]$",line) or re.search("^RFC.+[0-9]+$",line):
            newpage=1
        if re.search("^[ \t]*$",line) and pageend and not newpage:
            continue
        if pageend and newpage and not formfeed:
            tempfile.write("\f")
        pageend=0
        formfeed=0
        newpage=0
        tempfile.write(line)

    infile.close()
    tempfile.close()
    t,psname = mkstemp()
    os.close(t)
    pipe("enscript --margins 76::76: -B -q -p "+psname + " " +tempname)
    os.unlink(tempname)
    pipe("ps2pdf "+psname+" "+outpath)
    os.unlink(psname)

def schedule_permissions(meeting, schedule, user):
    # do this in positive logic.
    cansee = False
    canedit = False
    secretariat = False

    if has_role(user, 'Secretariat'):
        cansee = True
        secretariat = True
        # NOTE: secretariat is not superuser for edit!
    elif schedule.public:
        cansee = True
    elif schedule.visible and has_role(user, ['Area Director', 'IAB Chair', 'IRTF Chair']):
        cansee = True

    if user_is_person(user, schedule.owner):
        cansee = True
        canedit = not schedule.is_official_record

    return cansee, canedit, secretariat


# -------------------------------------------------
# Interim Meeting Helpers
# -------------------------------------------------


def can_approve_interim_request(meeting, user):
    '''Returns True if the user has permissions to approve an interim meeting request'''
    if not user or isinstance(user,AnonymousUser):
        return False
    if meeting.type.slug != 'interim':
        return False
    if has_role(user, 'Secretariat'):
        return True
    person = get_person_for_user(user)
    session = meeting.session_set.first()
    if not session:
        return False
    group = session.group
    if group.type.slug in ['wg','ag']:
        if group.parent.role_set.filter(name='ad', person=person) or group.role_set.filter(name='ad', person=person):
            return True
    if group.type.slug in ['rg','rag'] and group.parent.role_set.filter(name='chair', person=person):
        return True
    if group.type.slug == 'program':
        if person.role_set.filter(group__acronym='iab', name='member'):
            return True
    return False


def can_edit_interim_request(meeting, user):
    '''Returns True if the user can edit the interim meeting request'''
    if meeting.type.slug != 'interim':
        return False
    if has_role(user, 'Secretariat'): # Consider removing - can_manage_group should handle this
        return True
    session = meeting.session_set.first()
    if not session:
        return False
    group = session.group
    if can_manage_group(user, group):
        return True
    elif can_approve_interim_request(meeting, user):
        return True
    else:
        return False


def can_request_interim_meeting(user):
    return can_manage_some_groups(user)

def can_view_interim_request(meeting, user):
    '''Returns True if the user can see the pending interim request in the pending interim view'''
    if meeting.type.slug != 'interim':
        return False
    session = meeting.session_set.first()
    if not session:
        return False
    group = session.group
    return can_manage_group(user, group)


def create_interim_meeting(group, date, city='', country='', timezone='UTC',
                           person=None):
    """Helper function to create interim meeting and associated schedule"""
    if not person:
        person = Person.objects.get(name='(System)')
    number = get_next_interim_number(group.acronym, date)
    meeting = Meeting.objects.create(
        number=number,
        type_id='interim',
        date=date,
        days=1,
        city=city,
        country=country,
        time_zone=timezone)
    schedule = Schedule.objects.create(
        meeting=meeting,
        owner=person,
        visible=True,
        public=True)
    meeting.schedule = schedule
    meeting.save()
    return meeting


def get_announcement_initial(meeting, is_change=False):
    '''Returns a dictionary suitable to initialize an InterimAnnouncementForm
    (Message ModelForm)'''
    group = meeting.session_set.first().group
    in_person = bool(meeting.city)
    initial = {}
    addrs = gather_address_lists('interim_announced',group=group).as_strings()
    initial['to'] = addrs.to
    initial['cc'] = addrs.cc
    initial['frm'] = settings.INTERIM_ANNOUNCE_FROM_EMAIL_PROGRAM if group.type_id=='program' else settings.INTERIM_ANNOUNCE_FROM_EMAIL_DEFAULT
    if in_person:
        desc = 'Interim'
    else:
        desc = 'Virtual'
    if is_change:
        change = ' CHANGED'
    else:
        change = ''
    type = group.type.slug.upper()
    if group.type.slug == 'wg' and group.state.slug == 'bof':
        type = 'BOF'

    assignments = SchedTimeSessAssignment.objects.filter(
        schedule__in=[meeting.schedule, meeting.schedule.base if meeting.schedule else None],
        session__in=meeting.session_set.not_canceled()
    ).order_by('timeslot__time')

    initial['subject'] = '{name} ({acronym}) {type} {desc} Meeting: {date}{change}'.format(
        name=group.name, 
        acronym=group.acronym,
        type=type,
        desc=desc,
        date=meeting.date,
        change=change)
    body = render_to_string('meeting/interim_announcement.txt', locals() | {"settings": settings})
    initial['body'] = body
    return initial


def get_earliest_session_date(formset):
    '''Return earliest date from InterimSession Formset'''
    return sorted([f.cleaned_data['date'] for f in formset.forms if f.cleaned_data.get('date')])[0]


def is_interim_meeting_approved(meeting):
    return add_event_info_to_session_qs(meeting.session_set.all()).first().current_status == 'apprw'

def get_next_interim_number(acronym,date):
    '''
    This function takes a group acronym and date object and returns the next number
    to use for an interim meeting.  The format is interim-[year]-[acronym]-[01-99]
    '''
    base = 'interim-%s-%s-' % (date.year, acronym)
    # can't use count() to calculate the next number in case one was deleted
    meetings = Meeting.objects.filter(type='interim', number__startswith=base)
    if meetings:
        serial = sorted([ int(x.number.split('-')[-1]) for x in meetings ])[-1]
    else:
        serial = 0
    return "%s%02d" % (base, serial+1)

def get_next_agenda_name(meeting):
    """Returns the next name to use for an agenda document for *meeting*"""
    group = meeting.session_set.first().group
    documents = Document.objects.filter(type='agenda', session__meeting=meeting)
    if documents:
        sequences = [int(d.name.split('-')[-1]) for d in documents]
        last_sequence = sorted(sequences)[-1]
    else:
        last_sequence = 0
    return 'agenda-{meeting}-{group}-{sequence}'.format(
        meeting=meeting.number,
        group=group.acronym,
        sequence=str(last_sequence + 1).zfill(2))


def make_materials_directories(meeting):
    '''
    This function takes a meeting object and creates the appropriate materials directories
    '''
    path = meeting.get_materials_path()
    # Default umask is 0x022, meaning strip write permission for group and others.
    # Change this temporarily to 0x0, to keep write permission for group and others.
    # (WHY??) (Note: this code is old -- was present already when the secretariat code
    # was merged with the regular datatracker code; then in secr/proceedings/views.py
    # in make_directories())
    saved_umask = os.umask(0)   
    for leaf in ('slides','agenda','minutes', 'narrativeminutes', 'id','rfc','bluesheets'):
        target = os.path.join(path,leaf)
        if not os.path.exists(target):
            os.makedirs(target)
    os.umask(saved_umask)


def send_interim_approval_request(meetings):
    """Sends an email to the secretariat, group chairs, and responsible area
    director or the IRTF chair noting that approval has been requested for a
    new interim meeting.  Takes a list of one or more meetings."""
    first_session = meetings[0].session_set.first()
    group = first_session.group
    requester = session_requested_by(first_session)
    (to_email, cc_list) = gather_address_lists('session_requested',group=group,person=requester)
    from_email = (settings.SESSION_REQUEST_FROM_EMAIL)
    subject = '{group} - New Interim Meeting Request'.format(group=group.acronym)
    template = 'meeting/interim_approval_request.txt'
    approval_urls = []
    for meeting in meetings:
        url = settings.IDTRACKER_BASE_URL + reverse('ietf.meeting.views.interim_request_details', kwargs={'number': meeting.number})
        approval_urls.append(url)
    if len(meetings) > 1:
        is_series = True
    else:
        is_series = False
    approver_set = set()
    for authrole in group.features.groupman_authroles: # NOTE: This makes an assumption that the authroles are exactly the set of approvers
        approver_set.add(authrole)
    approvers = list(approver_set)
    context = {
        'group': group,
        'is_series': is_series,
        'meetings': meetings,
        'approvers': approvers,
        'requester': requester,
        'approval_urls': approval_urls,
    }
    send_mail(None,
              to_email,
              from_email,
              subject,
              template,
              context,
              cc=cc_list)

def send_interim_approval(user, meeting):
    """Send an email to chairs and whoever initiated the action that resulted in approval that an interim is approved"""
    first_session = meeting.session_set.first()
    (to_email,cc_list) = gather_address_lists('interim_approved',group=first_session.group,person=user.person)
    from_email = (settings.SESSION_REQUEST_FROM_EMAIL)
    subject = f'{meeting.number} interim approved'
    template = 'meeting/interim_approval.txt'
    context = { 
        'meeting': meeting,
        'group' : first_session.group,
        'requester' : session_requested_by(first_session),
    }
    send_mail(None,
              to_email,
              from_email,
              subject,
              template,
              context,
              cc=cc_list)

def send_interim_announcement_request(meeting):
    """Sends an email to the secretariat that an interim meeting is ready for 
    announcement, includes the link to send the official announcement"""
    first_session = meeting.session_set.first()
    group = first_session.group
    requester = session_requested_by(first_session)
    (to_email, cc_list) = gather_address_lists('interim_announce_requested')
    from_email = (settings.SESSION_REQUEST_FROM_EMAIL)
    subject = '{group} - interim meeting ready for announcement'.format(group=group.acronym)
    template = 'meeting/interim_announcement_request.txt'
    announce_url = settings.IDTRACKER_BASE_URL + reverse('ietf.meeting.views.interim_request_details', kwargs={'number': meeting.number})
    context = locals()
    send_mail(None,
              to_email,
              from_email,
              subject,
              template,
              context,
              cc_list)

def send_interim_meeting_cancellation_notice(meeting):
    """Sends an email that a scheduled interim meeting has been cancelled."""
    session = meeting.session_set.first()
    group = session.group
    (to_email, cc_list) = gather_address_lists('interim_cancelled',group=group)
    from_email = settings.INTERIM_ANNOUNCE_FROM_EMAIL_PROGRAM if group.type_id=='program' else settings.INTERIM_ANNOUNCE_FROM_EMAIL_DEFAULT
    subject = '{group} ({acronym}) {type} Interim Meeting Cancelled (was {date})'.format(
        group=group.name,
        acronym=group.acronym,
        type=group.type.slug.upper(),
        date=meeting.date.strftime('%Y-%m-%d'))
    start_time = session.official_timeslotassignment().timeslot.time
    end_time = start_time + session.requested_duration
    is_multi_day = session.meeting.session_set.with_current_status().filter(current_status='sched').count() > 1
    template = 'meeting/interim_meeting_cancellation_notice.txt'
    context = locals()
    send_mail(None,
              to_email,
              from_email,
              subject,
              template,
              context,
              cc=cc_list)


def send_interim_session_cancellation_notice(session):
    """Sends an email that one session of a scheduled interim meeting has been cancelled."""
    group = session.group
    start_time = session.official_timeslotassignment().timeslot.time
    end_time = start_time + session.requested_duration
    (to_email, cc_list) = gather_address_lists('interim_cancelled',group=group)
    from_email = settings.INTERIM_ANNOUNCE_FROM_EMAIL_PROGRAM if group.type_id=='program' else settings.INTERIM_ANNOUNCE_FROM_EMAIL_DEFAULT

    if session.name:
        description = '"%s" session' % session.name
    else:
        description = 'interim meeting session'

    subject = '{group} ({acronym}) {type} {description} cancelled (was {date})'.format(
        group=group.name,
        acronym=group.acronym,
        type=group.type.slug.upper(),
        description=description,
        date=start_time.date().strftime('%Y-%m-%d'))
    is_multi_day = session.meeting.session_set.with_current_status().filter(current_status='sched').count() > 1
    template = 'meeting/interim_session_cancellation_notice.txt'
    context = locals()
    send_mail(None,
              to_email,
              from_email,
              subject,
              template,
              context,
              cc=cc_list)


def send_interim_minutes_reminder(meeting):
    """Sends an email reminding chairs to submit minutes of interim *meeting*"""
    session = meeting.session_set.first()
    group = session.group
    (to_email, cc_list) = gather_address_lists('session_minutes_reminder',group=group)
    from_email = 'proceedings@ietf.org'
    subject = 'Action Required: Minutes from {group} ({acronym}) {type} Interim Meeting on {date}'.format(
        group=group.name,
        acronym=group.acronym,
        type=group.type.slug.upper(),
        date=meeting.date.strftime('%Y-%m-%d'))
    template = 'meeting/interim_minutes_reminder.txt'
    context = locals()
    send_mail(None,
              to_email,
              from_email,
              subject,
              template,
              context,
              cc=cc_list)


def sessions_post_save(request, forms):
    """Helper function to perform various post save operations on each form of a
    InterimSessionModelForm formset"""
    for form in forms:
        if not form.has_changed():
            continue

        if form.instance.pk is not None and not SchedulingEvent.objects.filter(session=form.instance).exists():
            if not form.requires_approval:
                status_id = 'scheda'
            else:
                status_id = 'apprw'
            SchedulingEvent.objects.create(
                session=form.instance,
                status_id=status_id,
                by=request.user.person,
            )
        
        update_interim_session_assignment(form)
        if 'agenda' in form.changed_data:
            form.save_agenda()

        try:
            create_interim_session_conferences(
                form.instance for form in forms
                if form.cleaned_data.get('remote_participation', None) == 'meetecho'
            )
        except RuntimeError:
            messages.warning(
                request,
                'An error occurred while creating a Meetecho conference. The interim meeting request '
                'has been created without complete remote participation information. '
                'Please edit the request to add this or contact the secretariat if you require assistance.',
            )


def create_interim_session_conferences(sessions):
    error_occurred = False
    if hasattr(settings, 'MEETECHO_API_CONFIG'):  # do nothing if not configured
        meetecho_manager = meetecho.ConferenceManager(settings.MEETECHO_API_CONFIG)
        for session in sessions:
            ts = session.official_timeslotassignment().timeslot
            try:
                confs = meetecho_manager.create(
                    group=session.group,
                    session_id=session.pk,
                    description=str(session),
                    start_time=ts.utc_start_time(),
                    duration=ts.duration,
                )
            except Exception as err:
                log.log(f'Exception creating Meetecho conference for {session}: {err}')
                confs = []

            if len(confs) == 1:
                session.remote_instructions = confs[0].url
                session.save()
            else:
                error_occurred = True
    if error_occurred:
        raise RuntimeError('error creating meetecho conferences')


def delete_interim_session_conferences(sessions):
    """Delete Meetecho conference for the session, if any"""
    if hasattr(settings, 'MEETECHO_API_CONFIG'):  # do nothing if Meetecho API not configured
        meetecho_manager = meetecho.ConferenceManager(settings.MEETECHO_API_CONFIG)
        for session in sessions:
            if session.remote_instructions:
                for conference in meetecho_manager.fetch(session.group):
                    if conference.url == session.remote_instructions:
                        conference.delete()
                        break


def sessions_post_cancel(request, sessions):
    """Clean up after session cancellation

    When this is called, the session has already been canceled, so exceptions should
    not be raised.
    """
    try:
        delete_interim_session_conferences(sessions)
    except Exception as err:
        sess_pks = ', '.join(str(s.pk) for s in sessions)
        log.log(f'Exception deleting Meetecho conferences for sessions [{sess_pks}]: {err}')
        messages.warning(
            request,
            'An error occurred while cleaning up Meetecho conferences for the canceled sessions. '
            'The session or sessions have been canceled, but Meetecho conferences may not have been cleaned '
            'up properly.',
        )


def update_interim_session_assignment(form):
    """Helper function to create / update timeslot assigned to interim session

    form is an InterimSessionModelForm

    Only updates timeslot time (a datetime) and duration
    """
    session = form.instance
    meeting = session.meeting
    time = meeting.tz().localize(
        datetime.datetime.combine(form.cleaned_data['date'], form.cleaned_data['time'])
    )
    if session.official_timeslotassignment():
        slot = session.official_timeslotassignment().timeslot
        if slot.time != time or slot.duration != session.requested_duration:
            slot.time = time
            slot.duration = session.requested_duration
            slot.save()
    else:
        slot = TimeSlot.objects.create(
            meeting=meeting,
            type_id='regular',
            duration=session.requested_duration,
            time=time)
        SchedTimeSessAssignment.objects.create(
            timeslot=slot,
            session=session,
            schedule=meeting.schedule)

def populate_important_dates(meeting):
    assert ImportantDate.objects.filter(meeting=meeting).exists() is False
    assert meeting.type_id=='ietf'
    for datename in ImportantDateName.objects.filter(used=True):
        ImportantDate.objects.create(meeting=meeting,name=datename,date=meeting.date+datetime.timedelta(days=datename.default_offset_days))

def update_important_dates(meeting):
    assert meeting.type_id=='ietf'
    for datename in ImportantDateName.objects.filter(used=True):
        date = meeting.date+datetime.timedelta(days=datename.default_offset_days)
        d = ImportantDate.objects.filter(meeting=meeting, name=datename).first()
        if d:
            d.date = date
            d.save()
        else:
            ImportantDate.objects.create(meeting=meeting, name=datename, date=date)
