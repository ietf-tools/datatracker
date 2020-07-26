# Copyright The IETF Trust 2016-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime
import debug                            # pyflakes:ignore

from ietf.doc.models import Document, DocAlias, RelatedDocument, DocEvent, TelechatDocEvent, BallotDocEvent
from ietf.doc.expire import expirable_draft
from ietf.doc.utils import augment_docs_and_user_with_user_info
from ietf.meeting.models import SessionPresentation, Meeting, Session

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
            d = doc_dict[e.doc_id]
            d.telechat_date = wrap_value(d.telechat_date(e))
            seen.add(e.doc_id)

def fill_in_document_sessions(docs, doc_dict, doc_ids):
    beg_date = datetime.date.today()-datetime.timedelta(days=7)
    end_date = datetime.date.today()+datetime.timedelta(days=30)
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
    # TODO - this function evolved from something that assumed it was handling only drafts. It still has places where it assumes all docs are drafts where that is not a correct assumption

    doc_dict = dict((d.pk, d) for d in docs)
    doc_ids = list(doc_dict.keys())

    rfc_aliases = dict([ (a.document.id, a.name) for a in DocAlias.objects.filter(name__startswith="rfc", docs__id__in=doc_ids) ])

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
    for d in docs:
        # emulate canonical name which is used by a lot of the utils
        d.canonical_name = wrap_value(rfc_aliases[d.pk] if d.pk in rfc_aliases else d.name)

        if d.rfc_number() != None and d.latest_event_cache["published_rfc"]:
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
                    d.expirable = expirable_draft(d)
                else:
                    d.expirable = False
        else:
            d.search_heading = "%s" % (d.type,)
            d.expirable = False

        if d.get_state_slug() != "rfc":
            d.milestones = [ m for (t, s, v, m) in sorted(((m.time, m.state.slug, m.desc, m) for m in d.groupmilestone_set.all() if m.state_id == "active")) ]
            d.reviewed_by_teams = sorted(set(r.team.acronym for r in d.reviewrequest_set.filter(state__in=["assigned","accepted","part-completed","completed"]).distinct().select_related('team')))

        e = d.latest_event_cache.get('started_iesg_process', None)
        d.balloting_started = e.time if e else datetime.datetime.min

    # RFCs

    # errata
    erratas = set(Document.objects.filter(tags="errata", id__in=list(rfc_aliases.keys())).distinct().values_list("name", flat=True))
    verified_erratas = set(Document.objects.filter(tags="verified-errata", id__in=list(rfc_aliases.keys())).distinct().values_list("name", flat=True))
    for d in docs:
        d.has_errata = d.name in erratas
        d.has_verified_errata = d.name in verified_erratas

    # obsoleted/updated by
    for a in rfc_aliases:
        d = doc_dict[a]
        d.obsoleted_by_list = []
        d.updated_by_list = []

    xed_by = RelatedDocument.objects.filter(target__name__in=list(rfc_aliases.values()),
                                            relationship__in=("obs", "updates")).select_related('target')
    rel_rfc_aliases = dict([ (a.document.id, a.name) for a in DocAlias.objects.filter(name__startswith="rfc", docs__id__in=[rel.source_id for rel in xed_by]) ])
    for rel in xed_by:
        d = doc_dict[rel.target.document.id]
        if rel.relationship_id == "obs":
            l = d.obsoleted_by_list
        elif rel.relationship_id == "updates":
            l = d.updated_by_list
        l.append(rel_rfc_aliases[rel.source_id].upper())
        l.sort()


def prepare_document_table(request, docs, query=None, max_results=200):
    """Take a queryset of documents and a QueryDict with sorting info
    and return list of documents with attributes filled in for
    displaying a full table of information about the documents, plus
    dict with information about the columns."""

    if docs.count() > max_results:
        docs = docs[:max_results]

    if not isinstance(docs, list):
        # evaluate and fill in attribute results immediately to decrease
        # the number of queries
        docs = docs.select_related("ad", "std_level", "intended_std_level", "group", "stream", "shepherd", )
        docs = docs.prefetch_related("states__type", "tags", "groupmilestone_set__group", "reviewrequest_set__team",
                                     "submission_set__checks", "ad__email_set", "docalias__iprdocrel_set")
        docs = list(docs)

    fill_in_document_table_attributes(docs)
    augment_docs_and_user_with_user_info(docs, request.user)

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

        rfc_num = d.rfc_number()

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
            res.append(str(d.latest_revision_date))
        elif sort_key == "status":
            if rfc_num != None:
                res.append(num(rfc_num))
            else:
                res.append(num(d.get_state().order) if d.get_state() else None)
        elif sort_key == "ipr":
            res.append(len(d.ipr()))
        elif sort_key == "ad":
            if rfc_num != None:
                res.append(num(rfc_num))
            elif d.get_state_slug() == "active":
                if d.get_state("draft-iesg"):
                    res.append(d.get_state("draft-iesg").order)
                else:
                    res.append(0)
        else:
            if rfc_num != None:
                res.append(num(rfc_num))
            else:
                res.append(d.canonical_name())

        return res

    docs.sort(key=generate_sort_key, reverse=sort_reversed)

    # fill in a meta dict with some information for rendering the table
    if len(docs) == max_results:
        meta['max'] = max_results

    meta['headers'] = [{'title': 'Document', 'key':'document'},
                       {'title': 'Title', 'key':'title'},
                       {'title': 'Date', 'key':'date'},
                       {'title': 'Status', 'key':'status'},
                       {'title': 'IPR', 'key':'ipr'},
                       {'title': 'AD / Shepherd', 'key':'ad'}]

    if query and hasattr(query, "urlencode"):  # fed a Django QueryDict
        d = query.copy()
        for h in meta['headers']:
            h["sort_url"] = "?" + d.urlencode()
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

    return (docs, meta)


