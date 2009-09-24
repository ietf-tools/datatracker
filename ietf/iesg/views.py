# Copyright The IETF Trust 2007, All Rights Reserved

# Portion Copyright (C) 2008 Nokia Corporation and/or its subsidiary(-ies).
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

# Create your views here.
#from django.views.generic.date_based import archive_index
from ietf.idtracker.models import IDInternal, InternetDraft,AreaGroup, Position
from django.views.generic.list_detail import object_list
from django.views.generic.simple import direct_to_template
from django.http import Http404, HttpResponse
from django.template import RequestContext, Context, loader
from django.shortcuts import render_to_response
from ietf.iesg.models import TelechatDates, TelechatAgendaItem, WGAction
from ietf.idrfc.idrfc_wrapper import IdWrapper, RfcWrapper
from ietf.idrfc.models import RfcIndex

import datetime 

def date_threshold():
    """Return the first day of the month that is 185 days ago."""
    ret = datetime.date.today() - datetime.timedelta(days=185)
    ret = ret - datetime.timedelta(days=ret.day - 1)
    return ret

def inddocs(request):
   queryset_list_ind = InternetDraft.objects.filter(idinternal__via_rfc_editor=1, idinternal__rfc_flag=0, idinternal__noproblem=1, idinternal__dnp=0).order_by('-b_approve_date')
   queryset_list_ind_dnp = IDInternal.objects.filter(via_rfc_editor = 1,rfc_flag=0,dnp=1).order_by('-dnp_date')
   return object_list(request, queryset=queryset_list_ind, template_name='iesg/independent_doc.html', allow_empty=True, extra_context={'object_list_dnp':queryset_list_ind_dnp })

def wgdocs(request,cat):
   is_recent = 0
   queryset_list=[]
   queryset_list_doc=[]
   if cat == 'new':
      is_recent = 1
      queryset = InternetDraft.objects.filter(b_approve_date__gte = date_threshold(), intended_status__in=[1,2,6,7],idinternal__via_rfc_editor=0,idinternal__primary_flag=1).order_by("-b_approve_date")
      queryset_doc = InternetDraft.objects.filter(b_approve_date__gte = date_threshold(), intended_status__in=[3,5],idinternal__via_rfc_editor=0, idinternal__primary_flag=1).order_by("-b_approve_date")
   elif cat == 'prev':
      queryset = InternetDraft.objects.filter(b_approve_date__lt = date_threshold(), b_approve_date__gte = '1997-12-1', intended_status__in=[1,2,6,7],idinternal__via_rfc_editor=0,idinternal__primary_flag=1).order_by("-b_approve_date")
      queryset_doc = InternetDraft.objects.filter(b_approve_date__lt = date_threshold(), b_approve_date__gte = '1998-10-15', intended_status__in=[3,5],idinternal__via_rfc_editor=0,idinternal__primary_flag=1).order_by("-b_approve_date")
   else:
     raise Http404
   for item in list(queryset):
      queryset_list.append(item)
      try:
        ballot_id=item.idinternal.ballot_id
      except AttributeError:
        ballot_id=0
      for sub_item in list(InternetDraft.objects.filter(idinternal__ballot=ballot_id,idinternal__primary_flag=0)):
         queryset_list.append(sub_item)
   for item2 in list(queryset_doc):
      queryset_list_doc.append(item2)
      try:
        ballot_id=item2.idinternal.ballot_id
      except AttributeError:
        ballot_id=0
      for sub_item2 in list(InternetDraft.objects.filter(idinternal__ballot=ballot_id,idinternal__primary_flag=0)):
         queryset_list_doc.append(sub_item2)
   return render_to_response( 'iesg/ietf_doc.html', {'object_list': queryset_list, 'object_list_doc':queryset_list_doc, 'is_recent':is_recent}, context_instance=RequestContext(request) )

def get_doc_section(id):
    states = [16,17,18,19,20,21]
    if id.document().intended_status.intended_status_id in [1,2,6,7]:
        s = "2"
    else:
        s = "3"
    if id.rfc_flag == 0:
        g = id.document().group_acronym()
    else:
        g = id.document().group_acronym
    if g and str(g) != 'none':
        s = s + "1"
    elif (s == "3") and id.via_rfc_editor > 0:
        s = s + "3"
    else:
        s = s + "2"
    if not id.rfc_flag and id.cur_state.document_state_id not in states:
        s = s + "3"
    elif id.returning_item > 0:
        s = s + "2"
    else:
        s = s + "1"
    return s

def agenda_docs(date, next_agenda):
    if next_agenda:
        matches = IDInternal.objects.filter(telechat_date=date, primary_flag=1, agenda=1)
    else:
        matches = IDInternal.objects.filter(telechat_date=date, primary_flag=1)
    idmatches = matches.filter(rfc_flag=0).order_by('ballot')
    rfcmatches = matches.filter(rfc_flag=1).order_by('ballot')
    res = {}
    for id in list(idmatches)+list(rfcmatches):
        section_key = "s"+get_doc_section(id)
        if section_key not in res:
            res[section_key] = []
        others = id.ballot_others()
        if id.note:
            id.note = str(id.note).replace("\240","&nbsp;")
        if len(others) > 0:
            res[section_key].append({'obj':id, 'ballot_set':[id]+list(others)})
        else:
            res[section_key].append({'obj':id})
    return res

def agenda_wg_actions(date):
    mapping = {12:'411', 13:'412',22:'421',23:'422'}
    matches = WGAction.objects.filter(agenda=1,telechat_date=date,category__in=mapping.keys()).order_by('category')
    res = {}
    for o in matches:
        section_key = "s"+mapping[o.category]
        if section_key not in res:
            res[section_key] = []
        area = AreaGroup.objects.get(group=o.group_acronym)
        res[section_key].append({'obj':o, 'area':str(area.area)})
    return res

def agenda_management_issues(date):
    matches = TelechatAgendaItem.objects.filter(type=3).order_by('id')
    return [o.title for o in matches]

def telechat_agenda(request, date=None):
    if not date:
        date = TelechatDates.objects.all()[0].date1
        next_agenda = True
    else:
        y,m,d = date.split("-")
        date = datetime.date(int(y), int(m), int(d))
        next_agenda = None
    #date = "2006-03-16"
    docs = agenda_docs(date, next_agenda)
    mgmt = agenda_management_issues(date)
    wgs = agenda_wg_actions(date)
    private = 'private' in request.REQUEST
    return render_to_response('iesg/agenda.html', {'date':str(date), 'docs':docs,'mgmt':mgmt,'wgs':wgs, 'private':private}, context_instance=RequestContext(request) )
    

def telechat_agenda_documents_txt(request):
    dates = TelechatDates.objects.all()[0].dates()
    docs = []
    for date in dates:
        docs.extend(IDInternal.objects.filter(telechat_date=date, primary_flag=1, agenda=1))
    t = loader.get_template('iesg/agenda_documents.txt')
    c = Context({'docs':docs})
    return HttpResponse(t.render(c), mimetype='text/plain')

def discusses(request):
    positions = Position.objects.filter(discuss=1)
    res = []
    try:
        ids = set()
    except NameError:
        # for Python 2.3 
        from sets import Set as set
        ids = set()
    
    for p in positions:
        try:
            draft = p.ballot.drafts.filter(primary_flag=1)
            if len(draft) > 0 and draft[0].rfc_flag:
                if not -draft[0].draft_id in ids:
                    ids.add(-draft[0].draft_id)
                    try:
                        ri = RfcIndex.objects.get(rfc_number=draft[0].draft_id)
                        doc = RfcWrapper(ri)
                        if doc.in_ietf_process() and doc.ietf_process.has_active_iesg_ballot():
                            res.append(doc)
                    except RfcIndex.DoesNotExist:
                        # NOT QUITE RIGHT, although this should never happen
                        pass
            if len(draft) > 0 and not draft[0].rfc_flag and draft[0].draft.id_document_tag not in ids:
                ids.add(draft[0].draft.id_document_tag)
                doc = IdWrapper(draft=draft[0])
                if doc.in_ietf_process() and doc.ietf_process.has_active_iesg_ballot():
                    res.append(doc)
        except IDInternal.DoesNotExist:
            pass
    return direct_to_template(request, 'iesg/discusses.html', {'docs':res})

def telechat_agenda_documents(request):
    dates = TelechatDates.objects.all()[0].dates()
    telechats = []
    for date in dates:
        matches = IDInternal.objects.filter(telechat_date=date,primary_flag=1,agenda=1)
        idmatches = matches.filter(rfc_flag=0).order_by('ballot')
        rfcmatches = matches.filter(rfc_flag=1).order_by('ballot')
        res = {}
        for id in list(idmatches)+list(rfcmatches):
            section_key = "s"+get_doc_section(id)
            if section_key not in res:
                res[section_key] = []
            if not id.rfc_flag:
                w = IdWrapper(draft=id)
            else:
                ri = RfcIndex.objects.get(rfc_number=id.draft_id)
                w = RfcWrapper(ri)
            res[section_key].append(w)
        telechats.append({'date':date, 'docs':res})
    return direct_to_template(request, 'iesg/agenda_documents.html', {'telechats':telechats})
                                                                                                        
def telechat_agenda_scribe_template(request):
    date = TelechatDates.objects.all()[0].date1
    docs = agenda_docs(date, True)
    return render_to_response('iesg/scribe_template.html', {'date':str(date), 'docs':docs}, context_instance=RequestContext(request) )
    
    
