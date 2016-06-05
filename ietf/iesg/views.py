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

import os
import datetime
import tarfile
import StringIO
import time
import itertools
import json

import debug               # pyflakes:ignore


from django import forms
from django.conf import settings
from django.db import models
from django.http import HttpResponse
from django.shortcuts import render_to_response, render, redirect
from django.template import RequestContext
from django.contrib.sites.models import Site


from ietf.doc.models import Document, TelechatDocEvent, LastCallDocEvent, ConsensusDocEvent, DocEvent, IESG_BALLOT_ACTIVE_STATES
from ietf.doc.utils import update_telechat, augment_events_with_revision
from ietf.group.models import GroupMilestone, Role
from ietf.iesg.agenda import agenda_data, agenda_sections, fill_in_agenda_docs, get_agenda_date
from ietf.iesg.models import TelechatDate
from ietf.iesg.utils import telechat_page_count
from ietf.ietfauth.utils import has_role, role_required, user_is_person
from ietf.person.models import Person
from ietf.doc.utils_search import fill_in_document_table_attributes

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
    data = agenda_data(date)

    res = {
        "telechat-date": str(data["date"]),
        "as-of": str(datetime.datetime.utcnow()),
        "page-counts": telechat_page_count(get_agenda_date(date))._asdict(),
        "sections": {},
        }

    for num, section in data["sections"].iteritems():
        s = res["sections"][num] = {
            "title": section["title"],
            }

        if "docs" not in section:
            continue

        docs = section["docs"]

        if "4" <= num < "5":
            # charters
            s["wgs"] = []

            for doc in docs:
                wginfo = {
                    'docname': doc.canonical_name(),
                    'rev': doc.rev,
                    'wgname': doc.group.name,
                    'acronym': doc.group.acronym,
                    'ad': doc.group.ad_role().person.name if doc.group.ad_role() else None,
                    }

                # consider moving the charters to "docs" like the other documents
                s['wgs'].append(wginfo)
        else:
            # other documents
            s["docs"] = []

            for doc in docs:
                docinfo = {
                    'docname':doc.canonical_name(),
                    'title':doc.title,
                    'ad':doc.ad.name if doc.ad else None,
                    }

                if doc.note:
                    docinfo['note'] = doc.note
                defer = doc.active_defer_event()
                if defer:
                    docinfo['defer-by'] = defer.by.name
                    docinfo['defer-at'] = str(defer.time)
                if doc.type_id == "draft":
                    docinfo['rev'] = doc.rev
                    docinfo['intended-std-level'] = str(doc.intended_std_level)
                    if doc.rfc_number():
                        docinfo['rfc-number'] = doc.rfc_number()

                    iana_state = doc.get_state("draft-iana-review")
                    if iana_state and iana_state.slug in ("not-ok", "changed", "need-rev"):
                        docinfo['iana-review-state'] = str(iana_state)

                    if doc.get_state_slug("draft-iesg") == "lc":
                        e = doc.latest_event(LastCallDocEvent, type="sent_last_call")
                        if e:
                            docinfo['lastcall-expires'] = e.expires.strftime("%Y-%m-%d")

                    docinfo['consensus'] = None
                    e = doc.latest_event(ConsensusDocEvent, type="changed_consensus")
                    if e:
                        docinfo['consensus'] = e.consensus

                    docinfo['rfc-ed-note'] = doc.has_rfc_editor_note()

                elif doc.type_id == 'conflrev':
                    docinfo['rev'] = doc.rev
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

                s["docs"].append(docinfo)

    return HttpResponse(json.dumps(res, indent=2), content_type='text/plain')

def agenda(request, date=None):
    data = agenda_data(date)

    if has_role(request.user, ["Area Director", "IAB Chair", "Secretariat"]):
        data["sections"]["1.1"]["title"] = data["sections"]["1.1"]["title"].replace("Roll call", '<a href="https://www.ietf.org/iesg/internal/rollcall.txt">Roll Call</a>')
        data["sections"]["1.3"]["title"] = data["sections"]["1.3"]["title"].replace("minutes", '<a href="https://www.ietf.org/iesg/internal/minutes.txt">Minutes</a>')

    request.session['ballot_edit_return_point'] = request.path_info
    return render_to_response("iesg/agenda.html", {
            "date": data["date"],
            "sections": sorted(data["sections"].iteritems()),
            "settings": settings,
            }, context_instance=RequestContext(request))

def agenda_txt(request, date=None):
    data = agenda_data(date)
    return render_to_response("iesg/agenda.txt", {
            "date": data["date"],
            "sections": sorted(data["sections"].iteritems()),
            "domain": Site.objects.get_current().domain,
            }, context_instance=RequestContext(request), content_type="text/plain; charset=%s"%settings.DEFAULT_CHARSET)

def agenda_scribe_template(request, date=None):
    data = agenda_data(date)
    sections = sorted((num, section) for num, section in data["sections"].iteritems() if "2" <= num < "4")
    appendix_docs = []
    for num, section in sections:
        if "docs" in section:
            # why are we here including documents that have no discuss/comment?
            appendix_docs.extend(section["docs"])
    return render_to_response("iesg/scribe_template.html", {
            "date": data["date"],
            "sections": sections,
            "appendix_docs": appendix_docs,
            "domain": Site.objects.get_current().domain,
            }, context_instance=RequestContext(request) )

@role_required('Area Director', 'Secretariat')
def agenda_moderator_package(request, date=None):
    """Output telechat agenda with one page per section, with each
    document in its own section."""
    data = agenda_data(date)

    def leaf_section(num, section):
        return not (num == "1"
                    or "2" <= num < "5" and "docs" not in section
                    or (num == "6" and "6.1" not in data["sections"]))

    # sort and prune non-leaf headlines
    sections = sorted((num, section) for num, section in data["sections"].iteritems()
                      if leaf_section(num, section))

    # add parents field to each section
    for num, s in sections:
        s["parents"] = []
        split = num.split(".")

        for i in xrange(num.count(".")):
            parent_num = ".".join(split[:i + 1])
            parent = data["sections"].get(parent_num)
            if parent:
                s["parents"].append((parent_num, parent))


    # put each document in its own section
    flattened_sections = []
    for num, s in sections:
        if "2" <= num < "5" and "docs" in s and s["docs"]:
            for i, d in enumerate(s["docs"], start=1):
                flattened_sections.append((num, {
                            "title": s["title"] + " (%s of %s)" % (i, len(s["docs"])),
                            "doc": d,
                            "parents": s["parents"],
                            }))
        else:
            flattened_sections.append((num, s))

    # add ads
    data["sections"]["7"]["ads"] = sorted(Person.objects.filter(role__name="ad", role__group__state="active", role__group__type="area"),
                                          key=lambda p: p.name_parts()[3])

    return render_to_response("iesg/moderator_package.html", {
            "date": data["date"],
            "sections": flattened_sections,
            }, context_instance=RequestContext(request))

@role_required('Area Director', 'Secretariat')
def agenda_package(request, date=None):
    data = agenda_data(date)
    return render_to_response("iesg/agenda_package.txt", {
            "date": data["date"],
            "sections": sorted(data["sections"].iteritems()),
            "roll_call": data["sections"]["1.1"]["text"],
            "minutes": data["sections"]["1.3"]["text"],
            "management_items": [(num, section) for num, section in data["sections"].iteritems() if "6" < num < "7"],
            }, context_instance=RequestContext(request), content_type='text/plain')


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
    return HttpResponse(u"\n".join(rows), content_type='text/plain')

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

def handle_reschedule_form(request, doc, dates, status):
    initial = dict(telechat_date=doc.telechat_date())

    formargs = dict(telechat_dates=dates,
                    prefix="%s" % doc.name,
                    initial=initial)
    if request.method == 'POST':
        form = RescheduleForm(request.POST, **formargs)
        if form.is_valid():
            update_telechat(request, doc, request.user.person,
                            form.cleaned_data['telechat_date'],
                            False if form.cleaned_data['clear_returning_item'] else None)
            doc.time = datetime.datetime.now()
            doc.save()

            status["changed"] = True
    else:
        form = RescheduleForm(**formargs)

    form.show_clear = doc.returning_item()
    return form

def agenda_documents(request):
    dates = list(TelechatDate.objects.active().order_by('date').values_list("date", flat=True)[:4])

    docs_by_date = dict((d, []) for d in dates)
    for doc in Document.objects.filter(docevent__telechatdocevent__telechat_date__in=dates).select_related("stream", "group").distinct():
        d = doc.latest_event(TelechatDocEvent, type="scheduled_for_telechat").telechat_date
        if d in docs_by_date:
            docs_by_date[d].append(doc)

    reschedule_status = { "changed": False }

    for i in itertools.chain(*docs_by_date.values()):
        i.reschedule_form = handle_reschedule_form(request, i, dates, reschedule_status)

    if reschedule_status["changed"]:
        # if any were changed, redirect so the browser history is preserved
        return redirect("ietf.iesg.views.agenda_documents")

    telechats = []
    for date in dates:
        sections = agenda_sections()
        # augment the docs with the search attributes, since we're using
        # the search_result_row view to display them (which expects them)
        fill_in_document_table_attributes(docs_by_date[date])
        fill_in_agenda_docs(date, sections, docs_by_date[date])

        telechats.append({
                "date":date,
                "sections": sorted((num, section) for num, section in sections.iteritems()
                                   if "2" <= num < "5")
                })
    request.session['ballot_edit_return_point'] = request.path_info
    return render(request, 'iesg/agenda_documents.html', { 'telechats': telechats })

def telechat_docs_tarfile(request, date):
    date = get_agenda_date(date)

    docs = []
    for d in Document.objects.filter(docevent__telechatdocevent__telechat_date=date).distinct():
        if d.latest_event(TelechatDocEvent, type="scheduled_for_telechat").telechat_date == date:
            docs.append(d)

    response = HttpResponse(content_type='application/octet-stream')
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

    return render(request, 'iesg/discusses.html', { 'docs': docs })

@role_required('Area Director', 'Secretariat')
def milestones_needing_review(request):
    # collect milestones, grouped on AD and group
    ads = {}
    for m in GroupMilestone.objects.filter(state="review").exclude(group__state="concluded").distinct().select_related("group"):
        if m.group.ad_role():
            groups = ads.setdefault(m.group.ad_role().person, {})
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

def photos(request):
    roles = sorted(Role.objects.filter(group__type='area', group__state='active', name_id='ad'),key=lambda x: "" if x.group.acronym=="gen" else x.group.acronym)
    for role in roles:
        role.last_initial = role.person.last_name()[0]
    return render(request, 'iesg/photos.html', {'group_type': 'IESG', 'role': '', 'roles': roles })

    
