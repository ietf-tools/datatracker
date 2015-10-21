# Copyright (C) 2009-2010 Nokia Corporation and/or its subsidiary(-ies).
# All rights reserved. Contact: Pasi Eronen <pasi.eronen@nokia.com>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#
#  * Redistributions in binary form must reproduce the above
#    copyright notice, this list of conditions and the following
#    disclaimer in the documentation and/or other materials provided
#    with the distribution.
#
#  * Neither the name of the Nokia Corporation and/or its
#    subsidiary(-ies) nor the names of its contributors may be used
#    to endorse or promote products derived from this software
#    without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import datetime, re

from django import forms
from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse as urlreverse
from django.shortcuts import render
from django.db.models import Q
from django.http import Http404, HttpResponseBadRequest, HttpResponse, HttpResponseRedirect

import debug                            # pyflakes:ignore

from ietf.community.models import CommunityList
from ietf.doc.models import ( Document, DocHistory, DocAlias, State, RelatedDocument,
    DocEvent, LastCallDocEvent, TelechatDocEvent, IESG_SUBSTATE_TAGS )
from ietf.doc.expire import expirable_draft
from ietf.doc.fields import select2_id_doc_name_json
from ietf.group.models import Group
from ietf.idindex.index import active_drafts_index_by_group
from ietf.name.models import DocTagName, DocTypeName, StreamName
from ietf.person.models import Person
from ietf.utils.draft_search import normalize_draftname


class SearchForm(forms.Form):
    name = forms.CharField(required=False)
    rfcs = forms.BooleanField(required=False, initial=True)
    activedrafts = forms.BooleanField(required=False, initial=True)
    olddrafts = forms.BooleanField(required=False, initial=False)

    by = forms.ChoiceField(choices=[(x,x) for x in ('author','group','area','ad','state','stream')], required=False, initial='wg')
    author = forms.CharField(required=False)
    group = forms.CharField(required=False)
    stream = forms.ModelChoiceField(StreamName.objects.all().order_by('name'), empty_label="any stream", required=False)
    area = forms.ModelChoiceField(Group.objects.filter(type="area", state="active").order_by('name'), empty_label="any area", required=False)
    ad = forms.ChoiceField(choices=(), required=False)
    state = forms.ModelChoiceField(State.objects.filter(type="draft-iesg"), empty_label="any state", required=False)
    substate = forms.ChoiceField(choices=(), required=False)

    sort = forms.ChoiceField(choices=(("document", "Document"), ("title", "Title"), ("date", "Date"), ("status", "Status"), ("ipr", "Ipr"), ("ad", "AD")), required=False, widget=forms.HiddenInput)

    doctypes = DocTypeName.objects.exclude(slug='draft').order_by('name');

    def __init__(self, *args, **kwargs):
        super(SearchForm, self).__init__(*args, **kwargs)
        responsible = Document.objects.values_list('ad', flat=True).distinct()
        active_ads = list(Person.objects.filter(role__name="ad",
                                                role__group__type="area",
                                                role__group__state="active").distinct())
        inactive_ads = list(((Person.objects.filter(pk__in=responsible) | Person.objects.filter(role__name="pre-ad",
                                                                                              role__group__type="area",
                                                                                              role__group__state="active")).distinct())
                            .exclude(pk__in=[x.pk for x in active_ads]))
        extract_last_name = lambda x: x.name_parts()[3]
        active_ads.sort(key=extract_last_name)
        inactive_ads.sort(key=extract_last_name)

        self.fields['ad'].choices = [('', 'any AD')] + [(ad.pk, ad.plain_name()) for ad in active_ads] + [('', '------------------')] + [(ad.pk, ad.name) for ad in inactive_ads]
        self.fields['substate'].choices = [('', 'any substate'), ('0', 'no substate')] + [(n.slug, n.name) for n in DocTagName.objects.filter(slug__in=IESG_SUBSTATE_TAGS)]

    def clean_name(self):
        value = self.cleaned_data.get('name','')
        return normalize_draftname(value)

    def clean(self):
        q = self.cleaned_data
        # Reset query['by'] if needed
        if 'by' in q:
            for k in ('author', 'group', 'area', 'ad'):
                if q['by'] == k and not q.get(k):
                    q['by'] = None
            if q['by'] == 'state' and not (q.get("state") or q.get('substate')):
                q['by'] = None
        else:
            q['by'] = None
        # Reset other fields
        for k in ('author','group', 'area', 'ad'):
            if k != q['by']:
                q[k] = ""
        if q['by'] != 'state':
            q['state'] = q['substate'] = None
        return q

def wrap_value(v):
    return lambda: v

def fill_in_search_attributes(docs):
    # fill in some attributes for the search results to save some
    # hairy template code and avoid repeated SQL queries

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
            d.milestones = d.groupmilestone_set.filter(state="active").order_by("time").select_related("group")



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


def retrieve_search_results(form, all_types=False):

    """Takes a validated SearchForm and return the results."""
    if not form.is_valid():
        raise ValueError("SearchForm doesn't validate: %s" % form.errors)

    query = form.cleaned_data

    types=[];
    meta = {}

    if (query['activedrafts'] or query['olddrafts'] or query['rfcs']):
        types.append('draft')

    # Advanced document types are data-driven, so we need to read them from the
    # raw form.data field (and track their checked/unchecked state ourselves)
    meta['checked'] = {}
    alltypes = DocTypeName.objects.exclude(slug='draft').order_by('name');
    for doctype in alltypes:
        if form.data.__contains__('include-' + doctype.slug):
            types.append(doctype.slug)
            meta['checked'][doctype.slug] = True

    if len(types) == 0 and not all_types:
        return ([], {})

    MAX = 500

    if all_types:
        docs = Document.objects.all()
    else:
        docs = Document.objects.filter(type__in=types)

    # name
    if query["name"]:
        docs = docs.filter(Q(docalias__name__icontains=query["name"]) |
                           Q(title__icontains=query["name"])).distinct()

    # rfc/active/old check buttons
    allowed_draft_states = []
    if query["rfcs"]:
        allowed_draft_states.append("rfc")
    if query["activedrafts"]:
        allowed_draft_states.append("active")
    if query["olddrafts"]:
        allowed_draft_states.extend(['repl', 'expired', 'auth-rm', 'ietf-rm'])

    docs = docs.filter(Q(states__slug__in=allowed_draft_states) |
                       ~Q(type__slug='draft')).distinct()

    # radio choices
    by = query["by"]
    if by == "author":
        docs = docs.filter(authors__person__name__icontains=query["author"])
    elif by == "group":
        docs = docs.filter(group__acronym=query["group"])
    elif by == "area":
        docs = docs.filter(Q(group__type="wg", group__parent=query["area"]) |
                           Q(group=query["area"])).distinct()
    elif by == "ad":
        docs = docs.filter(ad=query["ad"])
    elif by == "state":
        if query["state"]:
            docs = docs.filter(states=query["state"])
        if query["substate"]:
            docs = docs.filter(tags=query["substate"])
    elif by == "stream":
        docs = docs.filter(stream=query["stream"])

    # evaluate and fill in attribute results immediately to cut down
    # the number of queries
    docs = docs.select_related("ad", "ad__person", "std_level", "intended_std_level", "group", "stream")
    docs = docs.prefetch_related("states__type", "tags")
    results = list(docs[:MAX])

    fill_in_search_attributes(results)

    # sort
    def sort_key(d):
        res = []

        rfc_num = d.rfc_number()


        if d.type_id == "draft":
            res.append(["Active", "Expired", "Replaced", "Withdrawn", "RFC"].index(d.search_heading.split()[0] ))
        else:
            res.append(d.type_id);
            res.append("-");
            res.append(d.get_state_slug());
            res.append("-");

        if query["sort"] == "title":
            res.append(d.title)
        elif query["sort"] == "date":
            res.append(str(d.latest_revision_date))
        elif query["sort"] == "status":
            if rfc_num != None:
                res.append(int(rfc_num))
            else:
                res.append(d.get_state().order if d.get_state() else None)
        elif query["sort"] == "ipr":
            res.append(len(d.ipr()))
        elif query["sort"] == "ad":
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

    results.sort(key=sort_key)

    # fill in a meta dict with some information for rendering the result table
    if len(results) == MAX:
        meta['max'] = MAX
    meta['by'] = query['by']
    meta['advanced'] = bool(query['by'] or len(meta['checked']))

    meta['headers'] = [{'title': 'Document', 'key':'document'},
                       {'title': 'Title', 'key':'title'},
                       {'title': 'Date', 'key':'date'},
                       {'title': 'Status', 'key':'status'},
                       {'title': 'IPR', 'key':'ipr'},
                       {'title': 'AD / Shepherd', 'key':'ad'}]

    if hasattr(form.data, "urlencode"): # form was fed a Django QueryDict, not local plain dict
        d = form.data.copy()
        for h in meta['headers']:
            d["sort"] = h["key"]
            h["sort_url"] = "?" + d.urlencode()
            if h['key'] == query.get('sort'):
                h['sorted'] = True
    return (results, meta)


def get_doc_is_tracked(request, results):
    # Determine whether each document is being tracked or not, and remember
    # that so we can display the proper track/untrack option.
    doc_is_tracked = { }
    if request.user.is_authenticated():
        try:
            clist = CommunityList.objects.get(user=request.user)
            clist.update()
        except ObjectDoesNotExist:
            return doc_is_tracked
        for doc in results:
            if clist.get_documents().filter(name=doc.name).count() > 0:
                doc_is_tracked[doc.name] = True
    return doc_is_tracked

def search(request):
    if request.GET:
        # backwards compatibility
        get_params = request.GET.copy()
        if 'activeDrafts' in request.GET:
            get_params['activedrafts'] = request.GET['activeDrafts']
        if 'oldDrafts' in request.GET:
            get_params['olddrafts'] = request.GET['oldDrafts']
        if 'subState' in request.GET:
            get_params['substate'] = request.GET['subState']

        form = SearchForm(get_params)
        if not form.is_valid():
            return HttpResponseBadRequest("form not valid: %s" % form.errors)

        results, meta = retrieve_search_results(form)
        meta['searching'] = True
    else:
        form = SearchForm()
        results = []
        meta = { 'by': None, 'advanced': False, 'searching': False }

    doc_is_tracked = get_doc_is_tracked(request, results)

    return render(request, 'doc/search/search.html', {
        'form':form, 'docs':results, 'doc_is_tracked':doc_is_tracked, 'meta':meta, },
    )

def frontpage(request):
    form = SearchForm()
    return render(request, 'doc/frontpage.html', {'form':form})

def search_for_name(request, name):
    def find_unique(n):
        exact = DocAlias.objects.filter(name=n).first()
        if exact:
            return exact.name

        aliases = DocAlias.objects.filter(name__startswith=n)[:2]
        if len(aliases) == 1:
            return aliases[0].name

        aliases = DocAlias.objects.filter(name__contains=n)[:2]
        if len(aliases) == 1:
            return aliases[0].name

        return None

    n = name

    # chop away extension
    extension_split = re.search("^(.+)\.(txt|ps|pdf)$", n)
    if extension_split:
        n = extension_split.group(1)

    redirect_to = find_unique(name)
    if redirect_to:
        return HttpResponseRedirect(urlreverse("doc_view", kwargs={ "name": redirect_to }))
    else:
        # check for embedded rev - this may be ambigious, so don't
        # chop it off if we don't find a match
        rev_split = re.search("^(.+)-([0-9]{2})$", n)
        if rev_split:
            redirect_to = find_unique(rev_split.group(1))
            if redirect_to:
                rev = rev_split.group(2)
                # check if we can redirect directly to the rev
                if DocHistory.objects.filter(doc__docalias__name=redirect_to, rev=rev).exists():
                    return HttpResponseRedirect(urlreverse("doc_view", kwargs={ "name": redirect_to, "rev": rev }))
                else:
                    return HttpResponseRedirect(urlreverse("doc_view", kwargs={ "name": redirect_to }))

    # build appropriate flags based on string prefix
    doctypenames = DocTypeName.objects.filter(used=True)
    # This would have been more straightforward if document prefixes couldn't
    # contain a dash.  Probably, document prefixes shouldn't contain a dash ...
    search_args = "?name=%s" % n
    if   n.startswith("draft"):
        search_args += "&rfcs=on&activedrafts=on&olddrafts=on"
    else:
        for t in doctypenames:
            if n.startswith(t.prefix):
                search_args += "&include-%s=on" % t.slug
                break
        else:
            search_args += "&rfcs=on&activedrafts=on&olddrafts=on"

    return HttpResponseRedirect(urlreverse("doc_search") + search_args)

def ad_dashboard_group(doc):

    if doc.type.slug=='draft':
        if doc.get_state_slug('draft') == 'rfc':
            return 'RFC'
        elif doc.get_state_slug('draft') == 'active' and doc.get_state_slug('draft-iesg'):
            return '%s Internet-Draft' % doc.get_state('draft-iesg').name
        else:
            return '%s Internet-Draft' % doc.get_state('draft').name
    elif doc.type.slug=='conflrev':
        if doc.get_state_slug('conflrev') in ('appr-reqnopub-sent','appr-noprob-sent'):
            return 'Approved Conflict Review'
        elif doc.get_state_slug('conflrev') in ('appr-reqnopub-pend','appr-noprob-pend','appr-reqnopub-pr','appr-noprob-pr'):
            return "%s Conflict Review" % State.objects.get(type__slug='draft-iesg',slug='approved')
        else:
          return '%s Conflict Review' % doc.get_state('conflrev')
    elif doc.type.slug=='statchg':
        if doc.get_state_slug('statchg') in ('appr-sent',):
            return 'Approved Status Change'
        if doc.get_state_slug('statchg') in ('appr-pend','appr-pr'):
            return '%s Status Change' % State.objects.get(type__slug='draft-iesg',slug='approved')
        else:
            return '%s Status Change' % doc.get_state('statchg')
    elif doc.type.slug=='charter':
        if doc.get_state_slug('charter') == 'approved':
            return "Approved Charter"
        else:
            return '%s Charter' % doc.get_state('charter')
    else:
        return "Document"

def ad_dashboard_sort_key(doc):

    if doc.type.slug=='draft' and doc.get_state_slug('draft') == 'rfc':
        return "21%04d" % int(doc.rfc_number())
    if doc.type.slug=='statchg' and doc.get_state_slug('statchg') == 'appr-sent':
        return "22%d" % 0 # TODO - get the date of the transition into this state here
    if doc.type.slug=='conflrev' and doc.get_state_slug('conflrev') in ('appr-reqnopub-sent','appr-noprob-sent'):
        return "23%d" % 0 # TODO - get the date of the transition into this state here
    if doc.type.slug=='charter' and doc.get_state_slug('charter') == 'approved':
        return "24%d" % 0 # TODO - get the date of the transition into this state here

    seed = ad_dashboard_group(doc)

    if doc.type.slug=='conflrev' and doc.get_state_slug('conflrev') == 'adrev':
        state = State.objects.get(type__slug='draft-iesg',slug='ad-eval')
        return "1%d%s" % (state.order,seed)

    if doc.type.slug=='charter':
        if doc.get_state_slug('charter') in ('notrev','infrev'):
            return "100%s" % seed
        elif  doc.get_state_slug('charter') == 'intrev':
            state = State.objects.get(type__slug='draft-iesg',slug='ad-eval')
            return "1%d%s" % (state.order,seed)
        elif  doc.get_state_slug('charter') == 'extrev':
            state = State.objects.get(type__slug='draft-iesg',slug='lc')
            return "1%d%s" % (state.order,seed)
        elif  doc.get_state_slug('charter') == 'iesgrev':
            state = State.objects.get(type__slug='draft-iesg',slug='iesg-eva')
            return "1%d%s" % (state.order,seed)

    if doc.type.slug=='statchg' and  doc.get_state_slug('statchg') == 'adrev':
        state = State.objects.get(type__slug='draft-iesg',slug='ad-eval')
        return "1%d%s" % (state.order,seed)

    if seed.startswith('Needs Shepherd'):
        return "100%s" % seed
    if seed.endswith(' Document'):
        seed = seed[:-9]
    elif seed.endswith(' Internet-Draft'):
        seed = seed[:-15]
    elif seed.endswith(' Conflict Review'):
        seed = seed[:-16]
    elif seed.endswith(' Status Change'):
        seed = seed[:-14]
    state = State.objects.filter(type__slug='draft-iesg',name=seed)
    if state:
        ageseconds = 0
        changetime= doc.latest_event(type='changed_document')
        if changetime:
            ad = (datetime.datetime.now()-doc.latest_event(type='changed_document').time)
            ageseconds = (ad.microseconds + (ad.seconds + ad.days * 24 * 3600) * 10**6) / 10**6
        return "1%d%s%s%010d" % (state[0].order,seed,doc.type.slug,ageseconds)

    return "3%s" % seed

def docs_for_ad(request, name):
    ad = None
    responsible = Document.objects.values_list('ad', flat=True).distinct()
    for p in Person.objects.filter(Q(role__name__in=("pre-ad", "ad"),
                                     role__group__type="area",
                                     role__group__state="active")
                                   | Q(pk__in=responsible)).distinct():
        if name == p.full_name_as_key():
            ad = p
            break
    if not ad:
        raise Http404
    form = SearchForm({'by':'ad','ad': ad.id,
                       'rfcs':'on', 'activedrafts':'on', 'olddrafts':'on',
                       'sort': 'status'})
    results, meta = retrieve_search_results(form, all_types=True)
    results.sort(key=ad_dashboard_sort_key)
    del meta["headers"][-1]
    #
    for d in results:
        d.search_heading = ad_dashboard_group(d)
    #
    return render(request, 'doc/drafts_for_ad.html', {
        'form':form, 'docs':results, 'meta':meta, 'ad_name': ad.plain_name()
    })

def drafts_in_last_call(request):
    lc_state = State.objects.get(type="draft-iesg", slug="lc").pk
    form = SearchForm({'by':'state','state': lc_state, 'rfcs':'on', 'activedrafts':'on'})
    results, meta = retrieve_search_results(form)

    return render(request, 'doc/drafts_in_last_call.html', {
        'form':form, 'docs':results, 'meta':meta
    })

def drafts_in_iesg_process(request, last_call_only=None):
    if last_call_only:
        states = State.objects.filter(type="draft-iesg", slug__in=("lc", "writeupw", "goaheadw"))
        title = "Documents in Last Call"
    else:
        states = State.objects.filter(type="draft-iesg").exclude(slug__in=('pub', 'dead', 'watching', 'rfcqueue'))
        title = "Documents in IESG process"

    grouped_docs = []

    for s in states.order_by("order"):
        docs = Document.objects.filter(type="draft", states=s).distinct().order_by("time").select_related("ad", "group", "group__parent")
        if docs:
            if s.slug == "lc":
                for d in docs:
                    e = d.latest_event(LastCallDocEvent, type="sent_last_call")
                    d.lc_expires = e.expires if e else datetime.datetime.min
                docs = list(docs)
                docs.sort(key=lambda d: d.lc_expires)

            grouped_docs.append((s, docs))

    return render(request, 'doc/drafts_in_iesg_process.html', {
            "grouped_docs": grouped_docs,
            "title": title,
            "last_call_only": last_call_only,
            })

def index_all_drafts(request):
    # try to be efficient since this view returns a lot of data
    categories = []

    for s in ("active", "rfc", "expired", "repl", "auth-rm", "ietf-rm"):
        state = State.objects.get(type="draft", slug=s)

        if state.slug == "rfc":
            heading = "RFCs"
        elif state.slug in ("ietf-rm", "auth-rm"):
            heading = "Internet-Drafts %s" % state.name
        else:
            heading = "%s Internet-Drafts" % state.name

        draft_names = DocAlias.objects.filter(document__states=state).values_list("name", "document")

        names = []
        names_to_skip = set()
        for name, doc in draft_names:
            sort_key = name
            if name != doc:
                if not name.startswith("rfc"):
                    name, doc = doc, name
                names_to_skip.add(doc)

            if name.startswith("rfc"):
                name = name.upper()
                sort_key = -int(name[3:])

            names.append((name, sort_key))

        names.sort(key=lambda t: t[1])

        names = ['<a href="/doc/' + n + '/">' + n +'</a>'
                 for n, __ in names if n not in names_to_skip]

        categories.append((state,
                      heading,
                      len(names),
                      "<br>".join(names)
                      ))
    return render(request, 'doc/index_all_drafts.html', { "categories": categories })

def index_active_drafts(request):
    groups = active_drafts_index_by_group()

    return render(request, "doc/index_active_drafts.html", { 'groups': groups })

def ajax_select2_search_docs(request, model_name, doc_type):
    if model_name == "docalias":
        model = DocAlias
    else:
        model = Document

    q = [w.strip() for w in request.GET.get('q', '').split() if w.strip()]

    if not q:
        objs = model.objects.none()
    else:
        qs = model.objects.all()

        if model == Document:
            qs = qs.filter(type=doc_type)
        elif model == DocAlias:
            qs = qs.filter(document__type=doc_type)

        for t in q:
            qs = qs.filter(name__icontains=t)

        objs = qs.distinct().order_by("name")[:20]

    return HttpResponse(select2_id_doc_name_json(objs), content_type='application/json')
