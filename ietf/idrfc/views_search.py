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

import re
from django import forms
from django.shortcuts import render_to_response
from django.db.models import Q
from django.template import RequestContext
from django.views.decorators.cache import cache_page
from ietf.idtracker.models import IDState, IESGLogin, IDSubState, Area, InternetDraft, Rfc, IDInternal, IETFWG
from ietf.idrfc.models import RfcIndex
from django.http import Http404, HttpResponse, HttpResponsePermanentRedirect
from ietf.idrfc.idrfc_wrapper import IdWrapper,RfcWrapper,IdRfcWrapper
from ietf.utils import normalize_draftname

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

def genParamURL(request, ignore_list):
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
        return HttpResponse("form not valid?", mimetype="text/plain")

    sort_by = None
    if "sortBy" in request.GET:
        sort_by = request.GET["sortBy"]

    (results,meta) = search_query(form.cleaned_data, sort_by)

    meta['searching'] = True
    meta['by'] = form.cleaned_data['by']
    meta['rqps'] = genParamURL(request, ['sortBy'])
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
        lcdocs.append(IdRfcWrapper(None,RfCWrapper(p))) 
      else:
        lcdocs.append(IdRfcWrapper(IdWrapper(p),None))

    return render_to_response("idrfc/in_last_call.html", {'lcdocs':lcdocs}, context_instance=RequestContext(request))
