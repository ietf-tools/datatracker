# Copyright The IETF Trust 2007, All Rights Reserved

# Create your views here.
from django.http import HttpResponsePermanentRedirect
from django import forms
from django.template import RequestContext
from django.shortcuts import get_object_or_404, render_to_response
from django.db.models import Q
from django.views.generic.list_detail import object_detail, object_list
from ietf.idtracker.models import InternetDraft, IDInternal, IDState, IDSubState, Rfc, DocumentWrapper
from ietf.idtracker.forms import IDSearch
from ietf.utils import normalize_draftname
import re

def search(request):
    # for compatability with old tracker form, which has
    #  "all substates" = 6.
    args = request.GET.copy()
    if args.get('sub_state_id', '') == '6':
	args['sub_state_id'] = ''
    # "job_owner" of "0" means "All/Any"
    if args.get('search_job_owner', '') == '0':
	args['search_job_owner'] = ''
    if args.has_key('search_filename'):
	args['search_filename'] = normalize_draftname(args['search_filename'])
    form = IDSearch(args)
    # if there's a post, do the search and supply results to the template
    searching = False
    # filename, rfc_number, group searches are seperate because
    # they can't be represented as simple searches in the data model.
    qdict = { 
	      'search_job_owner': 'job_owner',
	      'search_cur_state': 'cur_state',
	      'sub_state_id': 'cur_sub_state',
	      'search_area_acronym': 'area_acronym',
	    }
    q_objs = []
    for k in qdict.keys() + ['search_group_acronym', 'search_rfcnumber', 'search_filename', 'search_status_id']:
	if args.has_key(k):
	    searching = True
	    if args[k] != '' and qdict.has_key(k):
		q_objs.append(Q(**{qdict[k]: args[k]}))
    if form.is_valid() == False:
	searching = False
    if searching:
        # Non-ASCII group/filename doesn't match anything; this check
        # is currently needed to avoid complaints from MySQL.
        for k in ['search_group_acronym','search_filename']:
            try:
                tmp = str(args.get(k, ''))
            except:
                args[k] = '*NOSUCH*'

        group = args.get('search_group_acronym', '')
	if group != '':
	    rfclist = [rfc['rfc_number'] for rfc in Rfc.objects.all().filter(group_acronym=group).values('rfc_number')]
	    draftlist = [draft['id_document_tag'] for draft in InternetDraft.objects.all().filter(group__acronym=group).values('id_document_tag')]
	    if rfclist or draftlist:
		q_objs.append(Q(draft__in=draftlist)&Q(rfc_flag=0)|Q(draft__in=rfclist)&Q(rfc_flag=1))
	    else:
		q_objs.append(Q(draft__isnull=True)) # no matches
        rfc_number = args.get('search_rfcnumber', '')
	if rfc_number != '':
	    draftlist = [draft['id_document_tag'] for draft in InternetDraft.objects.all().filter(rfc_number=rfc_number).values('id_document_tag')]
	    q_objs.append(Q(draft__in=draftlist)&Q(rfc_flag=0)|Q(draft=rfc_number)&Q(rfc_flag=1))
        filename = args.get('search_filename', '')
	if filename != '':
	    q_objs.append(Q(draft__filename__icontains=filename,rfc_flag=0))
	status = args.get('search_status_id', '')
	if status != '':
	    q_objs.append(Q(draft__status=status,rfc_flag=0))
	matches = IDInternal.objects.all().exclude(draft=999999).filter(*q_objs)
	matches = matches.order_by('cur_state', 'cur_sub_state', 'ballot', '-primary_flag')
        # sort by date in reverse
        # first build docstate groups, within which we sort
        # in each docstate group, we build ballot id groups, which we sort
        m1 = []                 # list of: docstate, list of: event date; ballot id; list of: ms for the ballot id
        for m in matches:
            if m1 and m1[-1][0] == m.docstate():
                if m1[-1][1] and m1[-1][1][0][1] == m.ballot_id:
                    m1[-1][1][0][4].append(m)
                else:
                    m1[-1][1].append((m.event_date, m.ballot_id, m.primary_flag, m.draft_id, [m]))
            else:
                m1.append((m.docstate(), [(m.event_date, m.ballot_id, m.primary_flag, m.draft_id, [m])]))
        matches = []
        for ms in m1: ms[1].sort(reverse=True)
        for ms in m1:
            for mt in ms[1]:
                matches.extend(mt[4])
	#
	# Now search by I-D exists, if there could be any results.
	# If searching by job owner, current state or substate, there
	# can't be any "I-D exists" matches.
	if not(args.get('search_job_owner', 0) or args.get('search_cur_state', 0) or args.get('sub_state_id', 0)):
	    if not(args.get('search_rfcnumber', 0)):
		in_tracker=[i['draft'] for i in IDInternal.objects.filter(rfc_flag=0).values('draft')]
		qdict = {
		    'search_area_acronym': 'group__ietfwg__areagroup__area',
		    'search_group_acronym': 'group__acronym',
		    'search_filename': 'filename__icontains',
		    #'search_status_id': 'status',
		}
		q_objs = [Q(**{qdict[k]: args[k]}) for k in qdict.keys() if args.get(k, '') != '']
		idmatches = InternetDraft.objects.filter(*q_objs).exclude(id_document_tag__in=in_tracker).filter(status__status='Active').order_by('filename')
		# resolve the queryset, append wrapper objects.
		matches = list(matches) + [DocumentWrapper(id) for id in idmatches]
	    if not(args.get('search_filename', '') or args.get('search_status_id', 0)) and args.get('search_rfcnumber', 0):
		# the existing area acronym support in this function
		# in pidtracker.cgi is broken, since it compares an
		# area acronym string in the database against an
		# area acronym number in the form.  We just ignore
		# the area (resulting in a different search, but
		# given that this search is only performed when there's
		# an explicit rfc number, it seems more or less silly
		# to filter it further anyway.)
		in_tracker=[i['draft'] for i in IDInternal.objects.filter(rfc_flag=1).values('draft')]
		qdict = {
		    'search_group_acronym': 'group_acronym',
		    'search_rfcnumber': 'rfc_number',
		    'search_status_id': 'status',
		}
		q_objs = [Q(**{qdict[k]: args[k]}) for k in qdict.keys() if args.get(k, '') != '']
		rfcmatches = Rfc.objects.filter(*q_objs).exclude(rfc_number__in=in_tracker)
		matches = list(matches) + [DocumentWrapper(rfc) for rfc in rfcmatches]
    else:
	matches = None

    return render_to_response('idtracker/idtracker_search.html', {
	'form': form,
	'matches': matches,
	'searching': searching,
	'spacing': True
      }, context_instance=RequestContext(request))

def state_desc(request, state, is_substate=0):
    if int(state) == 100:
	object = {
		'state': 'I-D Exists',
		'description': """
Initial (default) state for all internet drafts. Such documents are
not being tracked by the IESG as no request has been made of the
IESG to do anything with the document.
"""
		}
    elif is_substate:
	sub = get_object_or_404(IDSubState, pk=state)
	object = { 'state': sub.sub_state, 'description': sub.description }
    else:
	object = get_object_or_404(IDState, pk=state)
    return render_to_response('idtracker/state_desc.html', {'state': object},
	context_instance=RequestContext(request))

def comment(request, slug, object_id, queryset):
    rfcnum = re.match(r'^rfc(\d+)$', slug)
    if rfcnum:
	queryset = queryset.filter(document=rfcnum.groups()[0])
    else:
	draft = get_object_or_404(InternetDraft, filename=slug)
	queryset = queryset.filter(document=draft.id_document_tag)
    return object_detail(request, queryset=queryset, object_id=object_id)

def status(request):
    queryset = IDInternal.objects.filter(primary_flag=1).exclude(cur_state__state__in=('RFC Ed Queue', 'RFC Published', 'AD is watching', 'Dead')).order_by('cur_state', 'status_date', 'ballot')
    return object_list(request, template_name="idtracker/status_of_items.html", queryset=queryset, extra_context={'title': 'IESG Status of Items'})

def last_call(request):
    queryset = IDInternal.objects.filter(primary_flag=1).filter(cur_state__state__in=('In Last Call', 'Waiting for Writeup', 'Waiting for AD Go-Ahead')).order_by('cur_state', 'status_date', 'ballot')
    return object_list(request, template_name="idtracker/status_of_items.html", queryset=queryset, extra_context={'title': 'Documents in Last Call', 'lastcall': 1})

def redirect_id(request, object_id):
    '''Redirect from historical document ID to preferred filename url.'''
    doc = get_object_or_404(InternetDraft, id_document_tag=object_id)
    return HttpResponsePermanentRedirect("/doc/"+doc.filename+"/")

# calling sequence similar to object_detail, but we have different
# 404 handling: if the draft exists, render a not-found template.
def view_id(request, queryset, slug, slug_field):
    try:
	object = IDInternal.objects.get(draft__filename=slug, rfc_flag=0)
    except IDInternal.DoesNotExist:
	draft = get_object_or_404(InternetDraft, filename=slug)
        return HttpResponsePermanentRedirect("/doc/"+draft.filename+"/")
    return render_to_response('idtracker/idinternal_detail.html', {'object': object, 'spacing': False}, context_instance=RequestContext(request))

def view_rfc(request, object_id):
    '''A replacement for the object_detail generic view for this
    specific case to work around the following problem:
    The object_detail generic view looks up the value of the
    primary key in order to hand it to populate_xheaders.
    In the IDInternal table, the primary key is a foreign key
    to InternetDraft.  object_detail assumes that the PK is not
    an FK so doesn't do the foo_id trick, so the lookup is
    attempted and an exception raised if there is no match.
    This view gets the appropriate row from IDInternal and
    calls the template with the necessary context.'''
    object = get_object_or_404(IDInternal, pk=object_id, rfc_flag=1)
    return render_to_response('idtracker/idinternal_detail.html', {'object': object, 'spacing': False}, context_instance=RequestContext(request))

# Wrappers around object_detail to give permalink a handle.
# The named-URLs feature in django 0.97 will eliminate the
# need for these.
def view_comment(*args, **kwargs):
    return object_detail(*args, **kwargs)

def view_ballot(*args, **kwargs):
    return object_detail(*args, **kwargs)

