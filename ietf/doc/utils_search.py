# Copyright The IETF Trust 2016-2020, All Rights Reserved
# -*- coding: utf-8 -*-

import re
import datetime
import debug                            # pyflakes:ignore

from zoneinfo import ZoneInfo

from django.conf import settings

from ietf.doc.models import Document, RelatedDocument, DocEvent, TelechatDocEvent, BallotDocEvent, DocTypeName
from ietf.doc.expire import expirable_drafts
from ietf.doc.utils import augment_docs_and_person_with_person_info
from ietf.meeting.models import SessionPresentation, Meeting, Session
from ietf.review.utils import review_assignments_to_list_for_docs
from ietf.utils.timezone import date_today


def wrap_value(v):
    return lambda: v


def fill_in_telechat_date(docs, doc_dict=None, doc_ids=None):
    if doc_dict is None:
        doc_dict = dict((d.pk, d) for d in docs)
        doc_ids = list(doc_dict.keys())
    if doc_ids is None:
        doc_ids = list(doc_dict.keys())

    seen = set()
    for e in TelechatDocEvent.objects.filter(doc__id__in=doc_ids, type="scheduled_for_telechat").order_by('-time'):
        if e.doc_id not in seen:
            #d = doc_dict[e.doc_id]
            #d.telechat_date = wrap_value(d.telechat_date(e))
            seen.add(e.doc_id)

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

    for e in DocEvent.objects.filter(doc__id__in=doc_ids, type__in=event_types).order_by('time'):
        doc_dict[e.doc_id].latest_event_cache[e.type] = e

    seen = set()
    for e in BallotDocEvent.objects.filter(doc__id__in=doc_ids, type__in=('created_ballot', 'closed_ballot')).order_by('-time','-id'):
        if not e.doc_id in seen:
            doc_dict[e.doc_id].ballot = e if e.type == 'created_ballot' else None
            seen.add(e.doc_id)

    if not have_telechat_date:
        fill_in_telechat_date(docs, doc_dict, doc_ids)

    # on agenda in upcoming meetings
    # get meetings
    fill_in_document_sessions(docs, doc_dict, doc_ids)

    # misc
    expirable_pks = expirable_drafts(Document.objects.filter(pk__in=doc_ids)).values_list('pk', flat=True)
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
                d.search_heading = "%s Internet-Draft" % d.get_state()
                if state_slug == "active":
                    d.expirable = d.pk in expirable_pks
                else:
                    d.expirable = False
        else:
            d.search_heading = "%s" % (d.type,)
            d.expirable = False

        if d.type_id == "draft" and d.get_state_slug() != "rfc":
            d.milestones = [ m for (t, s, v, m) in sorted(((m.time, m.state.slug, m.desc, m) for m in d.groupmilestone_set.all() if m.state_id == "active")) ]
            d.review_assignments = review_assignments_to_list_for_docs([d]).get(d.name, [])

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
        ).select_related("target")
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
        docs = docs.select_related("ad", "std_level", "intended_std_level", "group", "stream", "shepherd", )
        docs = docs.prefetch_related("states__type", "tags", "groupmilestone_set__group", "reviewrequest_set__team",
                                     "ad__email_set", "iprdocrel_set")
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
