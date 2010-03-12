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
from ietf.idtracker.models import Acronym, IETFWG, InternetDraft, IDInternal

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

