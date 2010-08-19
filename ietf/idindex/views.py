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
from ietf.idtracker.models import Acronym, IETFWG, InternetDraft, IDInternal,PersonOrOrgInfo, Area
from ietf.idtracker.templatetags.ietf_filters import clean_whitespace
import re
import sys

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

def all_id2_entry(id):
    fields = []
    # 0
    fields.append(id.filename+"-"+id.revision_display())
    # 1
    fields.append(id.id_document_tag)
    # 2
    status = id.status.status
    fields.append(status)
    # 3
    iesgstate = id.idstate() if status=="Active" else ""
    fields.append(iesgstate)
    # 4
    fields.append(id.rfc_number if status=="RFC" else "")
    # 5
    try:
        fields.append(id.replaced_by.filename)
    except (AttributeError, InternetDraft.DoesNotExist):
        fields.append("")
    # 6
    fields.append(id.revision_date)
    # 7
    group_acronym = id.group.acronym
    if group_acronym == "none":
        group_acronym = ""
    fields.append(group_acronym)

    # 8
    area = ""
    if id.idinternal:
        try:
            area = id.idinternal.area_acronym
        except Area.DoesNotExist:
            pass
    elif not group_acronym:
        pass
    else:
        try:
            area = id.group.ietfwg.area_acronym()
        except IETFWG.DoesNotExist:
            area = ""
    fields.append(area)
    # 9
    fields.append(id.idinternal.job_owner if id.idinternal else "")
    # 10
    if id.intended_status and id.intended_status.intended_status not in ("None","Request"):
        fields.append(id.intended_status.intended_status)
    else:
        fields.append("")
    # 11
    if (iesgstate=="In Last Call") or iesgstate.startswith("In Last Call::"):
        fields.append(id.lc_expiration_date)
    else:
        fields.append("")
    # 12
    fields.append(id.file_type if status=="Active" else "")
    # 13
    fields.append(clean_whitespace(id.title))
    # 14
    authors = []
    for author in sorted(id.authors.all(), key=lambda x: x.final_author_order()):
        try:
            realname = unicode(author.person)
            email = author.email() or ""
            name = re.sub(u"[<>@,]", u"", realname) + u" <"+re.sub(u"[<>,]", u"", email).strip()+u">"
            authors.append(clean_whitespace(name))
        except PersonOrOrgInfo.DoesNotExist:
            pass
    fields.append(u", ".join(authors))
    return "\t".join([unicode(x) for x in fields])
    
def all_id2_txt():
    all_ids = InternetDraft.objects.order_by('filename').select_related('status__status','group__acronym','intended_status__intended_status')
    data = "\n".join([all_id2_entry(id) for id in all_ids])
    return loader.render_to_string("idindex/all_id2.txt",{'data':data})

def id_index_txt():
    groups = IETFWG.objects.all()
    return loader.render_to_string("idindex/id_index.txt", {'groups':groups})

def id_abstracts_txt():
    groups = IETFWG.objects.all()
    return loader.render_to_string("idindex/id_abstracts.txt", {'groups':groups})

def test_all_id_txt(request):
    return HttpResponse(all_id_txt(), mimetype='text/plain')
def test_all_id2_txt(request):
    return HttpResponse(all_id2_txt(), mimetype='text/plain')
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

