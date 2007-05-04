from django.http import HttpResponse,HttpResponseRedirect
from django.views.generic.list_detail import object_list
from django.db.models import Q
from django.http import Http404
from django.template import RequestContext, Context, loader
from django.shortcuts import render_to_response
from ietf.idtracker.models import Acronym, GroupIETF, InternetDraft
from ietf.idindex.forms import IDIndexSearchForm
from ietf.idindex.models import alphabet, orgs, orgs_dict
from ietf.utils import orl, flattenl

base_extra = { 'alphabet': alphabet, 'orgs': orgs }

def wglist(request, wg=None):
    if wg == 'other':
        queryset = GroupIETF.objects.filter(
	    orl([Q(group_acronym__acronym__istartswith="%d" % i) for i in range(0,10)])
	    )
    else:
	queryset = GroupIETF.objects.filter(group_acronym__acronym__istartswith=wg)
    queryset = queryset.filter(group_type__type='WG').select_related().order_by('g_status.status', 'acronym.acronym')
    return object_list(request, queryset=queryset, template_name='idindex/wglist.html', allow_empty=True, extra_context=base_extra)

def wgdocs(request, **kwargs):
    if kwargs.has_key('id'):
	queryset = InternetDraft.objects.filter(group=kwargs['id'])
	group = Acronym.objects.get(acronym_id=kwargs['id'])
    else:
        queryset = InternetDraft.objects.filter(group__acronym=kwargs['slug'])
	group = Acronym.objects.get(acronym=kwargs['slug'])
    queryset = queryset.order_by('status_id', 'filename')
    extra = base_extra
    extra['group'] = group
    return object_list(request, queryset=queryset, template_name='idindex/wgdocs.html', allow_empty=True, extra_context=extra)

def inddocs(request, filter=None):
    ind_exception = orl(
	[Q(filename__istartswith='draft-%s-' % e) for e in
	    flattenl([org.get('prefixes', [ org['key'] ]) for org in orgs]) + ['ietf']])
    if filter == 'other':
        queryset = InternetDraft.objects.filter(
	    orl([Q(filename__istartswith="draft-%d" % i) for i in range(0,10)])
	    )
    else:
	queryset = InternetDraft.objects.filter(filename__istartswith='draft-' + filter)
    queryset = queryset.exclude(ind_exception).filter(group__acronym='none').order_by('filename')
    extra = base_extra
    extra['filter'] = filter
    return object_list(request, queryset=queryset, template_name='idindex/inddocs.html', allow_empty=True, extra_context=extra)

def otherdocs(request, cat=None):
    try:
	org = orgs_dict[cat]
    except KeyError:
	raise Http404
    queryset = InternetDraft.objects.filter(
	orl([Q(filename__istartswith="draft-%s-" % p)|
	     Q(filename__istartswith="draft-ietf-%s-" % p)
		for p in org.get('prefixes', [ org['key'] ])]))
    queryset = queryset.order_by('filename')
    extra = base_extra
    extra['category'] = cat
    return object_list(request, queryset=queryset, template_name='idindex/otherdocs.html', allow_empty=True, extra_context=extra)

def showdocs(request, cat=None, sortby=None):
    catmap = {
	'all': { 'extra': { 'header': 'All' } },
	'current': { 'extra': { 'header': 'Current', 'norfc': 1 },
		     'query': Q(status__status="Active") },
	'rfc': { 'extra': { 'header': 'Published' },
		 'query': Q(status__status="RFC") },
	'dead': { 'extra': { 'header': "Expired/Withdrawn/Replaced", 'norfc': 1 },
		  'query': Q(status__in=[2,4,5,6]) },	# Using the words seems fragile here for some reason
	}
    if not(catmap.has_key(cat)):
	raise Http404
    sortmap = { 'date': { 'header': "Submission Date",
			  'fields': ['revision_date','filename'] },
	        'name': { 'header': "Filename",
			  'fields': ['filename'] },
		'': { 'header': "WHA?",
			'fields': ['filename'] },
	}
    if sortby is None:
	sortby = 'name'
    queryset = InternetDraft.objects.all()
    if catmap[cat].has_key('query'):
	queryset = queryset.filter(catmap[cat]['query'])
    queryset = queryset.order_by(*list(['status_id'] + sortmap[sortby]['fields']))
    extra = catmap[cat]['extra']
    extra['sort_header'] = sortmap[sortby]['header']
    extra.update(base_extra)
    return object_list(request, queryset=queryset, template_name='idindex/showdocs.html', allow_empty=True, extra_context=extra)


def search(request):
    form = IDIndexSearchForm()
    t = loader.get_template('idindex/search.html')
    # if there's a post, do the search and supply results to the template
    # XXX should handle GET too
    if request.method == 'POST':
	qdict = { 'filename': 'filename__icontains',
		  'id_tracker_state_id': 'idinternal__cur_state',
		  'wg_id': 'group',
		  'status_id': 'status',
		  'last_name': 'authors__person__last_name__icontains',
		  'first_name': 'authors__person__first_name__icontains',
		}
	q_objs = [Q(**{qdict[k]: request.POST[k]})
		for k in qdict.keys()
		if request.POST[k] != '']
	try:
	    other = orgs_dict[request.POST['other_group']]
	    q_objs += [orl(
		[Q(filename__istartswith="draft-%s-" % p)|
		 Q(filename__istartswith="draft-ietf-%s-" % p)
		    for p in other.get('prefixes', [ other['key'] ])])]
	except KeyError:
	    pass	# either no other_group arg or no orgs_dict entry
	matches = InternetDraft.objects.all().filter(*q_objs)
	matches = matches.order_by('filename')
	searched = True
    else:
	matches = None
        searched = False

    c = RequestContext(request, {
	'form': form,
	'object_list': matches,
	'didsearch': searched,
	'alphabet': alphabet,
	'orgs': orgs,
    })
    return HttpResponse(t.render(c))

def all_id(request, template_name):
    from django.db import connection
    from ietf.utils import flattenl
    cursor = connection.cursor()
    # 99 = Dead
    # 32 = RFC Published
    cursor.execute("SELECT id_document_tag FROM id_internal WHERE rfc_flag=0 AND cur_state NOT IN (99,32)")
    in_tracker = flattenl(cursor.fetchall())
    tracker_list = InternetDraft.objects.all().filter(id_document_tag__in=in_tracker).order_by('status_id','filename').select_related(depth=1)
    object_list = []
    for o in tracker_list:
	object_list.append({'tracker': True, 'id': o})
    notracker_list = InternetDraft.objects.all().exclude(id_document_tag__in=in_tracker).order_by('status_id','filename').select_related(depth=1)
    for o in notracker_list:
	object_list.append({'tracker': False, 'id': o})
    return render_to_response(template_name, {'object_list': object_list},
		context_instance=RequestContext(request))
