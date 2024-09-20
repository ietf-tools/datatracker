# Copyright The IETF Trust 2007-2020, All Rights Reserved
# -*- coding: utf-8 -*-
#
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


import datetime
import io
import itertools
import json
import os
import tarfile
import time
from dateutil import relativedelta

from django import forms
from django.conf import settings
from django.db import models
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.sites.models import Site
from django.urls import reverse as urlreverse
from django.utils.encoding import force_bytes
#from django.views.decorators.cache import cache_page
#from django.views.decorators.vary import vary_on_cookie

import debug               # pyflakes:ignore

from ietf.doc.models import Document, State, LastCallDocEvent, ConsensusDocEvent, DocEvent, IESG_BALLOT_ACTIVE_STATES
from ietf.doc.utils import update_telechat, augment_events_with_revision
from ietf.group.models import GroupMilestone, Role
from ietf.iesg.agenda import agenda_data, agenda_sections, fill_in_agenda_docs, get_agenda_date
from ietf.iesg.models import TelechatDate, TelechatAgendaContent
from ietf.iesg.utils import telechat_page_count
from ietf.ietfauth.utils import has_role, role_required, user_is_person
from ietf.name.models import TelechatAgendaSectionName
from ietf.person.models import Person
from ietf.meeting.utils import get_activity_stats
from ietf.doc.utils_search import fill_in_document_table_attributes, fill_in_telechat_date
from ietf.utils.timezone import date_today, datetime_from_date

def review_decisions(request, year=None):
    events = DocEvent.objects.filter(type__in=("iesg_disapproved", "iesg_approved"))

    years = sorted((d.year for d in events.dates('time', 'year')), reverse=True)

    if year:
        year = int(year)
        events = events.filter(time__year=year)
    else:
        d = date_today() - datetime.timedelta(days=185)
        d = datetime.date(d.year, d.month, 1)
        events = events.filter(time__gte=datetime_from_date(d))

    events = events.select_related("doc", "doc__intended_std_level").order_by("-time", "-id")

    #proto_levels = ["bcp", "ds", "ps", "std"]
    #doc_levels = ["exp", "inf"]

    timeframe = "%s" % year if year else "the past 6 months"

    return render(request, 'iesg/review_decisions.html',
                              dict(events=events,
                                   years=years,
                                   year=year,
                                   timeframe=timeframe),
                              )

def agenda_json(request, date=None):
    data = agenda_data(date)

    res = {
        "telechat-date": str(data["date"]),
        "as-of": str(datetime.datetime.utcnow()),
        "page-counts": telechat_page_count(date=get_agenda_date(date))._asdict(),
        "sections": {},
        }

    for num, section in data["sections"].items():
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
                    'docname': doc.name,
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
                    'docname':doc.name,
                    'title':doc.title,
                    'ad':doc.ad.name if doc.ad else None,
                    }

                defer = doc.active_defer_event()
                if defer:
                    docinfo['defer-by'] = defer.by.name
                    docinfo['defer-at'] = str(defer.time)
                if doc.type_id == "draft":
                    docinfo['rev'] = doc.rev
                    docinfo['intended-std-level'] = str(doc.intended_std_level)
                    if doc.type_id == "rfc":
                        docinfo['rfc-number'] = doc.rfc_number

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
                    td = doc.relateddocument_set.get(relationship__slug='conflrev').target
                    docinfo['target-docname'] = td.name
                    docinfo['target-title'] = td.title
                    docinfo['target-rev'] = td.rev
                    docinfo['intended-std-level'] = str(td.intended_std_level)
                    docinfo['stream'] = str(td.stream)
                else:
                    # XXX check this -- is there nothing to set for
                    # all other documents here?
                    pass

                s["docs"].append(docinfo)

    return HttpResponse(json.dumps(res, indent=2), content_type='application/json')

# def past_agendas(request):
#     # This is not particularly useful with the current way of constructing
#     # an agenda, because the code and data strucutes assume we're showing
#     # the current agenda, and documents on later agendas won't show on
#     # earlier agendas, even if they were actually on them.
#     telechat_dates = TelechatDate.objects.filter(date__lt=datetime.date.today(), date__gte=datetime.date(2012,3,1))
#     return render(request, 'iesg/past_agendas.html', {'telechat_dates': telechat_dates })

def agenda(request, date=None):
    data = agenda_data(date)

    if has_role(request.user, ["Area Director", "IAB Chair", "Secretariat"]):
        data["sections"]["1.1"]["title"] = data["sections"]["1.1"]["title"].replace(
            "Roll call",
            '<a href="{}">Roll Call</a>'.format(
                urlreverse("ietf.iesg.views.telechat_agenda_content_view", kwargs={"section": "roll_call"})
            )
        )
        data["sections"]["1.3"]["title"] = data["sections"]["1.3"]["title"].replace(
            "minutes",
            '<a href="{}">Minutes</a>'.format(
                urlreverse("ietf.iesg.views.telechat_agenda_content_view", kwargs={"section": "minutes"})
            ))

    return render(request, "iesg/agenda.html", {
            "date": data["date"],
            "sections": sorted(data["sections"].items(), key=lambda x:[int(p) for p in x[0].split('.')]),
            "settings": settings,
            } )

def agenda_txt(request, date=None):
    data = agenda_data(date)
    return render(request, "iesg/agenda.txt", {
            "date": data["date"],
            "sections": sorted(data["sections"].items(), key=lambda x:[int(p) for p in x[0].split('.')]),
            "domain": Site.objects.get_current().domain,
            }, content_type="text/plain; charset=%s"%settings.DEFAULT_CHARSET)

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
    sections = sorted((num, section) for num, section in data["sections"].items()
                      if leaf_section(num, section))

    # add parents field to each section
    for num, s in sections:
        s["parents"] = []
        split = num.split(".")

        for i in range(num.count(".")):
            parent_num = ".".join(split[:i + 1])
            parent = data["sections"].get(parent_num)
            if parent:
                s["parents"].append((parent_num, parent))


    # put each document in its own section
    flattened_sections = []
    for num, s in sections:
        if "2" <= num < "5" and "docs" in s and s["docs"]:
            for i, d in enumerate(s["docs"], start=1):
                downrefs = [rel for rel in d.relateddocument_set.all() if rel.is_downref() and not rel.is_approved_downref()]
                flattened_sections.append((num, {
                            "title": s["title"] + " (%s of %s)" % (i, len(s["docs"])),
                            "doc": d,
                            "downrefs": downrefs,
                            "parents": s["parents"],
                            }))
        else:
            flattened_sections.append((num, s))

    # add ads
    data["sections"]["7"]["ads"] = sorted(Person.objects.filter(role__name="ad", role__group__state="active", role__group__type="area"),
                                          key=lambda p: p.name_parts()[3])

    return render(request, "iesg/moderator_package.html", {
            "date": data["date"],
            "sections": flattened_sections,
            } )

@role_required('Area Director', 'Secretariat')
def agenda_package(request, date=None):
    data = agenda_data(date)
    return render(request, "iesg/agenda_package.txt", {
            "date": data["date"],
            "sections": sorted(data["sections"].items()),
            "roll_call": data["sections"]["1.1"]["text"],
            "minutes": data["sections"]["1.3"]["text"],
            "management_items": [(num, section) for num, section in data["sections"].items() if "6" < num < "7"],
            "domain": Site.objects.get_current().domain,
            }, content_type='text/plain')


def agenda_documents_txt(request):
    dates = list(TelechatDate.objects.active().order_by('date').values_list("date", flat=True)[:4])

    all_docs = Document.objects.filter(docevent__telechatdocevent__telechat_date__in=dates).distinct()
    docs = []
    fill_in_telechat_date(all_docs)

    for d in all_docs:
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
            str(d.intended_std_level),
            "1" if d.stream_id in ("ise", "irtf") else "0",
            (d.area_acronym() or 'none').lower(),
            d.ad.plain_name() if d.ad else "None Assigned",
            d.rev,
            )
        rows.append("\t".join(row))
    return HttpResponse("\n".join(rows), content_type='text/plain')

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
            e = update_telechat(request, doc, request.user.person,
                                form.cleaned_data['telechat_date'],
                                False if form.cleaned_data['clear_returning_item'] else None)
            if e:
                doc.save_with_history([e])

            status["changed"] = True
    else:
        form = RescheduleForm(**formargs)

    form.show_clear = doc.returning_item()
    return form

def agenda_documents(request):
    ad = request.user.person if has_role(request.user, "Area Director") else None

    dates = list(TelechatDate.objects.active().order_by('date').values_list("date", flat=True)[:4])

    docs_by_date = dict((d, []) for d in dates)
    docs = Document.objects.filter(docevent__telechatdocevent__telechat_date__in=dates).distinct()
    docs = docs.select_related("ad", "std_level", "intended_std_level", "group", "stream", "shepherd", )
    # No prefetch-related -- turns out not to be worth it

    fill_in_telechat_date(docs)
    for doc in docs:
        d = doc.telechat_date()
        if d in docs_by_date:
            docs_by_date[d].append(doc)

    reschedule_status = { "changed": False }

    for i in itertools.chain(*list(docs_by_date.values())):
        i.reschedule_form = handle_reschedule_form(request, i, dates, reschedule_status)

    if reschedule_status["changed"]:
        # if any were changed, redirect so the browser history is preserved
        return redirect("ietf.iesg.views.agenda_documents")

    telechats = []
    for date in dates:
        sections = agenda_sections()
        # augment the docs with the search attributes, since we're using
        # the search_result_row view to display them (which expects them)
        fill_in_document_table_attributes(docs_by_date[date], have_telechat_date=True)
        fill_in_agenda_docs(date, sections, docs_by_date[date])
        page_count = telechat_page_count(docs=docs_by_date[date], ad=ad)
        pages = page_count.for_approval
        
        telechats.append({
                "date":     date,
                "pages":    pages,
                "ad_pages_left_to_ballot_on": page_count.ad_pages_left_to_ballot_on,
                "sections": sorted((num, section) for num, section in sections.items()
                                   if "2" <= num < "5")
                })
    
    return render(request, 'iesg/agenda_documents.html', { 'telechats': telechats })

def past_documents(request):
    iesg_state_slugs = ('approved', 'iesg-eva')
    iesg_states = State.objects.filter(type='draft-iesg', slug__in=iesg_state_slugs)
    possible_docs = Document.objects.filter(models.Q(states__type="draft-iesg",
                                                     states__slug__in=iesg_state_slugs) |
                                            models.Q(states__type__in=("statchg", "conflrev"),
                                                     states__slug__in=("appr-pr", )),
                                        )
    possible_docs = possible_docs.select_related("stream", "group", "ad").distinct()

    docs = []
    for doc in possible_docs:
        ballot = doc.latest_ballot()
        blocking_positions = []
        if ballot:
            blocking_positions = [p for p in ballot.all_positions() if p.pos.blocking]
            if blocking_positions:
                augment_events_with_revision(doc, blocking_positions)

        doc.by_me = bool([p for p in blocking_positions if user_is_person(request.user, p.balloter)])
        doc.for_me = user_is_person(request.user, doc.ad)
        doc.milestones = doc.groupmilestone_set.filter(state="active").order_by("time").select_related("group")
        doc.blocking_positions = blocking_positions
        doc.telechat = doc.previous_telechat_date()
        doc.ballot = ballot

        if doc.telechat:
            docs.append(doc)

    # latest first
    #docs.sort(key=lambda d: d.latest_event().time, reverse=True)
    docs.sort(key=lambda d: d.telechat, reverse=True)

    return render(request, 'iesg/past_documents.html', { 'docs': docs, 'states': iesg_states })


def telechat_docs_tarfile(request, date):
    date = get_agenda_date(date)

    all_docs = Document.objects.filter(docevent__telechatdocevent__telechat_date=date).distinct()
    fill_in_telechat_date(all_docs)
    docs = []
    for d in all_docs:
        if d.telechat_date() == date:
            docs.append(d)

    response = HttpResponse(content_type='application/octet-stream')
    response['Content-Disposition'] = 'attachment; filename=telechat-%s-docs.tgz' % date.isoformat()

    tarstream = tarfile.open('', 'w:gz', response)

    manifest = io.BytesIO()

    for doc in docs:
        doc_path = force_bytes(os.path.join(doc.get_file_path(), doc.name + "-" + doc.rev + ".txt"))
        if os.path.exists(doc_path):
            try:
                tarstream.add(doc_path, str(doc.name + "-" + doc.rev + ".txt"))
                manifest.write(b"Included:  %s\n" % doc_path)
            except Exception as e:
                manifest.write(b"Failed (%s): %s\n" % (force_bytes(e), doc_path))
        else:
            manifest.write(b"Not found: %s\n" % doc_path)

    manifest.seek(0)
    t = tarfile.TarInfo(name="manifest.txt")
    t.size = len(manifest.getvalue())
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
    possible_docs = possible_docs.exclude(states__in=State.objects.filter(type="draft", slug="repl"))
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

        doc.by_me = bool([p for p in blocking_positions if user_is_person(request.user, p.balloter)])
        doc.for_me = user_is_person(request.user, doc.ad)
        doc.milestones = doc.groupmilestone_set.filter(state="active").order_by("time").select_related("group")
        doc.blocking_positions = blocking_positions
        doc.ballot = ballot

        docs.append(doc)

    # latest first
    docs.sort(key=lambda d: min(p.time for p in d.blocking_positions), reverse=True)

    return render(request, 'iesg/discusses.html', { 'docs': docs })

@role_required('Area Director', 'Secretariat')
def milestones_needing_review(request):
    # collect milestones, grouped on AD and group
    ads = {}
    for m in GroupMilestone.objects.filter(state="review").exclude(group__state="conclude").distinct().select_related("group"):
        if m.group.ad_role():
            groups = ads.setdefault(m.group.ad_role().person, {})
            milestones = groups.setdefault(m.group, [])
            milestones.append(m)

    ad_list = []
    for ad, groups in ads.items():
        ad_list.append(ad)
        ad.groups_needing_review = sorted(groups, key=lambda g: g.acronym)
        for g, milestones in groups.items():
            g.milestones_needing_review = sorted(
                milestones, key=lambda m: m.due if m.group.uses_milestone_dates else m.order
            )

    return render(request, 'iesg/milestones_needing_review.html',
                  dict(ads=sorted(ad_list, key=lambda ad: ad.plain_name()),))

def photos(request):
    roles = sorted(Role.objects.filter(group__type='area', group__state='active', name_id='ad'),key=lambda x: "" if x.group.acronym=="gen" else x.group.acronym)
    for role in roles:
        role.last_initial = role.person.last_name()[0]
    return render(request, 'iesg/photos.html', {'group_type': 'IESG', 'role': '', 'roles': roles })

def month_choices():
    choices = [(str(n).zfill(2), str(n).zfill(2)) for n in range(1, 13)]
    return choices

def year_choices():
    this_year = date_today().year
    choices = [(str(n), str(n)) for n in range(this_year, 2009, -1)]
    return choices

class ActivityForm(forms.Form):
    month = forms.ChoiceField(choices=month_choices, help_text='Month', required=True)
    year = forms.ChoiceField(choices=year_choices, help_text='Year', required=True)

def ietf_activity(request):
    # default date range for last month
    today = date_today()
    edate = today.replace(day=1)
    sdate = (edate - datetime.timedelta(days=1)).replace(day=1)
    if request.method == 'GET':
        form = ActivityForm(request.GET)
        if form.is_valid():
            month = form.cleaned_data['month']
            year = form.cleaned_data['year']
            sdate = datetime.date(int(year), int(month), 1)
            edate = sdate + relativedelta.relativedelta(months=1)
    
    # always pass back an unbound form to avoid annoying is-valid styling
    form = ActivityForm(initial={'month': str(sdate.month).zfill(2), 'year': sdate.year})
    context = get_activity_stats(sdate, edate)
    context['form'] = form
    return render(request, "iesg/ietf_activity_report.html", context)


class TelechatAgendaContentForm(forms.Form):
    text = forms.CharField(max_length=100_000, widget=forms.Textarea, required=False)


@role_required("Secretariat")
def telechat_agenda_content_edit(request, section):
    section = get_object_or_404(TelechatAgendaSectionName, slug=section, used=True)
    content = TelechatAgendaContent.objects.filter(section=section).first()
    initial = {"text": content.text} if content else {}
    if request.method == "POST":
        form = TelechatAgendaContentForm(data=request.POST, initial=initial)
        if form.is_valid():
            TelechatAgendaContent.objects.update_or_create(
                section=section, defaults={"text": form.cleaned_data["text"]}
            )
            return redirect("ietf.iesg.views.telechat_agenda_content_manage")
    else:
        form = TelechatAgendaContentForm(initial=initial)
    return render(request, "iesg/telechat_agenda_content_edit.html", {"section": section, "form": form})


@role_required("Secretariat")
def telechat_agenda_content_manage(request):
    # Fill in any missing instances with empty stand-ins. The edit view will create persistent instances if needed.
    contents = [
        TelechatAgendaContent.objects.filter(section=section).first() or TelechatAgendaContent(section=section)
        for section in TelechatAgendaSectionName.objects.filter(used=True)
    ]
    return render(request, "iesg/telechat_agenda_content_manage.html", {"contents": contents})


@role_required("Secretariat", "IAB Chair", "Area Director")
def telechat_agenda_content_view(request, section):
    content = get_object_or_404(TelechatAgendaContent, section__slug=section, section__used=True)
    return HttpResponse(content=content.text, content_type="text/plain")
