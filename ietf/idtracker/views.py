# Copyright The IETF Trust 2007, All Rights Reserved

# Create your views here.
from django.http import HttpResponsePermanentRedirect, Http404
from django.template import RequestContext
from django.shortcuts import get_object_or_404, render_to_response
from django.views.generic.list_detail import object_detail, object_list
from ietf.idtracker.models import InternetDraft, IDInternal, IDState, IDSubState, BallotInfo, DocumentComment
import re

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

def redirect_rfc(request, rfc_number):
    return HttpResponsePermanentRedirect("/doc/rfc"+rfc_number+"/")

def redirect_filename(request, filename):
    return HttpResponsePermanentRedirect("/doc/"+filename+"/")

def redirect_ballot(request, object_id):
    ballot = get_object_or_404(BallotInfo, pk=object_id)
    ids = ballot.drafts.filter(primary_flag=1)
    if len(ids) == 0:
        raise Http404("Ballot does not correspond to any document")
    id = ids[0]
    if id.rfc_flag:
        return HttpResponsePermanentRedirect("/doc/rfc"+str(id.draft_id)+"/#ballot")
    else:
        return HttpResponsePermanentRedirect("/doc/"+id.draft.filename+"/#ballot")

def redirect_comment(request, object_id):
    comment = get_object_or_404(DocumentComment, pk=object_id)
    id = comment.document
    if id.rfc_flag:
        return HttpResponsePermanentRedirect("/doc/rfc"+str(id.draft_id)+"/#history-"+str(object_id))
    else:
        return HttpResponsePermanentRedirect("/doc/"+id.draft.filename+"/#history-"+str(object_id))

