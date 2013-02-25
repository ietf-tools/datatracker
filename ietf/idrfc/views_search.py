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

import re, datetime
from django import forms
from django.shortcuts import render_to_response
from django.db.models import Q
from django.template import RequestContext
from django.views.decorators.cache import cache_page
from ietf.idtracker.models import IDState, IESGLogin, IDSubState, Area, InternetDraft, Rfc, IDInternal, IETFWG
from ietf.idrfc.models import RfcIndex
from django.http import Http404, HttpResponse, HttpResponseBadRequest, HttpResponsePermanentRedirect
from ietf.idrfc.idrfc_wrapper import IdWrapper,RfcWrapper,IdRfcWrapper
from ietf.utils import normalize_draftname
from django.conf import settings

from ietf.doc.models import *
from ietf.person.models import *
from ietf.group.models import *

class SearchForm(forms.Form):
    name = forms.CharField(required=False)
    rfcs = forms.BooleanField(required=False,initial=True)
    activeDrafts = forms.BooleanField(required=False,initial=True)
    oldDrafts = forms.BooleanField(required=False,initial=False)
    lucky = forms.BooleanField(required=False,initial=False)

    by = forms.ChoiceField(choices=[(x,x) for x in ('author','group','area','ad','state')], required=False, initial='wg', label='Foobar')
    author = forms.CharField(required=False)
    group = forms.CharField(required=False)
    area = forms.ModelChoiceField(Group.objects.filter(type="area", state="active").order_by('name'), empty_label="any area", required=False)
    ad = forms.ChoiceField(choices=(), required=False)
    state = forms.ModelChoiceField(State.objects.filter(type="draft-iesg"), empty_label="any state", required=False)
    subState = forms.ChoiceField(choices=(), required=False)

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

        self.fields['ad'].choices = c = [('', 'any AD')] + [(ad.pk, ad.plain_name()) for ad in active_ads] + [('', '------------------')] + [(ad.pk, ad.name) for ad in inactive_ads]
        self.fields['subState'].choices = [('', 'any substate'), ('0', 'no substate')] + [(n.slug, n.name) for n in DocTagName.objects.filter(slug__in=('point', 'ad-f-up', 'need-rev', 'extpty'))]
    def clean_name(self):
        value = self.cleaned_data.get('name','')
        return normalize_draftname(value)
    def clean(self):
        q = self.cleaned_data
        # Reset query['by'] if needed
        if 'by' not in q:
            q['by'] = None            
        else:
            for k in ('author','group','area','ad'):
                if (q['by'] == k) and (k not in q or not q[k]):
                    q['by'] = None
            if (q['by'] == 'state') and (not 'state' in q or not 'subState' in q or not (q['state'] or q['subState'])):
                q['by'] = None
        # Reset other fields
        for k in ('author','group','area','ad'):
            if q['by'] != k:
                self.data[k] = ""
                q[k] = ""
        if q['by'] != 'state':
            self.data['state'] = ""
            self.data['subState'] = ""
            q['state'] = ""
            q['subState'] = ""
        return q

def search_query(query_original, sort_by=None):
    query = dict(query_original.items())
    drafts = query['activeDrafts'] or query['oldDrafts']
    if (not drafts) and (not query['rfcs']):
        return ([], {})

    # Non-ASCII strings don't match anything; this check
    # is currently needed to avoid complaints from MySQL.
    # FIXME: this should be fixed with MySQL if it's still a problem?
    for k in ['name','author','group']:
        try:
            tmp = str(query.get(k, ''))
        except:
            query[k] = '*NOSUCH*'

    # Start by search InternetDrafts
    idresults = []
    rfcresults = []
    MAX = 500

    docs = InternetDraft.objects.all()

    # name
    if query["name"]:
        docs = docs.filter(Q(docalias__name__icontains=query["name"]) |
                           Q(title__icontains=query["name"])).distinct()

    # rfc/active/old check buttons
    allowed_states = []
    if query["rfcs"]:
        allowed_states.append("rfc")
    if query["activeDrafts"]:
        allowed_states.append("active")
    if query["oldDrafts"]:
        allowed_states.extend(['repl', 'expired', 'auth-rm', 'ietf-rm'])

    docs = docs.filter(states__type="draft", states__slug__in=allowed_states)

    # radio choices
    by = query["by"]
    if by == "author":
        # FIXME: this is full name, not last name as hinted in the HTML
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
        if query["subState"]:
            docs = docs.filter(tags=query["subState"])

    # evaluate and fill in values with aggregate queries to avoid
    # too many individual queries
    results = list(docs.select_related("states", "ad", "ad__person", "std_level", "intended_std_level", "group", "stream")[:MAX])

    rfc_aliases = dict(DocAlias.objects.filter(name__startswith="rfc", document__in=[r.pk for r in results]).values_list("document_id", "name"))
    # canonical name
    for r in results:
        if r.pk in rfc_aliases:
            # lambda weirdness works around lambda binding in local for loop scope 
            r.canonical_name = (lambda x: lambda: x)(rfc_aliases[r.pk])
        else:
            r.canonical_name = (lambda x: lambda: x)(r.name)

    result_map = dict((r.pk, r) for r in results)

    # events
    event_types = ("published_rfc",
                   "changed_ballot_position",
                   "started_iesg_process",
                   "new_revision")
    for d in rfc_aliases.keys():
        for e in event_types:
            setattr(result_map[d], e, None)

    for e in DocEvent.objects.filter(doc__in=rfc_aliases.keys(), type__in=event_types).order_by('-time'):
        r = result_map[e.doc_id]
        if not getattr(r, e.type):
            # sets e.g. r.published_date = e for use in proxy wrapper
            setattr(r, e.type, e)

    # obsoleted/updated by
    for d in rfc_aliases:
        r = result_map[d]
        r.obsoleted_by_list = []
        r.updated_by_list = []

    xed_by = RelatedDocument.objects.filter(target__name__in=rfc_aliases.values(), relationship__in=("obs", "updates")).select_related('target__document_id')
    rel_rfc_aliases = dict(DocAlias.objects.filter(name__startswith="rfc", document__in=[rel.source_id for rel in xed_by]).values_list('document_id', 'name'))
    for rel in xed_by:
        r = result_map[rel.target.document_id]
        if rel.relationship_id == "obs":
            attr = "obsoleted_by_list"
        else:
            attr = "updated_by_list"

        getattr(r, attr).append(int(rel_rfc_aliases[rel.source_id][3:]))


    # sort
    def sort_key(d):
        res = []

        canonical = d.canonical_name()
        if canonical.startswith('rfc'):
            rfc_num = int(canonical[3:])
        else:
            rfc_num = None

        if rfc_num != None:
            res.append(2)
        elif d.get_state_slug() == "active":
            res.append(1)
        else:
            res.append(3)

        if sort_by == "title":
            res.append(d.title)
        elif sort_by == "date":
            res.append(str(d.revision_date or datetime.date(1990, 1, 1)))
        elif sort_by == "status":
            if rfc_num != None:
                res.append(rfc_num)
            else:
                res.append(d.get_state().order)
        elif sort_by == "ipr":
            res.append(d.name)
        elif sort_by == "ad":
            if rfc_num != None:
                res.append(rfc_num)
            elif d.get_state_slug() == "active":
                if d.get_state("draft-iesg"):
                    res.append(d.get_state("draft-iesg").order)
                else:
                    res.append(0)
        else:
            if rfc_num != None:
                res.append(rfc_num)
            else:
                res.append(canonical)

        return res

    results.sort(key=sort_key)

    meta = {}
    if len(docs) == MAX:
        meta['max'] = MAX
    if query['by']:
        meta['advanced'] = True

    # finally wrap in old wrappers

    wrapped_results = []
    for r in results:
        draft = None
        rfc = None
        if not r.name.startswith('rfc'):
            draft = IdWrapper(r)
        if r.name.startswith('rfc') or r.pk in rfc_aliases:
            rfc = RfcWrapper(r)
        wrapped_results.append(IdRfcWrapper(draft, rfc))

    return (wrapped_results, meta)
    

def generate_query_string(request, ignore_list):
    """Recreates the parameter string from the given request, and
       returns it as a string.
       Any parameter names present in ignore_list shall not be put
       in the result string.
    """
    params = []
    for i in request.GET:
        if not i in ignore_list:
            params.append(i + "=" + request.GET[i])
    return "?" + "&".join(params)

def search_results(request):
    if len(request.REQUEST.items()) == 0:
        return search_main(request)
    form = SearchForm(dict(request.REQUEST.items()))
    if not form.is_valid():
        return HttpResponseBadRequest("form not valid?", mimetype="text/plain")

    sort_by = None
    if "sortBy" in request.GET:
        sort_by = request.GET["sortBy"]

    (results,meta) = search_query(form.cleaned_data, sort_by)

    meta['searching'] = True
    meta['by'] = form.cleaned_data['by']
    meta['rqps'] = generate_query_string(request, ['sortBy'])
    # With a later Django we can do this from the template (incude with tag)
    # Pass the headers and their sort key names
    meta['hdrs'] = [{'htitle': 'Document', 'htype':'doc'},
                    {'htitle': 'Title', 'htype':'title'},
                    {'htitle': 'Date', 'htype':'date'},
                    {'htitle': 'Status', 'htype':'status', 'colspan':'2'},
                    {'htitle': 'IPR', 'htype':'ipr'},
                    {'htitle': 'Ad', 'htype':'ad'}]

    # Make sure we know which one is selected (for visibility later)
    if sort_by:
        for hdr in meta['hdrs']:
            if hdr['htype'] == sort_by:
                hdr['selected'] = True

    if 'ajax' in request.REQUEST and request.REQUEST['ajax']:
        return render_to_response('idrfc/search_results.html', {'docs':results, 'meta':meta}, context_instance=RequestContext(request))
    elif form.cleaned_data['lucky'] and len(results)==1:
        doc = results[0]
        if doc.id:
            return HttpResponsePermanentRedirect(doc.id.get_absolute_url())
        else:
            return HttpResponsePermanentRedirect(doc.rfc.get_absolute_url())
    else:
        return render_to_response('idrfc/search_main.html', {'form':form, 'docs':results,'meta':meta}, context_instance=RequestContext(request))
        

def search_main(request):
    form = SearchForm()
    return render_to_response('idrfc/search_main.html', {'form':form}, context_instance=RequestContext(request))

def by_ad(request, name):
    ad_id = None
    ad_name = None
    if settings.USE_DB_REDESIGN_PROXY_CLASSES:
        responsible = Document.objects.values_list('ad', flat=True).distinct()
        for p in Person.objects.filter(Q(role__name__in=("pre-ad", "ad"),
                                         role__group__type="area",
                                         role__group__state="active")
                                       | Q(pk__in=responsible)).distinct():
            if name == p.full_name_as_key():
                ad_id = p.id
                ad_name = p.plain_name()
                break
    else:
        for i in IESGLogin.objects.filter(user_level__in=[1,2]):
            iname = str(i).lower().replace(' ','.')
            if name == iname:
                ad_id = i.id
                ad_name = str(i)
                break
    if not ad_id:
        raise Http404
    form = SearchForm({'by':'ad','ad':ad_id,
                       'rfcs':'on', 'activeDrafts':'on', 'oldDrafts':'on'})
    if not form.is_valid():
        raise ValueError("form did not validate")
    (results,meta) = search_query(form.cleaned_data)
    results.sort(key=lambda obj: obj.view_sort_key_byad())
    return render_to_response('idrfc/by_ad.html', {'form':form, 'docs':results,'meta':meta, 'ad_name':ad_name}, context_instance=RequestContext(request))

@cache_page(15*60) # 15 minutes
def all(request):
    if settings.USE_DB_REDESIGN_PROXY_CLASSES:
        active = (dict(filename=n) for n in InternetDraft.objects.filter(states__type="draft", states__slug="active").order_by("name").values_list('name', flat=True))
        rfc1 = (dict(filename=d, rfc_number=int(n[3:])) for d, n in DocAlias.objects.filter(document__states__type="draft", document__states__slug="rfc", name__startswith="rfc").exclude(document__name__startswith="rfc").order_by("document__name").values_list('document__name','name').distinct())
        rfc2 = (dict(rfc_number=r, draft=None) for r in sorted(int(n[3:]) for n in Document.objects.filter(type="draft", name__startswith="rfc").values_list('name', flat=True)))
        dead = InternetDraft.objects.exclude(states__type="draft", states__slug__in=("active", "rfc")).select_related("states").order_by("name")
    else:
        active = InternetDraft.objects.all().filter(status=1).order_by("filename").values('filename')
        rfc1 = InternetDraft.objects.all().filter(status=3).order_by("filename").values('filename','rfc_number')
        rfc_numbers1 = InternetDraft.objects.all().filter(status=3).values_list('rfc_number', flat=True)
        rfc2 = RfcIndex.objects.all().exclude(rfc_number__in=rfc_numbers1).order_by('rfc_number').values('rfc_number','draft')
        dead = InternetDraft.objects.all().exclude(status__in=[1,3]).order_by("filename").select_related('status__status')
    return render_to_response('idrfc/all.html', {'active':active, 'rfc1':rfc1, 'rfc2':rfc2, 'dead':dead}, context_instance=RequestContext(request))

@cache_page(15*60) # 15 minutes
def active(request):
    groups = IETFWG.objects.exclude(group_acronym=1027)
    individual = IETFWG.objects.get(group_acronym=1027)
    return render_to_response("idrfc/active.html", {'groups':groups,'individual':individual}, context_instance=RequestContext(request))

def in_last_call(request):
    
    lcdocs = []

    for p in InternetDraft.objects.all().filter(idinternal__primary_flag=1).filter(idinternal__cur_state__state='In Last Call'):
      if (p.idinternal.rfc_flag):
        lcdocs.append(IdRfcWrapper(None,RfcWrapper(p))) 
      else:
        lcdocs.append(IdRfcWrapper(IdWrapper(p),None))

    return render_to_response("idrfc/in_last_call.html", {'lcdocs':lcdocs}, context_instance=RequestContext(request))
