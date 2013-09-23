# Copyright The IETF Trust 2008, All Rights Reserved

# Portion Copyright (C) 2010 Nokia Corporation and/or its subsidiary(-ies).
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

import itertools

from django.shortcuts import get_object_or_404, render_to_response
from django.template import RequestContext
from django.http import HttpResponse
from django.conf import settings
from django.core.urlresolvers import reverse as urlreverse

from ietf.doc.views_search import SearchForm, retrieve_search_results
from ietf.ipr.models import IprDetail
from ietf.group.models import Group, GroupURL
from ietf.doc.models import State, DocAlias, RelatedDocument
from ietf.doc.utils import get_chartering_type
from ietf.person.models import Email
from ietf.group.utils import get_charter_text
from ietf.doc.templatetags.ietf_filters import clean_whitespace
from ietf.ietfauth.utils import has_role


def fill_in_charter_info(group, include_drafts=False):
    group.areadirector = group.ad.role_email("ad", group.parent) if group.ad else None
    group.chairs = Email.objects.filter(role__group=group, role__name="chair").select_related("person")
    group.techadvisors = Email.objects.filter(role__group=group, role__name="techadv").select_related("person")
    group.editors = Email.objects.filter(role__group=group, role__name="editor").select_related("person")
    group.secretaries = Email.objects.filter(role__group=group, role__name="secr").select_related("person")
    milestone_state = "charter" if group.state_id == "proposed" else "active"
    group.milestones = group.groupmilestone_set.filter(state=milestone_state).order_by('due')

    if group.charter:
        group.charter_text = get_charter_text(group)
    else:
        group.charter_text = u"Not chartered yet."

    if include_drafts:
        aliases = DocAlias.objects.filter(document__type="draft", document__group=group).select_related('document').order_by("name")
        group.drafts = []
        group.rfcs = []
        for a in aliases:
            if a.name.startswith("draft"):
                group.drafts.append(a)
            else:
                group.rfcs.append(a)
                a.rel = RelatedDocument.objects.filter(source=a.document).distinct()
                a.invrel = RelatedDocument.objects.filter(target=a).distinct()

def extract_last_name(email):
    return email.person.name_parts()[3]

def extract_group_chairs(group):
    return sorted(Email.objects.filter(role__group=group, role__name="chair").select_related("person"), key=extract_last_name)

def wg_summary_area(request):
    areas = Group.objects.filter(type="area", state="active").order_by("name")
    for area in areas:
        area.ads = sorted(Email.objects.filter(role__group=area, role__name="ad").select_related("person"), key=extract_last_name)
        area.groups = Group.objects.filter(parent=area, type="wg", state="active").order_by("acronym")
        for group in area.groups:
            group.chairs = extract_group_chairs(group)

    areas = [a for a in areas if a.groups]

    return render_to_response('wginfo/1wg-summary.txt',
                              { 'areas': areas },
                              mimetype='text/plain; charset=UTF-8')

def wg_summary_acronym(request):
    areas = Group.objects.filter(type="area", state="active").order_by("name")
    groups = Group.objects.filter(type="wg", state="active").order_by("acronym").select_related("parent")
    for group in groups:
        group.chairs = extract_group_chairs(group)
    return render_to_response('wginfo/1wg-summary-by-acronym.txt',
                              { 'areas': areas,
                                'groups': groups },
                              mimetype='text/plain; charset=UTF-8')

def wg_charters(request):
    areas = Group.objects.filter(type="area", state="active").order_by("name")
    for area in areas:
        area.ads = sorted(Email.objects.filter(role__group=area, role__name="ad").select_related("person"), key=extract_last_name)
        area.groups = Group.objects.filter(parent=area, type="wg", state="active").order_by("name")
        for group in area.groups:
            fill_in_charter_info(group, include_drafts=True)
            group.area = area
    return render_to_response('wginfo/1wg-charters.txt',
                              { 'areas': areas },
                              mimetype='text/plain; charset=UTF-8')

def wg_charters_by_acronym(request):
    areas = dict((a.id, a) for a in Group.objects.filter(type="area", state="active").order_by("name"))

    for area in areas.itervalues():
        area.ads = sorted(Email.objects.filter(role__group=area, role__name="ad").select_related("person"), key=extract_last_name)

    groups = Group.objects.filter(type="wg", state="active").exclude(parent=None).order_by("acronym")
    for group in groups:
        fill_in_charter_info(group, include_drafts=True)
        group.area = areas.get(group.parent_id)
    return render_to_response('wginfo/1wg-charters-by-acronym.txt',
                              { 'groups': groups },
                              mimetype='text/plain; charset=UTF-8')

def active_wgs(request):
    areas = Group.objects.filter(type="area", state="active").order_by("name")
    for area in areas:
        # dig out information for template
        area.ads = []
        for e in Email.objects.filter(role__group=area, role__name="ad").select_related("person"):
            e.incoming = False
            area.ads.append(e)

        for e in Email.objects.filter(role__group=area, role__name="pre-ad").select_related("person"):
            e.incoming = True
            area.ads.append(e)

        area.ads.sort(key=lambda e: (e.incoming, extract_last_name(e)))
        area.wgs = Group.objects.filter(parent=area, type="wg", state="active").order_by("acronym")
        area.urls = area.groupurl_set.all().order_by("name")
        for wg in area.wgs:
            wg.chairs = extract_group_chairs(wg)

    return render_to_response('wginfo/active_wgs.html', {'areas':areas}, RequestContext(request))

def bofs(request):
    groups = Group.objects.filter(type="wg", state="bof")
    return render_to_response('wginfo/bofs.html',dict(groups=groups), RequestContext(request))

def chartering_wgs(request):
    charter_states = State.objects.filter(used=True, type="charter").exclude(slug__in=("approved", "notrev"))
    groups = Group.objects.filter(type="wg", charter__states__in=charter_states).select_related("state", "charter")

    for g in groups:
        g.chartering_type = get_chartering_type(g.charter)

    return render_to_response('wginfo/chartering_wgs.html',
                              dict(charter_states=charter_states,
                                   groups=groups),
                              RequestContext(request))


def construct_group_menu_context(request, group, selected, others):
    """Return context with info for the group menu filled in."""
    actions = []

    is_chair = group.has_role(request.user, "chair")
    is_ad_or_secretariat = has_role(request.user, ("Area Director", "Secretariat"))

    if group.state_id != "proposed" and (is_chair or is_ad_or_secretariat):
        actions.append((u"Add or edit milestones", urlreverse("wg_edit_milestones", kwargs=dict(acronym=group.acronym))))

    if group.state_id != "conclude" and is_ad_or_secretariat:
        actions.append((u"Edit group", urlreverse("group_edit", kwargs=dict(acronym=group.acronym))))

    if is_chair or is_ad_or_secretariat:
        actions.append((u"Customize workflow", urlreverse("ietf.wginfo.edit.customize_workflow", kwargs=dict(acronym=group.acronym))))

    if group.state_id in ("active", "dormant") and is_ad_or_secretariat:
        actions.append((u"Request closing group", urlreverse("wg_conclude", kwargs=dict(acronym=group.acronym))))

    d = {
        "group": group,
        "selected": selected,
        "menu_actions": actions,
        }

    d.update(others)

    return d

def search_for_group_documents(group):
    form = SearchForm({ 'by':'group', 'group': group.acronym or "", 'rfcs':'on', 'activedrafts': 'on' })
    docs, meta = retrieve_search_results(form)

    # get the related docs
    form_related = SearchForm({ 'by':'group', 'name': u'-%s-' % group.acronym, 'activedrafts': 'on' })
    raw_docs_related, meta_related = retrieve_search_results(form_related)

    docs_related = []
    for d in raw_docs_related:
        parts = d.name.split("-", 2);
        # canonical form draft-<name|ietf>-wg-etc
        if len(parts) >= 3 and parts[1] != "ietf" and parts[2].startswith(group.acronym + "-"):
            d.search_heading = "Related Internet-Draft"
            docs_related.append(d)

    # move call for WG adoption to related
    cleaned_docs = []
    docs_related_names = set(d.name for d in docs_related)
    for d in docs:
        if d.stream_id and d.get_state_slug("draft-stream-%s" % d.stream_id) in ("c-adopt", "wg-cand"):
            if d.name not in docs_related_names:
                d.search_heading = "Related Internet-Draft"
                docs_related.append(d)
        else:
            cleaned_docs.append(d)

    docs = cleaned_docs

    docs_related.sort(key=lambda d: d.name)

    return docs, meta, docs_related, meta_related

def group_documents(request, acronym):
    group = get_object_or_404(Group, type="wg", acronym=acronym)

    docs, meta, docs_related, meta_related = search_for_group_documents(group)

    return render_to_response('wginfo/group_documents.html',
                              construct_group_menu_context(request, group, "documents", {
                'docs': docs,
                'meta': meta,
                'docs_related': docs_related,
                'meta_related': meta_related
                }), RequestContext(request))

def group_documents_txt(request, acronym):
    """Return tabulator-separated rows with documents for group."""
    group = get_object_or_404(Group, type="wg", acronym=acronym)

    docs, meta, docs_related, meta_related = search_for_group_documents(group)

    for d in docs:
        d.prefix = d.get_state().name

    for d in docs_related:
        d.prefix = u"Related %s" % d.get_state().name

    rows = []
    for d in itertools.chain(docs, docs_related):
        rfc_number = d.rfc_number()
        if rfc_number != None:
            name = rfc_number
        else:
            name = "%s-%s" % (d.name, d.rev)

        rows.append(u"\t".join((d.prefix, name, clean_whitespace(d.title))))

    return HttpResponse(u"\n".join(rows), mimetype='text/plain; charset=UTF-8')


def group_charter(request, acronym):
    group = get_object_or_404(Group, type="wg", acronym=acronym)

    fill_in_charter_info(group, include_drafts=False)
    group.delegates = Email.objects.filter(role__group=group, role__name="delegate").select_related("person")

    e = group.latest_event(type__in=("changed_state", "requested_close",))
    requested_close = group.state_id != "conclude" and e and e.type == "requested_close"

    return render_to_response('wginfo/group_charter.html',
                              construct_group_menu_context(request, group, "charter", {
                "milestones_in_review": group.groupmilestone_set.filter(state="review"),
                "requested_close": requested_close,
                }), RequestContext(request))


def history(request, acronym):
    group = get_object_or_404(Group, acronym=acronym)

    events = group.groupevent_set.all().select_related('by').order_by('-time', '-id')

    return render_to_response('wginfo/history.html',
                              construct_group_menu_context(request, group, "history", {
                "events": events,
                }), RequestContext(request))
