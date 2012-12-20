# Copyright The IETF Trust 2007, All Rights Reserved

# Portion Copyright (C) 2008-2009 Nokia Corporation and/or its subsidiary(-ies).
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

import codecs, re, os, glob
import datetime
import tarfile

from ietf.idtracker.models import IDInternal, InternetDraft, AreaGroup, Position, IESGLogin, Acronym
from django.views.generic.list_detail import object_list
from django.views.generic.simple import direct_to_template
from django.views.decorators.vary import vary_on_cookie
from django.core.urlresolvers import reverse as urlreverse
from django.http import Http404, HttpResponse, HttpResponseForbidden, HttpResponseRedirect
from django.template import RequestContext, Context, loader
from django.shortcuts import render_to_response, get_object_or_404
from django.conf import settings
from django.utils import simplejson as json
from django import forms
from ietf.iesg.models import TelechatDates, TelechatAgendaItem, WGAction
from ietf.idrfc.idrfc_wrapper import IdWrapper, RfcWrapper
from ietf.idrfc.models import RfcIndex
from ietf.idrfc.utils import update_telechat
from ietf.ietfauth.decorators import group_required
from ietf.idtracker.templatetags.ietf_filters import in_group
from ietf.ipr.models import IprDocAlias 
from ietf.doc.models import Document, TelechatDocEvent, LastCallDocEvent, ConsensusDocEvent
from ietf.group.models import Group

def date_threshold():
    """Return the first day of the month that is 185 days ago."""
    ret = datetime.date.today() - datetime.timedelta(days=185)
    ret = ret - datetime.timedelta(days=ret.day - 1)
    return ret

def inddocs(request):
    queryset_list_ind = [d for d in InternetDraft.objects.filter(stream__in=("IRTF","ISE"), docevent__type="iesg_approved").distinct() if d.latest_event(type__in=("iesg_disapproved", "iesg_approved")).type == "iesg_approved"]
    queryset_list_ind.sort(key=lambda d: d.b_approve_date, reverse=True)

    queryset_list_ind_dnp = [d for d in IDInternal.objects.filter(stream__in=("IRTF","ISE"), docevent__type="iesg_disapproved").distinct() if d.latest_event(type__in=("iesg_disapproved", "iesg_approved")).type == "iesg_disapproved"]
    queryset_list_ind_dnp.sort(key=lambda d: d.dnp_date, reverse=True)

    return render_to_response('iesg/independent_doc.html',
                              dict(object_list=queryset_list_ind,
                                   object_list_dnp=queryset_list_ind_dnp),
                              context_instance=RequestContext(request))
   

def wgdocs(request,cat):
   pass

def wgdocsREDESIGN(request,cat):
    is_recent = 0
    proto_actions = []
    doc_actions = []
    threshold = date_threshold()
    
    proto_levels = ["bcp", "ds", "ps", "std"]
    doc_levels = ["exp", "inf"]
    
    if cat == 'new':
        is_recent = 1
        
        drafts = InternetDraft.objects.filter(docevent__type="iesg_approved", docevent__time__gte=threshold, intended_std_level__in=proto_levels + doc_levels).exclude(stream__in=("ISE","IRTF")).distinct()
        for d in drafts:
            if d.b_approve_date and d.b_approve_date >= threshold:
                if d.intended_std_level_id in proto_levels:
                    proto_actions.append(d)
                elif d.intended_std_level_id in doc_levels:
                    doc_actions.append(d)

    elif cat == 'prev':
        # proto
        start_date = datetime.date(1997, 12, 1)
        
        drafts = InternetDraft.objects.filter(docevent__type="iesg_approved", docevent__time__lt=threshold, docevent__time__gte=start_date, intended_std_level__in=proto_levels).exclude(stream__in=("ISE","IRTF")).distinct()

        for d in drafts:
            if d.b_approve_date and start_date <= d.b_approve_date < threshold:
                proto_actions.append(d)

        # doc
        start_date = datetime.date(1998, 10, 15)
        
        drafts = InternetDraft.objects.filter(docevent__type="iesg_approved", docevent__time__lt=threshold, docevent__time__gte=start_date, intended_std_level__in=doc_levels).exclude(stream__in=("ISE","IRTF")).distinct()

        for d in drafts:
            if d.b_approve_date and start_date <= d.b_approve_date < threshold:
                doc_actions.append(d)
    else:
        raise Http404

    proto_actions.sort(key=lambda d: d.b_approve_date, reverse=True)
    doc_actions.sort(key=lambda d: d.b_approve_date, reverse=True)
    
    return render_to_response('iesg/ietf_doc.html',
                              dict(object_list=proto_actions,
                                   object_list_doc=doc_actions,
                                   is_recent=is_recent,
                                   title_prefix="Recent" if is_recent else "Previous"),
                              context_instance=RequestContext(request))

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    wgdocs = wgdocsREDESIGN
    

def get_doc_section(id):
    pass

def get_doc_sectionREDESIGN(doc):
    if doc.type_id == 'draft':
        if doc.intended_std_level_id in ["bcp", "ds", "ps", "std"]:
            s = "2"
        else:
            s = "3"

        g = doc.group_acronym()
        if g and str(g) != 'none':
            s = s + "1"
        elif (s == "3") and doc.stream_id in ("ise","irtf"):
            s = s + "3"
        else:
            s = s + "2"
        if not doc.get_state_slug=="rfc" and doc.get_state_slug('draft-iesg') not in ("lc", "writeupw", "goaheadw", "iesg-eva", "defer"):
            s = s + "3"
        elif doc.returning_item():
            s = s + "2"
        else:
            s = s + "1"
    elif doc.type_id == 'charter':
        s = get_wg_section(doc.group)
    elif doc.type_id == 'conflrev':
        if doc.get_state('conflrev').slug not in ('adrev','iesgeval','appr-reqnopub-pend','appr-reqnopub-sent','appr-noprob-pend','appr-noprob-sent','defer'):
             s = "333"
        elif doc.returning_item():
             s = "332"
        else:
             s = "331"

    return s

def get_wg_section(wg):
    s = ""
    charter_slug = None
    if wg.charter:
        charter_slug = wg.charter.get_state_slug()
    if wg.state_id in ['active','dormant']:
        if charter_slug in ['extrev','iesgrev']:
            s = '422'
        else:
            s = '421'
    else:
        if charter_slug in ['extrev','iesgrev']:
            s = '412'
        else:
            s = '411'
    return s

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    get_doc_section = get_doc_sectionREDESIGN
    
def agenda_docs(date, next_agenda):
    matches = Document.objects.filter(docevent__telechatdocevent__telechat_date=date).select_related("stream").distinct()

    docmatches = []
        
    for doc in matches:
        if doc.latest_event(TelechatDocEvent, type="scheduled_for_telechat").telechat_date != date:
            continue

        e = doc.latest_event(type="started_iesg_process")
        doc.balloting_started = e.time if e else datetime.datetime.min

        if doc.type_id == "draft":
            s = doc.get_state("draft-iana-review")
            if s and s.slug in ("not-ok", "changed", "need-rev"):
                doc.iana_review_state = str(s)

            if doc.get_state_slug("draft-iesg") == "lc":
                e = doc.latest_event(LastCallDocEvent, type="sent_last_call")
                if e:
                    doc.lastcall_expires = e.expires

            if doc.stream_id in ("ietf", "irtf", "iab"):
                doc.consensus = "Unknown"
                e = doc.latest_event(ConsensusDocEvent, type="changed_consensus")
                if e:
                    doc.consensus = "Yes" if e.consensus else "No"
        elif doc.type_id=='conflrev':
            doc.conflictdoc = doc.relateddocument_set.get(relationship__slug='conflrev').target.document

        docmatches.append(doc)

    # Be careful to keep this the same as what's used in agenda_documents
    docmatches.sort(key=lambda d: d.balloting_started)
    
    res = dict(("s%s%s%s" % (i, j, k), []) for i in range(2, 5) for j in range (1, 4) for k in range(1, 4))
    for id in docmatches:
        section_key = "s"+get_doc_section(id)
        if section_key not in res:
            res[section_key] = []
        if id.note:
            # TODO: Find out why this is _here_
            id.note = id.note.replace(u"\240",u"&nbsp;")
        res[section_key].append({'obj':id})
    return res

def agenda_wg_actions(date):
    res = dict(("s%s%s%s" % (i, j, k), []) for i in range(2, 5) for j in range (1, 4) for k in range(1, 4))
    charters = Document.objects.filter(type="charter", docevent__telechatdocevent__telechat_date=date).select_related("group").distinct()
    charters = charters.filter(group__state__slug__in=["proposed","active"])
    for c in charters:
        if c.latest_event(TelechatDocEvent, type="scheduled_for_telechat").telechat_date != date:
            continue

        c.group.txt_link = settings.CHARTER_TXT_URL + "%s-%s.txt" % (c.canonical_name(), c.rev)

        section_key = "s" + get_wg_section(c.group)
        if section_key not in res:
            res[section_key] = []
        # Cleanup - Older view code wants obj, newer wants doc. Older code should be moved forward
        res[section_key].append({'obj': c.group, 'doc': c})
    return res

def agenda_management_issues(date):
    return TelechatAgendaItem.objects.filter(type=3).order_by('id')

def _agenda_json(request, date=None):
    if not date:
        date = TelechatDates.objects.all()[0].date1
        next_agenda = True
    else:
        y,m,d = date.split("-")
        date = datetime.date(int(y), int(m), int(d))
        next_agenda = None

    data = {'telechat-date':str(date),
            'as-of':str(datetime.datetime.utcnow()),
            'sections':{}}
    data['sections']['1'] = {'title':"Administrivia"}
    data['sections']['1.1'] = {'title':"Roll Call"}
    data['sections']['1.2'] = {'title':"Bash the Agenda"}
    data['sections']['1.3'] = {'title':"Approval of the Minutes of Past Telechats"}
    data['sections']['1.4'] = {'title':"List of Remaining Action Items from Last Telechat"}
    data['sections']['2'] = {'title':"Protocol Actions"}
    data['sections']['2.1'] = {'title':"WG Submissions"}
    data['sections']['2.1.1'] = {'title':"New Items", 'docs':[]}
    data['sections']['2.1.2'] = {'title':"Returning Items", 'docs':[]}
    data['sections']['2.2'] = {'title':"Individual Submissions"}
    data['sections']['2.2.1'] = {'title':"New Items", 'docs':[]}
    data['sections']['2.2.2'] = {'title':"Returning Items", 'docs':[]}
    data['sections']['3'] = {'title':"Document Actions"}
    data['sections']['3.1'] = {'title':"WG Submissions"}
    data['sections']['3.1.1'] = {'title':"New Items", 'docs':[]}
    data['sections']['3.1.2'] = {'title':"Returning Items", 'docs':[]}
    data['sections']['3.2'] = {'title':"Individual Submissions Via AD"}
    data['sections']['3.2.1'] = {'title':"New Items", 'docs':[]}
    data['sections']['3.2.2'] = {'title':"Returning Items", 'docs':[]}
    data['sections']['3.3'] = {'title':"IRTF and Independent Submission Stream Documents"}
    data['sections']['3.3.1'] = {'title':"New Items", 'docs':[]}
    data['sections']['3.3.2'] = {'title':"Returning Items", 'docs':[]}
    data['sections']['4'] = {'title':"Working Group Actions"}
    data['sections']['4.1'] = {'title':"WG Creation"}
    data['sections']['4.1.1'] = {'title':"Proposed for IETF Review", 'wgs':[]}
    data['sections']['4.1.2'] = {'title':"Proposed for Approval", 'wgs':[]}
    data['sections']['4.2'] = {'title':"WG Rechartering"}
    data['sections']['4.2.1'] = {'title':"Under Evaluation for IETF Review", 'wgs':[]}
    data['sections']['4.2.2'] = {'title':"Proposed for Approval", 'wgs':[]}
    data['sections']['5'] = {'title':"IAB News We Can Use"}
    data['sections']['6'] = {'title':"Management Issues"}
    data['sections']['7'] = {'title':"Working Group News"}

    docs = agenda_docs(date, next_agenda)
    for section in docs.keys():
        # in case the document is in a state that does not have an agenda section
        if section != 's':
            s = str(".".join(list(section)[1:]))
            if s[0:1] == '4':
                # ignore these; not sure why they are included by agenda_docs
                pass
            else:
                if len(docs[section]) != 0:
                    # If needed, add a "For Action" section to agenda
                    if s[4:5] == '3':
                        data['sections'][s] = {'title':"For Action", 'docs':[]}

                    for obj in docs[section]:
                        d = obj['obj']
                        docinfo = {'docname':d.canonical_name(),
                                   'title':d.title,
                                   'ad':d.ad.name}
                        if d.note:
                            docinfo['note'] = d.note
                        defer = d.active_defer_event()
                        if defer:
                            docinfo['defer-by'] = defer.by.name
                            docinfo['defer-at'] = str(defer.time)
			if doc.type_id == "draft":
                            docinfo['intended-std-level'] = str(doc.intended_std_level)
                            if doc.rfc_number():
                                docinfo['rfc-number'] = doc.rfc_number()
                            else:
                                docinfo['rev'] = doc.rev

                            iana_state = doc.get_state("draft-iana-review")
                            if iana_state.slug in ("not-ok", "changed", "need-rev"):
                                docinfo['iana_review_state'] = str(iana_state)

                            if doc.get_state_slug("draft-iesg") == "lc":
                                e = doc.latest_event(LastCallDocEvent, type="sent_last_call")
                                if e:
                                    docinfo['lastcall_expires'] = e.expires

                            docinfo['consensus'] = None
                            e = doc.latest_event(ConsensusDocEvent, type="changed_consensus")
                            if e:
                                docinfo['consensus'] = e.consensus
                        elif doc.type_id == 'conflrev':
                            td = doc.relateddocument_set.get(relationship__slug='conflrev').target.document
                            docinfo['target-docname'] = td.canonical_name()
                            docinfo['target-title'] = td.title
                            docinfo['target-rev'] = td.rev
                            docinfo['intended-std-level'] = str(td.intended_std_level)
                            docinfo['stream'] = str(td.stream)
			else:
			    # XXX check this -- is there nothing to set for
			    # all other documents here?
			    pass
                        data['sections'][s]['docs'] += [docinfo, ]

    wgs = agenda_wg_actions(date)
    for section in wgs.keys():
        # in case the charter is in a state that does not have an agenda section
        if section != 's':
            s = str(".".join(list(section)[1:]))
            if s[0:1] != '4':
                # ignore these; not sure why they are included by agenda_wg_actions
                pass
            else:
                if len(wgs[section]) != 0:
                    for obj in wgs[section]:
                        wg = obj['obj']
                        wginfo = {'wgname':wg.name,
                                  'acronym':wg.acronym,
                                  'ad':wg.ad.name}
                        data['sections'][s]['wgs'] += [wginfo, ]

    mgmt = agenda_management_issues(date)
    num = 0
    for m in mgmt:
        num += 1
        data['sections']["6.%d" % num] = {'title':m.title}

    return data

def _agenda_data(request, date=None):
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
    data = {'date':str(date), 'docs':docs,'mgmt':mgmt,'wgs':wgs}
    for key, filename in {'action_items':settings.IESG_TASK_FILE,
                          'roll_call':settings.IESG_ROLL_CALL_FILE,
                          'minutes':settings.IESG_MINUTES_FILE}.items():
        try:
            f = codecs.open(filename, 'r', 'utf-8', 'replace')
            text = f.read().strip()
            f.close()
            data[key] = text
        except IOError:
            data[key] = "(Error reading "+key+")"
    return data

@vary_on_cookie
def agenda(request, date=None):
    data = _agenda_data(request, date)
    data['private'] = 'private' in request.REQUEST
    data['settings'] = settings
    return render_to_response("iesg/agenda.html", data, context_instance=RequestContext(request))

def agenda_txt(request):
    data = _agenda_data(request)
    return render_to_response("iesg/agenda.txt", data, context_instance=RequestContext(request), mimetype="text/plain")

def agenda_json(request):
    response = HttpResponse(mimetype='text/plain')
    response.write(json.dumps(_agenda_json(request), indent=2))
    return response

def agenda_scribe_template(request):
    date = TelechatDates.objects.all()[0].date1
    docs = agenda_docs(date, True)
    return render_to_response('iesg/scribe_template.html', {'date':str(date), 'docs':docs, 'USE_DB_REDESIGN_PROXY_CLASSES': settings.USE_DB_REDESIGN_PROXY_CLASSES}, context_instance=RequestContext(request) )

def _agenda_moderator_package(request):
    data = _agenda_data(request)
    data['ad_names'] = [str(x) for x in IESGLogin.active_iesg()]
    data['ad_names'].sort(key=lambda x: x.split(' ')[-1])
    return render_to_response("iesg/moderator_package.html", data, context_instance=RequestContext(request))

@group_required('Area_Director','Secretariat')
def agenda_moderator_package(request):
    return _agenda_moderator_package(request)

def agenda_moderator_package_test(request):
    if request.META['REMOTE_ADDR'] == "127.0.0.1":
        return _agenda_moderator_package(request)
    else:
        return HttpResponseForbidden()

def _agenda_package(request):
    data = _agenda_data(request)
    return render_to_response("iesg/agenda_package.txt", data, context_instance=RequestContext(request), mimetype='text/plain')

@group_required('Area_Director','Secretariat')
def agenda_package(request):
    return _agenda_package(request)

def agenda_package_test(request):
    if request.META['REMOTE_ADDR'] == "127.0.0.1":
        return _agenda_package(request)
    else:
        return HttpResponseForbidden()

def agenda_documents_txt(request):
    dates = TelechatDates.objects.all()[0].dates()
    docs = []
    for date in dates:
        from ietf.doc.models import TelechatDocEvent
        for d in Document.objects.filter(docevent__telechatdocevent__telechat_date=date).distinct():
            if d.latest_event(TelechatDocEvent, type="scheduled_for_telechat").telechat_date == date:
                docs.append(d)
    t = loader.get_template('iesg/agenda_documents.txt')
    c = Context({'docs':docs,'special_stream_list':['ise','irtf']})
    return HttpResponse(t.render(c), mimetype='text/plain')

class RescheduleForm(forms.Form):
    telechat_date = forms.TypedChoiceField(coerce=lambda x: datetime.datetime.strptime(x, '%Y-%m-%d').date(), empty_value=None, required=False)
    clear_returning_item = forms.BooleanField(initial=False, required=False)

    def __init__(self, *args, **kwargs):
        dates = kwargs.pop('telechat_dates')
        
        super(self.__class__, self).__init__(*args, **kwargs)

        # telechat choices
        init = kwargs['initial']['telechat_date']
        if init and init not in dates:
            dates.insert(0, init)

        choices = [("", "(not on agenda)")]
        for d in dates:
            choices.append((d, d.strftime("%Y-%m-%d")))

        self.fields['telechat_date'].choices = choices

def handle_reschedule_form(request, doc, dates):
    initial = dict(
        telechat_date=doc.telechat_date if doc.on_upcoming_agenda() else None)

    formargs = dict(telechat_dates=dates,
                    prefix="%s" % doc.name,
                    initial=initial)
    if request.method == 'POST':
        form = RescheduleForm(request.POST, **formargs)
        if form.is_valid():
            login = request.user.get_profile()
            update_telechat(request, doc, login,
                            form.cleaned_data['telechat_date'],
                            False if form.cleaned_data['clear_returning_item'] else None)
            doc.time = datetime.datetime.now()
            doc.save()
    else:
        form = RescheduleForm(**formargs)

    form.show_clear = doc.returning_item()
    return form

def agenda_documents(request):
    dates = TelechatDates.objects.all()[0].dates()
    from ietf.doc.models import TelechatDocEvent
    docs = []
    for d in Document.objects.filter(docevent__telechatdocevent__telechat_date__in=dates).distinct():
        if d.latest_event(TelechatDocEvent, type="scheduled_for_telechat").telechat_date in dates:
            docs.append(d)

            e = d.latest_event(type="started_iesg_process")
            d.balloting_started = e.time if e else datetime.datetime.min
    docs.sort(key=lambda d: d.balloting_started)
    for i in docs:
        i.reschedule_form = handle_reschedule_form(request, i, dates)

    # some may have been taken off the schedule by the reschedule form
    docs = filter(lambda x: x.on_upcoming_agenda(), docs)
        
    telechats = []
    for date in dates:
        matches = filter(lambda x: x.telechat_date == date, docs)
        res = {}
        for i in matches:
            section_key = "s" + get_doc_section(i)
            if section_key not in res:
                res[section_key] = []
            if i.type_id=='draft':
                if i.get_state_slug()!="rfc":
                    i.iprUrl = "/ipr/search?option=document_search&id_document_tag=" + str(i.name)
                else:
                    i.iprUrl = "/ipr/search?option=rfc_search&rfc_search=" + str(i.rfc_number())
                i.iprCount = len(i.ipr())
            res[section_key].append(i)
        telechats.append({'date':date, 'docs':res})
    return direct_to_template(request, 'iesg/agenda_documents_redesign.html', {'telechats':telechats, 'hide_telechat_date':True})

def telechat_docs_tarfile(request,year,month,day):
    from tempfile import mkstemp
    date=datetime.date(int(year),int(month),int(day))
    if settings.USE_DB_REDESIGN_PROXY_CLASSES:
        from ietf.doc.models import TelechatDocEvent
        docs = []
        for d in IDInternal.objects.filter(docevent__telechatdocevent__telechat_date=date).distinct():
            if d.latest_event(TelechatDocEvent, type="scheduled_for_telechat").telechat_date == date:
                docs.append(d)
    else:
        docs= IDInternal.objects.filter(telechat_date=date, primary_flag=1, agenda=1)
    response = HttpResponse(mimetype='application/octet-stream')
    response['Content-Disposition'] = 'attachment; filename=telechat-%s-%s-%s-docs.tgz'%(year, month, day)
    tarstream = tarfile.open('','w:gz',response)
    mfh, mfn = mkstemp()
    manifest = open(mfn, "w")
    for doc in docs:
        doc_path = os.path.join(settings.INTERNET_DRAFT_PATH, doc.draft.filename+"-"+doc.draft.revision_display()+".txt")
        if os.path.exists(doc_path):
            try:
                tarstream.add(doc_path, str(doc.draft.filename+"-"+doc.draft.revision_display()+".txt"))
                manifest.write("Included:  "+doc_path+"\n")
            except Exception, e:
                manifest.write(("Failed (%s): "%e)+doc_path+"\n")
        else:
            manifest.write("Not found: "+doc_path+"\n")
    manifest.close()
    tarstream.add(mfn, "manifest.txt")
    tarstream.close()
    os.unlink(mfn)
    return response

def discusses(request):
    if settings.USE_DB_REDESIGN_PROXY_CLASSES:
        res = []

        for d in IDInternal.objects.filter(states__type="draft-iesg", states__slug__in=("pub-req", "ad-eval", "review-e", "lc-req", "lc", "writeupw", "goaheadw", "iesg-eva", "defer", "watching"), docevent__ballotpositiondocevent__pos="discuss").distinct():
            found = False
            for p in d.positions.all():
                if p.discuss:
                    found = True
                    break

            if not found:
                continue

            if d.rfc_flag:
                doc = RfcWrapper(d)
            else:
                doc = IdWrapper(draft=d)

            if doc.in_ietf_process() and doc.ietf_process.has_active_iesg_ballot():
                res.append(doc)

        return direct_to_template(request, 'iesg/discusses.html', {'docs':res})
    
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


if not settings.USE_DB_REDESIGN_PROXY_CLASSES:
    class TelechatDatesForm(forms.ModelForm):
        class Meta:
            model = TelechatDates
            fields = ['date1', 'date2', 'date3', 'date4']

@group_required('Secretariat')
def telechat_dates(request):
    if settings.USE_DB_REDESIGN_PROXY_CLASSES:
        return HttpResponseRedirect("/admin/iesg/telechatdate/")

    dates = TelechatDates.objects.all()[0]

    if request.method == 'POST':
        if request.POST.get('rollup_dates'):
            TelechatDates.objects.all().update(
                date1=dates.date2, date2=dates.date3, date3=dates.date4,
                date4=dates.date4 + datetime.timedelta(days=14))
            form = TelechatDatesForm(instance=dates)
        else:
            form = TelechatDatesForm(request.POST, instance=dates)
            if form.is_valid():
                form.save(commit=False)
                TelechatDates.objects.all().update(date1 = dates.date1,
                                                  date2 = dates.date2,
                                                  date3 = dates.date3,
                                                  date4 = dates.date4)
    else:
        form = TelechatDatesForm(instance=dates)

    from django.contrib.humanize.templatetags import humanize
    for f in form.fields:
        form.fields[f].label = "Date " + humanize.ordinal(form.fields[f].label[4])
        form.fields[f].thursday = getattr(dates, f).isoweekday() == 4
        
    return render_to_response("iesg/telechat_dates.html",
                              dict(form=form),
                              context_instance=RequestContext(request))

def parse_wg_action_file(path):
    f = open(path, 'rU')
    
    line = f.readline()
    while line and not line.strip():
        line = f.readline()

    # name
    m = re.search(r'([^\(]*) \(', line)
    if not m:
        return None
    name = m.group(1)

    # acronym
    m = re.search(r'\((\w+)\)', line)
    if not m:
        return None
    acronym = m.group(1)

    # date
    line = f.readline()
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})', line)
    while line and not m:
        line = f.readline()
        m = re.search(r'(\d{4})-(\d{2})-(\d{2})', line)

    last_updated = None
    if m:
        try:
            last_updated = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except:
            pass

    # token
    line = f.readline()
    while line and not 'area director' in line.lower():
        line = f.readline()

    line = f.readline()
    line = f.readline()
    m = re.search(r'\s*(\w+)\s*', line)
    token = ""
    if m:
        token = m.group(1)

    return dict(filename=os.path.basename(path), name=name, acronym=acronym,
                status_date=last_updated, token=token)

def get_possible_wg_actions():
    res = []
    charters = glob.glob(os.path.join(settings.IESG_WG_EVALUATION_DIR, '*-charter.txt'))
    for path in charters:
        d = parse_wg_action_file(path)
        if d:
            if not d['status_date']:
                d['status_date'] = datetime.date(1900,1,1)
            res.append(d)

    res.sort(key=lambda x: x['status_date'])

    return res


@group_required('Area_Director', 'Secretariat')
def working_group_actions(request):
    current_items = WGAction.objects.order_by('status_date').select_related()

    if request.method == 'POST' and in_group(request.user, 'Secretariat'):
        filename = request.POST.get('filename')
        if filename and filename in os.listdir(settings.IESG_WG_EVALUATION_DIR):
            if 'delete' in request.POST:
                os.unlink(os.path.join(settings.IESG_WG_EVALUATION_DIR, filename))
            if 'add' in request.POST:
                d = parse_wg_action_file(os.path.join(settings.IESG_WG_EVALUATION_DIR, filename))
                qstr = "?" + "&".join("%s=%s" % t for t in d.iteritems())
                return HttpResponseRedirect(urlreverse('iesg_add_working_group_action') + qstr)
    

    skip = [c.group_acronym.acronym for c in current_items]
    possible_items = filter(lambda x: x['acronym'] not in skip,
                            get_possible_wg_actions())
    
    return render_to_response("iesg/working_group_actions.html",
                              dict(current_items=current_items,
                                   possible_items=possible_items),
                              context_instance=RequestContext(request))

class EditWGActionForm(forms.ModelForm):
    token_name = forms.ChoiceField(required=True)
    telechat_date = forms.TypedChoiceField(coerce=lambda x: datetime.datetime.strptime(x, '%Y-%m-%d').date(), empty_value=None, required=False)

    class Meta:
        model = WGAction
        fields = ['status_date', 'token_name', 'category', 'note']

    def __init__(self, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)

        # token name choices
        self.fields['token_name'].choices = [("", "(None)")] + [(p.plain_name(), p.plain_name()) for p in IESGLogin.active_iesg().order_by('first_name')]
        
        # telechat choices
        dates = TelechatDates.objects.all()[0].dates()
        init = kwargs['initial']['telechat_date']
        if init and init not in dates:
            dates.insert(0, init)

        choices = [("", "(not on agenda)")]
        for d in dates:
            choices.append((d, d.strftime("%Y-%m-%d")))

        self.fields['telechat_date'].choices = choices
        
        
@group_required('Secretariat')
def edit_working_group_action(request, wga_id):
    if wga_id != None:
        wga = get_object_or_404(WGAction, pk=wga_id)
    else:
        wga = WGAction()
        try:
            wga.group_acronym = Acronym.objects.get(acronym=request.GET.get('acronym'))
        except Acronym.DoesNotExist:
            pass
        
        wga.token_name = request.GET.get('token')
        try:
            d = datetime.datetime.strptime(request.GET.get('status_date'), '%Y-%m-%d').date()
        except:
            d = datetime.date.today()
        wga.status_date = d
        wga.telechat_date = TelechatDates.objects.all()[0].date1
        wga.agenda = True

    initial = dict(telechat_date=wga.telechat_date if wga.agenda else None)

    if request.method == 'POST':
        if "delete" in request.POST:
            wga.delete()
            return HttpResponseRedirect(urlreverse('iesg_working_group_actions'))

        form = EditWGActionForm(request.POST, instance=wga, initial=initial)
        if form.is_valid():
            form.save(commit=False)
            wga.agenda = bool(form.cleaned_data['telechat_date'])
            if wga.category in (11, 21):
                wga.agenda = False
            if wga.agenda:
                wga.telechat_date = form.cleaned_data['telechat_date']
            wga.save()
            return HttpResponseRedirect(urlreverse('iesg_working_group_actions'))
    else:
        form = EditWGActionForm(instance=wga, initial=initial)
        

    return render_to_response("iesg/edit_working_group_action.html",
                              dict(wga=wga,
                                   form=form),
                              context_instance=RequestContext(request))
