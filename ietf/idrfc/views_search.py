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

def addInputEvents(widget):
    widget.attrs["oninput"] = 'inputEvent()'
    widget.attrs["onpropertychange"] = 'propertyChange()'

def addChangeEvent(widget):
    widget.attrs["onchange"] = 'changeEvent()'

class SearchForm(forms.Form):
    name = forms.CharField(required=False)
    addInputEvents(name.widget)
    rfcs = forms.BooleanField(required=False,initial=True)
    activeDrafts = forms.BooleanField(required=False,initial=True)
    oldDrafts = forms.BooleanField(required=False,initial=False)
    lucky = forms.BooleanField(required=False,initial=False)

    by = forms.ChoiceField(choices=[(x,x) for x in ('author','group','area','ad','state')], required=False, initial='wg', label='Foobar')
    author = forms.CharField(required=False)
    addInputEvents(author.widget)
    group = forms.CharField(required=False)
    addInputEvents(group.widget)
    area = forms.ModelChoiceField(Area.active_areas(), empty_label="any area", required=False)
    addChangeEvent(area.widget)
    ad = forms.ChoiceField(choices=(), required=False)
    addChangeEvent(ad.widget)
    state = forms.ModelChoiceField(IDState.objects.all(), empty_label="any state", required=False)
    addChangeEvent(state.widget)
    subState = forms.ChoiceField(choices=(), required=False)
    addChangeEvent(subState.widget)
        
    def __init__(self, *args, **kwargs):
        super(SearchForm, self).__init__(*args, **kwargs)
        self.fields['ad'].choices = [('', 'any AD')] + [(ad.id, "%s %s" % (ad.first_name, ad.last_name)) for ad in IESGLogin.objects.filter(user_level=1).order_by('last_name')] + [('-99', '------------------')] + [(ad.id, "%s %s" % (ad.first_name, ad.last_name)) for ad in IESGLogin.objects.filter(user_level=2).order_by('last_name')]
        self.fields['subState'].choices = [('', 'any substate'), ('0', 'no substate')] + [(state.sub_state_id, state.sub_state) for state in IDSubState.objects.all()]
    def clean_name(self):
        value = self.cleaned_data.get('name','')
        return normalize_draftname(value)
    def clean(self):
        q = self.cleaned_data
        # Reset query['by'] if needed
        for k in ('author','group','area','ad'):
            if (q['by'] == k) and not q[k]:
                q['by'] = None
        if (q['by'] == 'state') and not (q['state'] or q['subState']):
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
    for k in ['name','author','group']:
        try:
            tmp = str(query.get(k, ''))
        except:
            query[k] = '*NOSUCH*'

    # Start by search InternetDrafts
    idresults = []
    rfcresults = []
    MAX = 500
    maxReached = False

    prefix = ""
    q_objs = []
    if query['by'] in ('ad','state'):
        prefix = "draft__"
    if query['name']:
        q_objs.append(Q(**{prefix+"filename__icontains":query['name']})|Q(**{prefix+"title__icontains":query['name']}))

    if query['by'] == 'author':
        q_objs.append(Q(**{prefix+"authors__person__last_name__icontains":query['author']}))
    elif query['by'] == 'group':
        q_objs.append(Q(**{prefix+"group__acronym":query['group']}))
    elif query['by'] == 'area':
        q_objs.append(Q(**{prefix+"group__ietfwg__areagroup__area":query['area']}))
    elif query['by'] == 'ad':
        q_objs.append(Q(job_owner=query['ad']))
    elif query['by'] == 'state':
        if query['state']:
            q_objs.append(Q(cur_state=query['state']))
        if query['subState']:
            q_objs.append(Q(cur_sub_state=query['subState']))
    if (not query['rfcs']) and query['activeDrafts'] and (not query['oldDrafts']):
        q_objs.append(Q(**{prefix+"status":1}))
    elif query['rfcs'] and query['activeDrafts'] and (not query['oldDrafts']):
        q_objs.append(Q(**{prefix+"status":1})|Q(**{prefix+"status":3}))
    elif query['rfcs'] and (not drafts):
        q_objs.append(Q(**{prefix+"status":3}))
    if prefix:
        q_objs.append(Q(rfc_flag=0))
        matches = IDInternal.objects.filter(*q_objs)
    else:
        matches = InternetDraft.objects.filter(*q_objs)
    if not query['activeDrafts']:
        matches = matches.exclude(Q(**{prefix+"status":1}))
    if not query['rfcs']:
        matches = matches.exclude(Q(**{prefix+"status":3}))
    if prefix:
        matches = [id.draft for id in matches[:MAX]]
    else:
        matches = matches[:MAX]
    if len(matches) == MAX:
        maxReached = True
    for id in matches:
        if id.status.status == 'RFC':
            rfcresults.append([id.rfc_number, id, None, None])
        else:
            idresults.append([id])

    # Next, search RFCs
    if query['rfcs']:
        q_objs = []
        searchRfcIndex = True
        if query['name']:
            r = re.compile("^\s*(?:RFC)?\s*(\d+)\s*$", re.IGNORECASE)
            m = r.match(query['name'])
            if m:
                q_objs.append(Q(rfc_number__contains=m.group(1))|Q(title__icontains=query['name']))
            else:
                q_objs.append(Q(title__icontains=query['name']))
        if query['by'] == 'author':
            q_objs.append(Q(authors__icontains=query['author']))
        elif query['by'] == 'group':
            # We prefer searching RfcIndex, but it doesn't have group info
            searchRfcIndex = False
            q_objs.append(Q(group_acronym=query['group']))
        elif query['by'] == 'area':
            # Ditto for area
            searchRfcIndex = False
            q_objs.append(Q(area_acronym=query['area']))
        elif query['by'] == 'ad':
            numbers = IDInternal.objects.filter(rfc_flag=1,job_owner=query['ad']).values_list('draft_id',flat=True)
            q_objs.append(Q(rfc_number__in=numbers))
        elif query['by'] == 'state':
            numbers_q = [Q(rfc_flag=1)]
            if query['state']:
                numbers_q.append(Q(cur_state=query['state']))
            if query['subState']:
                numbers_q.append(Q(cur_state=query['subState']))
            numbers = IDInternal.objects.filter(*numbers_q).values_list('draft_id',flat=True)
            q_objs.append(Q(rfc_number__in=numbers))

        if searchRfcIndex:
            matches = RfcIndex.objects.filter(*q_objs)[:MAX]
        else:
            matches = Rfc.objects.filter(*q_objs)[:MAX]
        if len(matches) == MAX:
            maxReached = True
        for rfc in matches:
            found = False
            for r2 in rfcresults:
                if r2[0] == rfc.rfc_number:
                    if searchRfcIndex:
                        r2[3] = rfc
                    else:
                        r2[2] = rfc
                    found = True
            if not found:
                if searchRfcIndex:
                    rfcresults.append([rfc.rfc_number, None, None, rfc])
                else:
                    rfcresults.append([rfc.rfc_number, None, rfc, None])
                    
    # Find missing InternetDraft objects
    for r in rfcresults:
        if not r[1]:
            ids = InternetDraft.objects.filter(rfc_number=r[0])
            if len(ids) >= 1:
                r[1] = ids[0]
        if not r[1] and r[3] and r[3].draft:
            ids = InternetDraft.objects.filter(filename=r[3].draft)
            if len(ids) >= 1:
                r[1] = ids[0]

    # Finally, find missing RFC objects
    for r in rfcresults:
        if not r[2]:
            rfcs = Rfc.objects.filter(rfc_number=r[0])
            if len(rfcs) >= 1:
                r[2] = rfcs[0]
        if not r[3]:
            rfcs = RfcIndex.objects.filter(rfc_number=r[0])
            if len(rfcs) >= 1:
                r[3] = rfcs[0]

    # TODO: require that RfcIndex is present?

    results = []
    for res in idresults+rfcresults:
        if len(res)==1:
            doc = IdRfcWrapper(IdWrapper(res[0]), None)
            results.append(doc)
        else:
            d = None
            r = None
            if res[1]:
                d = IdWrapper(res[1])
            if res[3]:
                r = RfcWrapper(res[3])
            if d or r:
                doc = IdRfcWrapper(d, r)
                results.append(doc)
    results.sort(key=lambda obj: obj.view_sort_key(sort_by))
    
    meta = {}
    if maxReached:
        meta['max'] = MAX
    if query['by']:
        meta['advanced'] = True
    return (results,meta)

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    from doc.models import *
    from person.models import *
    from group.models import *

    class SearchForm(forms.Form):
        name = forms.CharField(required=False)
        addInputEvents(name.widget) # consider moving this to jQuery client-side instead
        rfcs = forms.BooleanField(required=False,initial=True)
        activeDrafts = forms.BooleanField(required=False,initial=True)
        oldDrafts = forms.BooleanField(required=False,initial=False)
        lucky = forms.BooleanField(required=False,initial=False)

        by = forms.ChoiceField(choices=[(x,x) for x in ('author','group','area','ad','state')], required=False, initial='wg', label='Foobar')
        author = forms.CharField(required=False)
        addInputEvents(author.widget)
        group = forms.CharField(required=False)
        addInputEvents(group.widget)
        area = forms.ModelChoiceField(Group.objects.filter(type="area", state="active").order_by('name'), empty_label="any area", required=False)
        addInputEvents(area.widget)
        ad = forms.ChoiceField(choices=(), required=False)
        addInputEvents(ad.widget)
        state = forms.ModelChoiceField(State.objects.filter(type="draft-iesg"), empty_label="any state", required=False)
        addInputEvents(state.widget)
        subState = forms.ChoiceField(choices=(), required=False)
        addInputEvents(subState.widget)

        def __init__(self, *args, **kwargs):
            super(SearchForm, self).__init__(*args, **kwargs)
            responsible = Document.objects.values_list('ad', flat=True).distinct()
            active_ads = list(Person.objects.filter(role__name="ad",
                                                    role__group__type="area",
                                                    role__group__state="active").distinct())
            inactive_ads = list(Person.objects.filter(pk__in=responsible)
                                .exclude(pk__in=[x.pk for x in active_ads]))
            extract_last_name = lambda x: x.name_parts()[3]
            active_ads.sort(key=extract_last_name)
            inactive_ads.sort(key=extract_last_name)

            self.fields['ad'].choices = c = [('', 'any AD')] + [(ad.pk, ad.name) for ad in active_ads] + [('', '------------------')] + [(ad.pk, ad.name) for ad in inactive_ads]
            self.fields['subState'].choices = [('', 'any substate'), ('0', 'no substate')] + [(n.slug, n.name) for n in DocTagName.objects.filter(slug__in=('point', 'ad-f-up', 'need-rev', 'extpty'))]
        def clean_name(self):
            value = self.cleaned_data.get('name','')
            return normalize_draftname(value)
        def clean(self):
            q = self.cleaned_data
            # Reset query['by'] if needed
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
            docs = docs.filter(Q(group__parent=query["area"]) |
                               Q(ad__role__name="ad",
                                 ad__role__group=query["area"]))
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
                        res.append(get_state("draft-iesg").order)
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
        for p in Person.objects.filter(Q(role__name="ad",
                                         role__group__type="area",
                                         role__group__state="active")
                                       | Q(pk__in=responsible)):
            if name == p.name.lower().replace(" ", "."):
                ad_id = p.id
                ad_name = p.name
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
        rfc1 = (dict(filename=d, rfc_number=int(n[3:])) for d, n in DocAlias.objects.filter(document__states__type="draft-iesg", document__states__slug="rfc", name__startswith="rfc").exclude(document__name__startswith="rfc").order_by("document__name").values_list('document__name','name').distinct())
        rfc2 = (dict(rfc_number=r, draft=None) for r in sorted(int(n[3:]) for n in Document.objects.filter(type="draft", name__startswith="rfc").values_list('name', flat=True)))
        dead = InternetDraft.objects.exclude(state__in=("active", "rfc")).select_related("state").order_by("name")
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
