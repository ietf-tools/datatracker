# Copyright (C) 2009 Nokia Corporation and/or its subsidiary(-ies).
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
from django import newforms as forms
from django.shortcuts import render_to_response
from django.db.models import Q
from django.template import RequestContext

from ietf.idtracker.models import IDState, IESGLogin, IDSubState, Area, InternetDraft, Rfc, IDInternal
from ietf.idrfc.models import RfcIndex
from django.http import Http404, HttpResponse
from ietf.idrfc.idrfc_wrapper import IdWrapper,RfcWrapper,IdRfcWrapper
from ietf.utils import normalize_draftname

class SearchForm(forms.Form):
    name = forms.CharField(required=False)
    author = forms.CharField(required=False)
    rfcs = forms.BooleanField(required=False,initial=True)
    activeDrafts = forms.BooleanField(required=False,initial=True)
    oldDrafts = forms.BooleanField(required=False,initial=False)

    group = forms.CharField(required=False)
    area = forms.ModelChoiceField(Area.objects.filter(status=Area.ACTIVE), empty_label="any area", required=False)

    ad = forms.ChoiceField(choices=(), required=False)
    state = forms.ModelChoiceField(IDState.objects.all(), empty_label="any state", required=False)
    subState = forms.ChoiceField(choices=(), required=False)
        
    def clean_name(self):
        value = self.clean_data.get('name','')
        return normalize_draftname(value)
    def __init__(self, *args, **kwargs):
        super(SearchForm, self).__init__(*args, **kwargs)
        self.fields['ad'].choices = [('', 'any AD')] + [(ad.id, "%s %s" % (ad.first_name, ad.last_name)) for ad in IESGLogin.objects.filter(user_level=1).order_by('last_name')] + [('-99', '------------------')] + [(ad.id, "%s %s" % (ad.first_name, ad.last_name)) for ad in IESGLogin.objects.filter(user_level=2).order_by('last_name')]
        self.fields['subState'].choices = [('', 'any substate'), ('0', 'no substate')] + [(state.sub_state_id, state.sub_state) for state in IDSubState.objects.all()]
                                                                        
def search_query(query):
    drafts = query['activeDrafts'] or query['oldDrafts']
    if (not drafts) and (not query['rfcs']):
        return ([], {})

    # Start by search InternetDrafts
    idresults = []
    rfcresults = []
    MAX = 500
    maxReached = False

    prefix = ""
    q_objs = []
    if query['ad'] or query['state'] or query['subState']:
        prefix = "draft__"
    if query['ad']:
        q_objs.append(Q(job_owner=query['ad']))
    if query['state']:
        q_objs.append(Q(cur_state=query['state']))
    if query['subState']:
        q_objs.append(Q(cur_sub_state=query['subState']))
    
    if query['name']:
        q_objs.append(Q(**{prefix+"filename__icontains":query['name']})|Q(**{prefix+"title__icontains":query['name']}))
    if query['author']:
        q_objs.append(Q(**{prefix+"authors__person__last_name__icontains":query['author']}))
    if query['group']:
        q_objs.append(Q(**{prefix+"group__acronym":query['group']}))
    if query['area']:
        q_objs.append(Q(**{prefix+"group__ietfwg__areagroup__area":query['area']}))
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
    if query['rfcs'] and not (query['ad'] or query['state'] or query['subState'] or query['area']):
        q_objs = []
        searchRfcIndex = True
        if query['name']:
            r = re.compile("^\s*(?:RFC)?\s*(\d+)\s*$", re.IGNORECASE)
            m = r.match(query['name'])
            if m:
                q_objs.append(Q(rfc_number__contains=m.group(1))|Q(title__icontains=query['name']))
            else:
                q_objs.append(Q(title__icontains=query['name']))
        # We prefer searching RfcIndex, but it doesn't have group info
        if query['group']:
            searchRfcIndex = False
            q_objs.append(Q(group_acronym=query['group']))
        if query['area']:
            # TODO: not implemented yet
            pass
        if query['author'] and searchRfcIndex:
            q_objs.append(Q(authors__icontains=query['author']))
        elif query['author']:
            q_objs.append(Q(authors__person__last_name__icontains=query['author']))
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

    # TODO: require that RfcINdex is present

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
    results.sort(key=lambda obj: obj.view_sort_key())
    meta = {}
    if maxReached:
        meta['max'] = MAX
    return (results,meta)

def search_results(request):
    form = SearchForm(request.REQUEST)
    if not form.is_valid():
        return HttpResponse("form not valid?", mimetype="text/plain")
    x = form.clean_data
    (results,meta) = search_query(form.clean_data)
    if 'ajax' in request.REQUEST and request.REQUEST['ajax']:
        return render_to_response('idrfc/search_results.html', {'docs':results, 'meta':meta}, context_instance=RequestContext(request))
    else:
        return render_to_response('idrfc/search_main.html', {'form':form, 'docs':results,'meta':meta}, context_instance=RequestContext(request))
        

def search_main(request):
    form = SearchForm()
    return render_to_response('idrfc/search_main.html', {'form':form}, context_instance=RequestContext(request))

def by_ad(request, name):
    ad_id = None
    ad_name = None
    for i in IESGLogin.objects.all():
        iname = str(i).lower().replace(' ','.')
        if name == iname:
            ad_id = i.id
            ad_name = str(i)
            break
    if not ad_id:
        raise Http404
    form = SearchForm(request.REQUEST)
    if form.is_valid():
        pass
    form.clean_data['ad'] = ad_id
    form.clean_data['activeDrafts'] = True
    form.clean_data['rfcs'] = True
    form.clean_data['oldDrafts'] = True
    (results,meta) = search_query(form.clean_data)

    results.sort(key=lambda obj: obj.view_sort_key_byad())
    return render_to_response('idrfc/by_ad.html', {'form':form, 'docs':results,'meta':meta, 'ad_name':ad_name}, context_instance=RequestContext(request))


