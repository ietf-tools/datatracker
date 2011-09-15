# Copyright The IETF Trust 2011, All Rights Reserved

import re, os
from django import forms
from django.shortcuts import render_to_response, redirect
from django.db.models import Q
from django.template import RequestContext
from django.views.decorators.cache import cache_page
from django.http import Http404, HttpResponse, HttpResponseBadRequest, HttpResponsePermanentRedirect
from redesign.doc.models import Document
from redesign.name.models import GroupStateName, CharterDocStateName
from redesign.group.models import Group
from redesign.person.models import Person, Email
from django.conf import settings
from django.utils import simplejson

class SearchForm(forms.Form):
    nameacronym = forms.CharField(required=False)

    inprocess = forms.BooleanField(required=False,initial=True)
    active = forms.BooleanField(required=False,initial=False)

    by = forms.ChoiceField(choices=[(x,x) for x in ('acronym','state','ad','area','anyfield', 'eacronym')], required=False, initial='wg', label='Foobar')
    state = forms.ModelChoiceField(GroupStateName.objects.all(), label="WG state", empty_label="any state", required=False)
    charter_state = forms.ModelChoiceField(CharterDocStateName.objects.all(), label="Charter state", empty_label="any state", required=False)
    ad = forms.ChoiceField(choices=(), required=False)
    area = forms.ModelChoiceField(Group.objects.filter(type="area", state="active").order_by('name'), empty_label="any area", required=False)
    anyfield= forms.CharField(required=False)
    eacronym = forms.CharField(required=False)
        
    def __init__(self, *args, **kwargs):
        super(SearchForm, self).__init__(*args, **kwargs)
        responsible = Document.objects.values_list('ad', flat=True).distinct()
        active_ads = list(Person.objects.filter(email__role__name="ad",
                                                email__role__group__type="area",
                                                email__role__group__state="active").distinct())
        inactive_ads = list(Person.objects.filter(pk__in=responsible)
                            .exclude(pk__in=[x.pk for x in active_ads]))
        extract_last_name = lambda x: x.name_parts()[3]
        active_ads.sort(key=extract_last_name)
        inactive_ads.sort(key=extract_last_name)
        
        self.fields['ad'].choices = c = [('', 'any AD')] + [(ad.pk, ad.name) for ad in active_ads] + [('', '------------------')] + [(ad.pk, ad.name) for ad in inactive_ads]
        
    def clean_nameacronym(self):
        value = self.cleaned_data.get('nameacronym','')
        return value
    def clean(self):
        q = self.cleaned_data
        # Reset query['by'] if needed
        for k in ('ad', 'area', 'anyfield', 'eacronym'):
            if (q['by'] == k) and not q[k]:
                q['by'] = None
        if (q['by'] == 'state') and not (q['state'] or q['charter_state']):
            q['by'] = None
        # Reset other fields
        for k in ('ad', 'area', 'anyfield', 'eacronym'):
            if q['by'] != k:
                self.data[k] = ""
                q[k] = ""
        if q['by'] != 'state':
            self.data['state'] = ""
            self.data['charter_state'] = ""
            q['state'] = ""
            q['charter_state'] = ""
        return q
                                                                        
def search_query(query_original, sort_by=None):
    query = dict(query_original.items())

    # Non-ASCII strings don't match anything; this check
    # is currently needed to avoid complaints from MySQL.
    for k in ['nameacronym','anyfield','eacronym']:
        try:
            tmp = str(query.get(k, ''))
        except:
            query[k] = '*NOSUCH*'

    # Search 
    MAX = 500
    maxReached = False

    if query["inprocess"]:
        if query["active"]:
            results = Group.objects.filter(type="wg")
        else:
            results = Group.objects.filter(type="wg").exclude(charter__charter_state__slug="approved")
    else:
        if query["active"]:
            results = Group.objects.filter(type="wg", charter__charter_state__slug="approved")
        else:
            raise Http404 # Empty, prevented by js

    prefix = ""
    q_objs = []
    # name
    if query["nameacronym"]:
        results = results.filter(Q(name__icontains=query["nameacronym"]) | Q(acronym__icontains=query["nameacronym"]))
    # radio choices
    by = query["by"]
    if by == "state":
        q_objs = []
        if query['state']:
            q_objs.append(Q(state=query['state']))
        if query['charter_state']:
            q_objs.append(Q(charter__charter_state=query['charter_state']))
        results = results.filter(*q_objs)
    elif by == "ad":
        results = results.filter(ad=query["ad"])
    elif by == "area":
        results = results.filter(parent=query["area"])
    elif by == "anyfield":
        q_obj = Q()
        q_obj |= Q(state__name__icontains=query['anyfield'])
        q_obj |= Q(charter__charter_state__name__icontains=query['anyfield'])
        q_obj |= Q(ad__name__icontains=query['anyfield'])
        q_obj |= Q(parent__name__icontains=query['anyfield'])
        q_obj |= Q(history_set__acronym__icontains=query['anyfield'])
        results = list(results.filter(q_obj))
        # Search charter texts
        m = re.compile(query['anyfield'], re.IGNORECASE)
        if query['name']:
            file_set = Group.objects.filter(type="wg", name__icontains=query["name"])
        else:
            file_set = Group.objects.filter(type="wg")
        for g in file_set:
            charter = g.charter
            if charter:
                try:
                    file = open(os.path.join(charter.get_file_path(), charter.name+"-"+charter.rev+".txt"))
                    for line in file:
                        if m.search(line):
                            results.append(g)
                            break
                except IOError:
                    pass # Pass silently for files not found
    elif by == "eacronym":
        results = results.filter(history_set__acronym__icontains=query["eacronym"]).distinct()

    results = list(results[:MAX])
    if len(results) == MAX:
        maxReached = True
    
    # sort
    def sort_key(g):
        res = []
        
        if sort_by == "acronym":
            res.append(g.acronym)
        elif sort_by == "name":
            res.append(g.name)
        elif sort_by == "date":
            res.append(str(g.time or datetime.date(1990, 1, 1)))
        elif sort_by == "status":
            res.append(g.charter.charter_state)

        return res
                
    results.sort(key=sort_key)

    meta = {}
    if maxReached:
        meta['max'] = MAX
    if query['by']:
        meta['advanced'] = True
    return (results,meta)

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
    meta['hdrs'] = [{'htitle': 'Acronym', 'htype':'acronym'},
                    {'htitle': 'Name', 'htype':'name'},
                    {'htitle': 'Date', 'htype':'date'},
                    {'htitle': 'Status', 'htype':'status', 'colspan':'2'},
                    ]
    if 'ajax' in request.REQUEST and request.REQUEST['ajax']:
        return render_to_response('wgrecord/search_results.html', {'recs':results, 'meta':meta}, context_instance=RequestContext(request))
    elif len(results)==1:
        wg = results[0]
        return redirect('wg_view_record', name=wg.acronym)
    else:
        return render_to_response('wgrecord/search_main.html', {'form':form, 'recs':results,'meta':meta}, context_instance=RequestContext(request))
        

def search_main(request):
    form = SearchForm()
    return render_to_response('wgrecord/search_main.html', {'form':form}, context_instance=RequestContext(request))

def by_ad(request, name):
    ad_id = None
    ad_name = None
    for p in Person.objects.filter(email__role__name__in=("ad", "ex-ad")):
        if name == p.name.lower().replace(" ", "."):
            ad_id = p.id
            ad_name = p.name
            break
    if not ad_id:
        raise Http404
    form = SearchForm({'by':'ad','ad':ad_id})
    if not form.is_valid():
        raise ValueError("form did not validate")
    (results,meta) = search_query(form.cleaned_data)
    meta['searching'] = True
    meta['by'] = form.cleaned_data['by']
    meta['rqps'] = generate_query_string(request, ['sortBy'])
    # With a later Django we can do this from the template (incude with tag)
    # Pass the headers and their sort key names
    meta['hdrs'] = [{'htitle': 'Acronym', 'htype':'acronym'},
                    {'htitle': 'Name', 'htype':'name'},
                    {'htitle': 'Date', 'htype':'date'},
                    {'htitle': 'Status', 'htype':'status', 'colspan':'2'},
                    ]
    results.sort(key=lambda g: str(g.time or datetime.date(1990, 1, 1)), reverse=True)
    return render_to_response('wgrecord/by_ad.html', {'form':form, 'recs':results,'meta':meta, 'ad_name':ad_name}, context_instance=RequestContext(request))

def in_process(request):
    results = Group.objects.filter(type="wg", 
                                   charter__charter_state__in=['infrev', 'intrev', 'extrev', 'iesgrev']).order_by('-time')
    meta = {}
    meta['searching'] = True
    meta['by'] = 'state'
    meta['rqps'] = generate_query_string(request, ['sortBy'])
    # With a later Django we can do this from the template (incude with tag)
    # Pass the headers and their sort key names
    meta['hdrs'] = [{'htitle': 'Acronym', 'htype':'acronym'},
                    {'htitle': 'Name', 'htype':'name'},
                    {'htitle': 'Date', 'htype':'date'},
                    {'htitle': 'Status', 'htype':'status', 'colspan':'2'},
                    ]
    return render_to_response('wgrecord/in_process.html', {'recs':results,'meta':meta}, context_instance=RequestContext(request))

def json_emails(list):
        result = []
        for p in list:
            result.append({"id": p.address + "", "name":p.person.name + " &lt;" + p.address + "&gt;"})
        return simplejson.dumps(result)

def search_person(request):
    if request.method == 'GET':
        emails = Email.objects.filter(person__name__istartswith=request.GET.get('q','')).order_by('person__name')
        return HttpResponse(json_emails(emails), mimetype='application/json')
