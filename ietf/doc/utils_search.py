# Copyright The IETF Trust 2016-2020, All Rights Reserved
# -*- coding: utf-8 -*-

import re
import datetime
import debug                            # pyflakes:ignore

from collections import defaultdict
from zoneinfo import ZoneInfo

from django.conf import settings

from ietf.doc.models import Document, RelatedDocument, DocEvent, TelechatDocEvent, BallotDocEvent, DocTypeName
from ietf.doc.expire import expirable_drafts
from ietf.doc.utils import augment_docs_and_person_with_person_info
from ietf.meeting.models import SessionPresentation, Meeting, Session
from ietf.person.models import Alias
from ietf.review.utils import review_assignments_to_list_for_docs
from ietf.utils.timezone import date_today


class wrap_value:
    """Callable stand-in for a no-argument method whose value was computed in bulk.

    Assigned over the method on the instance, so templates and code can keep calling
    doc.telechat_date() without hitting the database. A class rather than a closure
    because documents carrying one of these get pickled into the caches behind
    ietf.doc.views_search.recent_drafts, and a lambda is not picklable.
    """

    def __init__(self, value):
        self.value = value

    def __call__(self):
        return self.value

    def __eq__(self, other):
        return isinstance(other, wrap_value) and self.value == other.value

    def __hash__(self):
        # Defining __eq__ without this would set __hash__ to None and make instances
        # unhashable, which a method they stand in for is not.
        return hash(self.value)

    def __repr__(self):
        return f"wrap_value({self.value!r})"


# Relationships the document table renders for each row. RELATED_THAT holds the ones
# read in the "documents pointing at this one" direction (Document.related_that),
# RELATED_THAT_DOC the ones read in the "documents this one points at" direction
# (Document.related_that_doc).
RELATED_THAT = ("replaces", "contains")
RELATED_THAT_DOC = ("became_rfc", "replaces")

# Followed transitively to find the documents whose IPR disclosures count as related.
IPR_RELATED = ("obs", "replaces")


def fill_in_document_relations(docs, doc_dict, doc_ids):
    """Seed each document's relation caches from two queries.

    Document.related_that/related_that_doc otherwise run one query per document per
    relationship, and the table reads several of them for every row (friendly_state,
    part_of, replaces, became_rfc).
    """
    for d in docs:
        d._cached_related_that = {name: [] for name in RELATED_THAT}
        d._cached_related_that_doc = {name: [] for name in RELATED_THAT_DOC}

    for rel in RelatedDocument.objects.filter(
        target_id__in=doc_ids, relationship__in=RELATED_THAT
    ).select_related("source"):
        doc_dict[rel.target_id]._cached_related_that[rel.relationship_id].append(rel.source)

    for rel in RelatedDocument.objects.filter(
        source_id__in=doc_ids, relationship__in=RELATED_THAT_DOC
    ).select_related("target"):
        doc_dict[rel.source_id]._cached_related_that_doc[rel.relationship_id].append(rel.target)

    for d in docs:
        # related_that/related_that_doc deduplicate; match that.
        for cache in (d._cached_related_that, d._cached_related_that_doc):
            for name, related in cache.items():
                cache[name] = list({r.pk: r for r in related}.values())
        d._cached_became_rfc = next(iter(d._cached_related_that_doc["became_rfc"]), None)

    # For each subseries document a row is part of, the table also reads what that
    # subseries contains. Those documents are not in `docs`, so seed them here rather
    # than leaving a query per subseries membership.
    subseries = defaultdict(list)
    for d in docs:
        for sub in d._cached_related_that["contains"]:
            subseries[sub.pk].append(sub)
    if subseries:
        contains = defaultdict(list)
        for rel in RelatedDocument.objects.filter(
            source_id__in=subseries, relationship_id="contains"
        ).select_related("target"):
            contains[rel.source_id].append(rel.target)
        for pk, instances in subseries.items():
            targets = list({r.pk: r for r in contains[pk]}.values())
            for sub in instances:
                sub._cached_related_that_doc = {"contains": targets}


def fill_in_related_ipr(docs, doc_dict, doc_ids):
    """Attach the related IPR disclosure ids to each document.

    Document.related_ipr walks the obs/replaces graph with Document.all_relations_that_doc,
    which issues a query per node it visits, per document. Here the graph is walked once
    for the whole result set -- one query per level of depth -- and the disclosures are
    fetched in a single query.
    """
    from ietf.ipr.models import IprDocRel

    edges = defaultdict(set)
    seen = set(doc_ids)
    front = set(doc_ids)
    while front:
        next_front = set()
        for source_id, target_id in RelatedDocument.objects.filter(
            source_id__in=front, relationship__in=IPR_RELATED
        ).values_list("source_id", "target_id"):
            edges[source_id].add(target_id)
            if target_id not in seen:
                seen.add(target_id)
                next_front.add(target_id)
        front = next_front

    def reachable_from(start):
        """start plus every document it directly or indirectly obsoletes or replaces."""
        found = {start}
        stack = [start]
        while stack:
            for target_id in edges[stack.pop()]:
                if target_id not in found:
                    found.add(target_id)
                    stack.append(target_id)
        return found

    reachable = {pk: reachable_from(pk) for pk in doc_ids}

    disclosures = defaultdict(set)
    involved = set().union(*reachable.values()) if reachable else set()
    for document_id, disclosure_id in IprDocRel.objects.filter(
        document_id__in=involved, disclosure__state__in=settings.PUBLISH_IPR_STATES
    ).values_list("document_id", "disclosure_id"):
        disclosures[document_id].add(disclosure_id)

    for d in docs:
        related = set()
        for pk in reachable[d.pk]:
            related |= disclosures[pk]
        # Wrapped rather than assigned bare so that the attribute stays callable, like
        # the Document.related_ipr method it shadows. Templates auto-call either way,
        # but a bare list would turn doc.related_ipr() into a TypeError for any Python
        # caller handed a prepared document.
        d.related_ipr = wrap_value(sorted(related))


def fill_in_person_caches(docs):
    """Seed the per-instance caches person_link and email_person_link read.

    select_related hands every row its own Person instance, so Person.email() and
    Person.has_alias_for_name() each cost a query per person the table names -- the AD,
    the shepherd, and any action holders. The emails come from the prefetches set up in
    prepare_document_table; the aliases need one query between all of them.
    """
    # People whose address the table renders via Person.email(). Their email_set is
    # prefetched in prepare_document_table. Action holders are only read when the
    # document has them enabled, which is the same condition the template applies -- so
    # this costs nothing extra for callers that skipped the prefetch.
    with_email = [d.ad for d in docs if d.ad_id]
    for d in docs:
        if d.action_holders_enabled():
            with_email.extend(holder.person for holder in d.documentactionholder_set.all())
    # The shepherd column renders the address it already holds, but still needs an alias.
    shepherds = [d.shepherd.person for d in docs if d.shepherd_id and d.shepherd.person_id]

    people = with_email + shepherds
    if not people:
        return

    aliased = set(
        Alias.objects.filter(person__in={p.pk for p in people}).values_list("person_id", "name")
    )
    for person in people:
        person._cached_has_alias_for_name = (person.pk, person.name) in aliased

    for person in with_email:
        if hasattr(person, "_cached_email"):
            continue
        emails = list(person.email_set.all())
        # Mirror Person.email(): a primary address if there is one -- lowest by address,
        # which is the pk an unordered first() would have ordered by -- and otherwise
        # the most recent active one. Email.address is a CICharField, so the database
        # orders it case-insensitively; casefold the key to match.
        primary = sorted((e for e in emails if e.primary), key=lambda e: e.address.lower())
        if primary:
            person._cached_email = primary[0]
        else:
            active = sorted(
                (e for e in emails if e.active),
                key=lambda e: (e.time, e.address.lower()),
                reverse=True,
            )
            person._cached_email = active[0] if active else None


def fill_in_telechat_date(docs, doc_dict=None, doc_ids=None):
    if doc_dict is None:
        doc_dict = dict((d.pk, d) for d in docs)
        doc_ids = list(doc_dict.keys())
    if doc_ids is None:
        doc_ids = list(doc_dict.keys())

    seen = set()
    for e in TelechatDocEvent.objects.filter(doc__id__in=doc_ids, type="scheduled_for_telechat").order_by('-time', '-id'):
        if e.doc_id not in seen:
            d = doc_dict[e.doc_id]
            # Shadow Document.telechat_date with a callable returning the precomputed
            # value, so templates can keep calling doc.telechat_date without each row
            # issuing its own latest_event() query.
            d.telechat_date = wrap_value(d.telechat_date(e))
            seen.add(e.doc_id)

    for pk, d in doc_dict.items():
        if pk not in seen:
            d.telechat_date = wrap_value(None)

def fill_in_document_sessions(docs, doc_dict, doc_ids):
    today = date_today()
    beg_date = today-datetime.timedelta(days=7)
    end_date = today+datetime.timedelta(days=30)
    meetings = Meeting.objects.filter(date__gte=beg_date, date__lte=end_date).prefetch_related('session_set')
    # get sessions
    sessions = Session.objects.filter(meeting_id__in=[ m.id for m in meetings ])
    # get presentations
    presentations = SessionPresentation.objects.filter(session_id__in=[ s.id for s in sessions ])
    session_list = [ (p.document_id, p.session) for p in presentations ]
    for d in list(doc_dict.values()):
        d.sessions = []
    for (i, s) in session_list:
        if i in doc_ids:
            doc_dict[i].sessions.append(s)

def fill_in_document_table_attributes(docs, have_telechat_date=False):
    # fill in some attributes for the document table results to save
    # some hairy template code and avoid repeated SQL queries
    # TODO - this function evolved from something that assumed it was handling only drafts. 
    #        It still has places where it assumes all docs are drafts where that is not a correct assumption

    doc_dict = dict((d.pk, d) for d in docs)
    doc_ids = list(doc_dict.keys())

    rfcs = dict((d.pk, d.name) for d in docs if d.type_id == "rfc")

    # latest event cache
    event_types = ("published_rfc",
                   "changed_ballot_position",
                   "started_iesg_process",
                   "new_revision")
    for d in docs:
        d.latest_event_cache = dict()
        for e in event_types:
            d.latest_event_cache[e] = None

    # DISTINCT ON fetches only the newest event of each (doc, type) pair. Ordering
    # ascending and letting later rows overwrite earlier ones pulls back every matching
    # event, and a draft routinely has dozens of new_revision events.
    for e in (DocEvent.objects
              .filter(doc__id__in=doc_ids, type__in=event_types)
              .order_by('doc_id', 'type', '-time', '-id')
              .distinct('doc_id', 'type')):
        doc_dict[e.doc_id].latest_event_cache[e.type] = e

    # Default to None so that ballot_icon finds the attribute for documents with no
    # ballot event at all. Otherwise it falls back to doc.active_ballot(), which costs a
    # query per such row.
    for d in docs:
        d.ballot = None
    seen = set()
    for e in BallotDocEvent.objects.filter(doc__id__in=doc_ids, type__in=('created_ballot', 'closed_ballot')).order_by('-time','-id'):
        if not e.doc_id in seen:
            doc_dict[e.doc_id].ballot = e if e.type == 'created_ballot' else None
            seen.add(e.doc_id)

    fill_in_document_relations(docs, doc_dict, doc_ids)
    fill_in_related_ipr(docs, doc_dict, doc_ids)
    fill_in_person_caches(docs)

    if not have_telechat_date:
        fill_in_telechat_date(docs, doc_dict, doc_ids)

    # on agenda in upcoming meetings
    # get meetings
    fill_in_document_sessions(docs, doc_dict, doc_ids)

    # misc
    expirable_pks = expirable_drafts(Document.objects.filter(pk__in=doc_ids)).values_list('pk', flat=True)

    # Look up review assignments for every draft at once. Calling this per document, as
    # the loop below used to, repeats a breadth-first walk of the replaces graph and an
    # assignment query for each row.
    review_docs = [d for d in docs if d.type_id == "draft" and d.get_state_slug() != "rfc"]
    review_assignments = review_assignments_to_list_for_docs(review_docs) if review_docs else {}

    for d in docs:

        if d.type_id == "rfc" and d.latest_event_cache["published_rfc"]:
            d.latest_revision_date = d.latest_event_cache["published_rfc"].time
        elif d.latest_event_cache["new_revision"]:
            d.latest_revision_date = d.latest_event_cache["new_revision"].time
        else:
            d.latest_revision_date = d.time

        if d.type_id == "draft":
            state_slug = d.get_state_slug()
            if state_slug == "rfc":
                d.search_heading = "RFC"
                d.expirable = False
            elif state_slug in ("ietf-rm", "auth-rm"):
                d.search_heading = "Withdrawn Internet-Draft"
                d.expirable = False
            else:
                if d.type_id == "draft" and d.stream_id == 'ietf' and d.get_state_slug('draft-iesg') != 'idexists': # values can be: ad-eval idexists approved rfcqueue dead iesg-eva
                    d.search_heading = "%s with the IESG Internet-Draft" % d.get_state()
                else:
                    d.search_heading = "%s Internet-Draft" % d.get_state()
                if state_slug == "active":
                    d.expirable = d.pk in expirable_pks
                else:
                    d.expirable = False
        else:
            d.search_heading = "%s" % (d.type,)
            d.expirable = False

        if d.type_id == "draft" and d.get_state_slug() != "rfc":
            # m.state_id is the state slug; reading m.state.slug instead costs a query
            # per milestone because the prefetch does not cover it.
            d.milestones = [ m for (t, s, v, m) in sorted(((m.time, m.state_id, m.desc, m) for m in d.groupmilestone_set.all() if m.state_id == "active")) ]
            d.review_assignments = review_assignments.get(d.name, [])

        e = d.latest_event_cache.get('started_iesg_process', None)
        d.balloting_started = e.time if e else datetime.datetime.min

    # RFCs

    # errata
    erratas = set(Document.objects.filter(tags="errata", id__in=list(rfcs.keys())).distinct().values_list("name", flat=True))
    verified_erratas = set(Document.objects.filter(tags="verified-errata", id__in=list(rfcs.keys())).distinct().values_list("name", flat=True))
    for d in docs:
        d.has_errata = d.name in erratas
        d.has_verified_errata = d.name in verified_erratas

    # obsoleted/updated by
    for rfc in rfcs:
        d = doc_dict[rfc]
        d.obsoleted_by_list = []
        d.updated_by_list = []

    # Revisit this block after RFCs become first-class Document objects
    xed_by = list(
        RelatedDocument.objects.filter(
            target__name__in=list(rfcs.values()),
            relationship__in=("obs", "updates"),
        ).select_related("target", "source")
    )
    # TODO - this likely reduces to something even simpler
    rel_rfcs = {
        d.id: re.sub(r"rfc(\d+)", r"RFC \1", d.name, flags=re.IGNORECASE)
        for d in Document.objects.filter(
            type_id="rfc", id__in=[rel.source_id for rel in xed_by]
        )
    }
    xed_by.sort(
        key=lambda rel: int(
            re.sub(
                r"rfc\s*(\d+)",
                r"\1",
                rel_rfcs[rel.source_id],
                flags=re.IGNORECASE,
            )
        )
    )
    for rel in xed_by:
        d = doc_dict[rel.target.id]
        if rel.relationship_id == "obs":
            d.obsoleted_by_list.append(rel.source)
        elif rel.relationship_id == "updates":
            d.updated_by_list.append(rel.source)

def augment_docs_with_related_docs_info(docs):
    """Augment all documents with related documents information.
    At first, it handles only conflict review document page count to mirror the original document page count."""

    for d in docs:
        if d.type_id == 'conflrev':
            if len(d.related_that_doc('conflrev')) != 1:
                continue
            originalDoc = d.related_that_doc('conflrev')[0]
            d.pages = originalDoc.pages

def prepare_document_table(request, docs, query=None, max_results=200, show_ad_and_shepherd=True):
    """Take a queryset of documents and a QueryDict with sorting info
    and return list of documents with attributes filled in for
    displaying a full table of information about the documents, plus
    dict with information about the columns."""

    if not isinstance(docs, list):
        # evaluate and fill in attribute results immediately to decrease
        # the number of queries
        # "type" is here because fill_in_document_table_attributes renders it into
        # search_heading for every non-draft row. "iprdocrel_set" is not: the table shows
        # doc.related_ipr, which is precomputed in fill_in_document_table_attributes and
        # never touches that relation.
        docs = docs.select_related("ad", "std_level", "intended_std_level", "group", "stream",
                                   "shepherd__person", "type", )
        docs = docs.prefetch_related("states__type", "tags", "groupmilestone_set__group", "reviewrequest_set__team",
                                     "ad__email_set", "documentactionholder_set__person__email_set")
        docs = docs[:max_results] # <- that is still a queryset, but with a LIMIT now
        docs = list(docs)
    else:
        docs = docs[:max_results]

    fill_in_document_table_attributes(docs)
    if request.user.is_authenticated and hasattr(request.user, "person"):
        augment_docs_and_person_with_person_info(docs, request.user.person)
    augment_docs_with_related_docs_info(docs)

    meta = {}

    sort_key = query and query.get('sort') or ""
    sort_reversed = sort_key.startswith("-")
    sort_key = sort_key.lstrip("-")

    # sort
    def generate_sort_key(d):
        def num(i):
            # sortable representation of number as string
            return ('%09d' % int(i))

        res = []

        rfc_num = num(d.rfc_number) if d.rfc_number else None

        if d.type_id == "draft":
            res.append(num(["Active", "Expired", "Replaced", "Withdrawn", "RFC"].index(d.search_heading.split()[0])))
            if "with the IESG" in d.search_heading:
                res.append("1")
            else:
                res.append("0")
        else:
            res.append(d.type_id);
            res.append("-");
            res.append(d.get_state_slug() or '');
            res.append("-");

        if sort_key == "title":
            res.append(d.title)
        elif sort_key == "date":
            res.append(str(d.latest_revision_date.astimezone(ZoneInfo(settings.TIME_ZONE))))
        elif sort_key == "status":
            if rfc_num is not None:
                res.append(rfc_num)
            else:
                res.append(num(d.get_state().order) if d.get_state() else None)
        elif sort_key == "ipr":
            res.append(len(d.ipr()))
        elif sort_key == "ad":
            if rfc_num is not None:
                res.append(rfc_num)
            elif d.get_state_slug() == "active":
                if d.get_state("draft-iesg"):
                    res.append(d.get_state("draft-iesg").order)
                else:
                    res.append(0)
        else:
            if rfc_num is not None:
                res.append(rfc_num)
            else:
                res.append(d.name)

        return res

    docs.sort(key=generate_sort_key, reverse=sort_reversed)

    # fill in a meta dict with some information for rendering the table
    if len(docs) == max_results:
        meta['max'] = max_results

    meta['headers'] = [{'title': 'Document', 'key': 'document'},
                       {'title': 'Title', 'key': 'title'},
                       {'title': 'Date', 'key': 'date'},
                       {'title': 'Status', 'key': 'status'},
                       {'title': 'IPR', 'key': 'ipr'}]
    if show_ad_and_shepherd:
        meta['headers'].append({'title': 'AD / Shepherd', 'key': 'ad'})
    meta['show_ad_and_shepherd'] = show_ad_and_shepherd

    if query and hasattr(query, "urlencode"):  # fed a Django QueryDict
        d = query.copy()
        for h in meta['headers']:
            if h['key'] == sort_key:
                h['sorted'] = True
                if sort_reversed:
                    h['direction'] = 'desc'
                    d["sort"] = h["key"]
                else:
                    h['direction'] = 'asc'
                    d["sort"] = "-" + h["key"]
            else:
                d["sort"] = h["key"]
            h["sort_url"] = "?" + d.urlencode()

    return (docs, meta)


# The document types and state slugs to include in the AD dashboard
# and AD doc list, in the order they should be shown.
#
# "rfc" is a custom subset of "draft" that we special-case in the code
# to break out these docs into a separate table.
#
AD_WORKLOAD = {
    "draft": [
        "pub-req",
        "ad-eval",
        "lc-req",
        "lc",
        "goaheadw",
        "writeupw",
        # "defer",  # probably not a useful state to show, since it's rare
        "iesg-eva",
        "approved",
        "ann",
    ],
    "rfc": [
        "rfcqueue",
        "rfc",
    ],
    "conflrev": [
        "needshep",
        "adrev",
        "iesgeval",
        "approved",  # synthesized state for all the "appr-" states
        # "withdraw",  # probably not a useful state to show
    ],
    "statchg": [
        "needshep",
        "adrev",
        "lc-req",
        "in-lc",
        "iesgeval",
        "goahead",
        "appr-sent",
        # "dead",  # probably not a useful state to show
    ],
    "charter": [
        "notrev",
        "infrev",
        "intrev",
        "extrev",
        "iesgrev",
        "approved",
        # "replaced",  # probably not a useful state to show
    ],
}


def doc_type(doc):
    dt = doc.type.slug
    if (
        doc.get_state_slug("draft") == "rfc"
        or doc.get_state_slug("draft-iesg") == "rfcqueue"
    ):
        dt = "rfc"
    return dt


def doc_state(doc):
    dt = doc.type.slug
    ds = doc.get_state(dt)
    if dt == "draft":
        dis = doc.get_state("draft-iesg")
        if ds.slug == "active" and dis:
            return dis.slug
    elif dt == "conflrev":
        if ds.slug.startswith("appr"):
            return "approved"
    return ds.slug


def doc_type_name(doc_type):
    if doc_type == "rfc":
        return "RFC"
    if doc_type == "draft":
        return "Internet-Draft"
    return DocTypeName.objects.get(slug=doc_type).name
