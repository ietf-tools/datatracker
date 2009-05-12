# Copyright (C) 2009 Nokia Corporation and/or its subsidiary(-ies).
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

import re
from django.http import HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from ietf.idtracker.models import InternetDraft, IETFWG, Area, IDInternal
from ietf.idrfc.models import RfcIndex, RfcEditorQueue, DraftVersions
from ietf.idrfc.idrfc_wrapper import BallotWrapper, IdWrapper, RfcWrapper
from ietf.idrfc import markup_txt
from ietf import settings
from django.template import RequestContext
from django.template.defaultfilters import truncatewords_html
from ietf.idtracker.templatetags.ietf_filters import format_textarea, fill

def document_debug(request, name):
    r = re.compile("^rfc([0-9]+)$")
    m = r.match(name)
    if m:
        rfc_number = int(m.group(1))
        rfci = get_object_or_404(RfcIndex, rfc_number=rfc_number)
        doc = RfcWrapper(rfci)
    else:
        id = get_object_or_404(InternetDraft, filename=name)
        doc = IdWrapper(draft=id)
    return HttpResponse(doc.to_json(), mimetype='text/plain')

def document_main_rfc(request, rfc_number):
    rfci = get_object_or_404(RfcIndex, rfc_number=rfc_number)
    doc = RfcWrapper(rfci)

    info = {}
    content1 = None
    content2 = None
    f = None
    try:
        try:
            f = open(settings.RFC_PATH+"rfc"+str(rfc_number)+".txt")
            content = f.read()
            (content1, content2) = markup_txt.markup(content)
        except IOError:
            content1 = "Error - can't find"+"rfc"+str(rfc_number)+".txt"
            content2 = ""
    finally:
        if f:
            f.close()
            
    return render_to_response('idrfc/doc_main_rfc.html',
                              {'content1':content1, 'content2':content2,
                               'doc':doc, 'info':info},
                              context_instance=RequestContext(request));

def document_main(request, name):
    r = re.compile("^rfc([0-9]+)$")
    m = r.match(name)
    if m:
        return document_main_rfc(request, int(m.group(1)))
    id = get_object_or_404(InternetDraft, filename=name)
    doc = IdWrapper(id) 
    
    info = {}
    stream_id = doc.stream_id()
    if stream_id == 2:
        stream = " (IAB document)"
    elif stream_id == 3:
        stream = " (IRTF document)"
    elif stream_id == 4:
        stream = " (Independent submission via RFC Editor)"
    elif doc.group_acronym():
        stream = " ("+doc.group_acronym().upper()+" WG document)"
    else:
        stream = " (Individual document)"
        
    if id.status.status == "Active":
        info['is_active_draft'] = True
        info['type'] = "Active Internet-Draft"+stream
    else:
        info['is_active_draft'] = False
        info['type'] = "Old Internet-Draft"+stream

    info['has_pdf'] = (".pdf" in doc.file_types())
    
    content1 = None
    content2 = None
    if info['is_active_draft']:
        f = None
        try:
            try:
                f = open(settings.INTERNET_DRAFT_PATH+name+"-"+id.revision+".txt")
                content = f.read()
                (content1, content2) = markup_txt.markup(content)
            except IOError:
                content1 = "Error - can't find "+name+"-"+id.revision+".txt"
                content2 = ""
        finally:
            if f:
                f.close()
            
    return render_to_response('idrfc/doc_main_id.html',
                              {'content1':content1, 'content2':content2,
                               'doc':doc, 'info':info},
                              context_instance=RequestContext(request));

def document_comments(request, name):
    r = re.compile("^rfc([0-9]+)$")
    m = r.match(name)
    if m:
        id = get_object_or_404(IDInternal, rfc_flag=1, draft=int(m.group(1)))
    else:
        id = get_object_or_404(IDInternal, rfc_flag=0, draft__filename=name)
    results = []
    commentNumber = 0
    for comment in id.public_comments():
        info = {}
        r = re.compile(r'^(.*) by (?:<b>)?([A-Z]\w+ [A-Z]\w+)(?:</b>)?$')
        m = r.match(comment.comment_text)
        if m:
            info['text'] = m.group(1)
            info['by'] = m.group(2)
        else:
            info['text'] = comment.comment_text
            info['by'] = comment.get_username()
        info['textSnippet'] = truncatewords_html(format_textarea(fill(info['text'], 80)), 25)
        info['snipped'] = info['textSnippet'][-3:] == "..."
        info['commentNumber'] = commentNumber
        commentNumber = commentNumber + 1
        results.append({'comment':comment, 'info':info})
    return render_to_response('idrfc/doc_comments.html', {'comments':results}, context_instance=RequestContext(request))

def document_ballot(request, name):
    r = re.compile("^rfc([0-9]+)$")
    m = r.match(name)
    if m:
        id = get_object_or_404(IDInternal, rfc_flag=1, draft=int(m.group(1)))
    else:
        id = get_object_or_404(IDInternal, rfc_flag=0, draft__filename=name)
    try:
        if not id.ballot.ballot_issued:
            raise Http404
    except BallotInfo.DoesNotExist:
        raise Http404

    ballot = BallotWrapper(id)
    return render_to_response('idrfc/doc_ballot.html', {'ballot':ballot}, context_instance=RequestContext(request))

def document_versions(request, name):
    draft = get_object_or_404(InternetDraft, filename=name)
    ov = []
    ov.append({"draft_name":draft.filename, "revision":draft.revision, "revision_date":draft.revision_date})
    for d in [draft]+list(draft.replaces_set.all()):
        for v in DraftVersions.objects.filter(filename=d.filename).order_by('-revision'):
            if (d.filename == draft.filename) and (draft.revision == v.revision):
                continue
            ov.append({"draft_name":d.filename, "revision":v.revision, "revision_date":v.revision_date})
    
    return render_to_response('idrfc/doc_versions.html', {'versions':ov}, context_instance=RequestContext(request))

