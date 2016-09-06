import datetime

from django.core.cache import cache
from django.core.urlresolvers import reverse as urlreverse
from django.db.models.aggregates import Count
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.views.decorators.cache import cache_page

import debug                            # pyflakes:ignore

from ietf.doc.models import DocEvent
from ietf.doc.templatetags.ietf_filters import comma_separated_list
from ietf.doc.utils import get_search_cache_key
from ietf.doc.views_search import SearchForm, retrieve_search_results
from ietf.name.models import DocTypeName
from ietf.person.models import Person

epochday = datetime.datetime.utcfromtimestamp(0).date().toordinal()

def ms(t):
    return (t.toordinal() - epochday)*1000*60*60*24

def get_doctypes(queryargs, pluralize=False):
    doctypes = []
    if (   queryargs.get('rfcs') == 'on'
        or queryargs.get('activedrafts') == 'on'
        or queryargs.get('olddrafts') == 'on'):
            if pluralize:
                doctypes.append('Drafts')
            else:
                doctypes.append('Draft')
    alltypes = DocTypeName.objects.exclude(slug__in='draft').order_by('name');
    for doctype in alltypes:
        if 'include-' + doctype.slug in queryargs:
            name = doctype.name
            if pluralize and not name.endswith('s'):
                name += 's'
            doctypes.append(name)
    return comma_separated_list(doctypes)

def make_title(queryargs):
    title = 'New '
    title += get_doctypes(queryargs).lower()
    title += ' revisions'
    # radio choices
    by = queryargs.get('by')
    if by == "author":
        title += ' with author "%s"' % queryargs['author'].title()
    elif by == "group":
        group = queryargs['group']
        if group:
            title += ' for %s' % group.capitalize()
    elif by == "area":
        area = queryargs['area']
        if area:
            title += ' in %s Area' % area.upper()
    elif by == "ad":
        ad_id = queryargs['ad']
        if ad_id:
            title += ' with AD %s' % Person.objects.get(id=ad_id)
    elif by == "state":
        state = queryargs['state']
        if state:
            title += ' in state %s::%s' % (state, queryargs['substate'])
    elif by == "stream":
        stream = queryargs['stream']
        if stream:
            title += ' in stream %s' % stream
    name = queryargs.get('name')
    if name:
        title += ' with name matching "%s"' % name
    return title

def chart_newrevisiondocevent(request):
    return render_to_response("doc/stats/highstock.html", {
            "title": "Document Statistics",
            "dataurl": urlreverse("ietf.doc.views_stats.chart_data_newrevisiondocevent"),
            "queryargs": request.GET.urlencode(),
            },
        context_instance=RequestContext(request))

def dt(s):
    "convert the string from sqlite's date() to a datetime.date"
    ys, ms, ds = s.split('-')
    return datetime.date(int(ys), int(ms), int(ds))

def model_to_timeline(model, **kwargs):
    """Takes a Django model and a set of queryset filter arguments, and
    returns a dictionary with highchart settings and data, suitable as
    a JsonResponse() argument.  The model must have a time field."""
    #debug.pprint('model._meta.fields')
    assert 'time' in model._meta.get_all_field_names()

    objects = ( model.objects.filter(**kwargs)
                                .order_by('date')
                                .extra(select={'date': 'date(doc_docevent.time)'})
                                .values('date')
                                .annotate(count=Count('id')))
    if objects.exists():
        # debug.lap('got event query')
        obj_list = list(objects)
        # debug.lap('got event list')
        # This is needed for sqlite, when we're running tests:
        if type(obj_list[0]['date']) != datetime.date:
            # debug.say('converting string dates to datetime.date')
            obj_list = [ {'date': dt(e['date']), 'count': e['count']} for e in obj_list ]
        points = [ ((e['date'].toordinal()-epochday)*1000*60*60*24, e['count']) for e in obj_list ]
        # debug.lap('got event points')
        counts = dict(points)
        # debug.lap('got points dictionary')
        day_ms = 1000*60*60*24
        days = range(points[0][0], points[-1][0]+day_ms, day_ms)
        # debug.lap('got days array')
        data = [ (d, counts[d] if d in counts else 0) for d in days ]
        # debug.lap('merged points into days')
    else:
        data = []

    info = {
        "chart": {
            "type": 'column'
        },
        "rangeSelector" : {
            "selected": 4,
            "allButtonsEnabled": True,
        },
        "title" : {
            "text" : "%s items over time" % model._meta.model_name
        },
        "credits": {
            "enabled": False,
        },
        "series" : [{
            "name" : "Items",
            "type" : "column",
            "data" : data,
            "dataGrouping": {
                "units": [[
                    'week',                                 # unit name
                    [1,],                                   # allowed multiples
                ], [
                    'month',
                    [1, 4,],
                ]]
            },
            "turboThreshold": 1, # Only check format of first data point. All others are the same
            "pointInterval": 24*60*60*1000,
            "pointPadding": 0.05,
        }]
    }   
    return info

    

@cache_page(60*15)
def chart_data_newrevisiondocevent(request):
    # debug.mark()
    queryargs = request.GET
    if queryargs:
        # debug.lap('got queryargs')
        key = get_search_cache_key(queryargs)
        # debug.lap('got cache key')
        results = cache.get(key)
        # debug.lap('did cache lookup')
        if not results:
            # debug.say('doing new search')
            form = SearchForm(queryargs)
            # debug.lap('set up search form')
            if not form.is_valid():
                return HttpResponseBadRequest("form not valid: %s" % form.errors)
            results = retrieve_search_results(form)
            # debug.lap('got search result')
            if results.exists():
                cache.set(key, results)
                # debug.lap('cached search result')
        if results.exists():
            info = model_to_timeline(DocEvent, doc__in=results, type='new_revision')
            info['title']['text'] = make_title(queryargs)
            info['series'][0]['name'] = "Submitted %s" % get_doctypes(queryargs, pluralize=True).lower(),
        else:
            info = {}
        # debug.clock('set up info dict')
    else:
        info = {}
    return JsonResponse(info)


@cache_page(60*15)
def chart_data_person_drafts(request, id):
    # debug.mark()
    person = Person.objects.filter(id=id).first()
    if not person:
        info = {}
    else:
        info = model_to_timeline(DocEvent, doc__authors__person=person, type='new_revision')
        info['title']['text'] = "New draft revisions over time for %s" % person.name
        info['series'][0]['name'] = "Submitted drafts" 
    return JsonResponse(info)
    

