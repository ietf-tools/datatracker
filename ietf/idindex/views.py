# Copyright The IETF Trust 2007, All Rights Reserved

# Portions Copyright (C) 2009-2010 Nokia Corporation and/or its subsidiary(-ies).
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
from django.template import loader
from django.shortcuts import get_object_or_404
from ietf.idtracker.models import Acronym, IETFWG, InternetDraft, Rfc, IDInternal

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

def redirect_id(request, object_id):
    '''Redirect from historical document ID to preferred filename url.'''
    doc = get_object_or_404(InternetDraft, id_document_tag=object_id)
    return HttpResponsePermanentRedirect("/doc/"+doc.filename+"/")

def redirect_filename(request, filename):
    return HttpResponsePermanentRedirect("/doc/"+filename+"/")

def wgdocs_redirect_id(request, id):
    group = get_object_or_404(Acronym, acronym_id=id)
    return HttpResponsePermanentRedirect("/wg/"+group.acronym+"/")

def wgdocs_redirect_acronym(request, acronym):
    return HttpResponsePermanentRedirect("/wg/"+acronym+"/")

