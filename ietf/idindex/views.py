# Copyright The IETF Trust 2007, All Rights Reserved

# Portions Copyright (C) 2009 Nokia Corporation and/or its subsidiary(-ies).
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

from django.http import HttpResponse, HttpResponsePermanentRedirect
from django.views.generic.list_detail import object_list
from django.db.models import Q
from django.http import Http404
from django.template import RequestContext, loader
from django.shortcuts import render_to_response, get_object_or_404
from django.core.urlresolvers import reverse
from django.views.generic.list_detail import object_detail
from ietf.idtracker.models import Acronym, IETFWG, InternetDraft, Rfc, IDInternal
from ietf.idindex.forms import IDIndexSearchForm
from ietf.idindex.models import alphabet, orgs, orgs_dict
from ietf.utils import orl, flattenl, normalize_draftname

base_extra = { 'alphabet': alphabet, 'orgs': orgs }

def wgdocs_redir(request, id):
    group = get_object_or_404(Acronym, acronym_id=id)
    return HttpResponsePermanentRedirect(reverse(wgdocs, urlconf="ietf.idindex.urls", args=[group.acronym]))

def wgdocs(request, wg):
    try:
	group = Acronym.objects.get(acronym=wg)
    except Acronym.DoesNotExist:	# try a search
	if wg == 'other':
	    queryset = IETFWG.objects.filter(
		orl([Q(group_acronym__acronym__istartswith="%d" % i) for i in range(0,10)])
		)
	else:
	    queryset = IETFWG.objects.filter(group_acronym__acronym__istartswith=wg)
	queryset = queryset.filter(group_type__type='WG').select_related().order_by('status', 'acronym.acronym')
	extra = base_extra.copy()
	extra['search'] = wg
	return object_list(request, queryset=queryset, template_name='idindex/wglist.html', allow_empty=True, extra_context=extra)
    queryset = InternetDraft.objects.filter(group__acronym=wg)
    queryset = queryset.order_by('status', 'filename')
    extra = base_extra.copy()
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
    extra = base_extra.copy()
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
    queryset = queryset.order_by('status','filename')
    extra = base_extra.copy()
    extra['category'] = cat
    return object_list(request, queryset=queryset, template_name='idindex/otherdocs.html', allow_empty=True, extra_context=extra)

def showdocs(request, cat=None):
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
    sortby = request.GET.get('sort', 'name')
    if not(sortmap.has_key(sortby)):
	sortby = 'name'
    queryset = InternetDraft.objects.all()
    if catmap[cat].has_key('query'):
	queryset = queryset.filter(catmap[cat]['query'])
    queryset = queryset.order_by(*list(['status'] + sortmap[sortby]['fields']))
    extra = catmap[cat]['extra']
    extra['sort_header'] = sortmap[sortby]['header']
    extra.update(base_extra)
    return object_list(request, queryset=queryset, template_name='idindex/showdocs.html', allow_empty=True, extra_context=extra)


def search(request):
    args = request.GET.copy()
    if args.has_key('filename'):
	args['filename'] = normalize_draftname(args['filename'])
    form = IDIndexSearchForm()
    t = loader.get_template('idindex/search.html')
    # if there's a query, do the search and supply results to the template
    searching = False
    qdict = { 'filename': 'filename__icontains',
	      'id_tracker_state_id': 'idinternal__cur_state',
	      'wg_id': 'group',
	      'status_id': 'status',
	      'last_name': 'authors__person__last_name__icontains',
	      'first_name': 'authors__person__first_name__icontains',
	    }
    for key in qdict.keys() + ['other_group']:
	if key in args:
	    searching = True
    if searching:
	# '0' and '-1' are flag values for "any"
	# in the original .cgi search page.
	# They are compared as strings because the
	# query dict is always strings.
	q_objs = [Q(**{qdict[k]: args[k]})
		for k in qdict.keys()
		if args.get(k, '') != '' and
		   args[k] != '0' and
		   args[k] != '-1']
	try:
	    other = orgs_dict[args['other_group']]
	    q_objs += [orl(
		[Q(filename__istartswith="draft-%s-" % p)|
		 Q(filename__istartswith="draft-ietf-%s-" % p)
		    for p in other.get('prefixes', [ other['key'] ])])]
	except KeyError:
	    pass	# either no other_group arg or no orgs_dict entry
	matches = InternetDraft.objects.all().filter(*q_objs)
	matches = matches.order_by('status', 'filename')
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
    tracker_list = InternetDraft.objects.all().filter(id_document_tag__in=in_tracker).order_by('status','filename').select_related(depth=1)
    object_list = []
    for o in tracker_list:
	object_list.append({'tracker': True, 'id': o})
    notracker_list = InternetDraft.objects.all().exclude(id_document_tag__in=in_tracker).order_by('status','filename').select_related(depth=1)
    for o in notracker_list:
	object_list.append({'tracker': False, 'id': o})
    return render_to_response(template_name, {'object_list': object_list},
		context_instance=RequestContext(request))

def all_id_txt():
    all_ids = InternetDraft.objects.order_by('filename')
    in_track_ids = all_ids.filter(idinternal__rfc_flag=0).exclude(idinternal__cur_state__in=IDInternal.INACTIVE_STATES)
    exclude_ids = [item.id_document_tag for item in in_track_ids]
    not_in_track = all_ids.exclude(id_document_tag__in=exclude_ids)
    active = not_in_track.filter(status__status_id=IDInternal.ACTIVE)
    published = not_in_track.filter(status__status_id=IDInternal.PUBLISHED)
    expired = not_in_track.filter(status__status_id=IDInternal.EXPIRED)
    withdrawn_submitter = not_in_track.filter(status__status_id=IDInternal.WITHDRAWN_SUBMITTER)
    withdrawn_ietf = not_in_track.filter(status__status_id=IDInternal.WITHDRAWN_IETF)
    replaced = not_in_track.filter(status__status_id=IDInternal.REPLACED)

    return loader.render_to_string("idindex/all_ids.txt",
                                   { 'in_track_ids':in_track_ids,
                                     'active':active,
                                     'published':published,
                                     'expired':expired,
                                     'withdrawn_submitter':withdrawn_submitter,
                                     'withdrawn_ietf':withdrawn_ietf,
                                     'replaced':replaced})

def id_index_txt():
    groups = IETFWG.objects.all()
    return loader.render_to_string("idindex/id_index.txt", {'groups':groups})

def id_abstracts_txt():
    groups = IETFWG.objects.all()
    return loader.render_to_string("idindex/id_abstracts.txt", {'groups':groups})

def test_all_id_txt(request):
    return HttpResponse(all_id_txt(), mimetype='text/plain')
def test_id_index_txt(request):
    return HttpResponse(id_index_txt(), mimetype='text/plain')
def test_id_abstracts_txt(request):
    return HttpResponse(id_abstracts_txt(), mimetype='text/plain')

def related_docs(startdoc):
    related = []
    processed = []

    def handle(otherdoc,status,doc,skip=(0,0,0)):
        new = (otherdoc, status, doc)
    	if otherdoc in processed:
	    return
	related.append(new)
	process(otherdoc,skip)

    def process(doc, skip=(0,0,0)):
	processed.append(doc)
	if type(doc) == InternetDraft:
	    if doc.replaced_by_id != 0 and not(skip[0]):
		handle(doc.replaced_by, "that replaces", doc, (0,1,0))
	    if not(skip[1]):
		for replaces in doc.replaces_set.all():
		    handle(replaces, "that was replaced by", doc, (1,0,0))
	    if doc.rfc_number != 0 and not(skip[0]):
		# should rfc be an FK in the model?
		try:
		    handle(Rfc.objects.get(rfc_number=doc.rfc_number), "which came from", doc, (1,0,0))
		# In practice, there are missing rows in the RFC table.
		except Rfc.DoesNotExist:
		    pass
	if type(doc) == Rfc:
	    if not(skip[0]):
		try:
		    draft = InternetDraft.objects.get(rfc_number=doc.rfc_number)
		    handle(draft, "that was published as", doc, (0,0,1))
		except InternetDraft.DoesNotExist:
		    pass
		# The table has multiple documents published as the same RFC.
		# This raises an AssertionError because using get
		# presumes there is exactly one.
		except AssertionError:
		    pass
	    if not(skip[1]):
		for obsoleted_by in doc.updated_or_obsoleted_by.all():
		    handle(obsoleted_by.rfc, "that %s" % obsoleted_by.action.lower(), doc)
	    if not(skip[2]):
		for obsoletes in doc.updates_or_obsoletes.all():
		    handle(obsoletes.rfc_acted_on, "that was %s by" % obsoletes.action.lower().replace("tes", "ted"), doc)

    process(startdoc, (0,0,0))
    return related

def redirect_related(request, id):
    doc = get_object_or_404(InternetDraft, id_document_tag=id)
    return HttpResponsePermanentRedirect(reverse(view_related_docs, urlconf="ietf.idindex.urls", args=[doc.filename]))

def view_related_docs(request, slug):
    startdoc = get_object_or_404(InternetDraft, filename=slug)
    related = related_docs(startdoc)
    context = {'related': related, 'numdocs': len(related), 'startdoc': startdoc}
    context.update(base_extra)
    return render_to_response("idindex/view_related_docs.html", context,
		context_instance=RequestContext(request))

def redirect_id(request, object_id):
    '''Redirect from historical document ID to preferred filename url.'''
    doc = get_object_or_404(InternetDraft, id_document_tag=object_id)
    return HttpResponsePermanentRedirect(reverse(view_id, args=[doc.filename]))

# Wrapper around object_detail to give permalink a handle.
# The named-URLs feature in django 0.97 will eliminate the
# need for these.
def view_id(*args, **kwargs):
    return object_detail(*args, **kwargs)
