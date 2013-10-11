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
import tarfile, StringIO, time

from django.views.generic.simple import direct_to_template
from django.core.urlresolvers import reverse as urlreverse
from django.http import Http404, HttpResponse, HttpResponseForbidden, HttpResponseRedirect
from django.template import RequestContext, Context, loader
from django.shortcuts import render_to_response, get_object_or_404
from django.conf import settings
from django.utils import simplejson as json
from django.db import models
from django import forms

from ietf.iesg.models import TelechatDate, TelechatAgendaItem
from ietf.ipr.models import IprDocAlias
from ietf.doc.models import Document, TelechatDocEvent, LastCallDocEvent, ConsensusDocEvent, DocEvent, IESG_BALLOT_ACTIVE_STATES
from ietf.group.models import Group, GroupMilestone
from ietf.person.models import Person

from ietf.doc.utils import update_telechat, augment_events_with_revision
from ietf.ietfauth.utils import has_role, role_required, user_is_person
from ietf.iesg.agenda import *

def review_decisions(request, year=None):
    events = DocEvent.objects.filter(type__in=("iesg_disapproved", "iesg_approved"))

    years = sorted((d.year for d in events.dates('time', 'year')), reverse=True)

    if year:
        year = int(year)
        events = events.filter(time__year=year)
    else:
        d = datetime.date.today() - datetime.timedelta(days=185)
        d = datetime.date(d.year, d.month, 1)
        events = events.filter(time__gte=d)

    events = events.select_related("doc", "doc__intended_std_level").order_by("-time", "-id")

    #proto_levels = ["bcp", "ds", "ps", "std"]
    #doc_levels = ["exp", "inf"]

    timeframe = u"%s" % year if year else u"the past 6 months"

    return render_to_response('iesg/review_decisions.html',
                              dict(events=events,
                                   years=years,
                                   year=year,
                                   timeframe=timeframe),
                              context_instance=RequestContext(request))

def agenda_json(request, date=None):
    date = get_agenda_date(date)

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
    data['sections']['2.3'] = {'title':"Individual Submissions"}
    data['sections']['2.3.1'] = {'title':"New Items", 'docs':[]}
    data['sections']['2.3.2'] = {'title':"Returning Items", 'docs':[]}
    data['sections']['3'] = {'title':"Document Actions"}
    data['sections']['3.1'] = {'title':"WG Submissions"}
    data['sections']['3.1.1'] = {'title':"New Items", 'docs':[]}
    data['sections']['3.1.2'] = {'title':"Returning Items", 'docs':[]}
    data['sections']['3.2'] = {'title':"Individual Submissions Via AD"}
    data['sections']['3.2.1'] = {'title':"New Items", 'docs':[]}
    data['sections']['3.2.2'] = {'title':"Returning Items", 'docs':[]}
    data['sections']['3.3'] = {'title':"Status Changes"}
    data['sections']['3.3.1'] = {'title':"New Items", 'docs':[]}
    data['sections']['3.3.2'] = {'title':"Returning Items", 'docs':[]}
    data['sections']['3.4'] = {'title':"IRTF and Independent Submission Stream Documents"}
    data['sections']['3.4.1'] = {'title':"New Items", 'docs':[]}
    data['sections']['3.4.2'] = {'title':"Returning Items", 'docs':[]}
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

    docs = agenda_docs(date)
    for section in docs.keys():
        # in case the document is in a state that does not have an agenda section
        if section == 's':
            continue

        s = str(".".join(list(section)[1:]))
        if s[0:1] == '4':
            # ignore these; not sure why they are included by agenda_docs
            continue

        if not docs[section]:
            continue

        # If needed, add a "For Action" section to agenda
        if s[4:5] == '3':
            data['sections'][s] = {'title':"For Action", 'docs':[]}

        for d in docs[section]:
            docinfo = {'docname':d.canonical_name(),
                       'title':d.title,
                       'ad':d.ad.name if d.ad else None }
            if d.note:
                docinfo['note'] = d.note
            defer = d.active_defer_event()
            if defer:
                docinfo['defer-by'] = defer.by.name
                docinfo['defer-at'] = str(defer.time)
            if d.type_id == "draft":
                docinfo['rev'] = d.rev
                docinfo['intended-std-level'] = str(d.intended_std_level)
                if d.rfc_number():
                    docinfo['rfc-number'] = d.rfc_number()

                iana_state = d.get_state("draft-iana-review")
                if iana_state and iana_state.slug in ("not-ok", "changed", "need-rev"):
                    docinfo['iana-review-state'] = str(iana_state)

                if d.get_state_slug("draft-iesg") == "lc":
                    e = d.latest_event(LastCallDocEvent, type="sent_last_call")
                    if e:
                        docinfo['lastcall-expires'] = e.expires.strftime("%Y-%m-%d")

                docinfo['consensus'] = None
                e = d.latest_event(ConsensusDocEvent, type="changed_consensus")
                if e:
                    docinfo['consensus'] = e.consensus
            elif d.type_id == 'conflrev':
                docinfo['rev'] = d.rev
                td = d.relateddocument_set.get(relationship__slug='conflrev').target.document
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
        if section == 's':
            continue

        s = str(".".join(list(section)[1:]))
        if s[0:1] != '4':
            # ignore these; not sure why they are included by agenda_wg_actions
            continue

        if not wgs[section]:
            continue

        for doc in wgs[section]:
            wginfo = {'docname': doc.canonical_name(),
                      'rev': doc.rev,
                      'wgname': doc.group.name,
                      'acronym': doc.group.acronym,
                      'ad': doc.group.ad.name if doc.group.ad else None}
            data['sections'][s]['wgs'] += [wginfo, ]

    mgmt = agenda_management_issues(date)
    num = 0
    for m in mgmt:
        num += 1
        data['sections']["6.%d" % num] = {'title':m.title}

    return HttpResponse(json.dumps(data, indent=2), mimetype='text/plain')

def agenda(request, date=None):
    data = agenda_data(request, date)
    data['settings'] = settings
    return render_to_response("iesg/agenda.html", data, context_instance=RequestContext(request))

def agenda_txt(request, date=None):
    data = agenda_data(request, date)
    return render_to_response("iesg/agenda.txt", data, context_instance=RequestContext(request), mimetype="text/plain")

def agenda_scribe_template(request, date=None):
    date = get_agenda_date(date)
    docs = agenda_docs(date)
    return render_to_response('iesg/scribe_template.html', { 'date':str(date), 'docs':docs }, context_instance=RequestContext(request) )

@role_required('Area Director', 'Secretariat')
def agenda_moderator_package(request, date=None):
    data = agenda_data(request, date)
    data['ads'] = sorted(Person.objects.filter(role__name="ad", role__group__state="active"),
                         key=lambda p: p.name_parts()[3])
    return render_to_response("iesg/moderator_package.html", data, context_instance=RequestContext(request))

@role_required('Area Director', 'Secretariat')
def agenda_package(request, date=None):
    data = agenda_data(request)
    return render_to_response("iesg/agenda_package.txt", data, context_instance=RequestContext(request), mimetype='text/plain')


def agenda_documents_txt(request):
    dates = list(TelechatDate.objects.active().order_by('date').values_list("date", flat=True)[:4])

    docs = []
    for d in Document.objects.filter(docevent__telechatdocevent__telechat_date__in=dates).distinct():
        date = d.telechat_date()
        if date in dates:
            d.computed_telechat_date = date
            docs.append(d)
    docs.sort(key=lambda d: d.computed_telechat_date)

    # output table
    rows = []
    rows.append("# Fields: telechat date, filename (draft-foo-bar or rfc1234), intended status, rfc editor submission flag (0=no, 1=yes), area acronym, AD name, version")
    for d in docs:
        row = (
            d.computed_telechat_date.isoformat(),
            d.name,
            unicode(d.intended_std_level),
            "1" if d.stream_id in ("ise", "irtf") else "0",
            unicode(d.area_acronym()).lower(),
            d.ad.plain_name() if d.ad else "None Assigned",
            d.rev,
            )
        rows.append("\t".join(row))
    return HttpResponse(u"\n".join(rows), mimetype='text/plain')

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
    initial = dict(telechat_date=doc.telechat_date())

    formargs = dict(telechat_dates=dates,
                    prefix="%s" % doc.name,
                    initial=initial)
    if request.method == 'POST':
        form = RescheduleForm(request.POST, **formargs)
        if form.is_valid():
            update_telechat(request, doc, request.user.get_profile(),
                            form.cleaned_data['telechat_date'],
                            False if form.cleaned_data['clear_returning_item'] else None)
            doc.time = datetime.datetime.now()
            doc.save()
    else:
        form = RescheduleForm(**formargs)

    form.show_clear = doc.returning_item()
    return form

def agenda_documents(request):
    dates = list(TelechatDate.objects.active().order_by('date').values_list("date", flat=True)[:4])
    docs = []
    for d in Document.objects.filter(docevent__telechatdocevent__telechat_date__in=dates).select_related().distinct():
        if d.latest_event(TelechatDocEvent, type="scheduled_for_telechat").telechat_date in dates:
            docs.append(d)

            e = d.latest_event(type="started_iesg_process")
            d.balloting_started = e.time if e else datetime.datetime.min
    docs.sort(key=lambda d: d.balloting_started)

    for i in docs:
        i.reschedule_form = handle_reschedule_form(request, i, dates)

    # some may have been taken off the schedule by the reschedule form
    docs = [d for d in docs if d.telechat_date() in dates]

    telechats = []
    for date in dates:
        matches = filter(lambda x: x.telechat_date() == date, docs)
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
    return direct_to_template(request, 'iesg/agenda_documents.html', { 'telechats':telechats })

def telechat_docs_tarfile(request, date):
    date = get_agenda_date(date)

    docs = []
    for d in Document.objects.filter(docevent__telechatdocevent__telechat_date=date).distinct():
        if d.latest_event(TelechatDocEvent, type="scheduled_for_telechat").telechat_date == date:
            docs.append(d)

    response = HttpResponse(mimetype='application/octet-stream')
    response['Content-Disposition'] = 'attachment; filename=telechat-%s-docs.tgz' % date.isoformat()

    tarstream = tarfile.open('', 'w:gz', response)

    manifest = StringIO.StringIO()

    for doc in docs:
        doc_path = os.path.join(doc.get_file_path(), doc.name + "-" + doc.rev + ".txt")
        if os.path.exists(doc_path):
            try:
                tarstream.add(doc_path, str(doc.name + "-" + doc.rev + ".txt"))
                manifest.write("Included:  %s\n" % doc_path)
            except Exception as e:
                manifest.write("Failed (%s): %s\n" % (e, doc_path))
        else:
            manifest.write("Not found: %s\n" % doc_path)

    manifest.seek(0)
    t = tarfile.TarInfo(name="manifest.txt")
    t.size = len(manifest.buf)
    t.mtime = time.time()
    tarstream.addfile(t, manifest)

    tarstream.close()

    return response

def discusses(request):
    possible_docs = Document.objects.filter(models.Q(states__type="draft-iesg",
                                                     states__slug__in=IESG_BALLOT_ACTIVE_STATES) |
                                            models.Q(states__type="charter",
                                                     states__slug__in=("intrev", "iesgrev")) |
                                            models.Q(states__type__in=("statchg", "conflrev"),
                                                     states__slug__in=("iesgeval", "defer")),
                                            docevent__ballotpositiondocevent__pos__blocking=True)
    possible_docs = possible_docs.select_related("stream", "group", "ad").distinct()

    docs = []
    for doc in possible_docs:
        ballot = doc.active_ballot()
        if not ballot:
            continue

        blocking_positions = [p for p in ballot.all_positions() if p.pos.blocking]

        if not blocking_positions:
            continue

        augment_events_with_revision(doc, blocking_positions)

        doc.by_me = bool([p for p in blocking_positions if user_is_person(request.user, p.ad)])
        doc.for_me = user_is_person(request.user, doc.ad)
        doc.milestones = doc.groupmilestone_set.filter(state="active").order_by("time").select_related("group")
        doc.blocking_positions = blocking_positions

        docs.append(doc)

    # latest first
    docs.sort(key=lambda d: min(p.time for p in d.blocking_positions), reverse=True)

    return direct_to_template(request, 'iesg/discusses.html', { 'docs': docs })

@role_required('Area Director', 'Secretariat')
def milestones_needing_review(request):
    # collect milestones, grouped on AD and group
    ads = {}
    for m in GroupMilestone.objects.filter(state="review").exclude(group__state="concluded", group__ad=None).distinct().select_related("group", "group__ad"):
        groups = ads.setdefault(m.group.ad, {})
        milestones = groups.setdefault(m.group, [])
        milestones.append(m)

    ad_list = []
    for ad, groups in ads.iteritems():
        ad_list.append(ad)
        ad.groups_needing_review = sorted(groups, key=lambda g: g.acronym)
        for g, milestones in groups.iteritems():
            g.milestones_needing_review = sorted(milestones, key=lambda m: m.due)

    return render_to_response('iesg/milestones_needing_review.html',
                              dict(ads=sorted(ad_list, key=lambda ad: ad.plain_name()),
                                   ),
                              context_instance=RequestContext(request))

