# Copyright The IETF Trust 2016, All Rights Reserved

import copy
import datetime

from django.conf import settings
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

column_chart_conf = settings.CHART_TYPE_COLUMN_OPTIONS

def dt(s):
    "Convert the date string returned by sqlite's date() to a datetime.date"
    ys, ms, ds = s.split('-')
    return datetime.date(int(ys), int(ms), int(ds))

def model_to_timeline_data(model, field='time', **kwargs):
    """Takes a Django model and a set of queryset filter arguments, and
    returns a dictionary with highchart settings and data, suitable as
    a JsonResponse() argument.  The model must have a DateTimeField field.
    If the time field is named something else than 'time', the name must
    be supplied."""
    assert field in model._meta.get_all_field_names()

    objects = ( model.objects.filter(**kwargs)
                                .order_by('date')
                                .extra(select={'date': 'date(%s.%s)'% (model._meta.db_table, field) })
                                .values('date')
                                .annotate(count=Count('id')))
    if objects.exists():
        obj_list = list(objects)
        # This is needed for sqlite, when we're running tests:
        if type(obj_list[0]['date']) != datetime.date:
            obj_list = [ {'date': dt(e['date']), 'count': e['count']} for e in obj_list ]
        today = datetime.date.today()
        if not obj_list[-1]['date'] == today:
            obj_list += [ {'date': today, 'count': 0} ]
        data = [ ((e['date'].toordinal()-epochday)*1000*60*60*24, e['count']) for e in obj_list ]
    else:
        data = []

    return data

    

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
        title += ' with author %s' % queryargs['author'].title()
    elif by == "group":
        group = queryargs.get('group')
        if group:
            title += ' for %s' % group.capitalize()
    elif by == "area":
        area = queryargs.get('area')
        if area:
            title += ' in %s Area' % area.upper()
    elif by == "ad":
        ad_id = queryargs.get('ad')
        if ad_id:
            title += ' with AD %s' % Person.objects.get(id=ad_id)
    elif by == "state":
        state = queryargs.get('state')
        if state:
            title += ' in state %s::%s' % (state, queryargs['substate'])
    elif by == "stream":
        stream = queryargs.get('stream')
        if stream:
            title += ' in stream %s' % stream
    name = queryargs.get('name')
    if name:
        title += ' with name matching "%s"' % name
    return title

def chart_newrevisiondocevent(request):
    return render_to_response("doc/stats/highstock.html", {
            "title": "Document Statistics",
            "confurl": urlreverse("ietf.doc.views_stats.chart_conf_newrevisiondocevent"),
            "dataurl": urlreverse("ietf.doc.views_stats.chart_data_newrevisiondocevent"),
            "queryargs": request.GET.urlencode(),
            },
        context_instance=RequestContext(request))

#@cache_page(60*15)
def chart_data_newrevisiondocevent(request):
    queryargs = request.GET
    if queryargs:
        key = get_search_cache_key(queryargs)
        results = cache.get(key)
        if not results:
            form = SearchForm(queryargs)
            if not form.is_valid():
                return HttpResponseBadRequest("form not valid: %s" % form.errors)
            results = retrieve_search_results(form)
            if results.exists():
                cache.set(key, results)
        if results.exists():
            data = model_to_timeline_data(DocEvent, doc__in=results, type='new_revision')
        else:
            data = []
    else:
        data = []
    return JsonResponse(data, safe=False)


@cache_page(60*15)
def chart_conf_newrevisiondocevent(request):
    queryargs = request.GET
    if queryargs:
        conf = copy.deepcopy(settings.CHART_TYPE_COLUMN_OPTIONS)
        conf['title']['text'] = make_title(queryargs)
        conf['series'][0]['name'] = "Submitted %s" % get_doctypes(queryargs, pluralize=True).lower(),
    else:
        conf = {}
    return JsonResponse(conf)


@cache_page(60*15)
def chart_conf_person_drafts(request, id):
    person = Person.objects.filter(id=id).first()
    if not person:
        conf = {}
    else:
        conf = copy.deepcopy(settings.CHART_TYPE_COLUMN_OPTIONS)
        conf['title']['text'] = "New draft revisions over time for %s" % person.name
        conf['series'][0]['name'] = "Submitted drafts" 
    return JsonResponse(conf)

@cache_page(60*15)
def chart_data_person_drafts(request, id):
    person = Person.objects.filter(id=id).first()
    if not person:
        data = []
    else:
        data = model_to_timeline_data(DocEvent, doc__authors__person=person, type='new_revision')
    return JsonResponse(data, safe=False)
    

