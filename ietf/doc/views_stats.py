import datetime

from django.core.cache import cache
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
    title += get_doctypes(queryargs)
    title += ' Revisions'
    # radio choices
    by = queryargs.get('by')
    if by == "author":
        title += ' with author "%s"' % queryargs['author'].title()
    elif by == "group":
        title += ' for %s' % queryargs['group'].capitalize()
    elif by == "area":
        title += ' in %s Area' % queryargs['area'].upper()
    elif by == "ad":
        title += ' with AD %s' % Person.objects.get(id=queryargs['ad'])
    elif by == "state":
        title += ' in state %s::%s' % (queryargs['state'], queryargs['substate'])
    elif by == "stream":
        title += ' in stream %s' % queryargs['stream']
    name = queryargs.get('name')
    if name:
        title += ' matching "%s"' % name
    title += ' over Time'
    return title

def doc_stats_newrevisiondocevent(request):
    return render_to_response("doc/stats/highstock.html", {
            "title": "Document Statistics",
            "dataurl": "/doc/stats/data/newrevisiondocevent",
            "queryargs": request.GET.urlencode(),
            },
        context_instance=RequestContext(request))

@cache_page(60*15)
def doc_stats_data_newrevisiondocevent(request):
#    debug.mark()
    queryargs = request.GET
#    debug.lap('got queryargs')
    key = get_search_cache_key(queryargs)
#    debug.lap('got cache key')
    searchresult = cache.get(key)
#    debug.lap('did cache lookup')
    if not searchresult:
#        debug.say('doing new search')
        form = SearchForm(queryargs)
#        debug.lap('set up search form')
        if not form.is_valid():
            return HttpResponseBadRequest("form not valid: %s" % form.errors)
        searchresult = retrieve_search_results(form)
#        debug.lap('got search result')
        cache.set(key, searchresult)
#        debug.lap('cached search result')

    results, meta, qs = searchresult
    events = ( DocEvent.objects.filter(doc__in=qs, type='new_revision')
                                .order_by('date')
                                .extra(select={'date': 'date(doc_docevent.time)'})
                                .values('date')
                                .annotate(count=Count('id')))
#    debug.lap('got event query')
    event_list = list(events)
#    debug.lap('got event list')
    points = [ ((e['date'].toordinal()-epochday)*1000*60*60*24, e['count']) for e in event_list ]
#    debug.lap('got event points')
    counts = dict(points)
#    debug.lap('got points dictionary')
    day_ms = 1000*60*60*24
    days = range(points[0][0], points[-1][0]+day_ms, day_ms)
#    debug.lap('got days array')
    data = [ (d, counts[d] if d in counts else 0) for d in days ]
#    debug.lap('merged points into days')
    info = {

                "chart": {
                    "type": 'column'
                },

                "rangeSelector" : {
                    "selected": 4,
                    "allButtonsEnabled": True,
                },
                "title" : {
                    "text" : make_title(queryargs)
                },
                "credits": {
                    "enabled": False,
                },
                "series" : [{
                    "name" : "Submitted %s"%get_doctypes(queryargs, pluralize=True),
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
#    debug.clock('set up info dict')
    return JsonResponse(info)


