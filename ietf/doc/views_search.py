# Copyright The IETF Trust 2009-2023, All Rights Reserved
# -*- coding: utf-8 -*-
#
# Some parts Copyright (C) 2009-2010 Nokia Corporation and/or its subsidiary(-ies).
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

import hashlib
import json
import re
import datetime
import copy
import operator

from collections import defaultdict
from functools import reduce

from django import forms
from django.conf import settings
from django.core.cache import cache, caches
from django.urls import reverse as urlreverse
from django.db.models import Q
from django.http import Http404, HttpResponseBadRequest, HttpResponse, HttpResponseRedirect, QueryDict
from django.shortcuts import render
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.cache import _generate_cache_key # type: ignore
from django.utils.text import slugify


import debug                            # pyflakes:ignore

from ietf.doc.models import ( Document, DocHistory, State,
    LastCallDocEvent, NewRevisionDocEvent, IESG_SUBSTATE_TAGS,
    IESG_BALLOT_ACTIVE_STATES, IESG_STATCHG_CONFLREV_ACTIVE_STATES,
    IESG_CHARTER_ACTIVE_STATES )
from ietf.doc.fields import select2_id_doc_name_json
from ietf.doc.utils import augment_events_with_revision, needed_ballot_positions
from ietf.group.models import Group
from ietf.idindex.index import active_drafts_index_by_group
from ietf.name.models import DocTagName, DocTypeName, StreamName
from ietf.person.models import Person
from ietf.person.utils import get_active_ads
from ietf.utils.draft_search import normalize_draftname
from ietf.utils.fields import ModelMultipleChoiceField
from ietf.utils.log import log
from ietf.doc.utils_search import prepare_document_table, doc_type, doc_state, doc_type_name, AD_WORKLOAD
from ietf.ietfauth.utils import has_role


class SearchForm(forms.Form):
    name = forms.CharField(required=False)
    rfcs = forms.BooleanField(required=False, initial=True)
    activedrafts = forms.BooleanField(required=False, initial=True)
    olddrafts = forms.BooleanField(required=False, initial=False)

    by = forms.ChoiceField(choices=[(x,x) for x in ('author','group','area','ad','state','irtfstate','stream')], required=False, initial='group')
    author = forms.CharField(required=False)
    group = forms.CharField(required=False)
    stream = forms.ModelChoiceField(StreamName.objects.all().order_by('name'), empty_label="any stream", required=False)
    area = forms.ModelChoiceField(Group.objects.filter(type="area", state="active").order_by('name'), empty_label="any area", required=False)
    ad = forms.ChoiceField(choices=(), required=False)
    state = forms.ModelChoiceField(State.objects.filter(type="draft-iesg"), empty_label="any state", required=False)
    substate = forms.ChoiceField(choices=(), required=False)
    irtfstate = forms.ModelChoiceField(State.objects.filter(type="draft-stream-irtf"), empty_label="any state", required=False)

    sort = forms.ChoiceField(
        choices= (
            ("document", "Document"), ("-document", "Document (desc.)"),
            ("title", "Title"), ("-title", "Title (desc.)"),
            ("date", "Date"), ("-date", "Date (desc.)"),
            ("status", "Status"), ("-status", "Status (desc.)"),
            ("ipr", "Ipr"), ("ipr", "Ipr (desc.)"),
            ("ad", "AD"), ("-ad", "AD (desc)"), ),
        required=False, widget=forms.HiddenInput)

    doctypes = ModelMultipleChoiceField(queryset=DocTypeName.objects.filter(used=True).exclude(slug__in=('draft', 'rfc', 'bcp', 'std', 'fyi', 'liai-att')).order_by('name'), required=False)

    def __init__(self, *args, **kwargs):
        super(SearchForm, self).__init__(*args, **kwargs)
        responsible = Document.objects.values_list('ad', flat=True).distinct()
        active_ads = get_active_ads()
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
            if q['by'] == 'state' and not (q.get('state') or q.get('substate')):
                q['by'] = None
            if q['by'] == 'irtfstate' and not (q.get('irtfstate')):
                q['by'] = None
        else:
            q['by'] = None
        # Reset other fields
        for k in ('author','group', 'area', 'ad'):
            if k != q['by']:
                q[k] = ""
        if q['by'] != 'state':
            q['state'] = q['substate'] = None
        if q['by'] != 'irtfstate':
            q['irtfstate'] = None
        return q

def retrieve_search_results(form, all_types=False):
    """Takes a validated SearchForm and return the results."""

    if not form.is_valid():
        raise ValueError("SearchForm doesn't validate: %s" % form.errors)

    query = form.cleaned_data

    if all_types:
        # order by time here to retain the most recent documents in case we
        # find too many and have to chop the results list
        docs = Document.objects.all().order_by('-time')
    else:
        types = []

        if query['activedrafts'] or query['olddrafts']:
            types.append('draft')
        
        if query['rfcs']:
            types.append('rfc')

        types.extend(query["doctypes"])

        if not types:
            return Document.objects.none()

        docs = Document.objects.filter(type__in=types)

    # name
    if query["name"]:
        look_for = query["name"]
        queries = [
            Q(name__icontains=look_for),
            Q(title__icontains=look_for)
        ]
        # Check to see if this is just a search for an rfc look for a few variants
        if look_for.lower()[:3] == "rfc" and look_for[3:].strip().isdigit():
            spaceless = look_for.lower()[:3]+look_for[3:].strip()
            if spaceless != look_for:
                queries.extend([
                    Q(name__icontains=spaceless),
                    Q(title__icontains=spaceless)            
                ])
            singlespace = look_for.lower()[:3]+" "+look_for[3:].strip()
            if singlespace != look_for:
                queries.extend([
                    Q(name__icontains=singlespace),
                    Q(title__icontains=singlespace)            
                ])        

        # Do a similar thing if the search is just for a subseries doc, like a bcp.
        if look_for.lower()[:3] in ["bcp", "fyi", "std"] and look_for[3:].strip().isdigit() and query["rfcs"]: # Also look for rfcs contained in the subseries.
            queries.extend([
                Q(targets_related__source__name__icontains=look_for, targets_related__relationship_id="contains"),
                Q(targets_related__source__title__icontains=look_for, targets_related__relationship_id="contains"),
            ])
            spaceless = look_for.lower()[:3]+look_for[3:].strip()
            if spaceless != look_for:
                queries.extend([
                    Q(targets_related__source__name__icontains=spaceless, targets_related__relationship_id="contains"),
                    Q(targets_related__source__title__icontains=spaceless, targets_related__relationship_id="contains"),
                ])
            singlespace = look_for.lower()[:3]+" "+look_for[3:].strip()
            if singlespace != look_for:
                queries.extend([
                    Q(targets_related__source__name__icontains=singlespace, targets_related__relationship_id="contains"),
                    Q(targets_related__source__title__icontains=singlespace, targets_related__relationship_id="contains"),
                ])

        if query["rfcs"]:
            queries.extend([Q(targets_related__source__name__icontains=look_for, targets_related__relationship_id="became_rfc")])

        combined_query = reduce(operator.or_, queries)
        docs = docs.filter(combined_query).distinct()

    # rfc/active/old check buttons
    allowed_draft_states = []
    if query["activedrafts"]:
        allowed_draft_states.append("active")
    if query["olddrafts"]:
        allowed_draft_states.extend(['repl', 'expired', 'auth-rm', 'ietf-rm'])

    docs = docs.filter(Q(states__slug__in=allowed_draft_states) |
                       ~Q(type__slug='draft')).distinct()

    # radio choices
    by = query["by"]
    if by == "author":
        docs = docs.filter(
            Q(documentauthor__person__alias__name__icontains=query["author"]) |
            Q(documentauthor__person__email__address__icontains=query["author"])
        )
    elif by == "group":
        docs = docs.filter(group__acronym__iexact=query["group"])
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
    elif by == "irtfstate":
        docs = docs.filter(states=query["irtfstate"])
    elif by == "stream":
        docs = docs.filter(stream=query["stream"])

    return docs


def search(request):
    def _get_cache_key(params):
        fields = set(SearchForm.base_fields) - {'sort'}
        kwargs = dict([(k, v) for (k, v) in list(params.items()) if k in fields])
        key = "doc:document:search:" + hashlib.sha512(json.dumps(kwargs, sort_keys=True).encode('utf-8')).hexdigest()
        return key

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

        cache_key = _get_cache_key(get_params)
        cached_val = cache.get(cache_key)
        if cached_val:
            [results, meta] = cached_val
        else:
            results = retrieve_search_results(form)
            results, meta = prepare_document_table(request, results, get_params)
            cache.set(cache_key, [results, meta]) # for settings.CACHE_MIDDLEWARE_SECONDS
            log(f"Search results computed for {get_params}")
        meta['searching'] = True
    else:
        form = SearchForm()
        results = []
        meta = { 'by': None, 'searching': False }
        get_params = QueryDict('')

    return render(request, 'doc/search/search.html', {
        'form':form, 'docs':results, 'meta':meta, 'queryargs':get_params.urlencode() },
    )

def frontpage(request):
    form = SearchForm()
    return render(request, 'doc/frontpage.html', {'form':form})

def search_for_name(request, name):
    def find_unique(n):
        exact = Document.objects.filter(name__iexact=n).first()
        if exact:
            return exact.name

        startswith = Document.objects.filter(name__istartswith=n)[:2]
        if len(startswith) == 1:
            return startswith[0].name

        contains = Document.objects.filter(name__icontains=n)[:2]
        if len(contains) == 1:
            return contains[0].name

        return None

    def cached_redirect(cache_key, url):
        cache.set(cache_key, url, settings.CACHE_MIDDLEWARE_SECONDS)
        return HttpResponseRedirect(url)

    n = name

    cache_key = _generate_cache_key(request, 'GET', [], settings.CACHE_MIDDLEWARE_KEY_PREFIX)
    if cache_key:
        url = cache.get(cache_key, None)
        if url:
            return HttpResponseRedirect(url)

    # chop away extension
    extension_split = re.search(r"^(.+)\.(txt|ps|pdf)$", n)
    if extension_split:
        n = extension_split.group(1)

    redirect_to = find_unique(name)
    if redirect_to:
        return cached_redirect(cache_key, urlreverse("ietf.doc.views_doc.document_main", kwargs={ "name": redirect_to }))
    else:
        # check for embedded rev - this may be ambiguous, so don't
        # chop it off if we don't find a match
        rev_split = re.search("^(.+)-([0-9]{2})$", n)
        if rev_split:
            redirect_to = find_unique(rev_split.group(1))
            if redirect_to:
                rev = rev_split.group(2)
                # check if we can redirect directly to the rev if it's draft, if rfc - always redirect to main page
                if not redirect_to.startswith('rfc') and DocHistory.objects.filter(doc__name=redirect_to, rev=rev).exists():
                    return cached_redirect(cache_key, urlreverse("ietf.doc.views_doc.document_main", kwargs={ "name": redirect_to, "rev": rev }))
                else:
                    return cached_redirect(cache_key, urlreverse("ietf.doc.views_doc.document_main", kwargs={ "name": redirect_to }))

    # build appropriate flags based on string prefix
    doctypenames = DocTypeName.objects.filter(used=True).exclude(slug__in=["bcp","std","fyi"])
    # This would have been more straightforward if document prefixes couldn't
    # contain a dash.  Probably, document prefixes shouldn't contain a dash ...
    search_args = "?name=%s" % n
    if   n.startswith("draft"):
        search_args += "&rfcs=on&activedrafts=on&olddrafts=on"
    else:
        for t in doctypenames:
            if t.prefix and n.startswith(t.prefix):
                search_args += "&doctypes=%s" % t.slug
                break
        else:
            search_args += "&rfcs=on&activedrafts=on&olddrafts=on"

    return cached_redirect(cache_key, urlreverse('ietf.doc.views_search.search') + search_args)


def get_state_name_calculator():
    """Get a function to calculate state names
    
    Queries the database once when called, then uses cached look-up table for name calculations.
    """
    # state_lut always has at least rfc, draft, and draft-iesg keys
    state_lut = defaultdict(dict, **{"rfc": {}, "draft":{}, "draft-iesg": {}})
    for state in State.objects.filter(used=True):
        state_lut[state.type_id][state.slug] = state.name
    state_lut = dict(state_lut)  # convert to dict to freeze key changes

    def _get_state_name(doc_type, state_slug):
        """Get display name for a doc type / state slug
        
        Note doc_type rfc here is _not_ necessarily Document.type - for some callers
        it is a type derived from draft... The ad_workload view needs more rework so that
        the code isn't having to shadow-box so much.
        """
        if doc_type == "rfc":
            if state_slug == "rfc":
                return "RFC"
            elif state_slug in state_lut["rfc"]:
                return state_lut["rfc"][state_slug]
            else:
                return state_lut["draft"].get(
                    state_slug,
                    state_lut["draft-iesg"][state_slug],
                )
        elif doc_type == "draft" and state_slug not in ["rfc", "expired"]:
            return state_lut["draft"].get(
                state_slug,
                state_lut["draft-iesg"][state_slug],
            )
        elif doc_type == "draft" and state_slug == "rfc":
            return "RFC"
        elif doc_type == "conflrev" and state_slug.startswith("appr"):
            return "Approved"
        else:
            return state_lut[doc_type][state_slug]

    # return the function as a closure
    return _get_state_name


def shorten_state_name(name):
    """Get abbreviated display name for a state"""
    for pat, sub in [
        (r" \(Internal Steering Group/IAB Review\)", ""),
        ("Writeup", "Write-up"),
        ("Requested", "Req"),
        ("Evaluation", "Eval"),
        ("Publication", "Pub"),
        ("Waiting", "Wait"),
        ("Go-Ahead", "OK"),
        ("Approved-", "App, "),
        ("Approved No Problem", "App."),
        ("announcement", "ann."),
        ("IESG Eval - ", ""),
        ("Not currently under review", "Not under review"),
        ("External Review", "Ext. Review"),
        (
            r"IESG Review \(Charter for Approval, Selected by Secretariat\)",
            "IESG Review",
        ),
        ("Needs Shepherd", "Needs Shep."),
        ("Approved", "App."),
        ("Replaced", "Repl."),
        ("Withdrawn", "Withd."),
        ("Chartering/Rechartering", "Charter"),
        (r"\(Message to Community, Selected by Secretariat\)", ""),
    ]:
        name = re.sub(pat, sub, name)
    return name.strip()


def date_to_bucket(date, now, num_buckets):
    return num_buckets - int((now.date() - date.date()).total_seconds() / 60 / 60 / 24)


def ad_workload(request):
    _calculate_state_name = get_state_name_calculator()
    IESG_STATES = State.objects.filter(type="draft-iesg").values_list("name", flat=True)
    STATE_SLUGS = {
        dt: {_calculate_state_name(dt, ds): ds for ds in AD_WORKLOAD[dt]}  # type: ignore
        for dt in AD_WORKLOAD.keys()
    }

    def _state_to_doc_type(state):
        for dt in STATE_SLUGS:
            if state in STATE_SLUGS[dt]:
                return dt
        return None

    # number of days (= buckets) to show in the graphs
    days = 120 if has_role(request.user, ["Area Director", "Secretariat"]) else 1
    now = timezone.now()

    ads = []
    responsible = Document.objects.values_list("ad", flat=True).distinct()
    for p in Person.objects.filter(
        Q(
            role__name__in=("pre-ad", "ad"),
            role__group__type="area",
            role__group__state="active",
        )
        | Q(pk__in=responsible)
    ).distinct():
        if p in get_active_ads():
            ads.append(p)

    bucket_template = {
        dt: {state: [[] for _ in range(days)] for state in STATE_SLUGS[dt].values()}
        for dt in STATE_SLUGS
    }
    sums = copy.deepcopy(bucket_template)

    for ad in ads:
        ad.dashboard = urlreverse(
            "ietf.doc.views_search.docs_for_ad", kwargs=dict(name=ad.full_name_as_key())
        )
        ad.buckets = copy.deepcopy(bucket_template)

        # https://github.com/ietf-tools/datatracker/issues/4577
        docs_via_group_ad = Document.objects.exclude(
            group__acronym="none"
        ).filter(
            group__role__name="ad",
            group__role__person=ad
        ).filter(
            states__type="draft-stream-ietf",
            states__slug__in=["wg-doc","wg-lc","waiting-for-implementation","chair-w","writeupw"]
        )

        doc_for_ad = Document.objects.filter(ad=ad)

        ad.pre_pubreq = (docs_via_group_ad | doc_for_ad).filter(
            type="draft"
        ).filter(
            states__type="draft",
            states__slug="active"
        ).filter(
            states__type="draft-iesg",
            states__slug="idexists"
        ).distinct().count()

        for doc in Document.objects.exclude(type_id="rfc").filter(ad=ad):
            dt = doc_type(doc)
            state = doc_state(doc)

            state_events = doc.docevent_set.filter(
                type__in=["started_iesg_process", "changed_state", "closed_ballot"]
            )
            if doc.became_rfc():
                state_events = state_events | doc.became_rfc().docevent_set.filter(type="published_rfc")
            state_events = state_events.order_by("-time")

            # compute state history for drafts
            last = now
            for e in state_events:
                to_state = None
                if dt == "charter":
                    if e.type == "closed_ballot":
                        to_state = _calculate_state_name(dt, state)
                    elif e.desc.endswith("has been replaced"):
                        # stop tracking
                        last = e.time
                        break

                if not to_state:
                    # get the state name this event changed the doc into
                    match = re.search(
                        r"(RFC) published|[Ss]tate changed to (.*?)(?:::.*)? from (.*?)(?=::|$)",
                        strip_tags(e.desc),
                        flags=re.MULTILINE,
                    )
                    if not match:
                        # some irrelevant state change for the AD dashboard, ignore it
                        continue
                    to_state = match.group(1) or match.group(2)

                # fix up some states that have been renamed
                if dt == "conflrev" and to_state.startswith("Approved"):
                    to_state = "Approved"
                elif dt == "charter" and to_state.startswith(
                    "Start Chartering/Rechartering"
                ):
                    to_state = "Start Chartering/Rechartering (Internal Steering Group/IAB Review)"
                elif to_state == "RFC Published":
                    to_state = "RFC"

                if dt == "rfc":
                    new_dt = _state_to_doc_type(to_state)
                    if new_dt is not None and new_dt != dt:
                        dt = new_dt

                if to_state not in STATE_SLUGS[dt].keys() or to_state == "Replaced":
                    # change into a state the AD dashboard doesn't display
                    if to_state in IESG_STATES or to_state == "Replaced":
                        # if it's an IESG state we don't display, record it's time
                        last = e.time
                    # keep going with next event
                    continue

                sn = STATE_SLUGS[dt][to_state]
                buckets_start = date_to_bucket(e.time, now, days)
                buckets_end = date_to_bucket(last, now, days)

                if dt == "charter" and to_state == "Approved" and buckets_start < 0:
                    # don't count old charter approvals
                    break

                if buckets_start <= 0:
                    if buckets_end >= 0:
                        for b in range(0, buckets_end):
                            ad.buckets[dt][sn][b].append(doc.name)
                            sums[dt][sn][b].append(doc.name)
                        last = e.time
                    break

                # record doc state in the indicated buckets
                for b in range(buckets_start, buckets_end):
                    ad.buckets[dt][sn][b].append(doc.name)
                    sums[dt][sn][b].append(doc.name)
                last = e.time

    metadata = [
        {
            "type": (dt, doc_type_name(dt)),
            "states": [
                (state, shorten_state_name(_calculate_state_name(dt, state))) for state in ad.buckets[dt]
            ],
            "ads": ads,
        }
        for dt in AD_WORKLOAD
    ]

    data = {
        dt: {slugify(ad): ad.buckets[dt] for ad in ads} | {"sum": sums[dt]}
        for dt in AD_WORKLOAD
    }

    return render(
        request,
        "doc/ad_list.html",
        {"metadata": metadata, "data": data, "delta": days},
    )


def docs_for_ad(request, name):
    def sort_key(doc):
        dt = doc_type(doc)
        dt_key = list(AD_WORKLOAD.keys()).index(dt)
        ds = doc_state(doc)
        ds_key = AD_WORKLOAD[dt].index(ds) if ds in AD_WORKLOAD[dt] else 99
        return dt_key * 100 + ds_key

    ad = None
    responsible = Document.objects.values_list("ad", flat=True).distinct()
    for p in Person.objects.filter(
        Q(
            role__name__in=("pre-ad", "ad"),
            role__group__type="area",
            role__group__state="active",
        )
        | Q(pk__in=responsible)
    ).distinct():
        if name == p.full_name_as_key():
            ad = p
            break
    if not ad:
        raise Http404

    results, meta = prepare_document_table(
        request, Document.objects.filter(ad=ad), max_results=500, show_ad_and_shepherd=False
    )
    results.sort(key=lambda d: sort_key(d))

    # filter out some results
    results = [
        r
        for r in results
        if not (
            r.type_id == "charter"
            and (
                r.group.state_id == "abandon"
                or r.get_state_slug("charter") == "replaced"
            )
        )
        and not (
            r.type_id == "draft"
            and (
                r.get_state_slug("draft-iesg") == "dead"
                or r.get_state_slug("draft") == "repl"
                or r.get_state_slug("draft") == "rfc"
            )
        )
    ]

    _calculate_state_name = get_state_name_calculator()
    for d in results:
        dt = d.type.slug
        d.search_heading = _calculate_state_name(dt, doc_state(d))
        if d.search_heading != "RFC":
            d.search_heading += f" {doc_type_name(dt)}"

    # Additional content showing docs with blocking positions by this AD,
    # and docs that the AD hasn't balloted on that are lacking ballot positions to progress
    blocked_docs = []
    not_balloted_docs = []
    if ad in get_active_ads():
        iesg_docs = Document.objects.filter(
            Q(states__type="draft-iesg", states__slug__in=IESG_BALLOT_ACTIVE_STATES)
            | Q(states__type="charter", states__slug__in=IESG_CHARTER_ACTIVE_STATES)
            | Q(
                states__type__in=("statchg", "conflrev"),
                states__slug__in=IESG_STATCHG_CONFLREV_ACTIVE_STATES,
            )
        ).distinct()
        possible_docs = iesg_docs.filter(
            docevent__ballotpositiondocevent__pos__blocking=True,
            docevent__ballotpositiondocevent__balloter=ad,
        )
        for doc in possible_docs:
            ballot = doc.active_ballot()
            if not ballot:
                continue

            blocking_positions = [p for p in ballot.all_positions() if p.pos.blocking]
            if not blocking_positions or not any(
                p.balloter == ad for p in blocking_positions
            ):
                continue

            augment_events_with_revision(doc, blocking_positions)

            doc.blocking_positions = blocking_positions
            doc.ballot = ballot

            blocked_docs.append(doc)

        # latest first
        if blocked_docs:
            blocked_docs.sort(
                key=lambda d: min(
                    p.time for p in d.blocking_positions if p.balloter == ad
                ),
                reverse=True,
            )

        possible_docs = iesg_docs.exclude(
            Q(docevent__ballotpositiondocevent__balloter=ad)
        )
        for doc in possible_docs:
            ballot = doc.active_ballot()
            if (
                not ballot
                or doc.get_state_slug("draft") == "repl"
                or doc.get_state_slug("draft-iesg") == "defer"
                or not doc.previous_telechat_date()
            ):
                continue

            iesg_ballot_summary = needed_ballot_positions(
                doc, list(ballot.active_balloter_positions().values())
            )
            if re.search(r"\bNeeds\s+\d+", iesg_ballot_summary):
                not_balloted_docs.append(doc)

    return render(
        request,
        "doc/drafts_for_ad.html",
        {
            "docs": results,
            "meta": meta,
            "ad": ad,
            "blocked_docs": blocked_docs,
            "not_balloted_docs": not_balloted_docs,
        },
    )


def drafts_in_last_call(request):
    lc_state = State.objects.get(type="draft-iesg", slug="lc").pk
    form = SearchForm({'by':'state','state': lc_state, 'rfcs':'on', 'activedrafts':'on'})
    results, meta = prepare_document_table(request, retrieve_search_results(form), form.data)
    pages = 0
    for doc in results:
        pages += doc.pages

    return render(request, 'doc/drafts_in_last_call.html', {
        'form':form, 'docs':results, 'meta':meta, 'pages':pages
    })

def drafts_in_iesg_process(request):
    states = State.objects.filter(type="draft-iesg").exclude(slug__in=('idexists', 'pub', 'dead', 'rfcqueue'))
    title = "Documents in IESG process"

    grouped_docs = []

    for s in states.order_by("order"):
        docs = Document.objects.filter(type="draft", states=s).distinct().order_by("time").select_related("ad", "group", "group__parent")
        if docs:
            if s.slug == "lc":
                for d in docs:
                    e = d.latest_event(LastCallDocEvent, type="sent_last_call")
                    # If we don't have an event, use an arbitrary date in the past (but not datetime.datetime.min,
                    # which causes problems with timezone conversions)
                    d.lc_expires = e.expires if e else datetime.datetime(1950, 1, 1)
                docs = list(docs)
                docs.sort(key=lambda d: d.lc_expires)

            grouped_docs.append((s, docs))

    return render(request, 'doc/drafts_in_iesg_process.html', {
            "grouped_docs": grouped_docs,
            "title": title,
            })

def recent_drafts(request, days=7):
    slowcache = caches['slowpages']
    cache_key = f'recentdraftsview{days}'
    cached_val = slowcache.get(cache_key)
    if not cached_val:
        since = timezone.now()-datetime.timedelta(days=days)
        state = State.objects.get(type='draft', slug='active')
        events = NewRevisionDocEvent.objects.filter(time__gt=since)
        names = [ e.doc.name for e in events ]
        docs = Document.objects.filter(name__in=names, states=state)
        results, meta = prepare_document_table(request, docs, query={'sort':'-date', }, max_results=len(names))
        slowcache.set(cache_key, [docs, results, meta], 1800)
    else:
        [docs, results, meta] = cached_val

    pages = 0
    for doc in results:
        pages += doc.pages or 0

    return render(request, 'doc/recent_drafts.html', {
        'docs':results, 'meta':meta, 'pages':pages, 'days': days,
    })


def index_all_drafts(request): # Should we rename this
    # try to be efficient since this view returns a lot of data
    categories = []

    # Gather drafts
    for s in ("active", "expired", "repl", "auth-rm", "ietf-rm"):
        state = State.objects.get(type="draft", slug=s)

        if state.slug in ("ietf-rm", "auth-rm"):
            heading = "Internet-Drafts %s" % state.name
        else:
            heading = "%s Internet-Drafts" % state.name

        drafts = Document.objects.filter(type_id="draft", states=state).order_by("name")

        names = [
            f'<a href=\"{urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=doc.name))}\">{doc.name}</a>'
            for doc in drafts
        ]        

        categories.append((state,
                      heading,
                      len(names),
                      "<br>".join(names)
                      ))
    
    # gather RFCs
    rfcs = Document.objects.filter(type_id="rfc").order_by('-rfc_number')
    names = [
        f'<a href=\"{urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=rfc.name))}\">{rfc.name.upper()}</a>'
        for rfc in rfcs
    ]
    
    state = State.objects.get(type_id="rfc", slug="published")

    categories.append((state,
                    "RFCs",
                    len(names),
                    "<br>".join(names)
                    ))
    
    # Return to the previous section ordering
    categories = categories[0:1]+categories[5:]+categories[1:5]

    return render(request, 'doc/index_all_drafts.html', { "categories": categories })

def index_active_drafts(request):
    slowcache = caches['slowpages']
    cache_key = 'doc:index_active_drafts'
    groups = slowcache.get(cache_key)
    if not groups:
        groups = active_drafts_index_by_group()
        slowcache.set(cache_key, groups, 15*60)
    return render(request, "doc/index_active_drafts.html", { 'groups': groups })

def ajax_select2_search_docs(request, model_name, doc_type): # TODO - remove model_name argument...
    """Get results for a select2 search field
    
    doc_type can be "draft", "rfc", or "all", to search for only docs of type "draft", only docs of
    type "rfc", or docs of type "draft" or "rfc" or any of the subseries ("bcp", "std", ...).
    
    If a need arises for searching _only_ for draft or rfc, without including the subseries, then an
    additional option or options will be needed.
    """
    model = Document # Earlier versions allowed searching over DocAlias which no longer exists

    q = [w.strip() for w in request.GET.get('q', '').split() if w.strip()]

    if not q:
        objs = model.objects.none()
    else:
        if doc_type == "draft":
            types = ["draft"]
        elif doc_type == "rfc":
            types = ["rfc"]
        elif doc_type == "all":
            types = ("draft", "rfc", "bcp", "fyi", "std")
        else:
            return HttpResponseBadRequest("Invalid document type")
        qs = model.objects.filter(type__in=[t.strip() for t in types])
        for t in q:
            qs = qs.filter(name__icontains=t)

        objs = qs.distinct().order_by("name")[:20]

    return HttpResponse(select2_id_doc_name_json(model, objs), content_type='application/json')

def index_subseries(request, type_id):
    docs = sorted(Document.objects.filter(type_id=type_id),key=lambda o: int(o.name[3:]))
    if len(docs)>0:
        type = docs[0].type
    else:
        type = DocTypeName.objects.get(slug=type_id)
    return render(request, "doc/index_subseries.html", {"type": type, "docs": docs})
