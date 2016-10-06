from ietf.doc.models import Document, DocAlias, RelatedDocument, DocEvent, TelechatDocEvent
from ietf.doc.expire import expirable_draft
from ietf.community.utils import augment_docs_with_tracking_info

def wrap_value(v):
    return lambda: v

def fill_in_document_table_attributes(docs):
    # fill in some attributes for the document table results to save
    # some hairy template code and avoid repeated SQL queries

    docs_dict = dict((d.pk, d) for d in docs)
    doc_ids = docs_dict.keys()

    rfc_aliases = dict(DocAlias.objects.filter(name__startswith="rfc", document__in=doc_ids).values_list("document_id", "name"))

    # latest event cache
    event_types = ("published_rfc",
                   "changed_ballot_position",
                   "started_iesg_process",
                   "new_revision")
    for d in docs:
        d.latest_event_cache = dict()
        for e in event_types:
            d.latest_event_cache[e] = None

    for e in DocEvent.objects.filter(doc__in=doc_ids, type__in=event_types).order_by('time'):
        docs_dict[e.doc_id].latest_event_cache[e.type] = e

    # telechat date, can't do this with above query as we need to get TelechatDocEvents out
    seen = set()
    for e in TelechatDocEvent.objects.filter(doc__in=doc_ids, type="scheduled_for_telechat").order_by('-time'):
        if e.doc_id not in seen:
            d = docs_dict[e.doc_id]
            d.telechat_date = wrap_value(d.telechat_date(e))
            seen.add(e.doc_id)

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
            if d.get_state_slug() == "rfc":
                d.search_heading = "RFC"
            elif d.get_state_slug() in ("ietf-rm", "auth-rm"):
                d.search_heading = "Withdrawn Internet-Draft"
            else:
                d.search_heading = "%s Internet-Draft" % d.get_state()
        else:
            d.search_heading = "%s" % (d.type,);

        d.expirable = expirable_draft(d)

        if d.get_state_slug() != "rfc":
            d.milestones = sorted((m for m in d.groupmilestone_set.all() if m.state_id == "active"), key=lambda m: m.time)

            d.reviewed_by_teams = sorted(set(r.team for r in d.reviewrequest_set.all()), key=lambda g: g.acronym)


    # RFCs

    # errata
    erratas = set(Document.objects.filter(tags="errata", name__in=rfc_aliases.keys()).distinct().values_list("name", flat=True))
    for d in docs:
        d.has_errata = d.name in erratas

    # obsoleted/updated by
    for a in rfc_aliases:
        d = docs_dict[a]
        d.obsoleted_by_list = []
        d.updated_by_list = []

    xed_by = RelatedDocument.objects.filter(target__name__in=rfc_aliases.values(),
                                            relationship__in=("obs", "updates")).select_related('target__document_id')
    rel_rfc_aliases = dict(DocAlias.objects.filter(name__startswith="rfc",
                                                   document__in=[rel.source_id for rel in xed_by]).values_list('document_id', 'name'))
    for rel in xed_by:
        d = docs_dict[rel.target.document_id]
        if rel.relationship_id == "obs":
            l = d.obsoleted_by_list
        elif rel.relationship_id == "updates":
            l = d.updated_by_list
        l.append(rel_rfc_aliases[rel.source_id].upper())
        l.sort()


def prepare_document_table(request, docs, query=None, max_results=500):
    """Take a queryset of documents and a QueryDict with sorting info
    and return list of documents with attributes filled in for
    displaying a full table of information about the documents, plus
    dict with information about the columns."""

    if not isinstance(docs, list):
        # evaluate and fill in attribute results immediately to decrease
        # the number of queries
        docs = docs.select_related("ad", "ad__person", "std_level", "intended_std_level", "group", "stream")
        docs = docs.prefetch_related("states__type", "tags", "groupmilestone_set__group", "reviewrequest_set__team")

    docs = list(docs[:max_results])

    fill_in_document_table_attributes(docs)
    augment_docs_with_tracking_info(docs, request.user)

    meta = {}

    sort_key = query and query.get('sort') or ""
    sort_reversed = sort_key.startswith("-")
    sort_key = sort_key.lstrip("-")

    # sort
    def generate_sort_key(d):
        res = []

        rfc_num = d.rfc_number()


        if d.type_id == "draft":
            res.append(["Active", "Expired", "Replaced", "Withdrawn", "RFC"].index(d.search_heading.split()[0]))
        else:
            res.append(d.type_id);
            res.append("-");
            res.append(d.get_state_slug());
            res.append("-");

        if sort_key == "title":
            res.append(d.title)
        elif sort_key == "date":
            res.append(str(d.latest_revision_date))
        elif sort_key == "status":
            if rfc_num != None:
                res.append(int(rfc_num))
            else:
                res.append(d.get_state().order if d.get_state() else None)
        elif sort_key == "ipr":
            res.append(len(d.ipr()))
        elif sort_key == "ad":
            if rfc_num != None:
                res.append(int(rfc_num))
            elif d.get_state_slug() == "active":
                if d.get_state("draft-iesg"):
                    res.append(d.get_state("draft-iesg").order)
                else:
                    res.append(0)
        else:
            if rfc_num != None:
                res.append(int(rfc_num))
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


