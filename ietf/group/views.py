# -*- coding: utf-8 -*-
# Copyright The IETF Trust 2009-2023, All Rights Reserved
#
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


import copy
import csv
import datetime
import itertools
import math
import json
import types

from collections import OrderedDict, defaultdict
from pathlib import Path
from simple_history.utils import update_change_reason

from django import forms
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Count, F, OuterRef, Prefetch, Q, Subquery, TextField, Value
from django.db.models.functions import Coalesce
from django.http import HttpResponse, HttpResponseRedirect, Http404, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse as urlreverse
from django.utils import timezone
from django.utils.html import escape
from django.views.decorators.cache import cache_page, cache_control

import debug                            # pyflakes:ignore

from ietf.community.models import CommunityList, EmailSubscription
from ietf.community.utils import docs_tracked_by_community_list
from ietf.doc.models import DocTagName, State, RelatedDocument, Document, DocEvent
from ietf.doc.templatetags.ietf_filters import clean_whitespace
from ietf.doc.utils import get_chartering_type, get_tags_for_stream_id
from ietf.doc.utils_charter import charter_name_for_group, replace_charter_of_replaced_group
from ietf.doc.utils_search import prepare_document_table
#
from ietf.group.forms import (GroupForm, StatusUpdateForm, ConcludeGroupForm, StreamEditForm,
                              ManageReviewRequestForm, EmailOpenAssignmentsForm, ReviewerSettingsForm,
                              AddUnavailablePeriodForm, EndUnavailablePeriodForm, ReviewSecretarySettingsForm, )
from ietf.group.mails import email_admin_re_charter, email_personnel_change, email_comment
from ietf.group.models import ( Group, Role, GroupEvent, GroupStateTransitions,
                              ChangeStateGroupEvent, GroupFeatures, AppealArtifact )
from ietf.group.utils import (can_manage_all_groups_of_type,
                              milestone_reviewer_for_group_type, can_provide_status_update,
                              can_manage_materials, group_attribute_change_desc,
                              construct_group_menu_context, get_group_materials,
                              save_group_in_history, can_manage_group, update_role_set,
                              get_group_or_404, setup_default_community_list_for_group, fill_in_charter_info,
                              get_group_email_aliases)                              
#
from ietf.ietfauth.utils import has_role, is_authorized_in_group
from ietf.mailtrigger.utils import gather_relevant_expansions
from ietf.meeting.helpers import get_meeting
from ietf.meeting.models import ImportantDate, SchedTimeSessAssignment, SchedulingEvent
from ietf.meeting.utils import group_sessions
from ietf.name.models import GroupTypeName, StreamName
from ietf.person.models import Email, Person
from ietf.review.models import (ReviewRequest, ReviewAssignment, ReviewerSettings, 
                                ReviewSecretarySettings, UnavailablePeriod )
from ietf.review.policies import get_reviewer_queue_policy
from ietf.review.utils import (can_manage_review_requests_for_team,
                               can_access_review_stats_for_team,

                               extract_revision_ordered_review_requests_for_documents_and_replaced,
                               assign_review_request_to_reviewer,
                               close_review_request,

                               suggested_review_requests_for_team,
                               unavailable_periods_to_list,
                               current_unavailable_periods_for_reviewers,
                               email_reviewer_availability_change,
                               latest_review_assignments_for_reviewers,
                               augment_review_requests_with_events,
                               get_default_filter_re,
                               days_needed_to_fulfill_min_interval_for_reviewers,
                              )
from ietf.doc.models import LastCallDocEvent


from ietf.name.models import ReviewAssignmentStateName
from ietf.utils.mail import send_mail_text, parse_preformatted

from ietf.ietfauth.utils import user_is_person, role_required
from ietf.dbtemplate.models import DBTemplate
from ietf.mailtrigger.utils import gather_address_lists
from ietf.mailtrigger.models import Recipient
from ietf.settings import MAILING_LIST_INFO_URL
from ietf.utils.decorators import ignore_view_kwargs
from ietf.utils.response import permission_denied
from ietf.utils.text import strip_suffix
from ietf.utils import markdown
from ietf.utils.timezone import date_today, datetime_today, DEADLINE_TZINFO


# --- Helpers ----------------------------------------------------------

def roles(group, role_name):
    return Role.objects.filter(group=group, name=role_name).select_related("email", "person")


def extract_last_name(role):
    return role.person.name_parts()[3]


def response_from_file(fpath: Path) -> HttpResponse:
    """Helper to shovel a file back in an HttpResponse"""
    try:
        content = fpath.read_bytes()
    except IOError:
        raise Http404
    return HttpResponse(content, content_type="text/plain; charset=utf-8")


# --- View functions ---------------------------------------------------

def wg_summary_area(request, group_type):
    if group_type != "wg":
        raise Http404
    return response_from_file(Path(settings.GROUP_SUMMARY_PATH) / "1wg-summary.txt")


def wg_summary_acronym(request, group_type):
    if group_type != "wg":
        raise Http404
    return response_from_file(Path(settings.GROUP_SUMMARY_PATH) / "1wg-summary-by-acronym.txt")


def wg_charters(request, group_type):
    if group_type != "wg":
        raise Http404
    return response_from_file(Path(settings.CHARTER_PATH) / "1wg-charters.txt") 


def wg_charters_by_acronym(request, group_type):
    if group_type != "wg":
        raise Http404
    return response_from_file(Path(settings.CHARTER_PATH) / "1wg-charters-by-acronym.txt") 


def active_groups(request, group_type=None):

    if not group_type:
        return active_group_types(request)
    elif group_type == "wg":
        return active_wgs(request)
    elif group_type == "rg":
        return active_rgs(request)
    elif group_type == "ag":
        return active_ags(request)
    elif group_type == "rag":
        return active_rags(request)
    elif group_type == "area":
        return active_areas(request)
    elif group_type == "team":
        return active_teams(request)
    elif group_type == "dir":
        return active_dirs(request)
    elif group_type == "review":
        return active_review_dirs(request)
    elif group_type in ("program", "iabasg","iabworkshop"):
        return active_iab(request)
    elif group_type == "adm":
        return active_adm(request)
    elif group_type == "rfcedtyp":
        return active_rfced(request)
    else:
        raise Http404

def active_group_types(request):
    grouptypes = (
        GroupTypeName.objects.filter(
            slug__in=[
                "wg",
                "rg",
                "ag",
                "rag",
                "team",
                "dir",
                "review",
                "area",
                "program",
                "iabasg",
                "iabworkshop"
                "adm",
            ]
        )
        .filter(group__state="active")
        .order_by('order', 'name')  # default ordering ignored for "GROUP BY" queries, make it explicit
        .annotate(group_count=Count("group"))
    )
    return render(request, "group/active_groups.html", {"grouptypes": grouptypes})

def active_dirs(request):
    dirs = Group.objects.filter(type__in=['dir', 'review'], state="active").order_by("name")
    for group in dirs:
        group.chairs = sorted(roles(group, "chair"), key=extract_last_name)
        group.secretaries = sorted(roles(group, "secr"), key=extract_last_name)
    return render(request, 'group/active_dirs.html', {'dirs' : dirs })

def active_review_dirs(request):
    dirs = Group.objects.filter(type="review", state="active").order_by("name")
    for group in dirs:
        group.chairs = sorted(roles(group, "chair"), key=extract_last_name)
        group.secretaries = sorted(roles(group, "secr"), key=extract_last_name)
    return render(request, 'group/active_review_dirs.html', {'dirs' : dirs })

def active_teams(request):
    teams = Group.objects.filter(type="team", state="active").order_by("name")
    for group in teams:
        group.chairs = sorted(roles(group, "chair"), key=extract_last_name)
    return render(request, 'group/active_teams.html', {'teams' : teams })

def active_iab(request):
    iabgroups = Group.objects.filter(type__in=("program","iabasg","iabworkshop"), state="active").order_by("-type_id","name")
    for group in iabgroups:
        group.leads = sorted(roles(group, "lead"), key=extract_last_name)
    return render(request, 'group/active_iabgroups.html', {'iabgroups' : iabgroups })

def active_adm(request):
    adm = Group.objects.filter(type="adm", state="active").order_by("parent","name")
    return render(request, 'group/active_adm.html', {'adm' : adm })

def active_rfced(request):
    rfced = Group.objects.filter(type__in=["rfcedtyp", "edwg", "edappr"], state="active").order_by("parent", "name")
    return render(request, 'group/active_rfced.html', {'rfced' : rfced})


def active_areas(request):
        areas = Group.objects.filter(type="area", state="active").order_by("name")  
        return render(request, 'group/active_areas.html', {'areas': areas })

def active_wgs(request):
    areas = Group.objects.filter(type="area", state="active").order_by("name")
    for area in areas:
        # dig out information for template
        area.ads_and_pre_ads = (
            list(area.ads) + list(sorted(roles(area, "pre-ad"), key=extract_last_name))
        )

        area.groups = Group.objects.filter(parent=area, type="wg", state="active").order_by("acronym")
        area.urls = area.groupextresource_set.all().order_by("name")
        for group in area.groups:
            group.chairs = sorted(roles(group, "chair"), key=extract_last_name)
            group.ad_out_of_area = group.ad_role() and group.ad_role().person not in [role.person for role in area.ads_and_pre_ads]
            # get the url for mailing list subscription
            if group.list_subscribe.startswith('http'):
                group.list_subscribe_url = group.list_subscribe
            elif group.list_email.endswith('@ietf.org'):
                group.list_subscribe_url = MAILING_LIST_INFO_URL % {'list_addr':group.list_email.split('@')[0].lower(),'domain':'ietf.org'}
            else:
                group.list_subscribe_url = "mailto:"+group.list_subscribe

    return render(request, 'group/active_wgs.html', { 'areas':areas })

def active_rgs(request):
    irtf = Group.objects.get(acronym="irtf")
    irtf.chair = roles(irtf, "chair").first()

    groups = Group.objects.filter(type="rg", state="active").order_by("acronym")
    for group in groups:
        group.chairs = sorted(roles(group, "chair"), key=extract_last_name)

    return render(request, 'group/active_rgs.html', { 'irtf': irtf, 'groups': groups })
    
def active_ags(request):

    groups = Group.objects.filter(type="ag", state="active").order_by("acronym")
    for group in groups:
        group.chairs = sorted(roles(group, "chair"), key=extract_last_name)

    return render(request, 'group/active_ags.html', { 'groups': groups })

def active_rags(request):

    groups = Group.objects.filter(type="rag", state="active").order_by("acronym")
    for group in groups:
        group.chairs = sorted(roles(group, "chair"), key=extract_last_name)

    return render(request, 'group/active_rags.html', { 'groups': groups })
    
def bofs(request, group_type):
    groups = Group.objects.filter(type=group_type, state="bof")
    return render(request, 'group/bofs.html',dict(groups=groups))

def chartering_groups(request):
    charter_states = State.objects.filter(used=True, type="charter").exclude(slug__in=("approved", "notrev"))

    group_type_slugs = [ f.type.slug for f in GroupFeatures.objects.filter(has_chartering_process=True) ]
    group_types = GroupTypeName.objects.filter(slug__in=group_type_slugs)

    for t in group_types:
        t.chartering_groups = Group.objects.filter(type=t, charter__states__in=charter_states,state_id__in=('active','bof','proposed','dormant')).select_related("state", "charter").order_by("acronym")
        t.can_manage = can_manage_all_groups_of_type(request.user, t.slug)

        for g in t.chartering_groups:
            g.chartering_type = get_chartering_type(g.charter)
            g.charter.ballot = g.charter.active_ballot()

    return render(request, 'group/chartering_groups.html',
                  dict(charter_states=charter_states,
                       group_types=group_types))


def concluded_groups(request):
    sections = OrderedDict()

    sections["WGs"] = (
        Group.objects.filter(type="wg", state="conclude")
        .select_related("state", "charter")
        .order_by("parent__name", "acronym")
    )
    sections["RGs"] = (
        Group.objects.filter(type="rg", state="conclude")
        .select_related("state", "charter")
        .order_by("parent__name", "acronym")
    )
    sections["BOFs"] = (
        Group.objects.filter(type="wg", state="bof-conc")
        .select_related("state", "charter")
        .order_by("parent__name", "acronym")
    )
    sections["AGs"] = (
        Group.objects.filter(type="ag", state="conclude")
        .select_related("state", "charter")
        .order_by("parent__name", "acronym")
    )
    sections["RAGs"] = (
        Group.objects.filter(type="rag", state="conclude")
        .select_related("state", "charter")
        .order_by("parent__name", "acronym")
    )
    sections["Directorates"] = (
        Group.objects.filter(type="dir", state="conclude")
        .select_related("state", "charter")
        .order_by("parent__name", "acronym")
    )
    sections["Review teams"] = (
        Group.objects.filter(type="review", state="conclude")
        .select_related("state", "charter")
        .order_by("parent__name", "acronym")
    )
    sections["Teams"] = (
        Group.objects.filter(type="team", state="conclude")
        .select_related("state", "charter")
        .order_by("parent__name", "acronym")
    )
    sections["Programs"] = (
        Group.objects.filter(type="program", state="conclude")
        .select_related("state", "charter")
        .order_by("parent__name", "acronym")
    )

    for name, groups in sections.items():
        # add start/conclusion date
        d = dict((g.pk, g) for g in groups)

        for g in groups:
            g.start_date = g.conclude_date = None

        # Some older BOFs were created in the "active" state, so consider both "active" and "bof"
        # ChangeStateGroupEvents when finding the start date. A group with _both_ "active" and "bof"
        # events should not be in the "bof-conc" state so this shouldn't cause a problem (if it does,
        # we'll need to clean up the data)
        for e in ChangeStateGroupEvent.objects.filter(
            group__in=groups,
            state__in=["active", "bof"] if name == "BOFs" else ["active"],
        ).order_by("-time"):
            d[e.group_id].start_date = e.time

        # Similarly, some older BOFs were concluded into the "conclude" state and the event was never
        # fixed, so consider both "conclude" and "bof-conc" ChangeStateGroupEvents when finding the
        # concluded date. A group with _both_ "conclude" and "bof-conc" events should not be in the
        # "bof-conc" state so this shouldn't cause a problem (if it does, we'll need to clean up the
        # data)
        for e in ChangeStateGroupEvent.objects.filter(
            group__in=groups,
            state__in=["bof-conc", "conclude"] if name == "BOFs" else ["conclude"],
        ).order_by("time"):
            d[e.group_id].conclude_date = e.time

    return render(request, "group/concluded_groups.html", dict(sections=sections))


def prepare_group_documents(request, group, clist):
    found_docs, meta = prepare_document_table(request, docs_tracked_by_community_list(clist), request.GET, max_results=500)

    docs = []
    docs_related = []

    # split results
    for d in found_docs:
        # non-WG drafts and call for WG adoption are considered related
        if (d.group != group
            or (d.stream_id and d.get_state_slug("draft-stream-%s" % d.stream_id) in ("c-adopt", "wg-cand"))):
            if (d.type_id == "draft" and d.get_state_slug() not in ["expired","rfc"]) or d.type_id == "rfc":
                d.search_heading = "Related Internet-Drafts and RFCs"
                docs_related.append(d)
        else:
            if not (d.get_state_slug('draft-iesg') == "dead" or (d.stream_id and d.get_state_slug("draft-stream-%s" % d.stream_id) == "dead")):
                docs.append(d)

    meta_related = meta.copy()

    return docs, meta, docs_related, meta_related


def get_leadership(group_type):
    people = Person.objects.filter(
        role__name__slug="chair",
        role__group__type=group_type,
        role__group__state__slug__in=("active", "bof", "proposed"),
    ).distinct()
    leaders = []
    for person in people:
        parts = person.name_parts()
        groups = [
            r.group.acronym
            for r in person.role_set.filter(
                name__slug="chair",
                group__type=group_type,
                group__state__slug__in=("active", "bof", "proposed"),
            )
        ]
        entry = {"name": "%s, %s" % (parts[3], parts[1]), "groups": ", ".join(groups)}
        leaders.append(entry)
    return sorted(leaders, key=lambda a: a["name"])


def group_leadership(request, group_type=None):
    context = {}
    context["leaders"] = get_leadership(group_type)
    context["group_type"] = group_type
    return render(request, "group/group_leadership.html", context)


def group_leadership_csv(request, group_type=None):
    leaders = get_leadership(group_type)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="group_leadership_{group_type}.csv"'
    )
    writer = csv.writer(response, dialect=csv.excel, delimiter=str(","))
    writer.writerow(["Name", "Groups"])
    for leader in leaders:
        writer.writerow([leader["name"], leader["groups"]])
    return response

def group_home(request, acronym, group_type=None):
    group = get_group_or_404(acronym, group_type)
    kwargs = dict(acronym=group.acronym)
    if group_type:
        kwargs["group_type"] = group_type
    return HttpResponseRedirect(urlreverse(group.features.default_tab, kwargs=kwargs))

def group_documents(request, acronym, group_type=None):
    group = get_group_or_404(acronym, group_type)
    if not group.features.has_documents:
        raise Http404

    if not group.communitylist_set.exists():
        setup_default_community_list_for_group(group)
    clist = group.communitylist_set.first()

    docs, meta, docs_related, meta_related = prepare_group_documents(request, group, clist)

    subscribed = request.user.is_authenticated and EmailSubscription.objects.filter(community_list=clist, email__person__user=request.user)

    context = construct_group_menu_context(request, group, "documents", group_type, {
                'docs': docs,
                'meta': meta,
                'docs_related': docs_related,
                'meta_related': meta_related,
                'subscribed': subscribed,
                'clist': clist,
                })

    return render(request, 'group/group_documents.html', context)

def group_documents_txt(request, acronym, group_type=None):
    """Return tabulator-separated rows with documents for group."""
    group = get_group_or_404(acronym, group_type)
    if not group.features.has_documents:
        raise Http404

    clist = get_object_or_404(CommunityList, group=group)

    docs, meta, docs_related, meta_related = prepare_group_documents(request, group, clist)

    for d in docs:
        d.prefix = d.get_state().name

    for d in docs_related:
        d.prefix = "Related %s" % d.get_state().name

    rows = []
    for d in itertools.chain(docs, docs_related):
        if d.type_id == "rfc":
            name = str(d.rfc_number)
        else:
            name = "%s-%s" % (d.name, d.rev)

        rows.append("\t".join((d.prefix, name, clean_whitespace(d.title))))

    return HttpResponse("\n".join(rows), content_type='text/plain; charset=UTF-8')

def group_about(request, acronym, group_type=None):
    group = get_group_or_404(acronym, group_type)

    fill_in_charter_info(group)

    e = group.latest_event(type__in=("changed_state", "requested_close",))
    requested_close = group.state_id != "conclude" and e and e.type == "requested_close"

    e = None
    if group.state_id == "conclude":
        e = group.latest_event(type='closing_note')

    can_manage = can_manage_all_groups_of_type(request.user, group.type_id)
    charter_submit_url = "" 
    if group.features.has_chartering_process: 
        charter_submit_url = urlreverse('ietf.doc.views_charter.submit', kwargs={ "name": charter_name_for_group(group) }) 

    can_provide_update = can_provide_status_update(request.user, group)
    status_update = group.latest_event(type="status_update")

    subgroups = Group.objects.filter(parent=group, state="active").exclude(type__slug__in=["sdo", "individ", "nomcom"]).order_by("type", "acronym")

    return render(request, 'group/group_about.html',
                  construct_group_menu_context(request, group, "about", group_type, {
                      "milestones_in_review": group.groupmilestone_set.filter(state="review"),
                      "milestone_reviewer": milestone_reviewer_for_group_type(group_type),
                      "requested_close": requested_close,
                      "can_manage": can_manage,
                      "can_provide_status_update": can_provide_update,
                      "status_update": status_update,
                      "charter_submit_url": charter_submit_url,
                      "editable_roles": group.used_roles or group.features.default_used_roles,
                      "closing_note": e,
                      "subgroups": subgroups,
                  }))

def all_status(request):
    wgs = Group.objects.filter(type='wg',state__in=['active','bof'])
    rgs = Group.objects.filter(type='rg',state__in=['active','proposed'])

    wg_reports = []
    for wg in wgs:
        e = wg.latest_event(type='status_update')
        if e:
            wg_reports.append(e)

    wg_reports.sort(key=lambda x: (x.group.parent.acronym,timezone.now()-x.time))

    rg_reports = []
    for rg in rgs:
        e = rg.latest_event(type='status_update')
        if e:
            rg_reports.append(e)

    return render(request, 'group/all_status.html',
                  { 'wg_reports': wg_reports,
                    'rg_reports': rg_reports,
                  }
                 )

def group_about_status(request, acronym, group_type=None):
    group = get_group_or_404(acronym, group_type)
    status_update = group.latest_event(type='status_update')
    can_provide_update = can_provide_status_update(request.user, group)
    return render(request, 'group/group_about_status.html',
                  { 'group' : group,
                    'status_update': status_update,
                    'can_provide_status_update': can_provide_update,
                  }
                 )

def group_about_status_meeting(request, acronym, num, group_type=None):
    meeting = get_meeting(num)
    group = get_group_or_404(acronym, group_type)
    status_update = group.status_for_meeting(meeting)
    return render(request, 'group/group_about_status_meeting.html',
                  { 'group' : group,
                    'status_update': status_update,
                    'meeting': meeting,
                  }
                 )

def group_about_status_edit(request, acronym, group_type=None):
    group = get_group_or_404(acronym, group_type)
    if not can_provide_status_update(request.user, group):
        raise Http404
    old_update = group.latest_event(type='status_update')

    login = request.user.person

    if request.method == 'POST':
        if 'submit_response' in request.POST:
            form = StatusUpdateForm(request.POST, request.FILES)
            if form.is_valid():
                from_file = form.cleaned_data['txt']
                if from_file:
                    update_text = from_file
                else:
                    update_text = form.cleaned_data['content']
                group.groupevent_set.create(
                    by=login,
                    type='status_update',
                    desc=update_text,
                ) 
                return redirect('ietf.group.views.group_about',acronym=group.acronym)
        else:
            form = None
    else:
        form = None

    if not form:
        form = StatusUpdateForm(initial={"content": old_update.desc if old_update else ""})

    return render(request, 'group/group_about_status_edit.html',
                  { 
                    'form': form,
                    'group':group,
                  }
                 )

def email(request, acronym, group_type=None):
    group = get_group_or_404(acronym, group_type)

    aliases = get_group_email_aliases(acronym, group_type)
    expansions = gather_relevant_expansions(group=group)

    return render(request, 'group/email.html',
                  construct_group_menu_context(request, group, "email expansions", group_type, {
                       'expansions':expansions,
                       'aliases':aliases,
                       'group':group,
                       'ietf_domain':settings.IETF_DOMAIN,
                  })) 

def history(request, acronym, group_type=None):
    group = get_group_or_404(acronym, group_type)

    events = group.groupevent_set.all().select_related('by').order_by('-time', '-id')
    can_add_comment = is_authorized_in_group(request.user,group)

    return render(request, 'group/history.html',
                  construct_group_menu_context(request, group, "history", group_type, {
                      "group": group,
                      "events": events,
                      "can_add_comment": can_add_comment,
                  }))

def materials(request, acronym, group_type=None):
    group = get_group_or_404(acronym, group_type)
    if not group.features.has_nonsession_materials:
        raise Http404

    docs = get_group_materials(group).order_by("type__order", "-time").select_related("type")
    doc_types = OrderedDict()
    for d in docs:
        if d.type not in doc_types:
            doc_types[d.type] = []
        doc_types[d.type].append(d)

    return render(request, 'group/materials.html',
                  construct_group_menu_context(request, group, "materials", group_type, {
                      "doc_types": list(doc_types.items()),
                      "can_manage_materials": can_manage_materials(request.user, group)
                  }))


@cache_page(60 * 60)
def dependencies(request, acronym, group_type=None):
    group = get_group_or_404(acronym, group_type)
    if not group.features.has_documents:
        raise Http404

    if not group.communitylist_set.exists():
        setup_default_community_list_for_group(group)
    clist = group.communitylist_set.first()

    docs, meta, docs_related, meta_related = prepare_group_documents(
        request, group, clist
    )
    cl_docs = set(docs).union(set(docs_related))

    references = Q(
        Q(source__group=group) | Q(source__in=cl_docs),
        source__type="draft",
        relationship__slug__startswith="ref",
    )
    rfc_or_subseries = {"rfc", "bcp", "fyi", "std"}
    both_rfcs = Q(source__type_id="rfc", target__type_id__in=rfc_or_subseries)
    pre_rfc_draft_to_rfc = Q(
        source__states__type="draft",
        source__states__slug="rfc",
        target__type_id__in=rfc_or_subseries,
    )
    both_pre_rfcs = Q(
        source__states__type="draft",
        source__states__slug="rfc",
        target__type_id="draft",
        target__states__type="draft",
        target__states__slug="rfc",
    )
    inactive = Q(
        source__states__type="draft",
        source__states__slug__in=["expired", "repl"],
    )
    attractor = Q(target__name__in=["rfc5000", "rfc5741"])
    removed = Q(source__states__type="draft", source__states__slug__in=["auth-rm", "ietf-rm"])
    relations = (
        RelatedDocument.objects.filter(references)
        .exclude(both_rfcs)
        .exclude(pre_rfc_draft_to_rfc)
        .exclude(both_pre_rfcs)
        .exclude(inactive)
        .exclude(attractor)
        .exclude(removed)
    )

    links = set()
    for x in relations:
        always_include = x.target.type_id not in rfc_or_subseries and x.target.get_state_slug("draft") != "rfc" 
        if always_include or x.is_downref():
            links.add(x)

    replacements = RelatedDocument.objects.filter(
        relationship__slug="replaces",
        target__in=[x.target for x in links],
    )

    for x in replacements:
        links.add(x)

    nodes = set([x.source for x in links]).union([x.target for x in links])
    graph = {
        "nodes": [
            {
                "id": x.became_rfc().name if x.became_rfc() else x.name,
                "rfc": x.type_id == "rfc" or x.became_rfc() is not None,
                "post-wg": x.get_state_slug("draft-iesg") not in ["idexists", "dead"],
                "expired": x.get_state_slug("draft") == "expired",
                "replaced": x.get_state_slug("draft") == "repl",
                "group": x.group.acronym if x.group and x.group.acronym != "none" else "",
                "url": x.get_absolute_url(),
                "level": x.intended_std_level.name
                if x.intended_std_level
                else x.std_level.name
                if x.std_level
                else "",
            }
            for x in nodes
        ],
        "links": [
            {
                "source": x.source.became_rfc().name if x.source.became_rfc() else x.source.name,
                "target": x.target.became_rfc().name if x.target.became_rfc() else x.target.name,
                "rel": "downref" if x.is_downref() else x.relationship.slug,
            }
            for x in links
        ],
    }

    return HttpResponse(json.dumps(graph), content_type="application/json")


def email_aliases(request, acronym=None, group_type=None):
    group = get_group_or_404(acronym,group_type) if acronym else None

    if not acronym:
        # require login for the overview page, but not for the group-specific
        # pages 
        if not request.user.is_authenticated:
                return redirect('%s?next=%s' % (settings.LOGIN_URL, request.path))

    aliases = get_group_email_aliases(acronym, group_type)

    return render(request,'group/email_aliases.html',{'aliases':aliases,'ietf_domain':settings.IETF_DOMAIN,'group':group})

def meetings(request, acronym, group_type=None):
    group = get_group_or_404(acronym, group_type)

    four_years_ago = timezone.now() - datetime.timedelta(days=4 * 365)

    stsas = SchedTimeSessAssignment.objects.filter(
        session__type__in=["regular", "plenary", "other"],
        session__group=group)
    if group.acronym not in ["iab", "iesg"]:
        stsas = stsas.filter(session__meeting__date__gt=four_years_ago)
    stsas = stsas.annotate(sessionstatus=Coalesce(
                Subquery(
                    SchedulingEvent.objects.filter(
                        session=OuterRef("session__pk")
                    ).order_by(
                        '-time', '-id'
                    ).values('status')[:1]),
                Value(''), 
                output_field=TextField())
    ).filter(
        sessionstatus__in=["sched", "schedw", "appr", "canceled"],
        session__meeting__schedule=F("schedule")
    ).distinct().select_related(
        "session", "session__group", "session__group__parent", "session__meeting__type", "timeslot"
    ).prefetch_related(
        "session__materials",
        "session__materials__states",
        Prefetch("session__materials",
            queryset=Document.objects.exclude(states__type=F("type"), states__slug='deleted').order_by('presentations__order').prefetch_related('states'),
            to_attr="prefetched_active_materials"
        ),
    )

    stsas = list(stsas)

    for stsa in stsas:
        stsa.session._otsa = stsa
        stsa.session.official_timeslotassignment = types.MethodType(lambda self:self._otsa, stsa.session)
        stsa.session.current_status = stsa.sessionstatus

    sessions = sorted(
        set([stsa.session for stsa in stsas]),
        key=lambda x: (
            x._otsa.timeslot.time,
            x._otsa.timeslot.type_id,
            x._otsa.session.group.parent.name if x._otsa.session.group.parent else None,
            x._otsa.session.name
        )
    )

    meeting_seen = None
    for s in sessions:
        if s.meeting != meeting_seen:
            meeting_seen = s.meeting
            order = 1
        s._oim = order
        s.order_in_meeting = types.MethodType(lambda self:self._oim, s)
        order += 1


    revsub_dates_by_meeting = dict(ImportantDate.objects.filter(name_id="revsub", meeting__session__in=sessions).distinct().values_list("meeting_id","date"))

    for s in sessions:
        s.order_number = s.order_in_meeting()
        if s.meeting.pk in revsub_dates_by_meeting:
            cutoff_date = revsub_dates_by_meeting[s.meeting.pk]
        else:
            cutoff_date = s.meeting.date + datetime.timedelta(days=s.meeting.submission_correction_day_offset)
        s.cached_is_cutoff = date_today(datetime.timezone.utc) > cutoff_date

    future, in_progress, recent, past = group_sessions(sessions)

    can_edit = group.has_role(request.user, group.features.groupman_roles)
    can_always_edit = has_role(request.user, ["Secretariat", "Area Director"])

    far_past = []
    if group.acronym in ["iab", "iesg"]:
        recent_past = []
        for s in past:
            if s.time >= four_years_ago:
                recent_past.append(s)
            else:
                far_past.append(s)
        past = recent_past

    return render(
        request,
        "group/meetings.html",
        construct_group_menu_context(
            request,
            group,
            "meetings",
            group_type,
            {
                "group": group,
                "future": future,
                "in_progress": in_progress,
                "recent": recent,
                "past": past,
                "far_past": far_past,
                "can_edit": can_edit,
                "can_always_edit": can_always_edit,
            },
        ),
    )


def chair_photos(request, group_type=None):
    roles = sorted(Role.objects.filter(group__type=group_type, group__state='active', name_id='chair'),key=lambda x: x.person.last_name()+x.person.name+x.group.acronym)
    for role in roles:
        role.last_initial = role.person.last_name()[0].upper()
    return render(request, 'group/all_photos.html', {'group_type': group_type, 'role': 'Chair', 'roles': roles })

def reorder_roles(roles, role_names):
    list = []
    for name in role_names:
        list += [ r for r in roles if r.name_id == name ]
    list += [ r for r in roles if not r in list ]
    return list
    
def group_photos(request, group_type=None, acronym=None):
    group = get_object_or_404(Group, acronym=acronym)
    roles = sorted(Role.objects.filter(group__acronym=acronym),key=lambda x: x.name.name+x.person.last_name())

    roles = reorder_roles(roles, group.features.role_order)
    for role in roles:
        role.last_initial = role.person.last_name()[0].upper()
    return render(request, 'group/group_photos.html',
                  construct_group_menu_context(request, group, "photos", group_type, {
                      'group_type': group_type,
                      'roles': roles,
                      'group':group }))


@login_required
def edit(request, group_type=None, acronym=None, action="edit", field=None):
    """Edit or create a group, notifying parties as
    necessary and logging changes as group events."""
    def format_resources(resources, fs="\n"):
        res = []
        for r in resources:
            if r.display_name:
                res.append("%s %s (%s)" % (r.name.slug, r.value, r.display_name.strip('()')))
            else:
                res.append("%s %s" % (r.name.slug, r.value)) 
                # TODO: This is likely problematic if value has spaces. How then to delineate value and display_name? Perhaps in the short term move to comma or pipe separation.
                # Might be better to shift to a formset instead of parsing these lines.
        return fs.join(res)

    def diff(attr, name):
        if attr not in clean or (field and attr != field):
            return
        v = getattr(group, attr)
        if clean[attr] != v:
            changes.append((
                attr,
                clean[attr],
                group_attribute_change_desc(name, clean[attr], v if v else None)
            ))
            setattr(group, attr, clean[attr])

    if action == "edit":
        new_group = False
    elif action in ("create","charter"):
        group = None
        new_group = True
    else:
        raise Http404

    if not new_group:
        group = get_group_or_404(acronym, group_type)
        if not group_type and group:
            group_type = group.type_id
        if not (can_manage_group(request.user, group)
                or group.has_role(request.user, group.features.groupman_roles)):
            permission_denied(request, "You don't have permission to access this view")
        hide_parent = not has_role(request.user, ("Secretariat", "Area Director", "IRTF Chair"))
    else:
        # This allows ADs to create RG and the IRTF Chair to create WG, but we trust them not to
        if not has_role(request.user, ("Secretariat", "Area Director", "IRTF Chair")):
             permission_denied(request, "You don't have permission to access this view")
        hide_parent = False

    if request.method == 'POST':
        form = GroupForm(request.POST, group=group, group_type=group_type, field=field, hide_parent=hide_parent)
        if field and not form.fields:
            permission_denied(request, "You don't have permission to edit this field")
        if form.is_valid():
            clean = form.cleaned_data
            if new_group:
                try:
                    group = Group.objects.get(acronym=clean["acronym"])
                    save_group_in_history(group)
                    group.time = timezone.now()
                    group.save()
                except Group.DoesNotExist:
                    group = Group.objects.create(name=clean["name"],
                                              acronym=clean["acronym"],
                                              type=GroupTypeName.objects.get(slug=group_type),
                                              state=clean["state"]
                                              )

                    if group.features.has_documents:
                        setup_default_community_list_for_group(group)

                e = ChangeStateGroupEvent(group=group, type="changed_state")
                e.time = group.time
                e.by = request.user.person
                e.state_id = clean["state"].slug
                e.desc = "Group created in state %s" % clean["state"].name
                e.save()
            else:
                save_group_in_history(group)

            changes = []

            # update the attributes, keeping track of what we're doing
            diff('name', "Name")
            diff('acronym', "Acronym")
            diff('state', "State")
            diff('description', "Description")
            diff('parent', "IETF Area" if group.type=="wg" else "Group parent")
            diff('list_email', "Mailing list email")
            diff('list_subscribe', "Mailing list subscribe address")
            diff('list_archive', "Mailing list archive")

            personnel_change_text=""
            changed_personnel = set()
            # update roles
            for attr, f in form.fields.items():
                if not attr.endswith("_roles"):
                    continue

                slug = attr
                slug = strip_suffix(slug, "_roles")

                title = f.label

                added, deleted = update_role_set(group, slug, clean[attr], request.user.person)
                changed_personnel.update(added | deleted)
                if added:
                    change_text=title + ' added: ' + ", ".join(x.name_and_email() for x in added)
                    personnel_change_text+=change_text+"\n"
                if deleted:
                    change_text=title + ' deleted: ' + ", ".join(x.name_and_email() for x in deleted)
                    personnel_change_text+=change_text+"\n"

                    today = date_today()
                    for deleted_email in deleted:
                        # Verify the person doesn't have a separate reviewer role for the group with a different address
                        if not group.role_set.filter(name_id='reviewer',person=deleted_email.person).exists():
                            active_assignments = ReviewAssignment.objects.filter(
                                review_request__team=group,
                                reviewer__person=deleted_email.person,
                                state_id__in=['accepted', 'assigned'],
                            )
                            for assignment in active_assignments:
                                if assignment.review_request.deadline > today:
                                    assignment.state_id = 'withdrawn'
                                else:
                                    assignment.state_id = 'no-response'
                                # save() will update review_request state to 'requested'
                                # if needed, so that the review can be assigned to someone else
                                assignment.save()


            if personnel_change_text!="":
                changed_personnel = [ str(p) for p in changed_personnel ]
                personnel_change_text = "%s has updated %s personnel:\n\n" % (request.user.person.plain_name(), group.acronym.upper() ) + personnel_change_text
                email_personnel_change(request, group, personnel_change_text, changed_personnel)

            if 'resources' in clean:
                old_resources = sorted(format_resources(group.groupextresource_set.all()).splitlines())
                new_resources = sorted(clean['resources'])
                if old_resources != new_resources:
                    group.groupextresource_set.all().delete()
                    for u in new_resources:
                        parts = u.split(None, 2)
                        name = parts[0]
                        value = parts[1]
                        display_name = ' '.join(parts[2:]).strip('()')
                        group.groupextresource_set.create(value=value, name_id=name, display_name=display_name)
                    changes.append((
                        'resources',
                        new_resources,
                        group_attribute_change_desc(
                            'Resources',
                            ", ".join(new_resources),
                            ", ".join(old_resources) if old_resources else None
                        )
                    ))

            group.time = timezone.now()

            if changes and not new_group:
                for attr, new, desc in changes:
                    if attr == 'state':
                        ChangeStateGroupEvent.objects.create(group=group, time=group.time, state=new, by=request.user.person, type="changed_state", desc=desc)
                        if new.slug == 'replaced':
                            replace_charter_of_replaced_group(group=group, by=request.user.person)
                    else:
                        GroupEvent.objects.create(group=group, time=group.time, by=request.user.person, type="info_changed", desc=desc)

            group.save()

            #Handle changes to Closing Note, if any. It's an event, not a group attribute like the others
            closing_note = ""
            e = group.latest_event(type='closing_note')
            if e:
                closing_note = e.desc

            if closing_note != clean.get("closing_note", ""):
                closing_note = clean.get("closing_note", "")
                e = GroupEvent(group=group, by=request.user.person)
                e.type = "closing_note"
                if closing_note == "":
                    e.desc = "(Closing note deleted)" #Flag value so something shows up in history
                else:
                    e.desc = closing_note
                e.save()
 
            if action=="charter":
                return redirect('ietf.doc.views_charter.submit', name=charter_name_for_group(group), option="initcharter")

            return HttpResponseRedirect(group.about_url())
    else: # Not POST:
        if not new_group:
            closing_note = ""
            e = group.latest_event(type='closing_note')
            if e:
                closing_note = e.desc
                if closing_note == "(Closing note deleted)":
                    closing_note = ""

            init = dict(name=group.name,
                        acronym=group.acronym,
                        state=group.state,
                        description = group.description,
                        parent=group.parent.id if group.parent else None,
                        list_email=group.list_email if group.list_email else None,
                        list_subscribe=group.list_subscribe if group.list_subscribe else None,
                        list_archive=group.list_archive if group.list_archive else None,
                        resources=format_resources(group.groupextresource_set.all()),
                        closing_note = closing_note,
                        )

        else:
            init = dict()
        form = GroupForm(initial=init, group=group, group_type=group_type, field=field, hide_parent=hide_parent)
        if field and not form.fields:
            permission_denied(request, "You don't have permission to edit this field")

    return render(request, 'group/edit.html',
                  dict(group=group,
                       form=form,
                       action=action))

@login_required
def conclude(request, acronym, group_type=None):
    """Request the closing of group, prompting for instructions."""
    group = get_group_or_404(acronym, group_type)

    if not can_manage_all_groups_of_type(request.user, group.type_id):
        permission_denied(request, "You don't have permission to access this view")

    if request.method == 'POST':
        form = ConcludeGroupForm(request.POST)
        if form.is_valid():
            instructions = form.cleaned_data['instructions']
            closing_note = form.cleaned_data['closing_note']

            if closing_note != "":
                instructions = instructions+"\n\n=====\nClosing note:\n\n"+closing_note
            email_admin_re_charter(request, group, "Request closing of group", instructions, 'group_closure_requested')

            e = GroupEvent(group=group, by=request.user.person)
            e.type = "requested_close"
            e.desc = "Requested closing group"
            e.save()

            if closing_note != "":
                e = GroupEvent(group=group, by=request.user.person)
                e.type = "closing_note"
                e.desc = closing_note
                e.save()

            kwargs = {'acronym':group.acronym}
            if group_type:
                kwargs['group_type'] = group_type
   
            return redirect(group.features.about_page, **kwargs)
    else:
        form = ConcludeGroupForm()

    return render(request, 'group/conclude.html', {
        'form': form,
        'group': group,
        'group_type': group_type,
    })

@login_required
def customize_workflow(request, group_type=None, acronym=None):
    group = get_group_or_404(acronym, group_type)
    if not group_type:
        group_type = group.type_id
    if not group.features.customize_workflow:
        raise Http404

    if not (can_manage_group(request.user, group)
            or group.has_role(request.user, group.features.groupman_roles)):
        permission_denied(request, "You don't have permission to access this view")

    if group_type == "rg":
        stream_id = "irtf"
        MANDATORY_STATES = ('candidat', 'active', 'rfc-edit', 'pub', 'dead')
    else:
        stream_id = "ietf"
        MANDATORY_STATES = ('c-adopt', 'wg-doc', 'sub-pub')

    if request.method == 'POST':
        action = request.POST.get("action")
        if action == "setstateactive":
            active = request.POST.get("active") == "1"
            try:
                state = State.objects.exclude(slug__in=MANDATORY_STATES).get(pk=request.POST.get("state"))
            except State.DoesNotExist:
                return HttpResponse("Invalid state %s" % request.POST.get("state"))

            if active:
                group.unused_states.remove(state)
            else:
                group.unused_states.add(state)

            # redirect so the back button works correctly, otherwise
            # repeated POSTs fills up the history
            return redirect("ietf.group.views.customize_workflow", group_type=group.type_id, acronym=group.acronym)

        if action == "setnextstates":
            try:
                state = State.objects.get(pk=request.POST.get("state"))
            except State.DoesNotExist:
                return HttpResponse("Invalid state %s" % request.POST.get("state"))

            next_states = State.objects.filter(used=True, type='draft-stream-%s' % stream_id, pk__in=request.POST.getlist("next_states"))
            unused = group.unused_states.all()
            if set(next_states.exclude(pk__in=unused)) == set(state.next_states.exclude(pk__in=unused)):
                # just use the default
                group.groupstatetransitions_set.filter(state=state).delete()
            else:
                transitions, _ = GroupStateTransitions.objects.get_or_create(group=group, state=state)
                transitions.next_states.clear()
                transitions.next_states.set(next_states)

            return redirect("ietf.group.views.customize_workflow", group_type=group.type_id, acronym=group.acronym)

        if action == "settagactive":
            active = request.POST.get("active") == "1"
            try:
                tag = DocTagName.objects.get(pk=request.POST.get("tag"))
            except DocTagName.DoesNotExist:
                return HttpResponse("Invalid tag %s" % request.POST.get("tag"))

            if active:
                group.unused_tags.remove(tag)
            else:
                group.unused_tags.add(tag)

            return redirect("ietf.group.views.customize_workflow", group_type=group.type_id, acronym=group.acronym)

    # put some info for the template on tags and states
    unused_tags = group.unused_tags.all().values_list('slug', flat=True)
    tags = DocTagName.objects.filter(slug__in=get_tags_for_stream_id(stream_id))
    for t in tags:
        t.used = t.slug not in unused_tags

    unused_states = group.unused_states.all().values_list('slug', flat=True)
    states = State.objects.filter(used=True, type="draft-stream-%s" % stream_id)
    transitions = dict((o.state, o) for o in group.groupstatetransitions_set.all())
    for s in states:
        s.used = s.slug not in unused_states
        s.mandatory = s.slug in MANDATORY_STATES

        default_n = s.next_states.all()
        if s in transitions:
            n = transitions[s].next_states.all()
        else:
            n = default_n

        s.next_states_checkboxes = [(x in n, x in default_n, x) for x in states]
        s.used_next_states = [x for x in n if x.slug not in unused_states]

    return render(request, 'group/customize_workflow.html', {
            'group': group,
            'states': states,
            'tags': tags,
            })


def streams(request):
    streams = [ s.slug for s in StreamName.objects.all().exclude(slug__in=['ietf', 'legacy']) ]
    streams = Group.objects.filter(acronym__in=streams)
    return render(request, 'group/index.html', {'streams':streams})

def stream_documents(request, acronym):
    if acronym == "editorial":
        return HttpResponseRedirect(urlreverse(group_documents, kwargs=dict(acronym="rswg")))
    streams = [ s.slug for s in StreamName.objects.all().exclude(slug__in=['ietf', 'legacy']) ]
    if not acronym in streams:
        raise Http404("No such stream: %s" % acronym)
    group = get_object_or_404(Group, acronym=acronym)
    editable = has_role(request.user, "Secretariat") or group.has_role(request.user, "chair")
    stream = StreamName.objects.get(slug=acronym)

    qs = Document.objects.filter(stream=acronym).filter(
        Q(type_id="draft", states__type="draft", states__slug="active")
        | Q(type_id="rfc")
    ).distinct()
    docs, meta = prepare_document_table(request, qs, max_results=1000)
    return render(request, 'group/stream_documents.html', {'stream':stream, 'docs':docs, 'meta':meta, 'editable':editable } )


def stream_edit(request, acronym):
    group = get_object_or_404(Group, acronym=acronym)

    if not (has_role(request.user, "Secretariat") or group.has_role(request.user, "chair")):
        permission_denied(request, "You don't have permission to access this page.")

    chairs = Email.objects.filter(role__group=group, role__name="chair").select_related("person")

    if request.method == 'POST':
        form = StreamEditForm(request.POST)

        if form.is_valid():
            save_group_in_history(group)

            # update roles
            attr, slug, title = ('delegates', 'delegate', "Delegates")

            new = form.cleaned_data[attr]
            old = Email.objects.filter(role__group=group, role__name=slug).select_related("person")
            if set(new) != set(old):
                desc = "%s changed to <b>%s</b> from %s" % (
                    title, ", ".join(x.get_name() for x in new), ", ".join(x.get_name() for x in old))

                GroupEvent.objects.create(group=group, by=request.user.person, type="info_changed", desc=desc)

                group.role_set.filter(name=slug).delete()
                for e in new:
                    Role.objects.get_or_create(name_id=slug, email=e, group=group, person=e.person)
                    if not e.origin or e.origin == e.person.user.username:
                        e.origin = "role: %s %s" % (group.acronym, slug)
                        e.save()

            return redirect("ietf.group.views.streams")
    else:
        form = StreamEditForm(initial=dict(delegates=Email.objects.filter(role__group=group, role__name="delegate")))

    return render(request, 'group/stream_edit.html',
                    {
                        'group': group,
                        'chairs': chairs,
                        'form': form,
                    },
                )


@cache_control(public=True, max_age=30 * 60)
@cache_page(30 * 60)
def group_menu_data(request):
    groups = (
        Group.objects.filter(state="active", parent__state="active")
        .filter(
            Q(type__features__acts_like_wg=True)
            | Q(type_id__in=["program", "iabasg", "iabworkshop"])
            | Q(parent__acronym="ietfadminllc")
            | Q(parent__acronym="rfceditor")
        )
        .order_by("-type_id", "acronym")
        .select_related("type")
    )

    groups_by_parent = defaultdict(list)
    for g in groups:
        url = urlreverse(
            "ietf.group.views.group_home",
            kwargs={"group_type": g.type_id, "acronym": g.acronym},
        )
        #        groups_by_parent[g.parent_id].append({ 'acronym': g.acronym, 'name': escape(g.name), 'url': url })
        groups_by_parent[g.parent_id].append(
            {
                "acronym": g.acronym,
                "name": escape(g.name),
                "type": escape(g.type.verbose_name or g.type.name),
                "url": url,
            }
        )

    iab = Group.objects.get(acronym="iab")
    groups_by_parent[iab.pk].insert(
        0,
        {
            "acronym": iab.acronym,
            "name": iab.name,
            "type": "Top Level Group",
            "url": urlreverse(
                "ietf.group.views.group_home", kwargs={"acronym": iab.acronym}
            ),
        },
    )
    return JsonResponse(groups_by_parent)



@cache_control(public=True, max_age=30 * 60)
@cache_page(30 * 60)
def group_stats_data(request, years="3", only_active=True):
    when = timezone.now() - datetime.timedelta(days=int(years) * 365)
    docs = (
        Document.objects.filter(type="draft", stream="ietf")
        .filter(
            Q(docevent__newrevisiondocevent__time__gte=when)
            | Q(docevent__type="published_rfc", docevent__time__gte=when)
        )
        .exclude(states__type="draft", states__slug="repl")
        .distinct()
    )

    data = []
    for a in Group.objects.filter(type="area"):
        if only_active and not a.is_active:
            continue

        area_docs = docs.filter(group__parent=a).exclude(group__acronym="none")
        if not area_docs:
            continue

        area_page_cnt = 0
        area_doc_cnt = 0
        for wg in Group.objects.filter(type="wg", parent=a):
            if only_active and not wg.is_active:
                continue

            wg_docs = area_docs.filter(group=wg)
            if not wg_docs:
                continue

            wg_page_cnt = 0
            for doc in wg_docs:
                # add doc data
                data.append(
                    {
                        "id": doc.name,
                        "active": True,
                        "parent": wg.acronym,
                        "grandparent": a.acronym,
                        "pages": doc.pages,
                        "docs": 1,
                    }
                )
                wg_page_cnt += doc.pages

            area_doc_cnt += len(wg_docs)
            area_docs = area_docs.exclude(group=wg)

            # add WG data
            data.append(
                {
                    "id": wg.acronym,
                    "active": wg.is_active,
                    "parent": a.acronym,
                    "grandparent": "ietf",
                    "pages": wg_page_cnt,
                    "docs": len(wg_docs),
                }
            )
            area_page_cnt += wg_page_cnt

        # add area data
        data.append(
            {
                "id": a.acronym,
                "active": a.is_active,
                "parent": "ietf",
                "pages": area_page_cnt,
                "docs": area_doc_cnt,
            }
        )

    data.append({"id": "ietf", "active": True})
    return JsonResponse(data, safe=False)


# --- Review views -----------------------------------------------------

def get_open_review_requests_for_team(team, assignment_status=None):
    open_review_requests = ReviewRequest.objects.filter(team=team).filter(
        Q(state_id='requested') | Q(state_id='assigned',reviewassignment__state__in=('assigned','accepted'))
    ).prefetch_related(
        "type", "state", "doc", "doc__states",
    ).order_by("-time", "-id").distinct()

    if assignment_status == "unassigned":
        open_review_requests = suggested_review_requests_for_team(team) + list(open_review_requests.filter(state_id='requested'))
    elif assignment_status == "assigned":
        open_review_requests = list(open_review_requests.filter(state_id='assigned'))
    else:
        open_review_requests = suggested_review_requests_for_team(team) + list(open_review_requests)

    #today = datetime.date.today()
    #unavailable_periods = current_unavailable_periods_for_reviewers(team)
    #for r in open_review_requests:
        #if r.reviewer:
        #    r.reviewer_unavailable = any(p.availability == "unavailable"
        #                                 for p in unavailable_periods.get(r.reviewer.person_id, []))
        #r.due = max(0, (today - r.deadline).days)

    return open_review_requests

def review_requests(request, acronym, group_type=None):
    group = get_group_or_404(acronym, group_type)
    if not group.features.has_reviews:
        raise Http404

    unassigned_review_requests = [r for r in get_open_review_requests_for_team(group) if not r.state_id=='assigned']
    unassigned_review_requests.sort(key=lambda r: r.doc.name)

    open_review_assignments = list(ReviewAssignment.objects.filter(review_request__team=group, state_id__in=('assigned','accepted')).order_by('-assigned_on'))
    today = date_today(DEADLINE_TZINFO)
    unavailable_periods = current_unavailable_periods_for_reviewers(group)
    for a in open_review_assignments:
        a.reviewer_unavailable = any(p.availability == "unavailable"
                                     for p in unavailable_periods.get(a.reviewer.person_id, []))
        a.due = max(0, (today - a.review_request.deadline).days)

    closed_review_assignments = ReviewAssignment.objects.filter(review_request__team=group).exclude(state_id__in=('assigned','accepted')).prefetch_related("state","result").order_by('-assigned_on')

    closed_review_requests = ReviewRequest.objects.filter(team=group).exclude(state__in=("requested", "assigned")).prefetch_related("type", "state", "doc").order_by("-time", "-id")

    since_choices = [
        (None, "1 month"),
        ("3m", "3 months"),
        ("6m", "6 months"),
        ("1y", "1 year"),
        ("2y", "2 years"),
        ("all", "All"),
    ]
    since = request.GET.get("since", None)
    if since not in [key for key, label in since_choices]:
        since = None

    if since != "all":
        date_limit = {
            None: datetime.timedelta(days=31),
            "3m": datetime.timedelta(days=31 * 3),
            "6m": datetime.timedelta(days=180),
            "1y": datetime.timedelta(days=365),
            "2y": datetime.timedelta(days=2 * 365),
        }[since]

        closed_review_requests = closed_review_requests.filter(
              Q(reviewrequestdocevent__type='closed_review_request',
                reviewrequestdocevent__time__gte=datetime_today(DEADLINE_TZINFO) - date_limit)
            | Q(reviewrequestdocevent__isnull=True, time__gte=datetime_today(DEADLINE_TZINFO) - date_limit)
        ).distinct()

        closed_review_assignments = closed_review_assignments.filter(
            completed_on__gte = datetime_today(DEADLINE_TZINFO) - date_limit,
        )

    return render(request, 'group/review_requests.html',
                  construct_group_menu_context(request, group, "review requests", group_type, {
                      "unassigned_review_requests": unassigned_review_requests,
                      "open_review_assignments": open_review_assignments,
                      "closed_review_requests": closed_review_requests,
                      "closed_review_assignments": closed_review_assignments,
                      "since_choices": since_choices,
                      "since": since,
                      "can_manage_review_requests": can_manage_review_requests_for_team(request.user, group),
                      "can_access_stats": can_access_review_stats_for_team(request.user, group),
                  }))

def reviewer_overview(request, acronym, group_type=None):
    group = get_group_or_404(acronym, group_type)
    if not group.features.has_reviews:
        raise Http404

    can_manage = can_manage_review_requests_for_team(request.user, group)

    can_reset_next_reviewer = can_manage and group.reviewteamsettings.reviewer_queue_policy_id == 'RotateAlphabetically'

    reviewers = get_reviewer_queue_policy(group).default_reviewer_rotation_list(include_unavailable=True)

    reviewer_settings = { s.person_id: s for s in ReviewerSettings.objects.filter(team=group) }
    unavailable_periods = defaultdict(list)
    for p in unavailable_periods_to_list().filter(team=group):
        unavailable_periods[p.person_id].append(p)
    reviewer_roles = { r.person_id: r for r in Role.objects.filter(group=group, name="reviewer").select_related("email") }

    today = date_today()

    max_closed_reqs = settings.GROUP_REVIEW_MAX_ITEMS_TO_SHOW_IN_REVIEWER_LIST
    days_back = settings.GROUP_REVIEW_DAYS_TO_SHOW_IN_REVIEWER_LIST
    if can_manage:
        secretary_settings = (ReviewSecretarySettings.objects.filter(person=
                                                                     request.user.person,
                                                                     team=group).first()
                              or ReviewSecretarySettings(person=request.user.person,
                                                         team=group))
        if secretary_settings:
            max_closed_reqs = secretary_settings.max_items_to_show_in_reviewer_list
            days_back = secretary_settings.days_to_show_in_reviewer_list

    if max_closed_reqs == None:
        max_closed_reqs = 10

    if days_back == None:
        days_back = 365
    req_data_for_reviewers = latest_review_assignments_for_reviewers(group, days_back)
    assignment_state_by_slug = { n.slug: n for n in ReviewAssignmentStateName.objects.all() }

    days_needed = days_needed_to_fulfill_min_interval_for_reviewers(group)

    for person in reviewers:
        person.settings = reviewer_settings.get(person.pk) or ReviewerSettings(team=group, person=person)
        person.settings_url = None
        person.role = reviewer_roles.get(person.pk)
        if person.role and (can_manage or user_is_person(request.user, person)):
            kwargs = { "acronym": group.acronym, "reviewer_email": person.role.email.address }
            if group_type:
                kwargs["group_type"] = group_type
            person.settings_url = urlreverse("ietf.group.views.change_reviewer_settings", kwargs=kwargs)
        if can_access_review_stats_for_team(request.user, group):
            person.unavailable_periods = unavailable_periods.get(person.pk, [])
            person.completely_unavailable = any(p.availability == "unavailable"
                                           and (p.start_date is None or p.start_date <= today) and (p.end_date is None or today <= p.end_date)
                                           for p in person.unavailable_periods)
            person.busy = person.id in days_needed 
        

        days_since = 9999
        req_data = req_data_for_reviewers.get(person.pk, [])
        closed_reqs = 0
        latest_reqs = []
        for d in req_data:
            if d.state in ["assigned", "accepted"] or closed_reqs < max_closed_reqs:
                if not d.state in ["assigned", "accepted"]:
                    closed_reqs += 1
                latest_reqs.append((d.assignment_pk, d.request_pk, d.doc_name, d.reviewed_rev, d.assigned_time, d.deadline,
                                    assignment_state_by_slug.get(d.state),
                                    int(math.ceil(d.assignment_to_closure_days)) if d.assignment_to_closure_days is not None else None))
            if d.state in ["completed", "completed_in_time", "completed_late"]:
                if d.assigned_time is not None:
                    delta = timezone.now() - d.assigned_time
                    if d.assignment_to_closure_days is not None:
                        days = int(delta.days - d.assignment_to_closure_days)
                        if days_since > days: days_since = days

        person.latest_reqs = latest_reqs
        person.days_since_completed_review = days_since

    return render(request, 'group/reviewer_overview.html',
                  construct_group_menu_context(request, group, "reviewers", group_type, {
                      "reviewers": reviewers,
                      "can_access_stats": can_access_review_stats_for_team(request.user, group),
                      "can_reset_next_reviewer": can_reset_next_reviewer,
                  }))


@login_required
def manage_review_requests(request, acronym, group_type=None, assignment_status=None):
    group = get_group_or_404(acronym, group_type)
    if not group.features.has_reviews:
        raise Http404

    if not can_manage_review_requests_for_team(request.user, group):
        permission_denied(request, "You do not have permission to perform this action")

    review_requests = get_open_review_requests_for_team(group, assignment_status=assignment_status)

    document_requests = extract_revision_ordered_review_requests_for_documents_and_replaced(
        ReviewRequest.objects.filter(state__in=("part-completed", "completed", "assigned"), team=group).prefetch_related("reviewassignment_set__result"),
        set(r.doc.name for r in review_requests),
    )

    # we need a mutable query dict for resetting upon saving with
    # conflicts
    query_dict = request.POST.copy() if request.method == "POST" else None

    for req in review_requests:
        req.form = ManageReviewRequestForm(req, query_dict)

        # add previous requests
        l = []
        rev = None
        for r in document_requests.get(req.doc.name, []):
            # take all on the latest reviewed rev
            for a in r.reviewassignment_set.all():
                if l and rev:
                    if r.doc_id == l[0].doc_id and a.reviewed_rev:
                        if int(a.reviewed_rev) > int(rev):
                            l = [r]
                        elif int(a.reviewed_rev) == int(rev):
                            l.append(r)
                else:
                    l = [r]
                rev = l[0].reviewassignment_set.first().reviewed_rev

        augment_review_requests_with_events(l)

        req.latest_reqs = l
        req.wg_chairs = None
        if req.doc.group:
            req.wg_chairs = [role.person for role in req.doc.group.role_set.filter(name__slug='chair')]

    saving = False
    newly_closed = newly_opened = newly_assigned = 0

    if request.method == "POST":
        form_action = request.POST.get("action", "")
        saving = form_action.startswith("save")

        # check for conflicts
        review_requests_dict = { str(r.pk): r for r in review_requests if r.pk}
        posted_reqs = set(request.POST.getlist("reviewrequest", []))
        posted_reqs.discard(u'None')
        current_reqs = set(review_requests_dict.keys())

        closed_reqs = posted_reqs - current_reqs
        newly_closed = len(closed_reqs)

        opened_reqs = current_reqs - posted_reqs
        newly_opened = len(opened_reqs)
        for r in opened_reqs:
            review_requests_dict[r].form.add_error(None, "New request.")

        form_results = []
        for req in review_requests:
            form_results.append(req.form.is_valid())

        if saving and all(form_results) and not (newly_closed > 0 or newly_opened > 0 or newly_assigned > 0):

            reqs_to_assign = []
            for review_req in review_requests:
                action = review_req.form.cleaned_data.get("action")
                if action=="close":
                    close_review_request(request, review_req, review_req.form.cleaned_data["close"],
                                         review_req.form.cleaned_data["close_comment"])
                elif action=="assign" and review_req.form.cleaned_data["reviewer"]:
                    if review_req.form.cleaned_data.get("review_type"):
                        review_req.type = review_req.form.cleaned_data.get("review_type")
                    reqs_to_assign.append(review_req)

            assignments_by_person = dict()
            for r in reqs_to_assign:
                person = r.form.cleaned_data["reviewer"].person
                if not person in assignments_by_person:
                    assignments_by_person[person] = []
                assignments_by_person[person].append(r)
            
            # Make sure the any assignments to the person at the head
            # of the rotation queue are processed first so that the queue
            # rotates before any more assignments are processed
            reviewer_policy = get_reviewer_queue_policy(group)
            head_of_rotation = reviewer_policy.default_reviewer_rotation_list_without_skipped()[0]
            while head_of_rotation in assignments_by_person:
                for review_req in assignments_by_person[head_of_rotation]:
                    assign_review_request_to_reviewer(request, review_req, review_req.form.cleaned_data["reviewer"],review_req.form.cleaned_data["add_skip"])
                    reqs_to_assign.remove(review_req)
                del assignments_by_person[head_of_rotation]
                head_of_rotation = reviewer_policy.default_reviewer_rotation_list_without_skipped()[0]

            for review_req in reqs_to_assign:
                assign_review_request_to_reviewer(request, review_req, review_req.form.cleaned_data["reviewer"],review_req.form.cleaned_data["add_skip"])
            
            kwargs = { "acronym": group.acronym }
            if group_type:
                kwargs["group_type"] = group_type

            if form_action == "save-continue":
                if assignment_status:
                    kwargs["assignment_status"] = assignment_status
                
                return redirect(manage_review_requests, **kwargs)
            else:
                import ietf.group.views
                return redirect(ietf.group.views.review_requests, **kwargs)

    other_assignment_status = {
        "unassigned": "assigned",
        "assigned": "unassigned",
    }.get(assignment_status)

    return render(request, 'group/manage_review_requests.html', {
        'group': group,
        'review_requests': review_requests,
        'newly_closed': newly_closed,
        'newly_opened': newly_opened,
        'newly_assigned': newly_assigned,
        'saving': saving,
        'assignment_status': assignment_status,
        'other_assignment_status': other_assignment_status,
    })

@login_required
def email_open_review_assignments(request, acronym, group_type=None):
    group = get_group_or_404(acronym, group_type)
    if not group.features.has_reviews:
        raise Http404

    if not can_manage_review_requests_for_team(request.user, group):
        permission_denied(request, "You do not have permission to perform this action")

    review_assignments = list(ReviewAssignment.objects.filter(
        review_request__team=group,
        state__in=("assigned", "accepted"),
    ).prefetch_related("reviewer", "review_request__type", "state", "review_request__doc").distinct().order_by("reviewer","-review_request__deadline"))

    for r in review_assignments:
        if r.review_request.doc.telechat_date():
            r.section = 'For telechat %s' % r.review_request.doc.telechat_date().isoformat()
            r.section_order='0'+r.section
        elif r.review_request.type_id == 'early':
            r.section = 'Early review requests:'
            r.section_order='2'
        else:
            r.section = 'Last calls:'
            r.section_order='1'
        e = r.review_request.doc.latest_event(LastCallDocEvent, type="sent_last_call")
        r.lastcall_ends = e and e.expires.astimezone(DEADLINE_TZINFO).date().isoformat()
        r.earlier_review = ReviewAssignment.objects.filter(review_request__doc=r.review_request.doc,reviewer__in=r.reviewer.person.email_set.all(),state="completed")
        if r.earlier_review:
            earlier_reviews_formatted = ['-{} {} reviewed'.format(ra.reviewed_rev, ra.review_request.type.slug) for ra in r.earlier_review]
            r.earlier_reviews = '({})'.format(', '.join(earlier_reviews_formatted))

    # If a document is both scheduled for a telechat and a last call review, replicate
    # a copy of the review assignment in the last calls section (#2118)
    def should_be_replicated_in_last_call_section(r):
        return r.section.startswith('For telechat') and r.review_request.type_id != 'early'
    
    for r in filter(should_be_replicated_in_last_call_section, review_assignments):
        r_new = copy.copy(r)
        r_new.section = 'Last calls:'
        r_new.section_order = '1'
        review_assignments.append(r_new)

    review_assignments.sort(key=lambda r: r.section_order + r.reviewer.person.last_name() + 
                                          r.reviewer.person.first_name())

    back_url = request.GET.get("next")
    if not back_url:
        kwargs = { "acronym": group.acronym }
        if group_type:
            kwargs["group_type"] = group_type

        import ietf.group.views
        back_url = urlreverse(ietf.group.views.review_requests, kwargs=kwargs)

    if request.method == "POST" and request.POST.get("action") == "email":
        form = EmailOpenAssignmentsForm(request.POST)
        if form.is_valid():
            send_mail_text(request,
                            to=form.cleaned_data["to"],
                            frm=form.cleaned_data["frm"],
                            subject=form.cleaned_data["subject"],
                            txt=form.cleaned_data["body"],
                            cc=form.cleaned_data["cc"],
                            extra={"Reply-To": form.cleaned_data["reply_to"]}
                        )
            return HttpResponseRedirect(back_url)
    else:
        (to,cc) = gather_address_lists('review_assignments_summarized',group=group)
        reply_to = Recipient.objects.get(slug='group_secretaries').gather(group=group)
        frm = request.user.person.formatted_email()

        templateqs = DBTemplate.objects.filter(path="/group/%s/email/open_assignments.txt" % group.acronym)
        if templateqs.exists():
            template = templateqs.first()
        else:
            template = DBTemplate.objects.get(path="/group/defaults/email/open_assignments.txt")

        partial_msg = render_to_string(template.path, {
            "review_assignments": review_assignments,
            "rotation_list": get_reviewer_queue_policy(group).default_reviewer_rotation_list()[:10],
            "group" : group,
        })
        
        (msg,_,_) = parse_preformatted(partial_msg)

        body = msg.get_payload()
        subject = msg['Subject']

        form = EmailOpenAssignmentsForm(initial={
            "to": ", ".join(to),
            "cc": ", ".join(cc),
            "reply_to": ", ".join(reply_to),
            "frm": frm,
            "subject": subject,
            "body": body,
        })

    return render(request, 'group/email_open_review_assignments.html', {
        'group': group,
        'review_assignments': review_assignments,
        'form': form,
        'back_url': back_url,
    })


@login_required
def change_reviewer_settings(request, acronym, reviewer_email, group_type=None):
    group = get_group_or_404(acronym, group_type)
    if not group.features.has_reviews:
        raise Http404

    reviewer_role = get_object_or_404(Role, name="reviewer", group=group, email=reviewer_email)
    reviewer = reviewer_role.person

    if not (user_is_person(request.user, reviewer)
            or can_manage_review_requests_for_team(request.user, group)):
        permission_denied(request, "You do not have permission to perform this action")

    exclude_fields = []
    if not can_manage_review_requests_for_team(request.user, group):
        exclude_fields.append('skip_next')

    settings = ReviewerSettings.objects.filter(person=reviewer, team=group).first()
    if not settings:
        settings = ReviewerSettings(person=reviewer, team=group)
        settings.filter_re = get_default_filter_re(reviewer)

    back_url = request.GET.get("next")
    if not back_url:
        import ietf.group.views
        kwargs = { "acronym": group.acronym}
        if group_type:
            kwargs["group_type"] = group_type
        back_url = urlreverse(ietf.group.views.reviewer_overview, kwargs=kwargs)

    # settings
    if request.method == "POST" and request.POST.get("action") == "change_settings":
        prev_min_interval = settings.get_min_interval_display()
        prev_skip_next = settings.skip_next
        settings_form = ReviewerSettingsForm(request.POST, instance=settings, exclude_fields=exclude_fields)
        if settings_form.is_valid():
            settings = settings_form.save()
            if settings_form.has_changed():
                update_change_reason(settings, "Updated %s" % ", ".join(settings_form.changed_data) )

            changes = []
            if settings.get_min_interval_display() != prev_min_interval:
                changes.append("Frequency changed to \"{}\" from \"{}\".".format(settings.get_min_interval_display() or "Not specified", prev_min_interval or "Not specified"))
            if settings.skip_next != prev_skip_next:
                changes.append("Skip next assignments changed to {} from {}.".format(settings.skip_next, prev_skip_next))
            if settings.request_assignment_next:
                changes.append("Reviewer has requested to be the next person selected for an "
                               "assignment, as soon as possible, and will be on the top of "
                               "the queue.") 
            if changes:
                email_reviewer_availability_change(request, group, reviewer_role, "\n\n".join(changes), request.user.person)

            return HttpResponseRedirect(back_url)
    else:
        settings_form = ReviewerSettingsForm(instance=settings,exclude_fields=exclude_fields)

    # periods
    unavailable_periods = unavailable_periods_to_list().filter(person=reviewer, team=group)

    if request.method == "POST" and request.POST.get("action") == "add_period":
        period_form = AddUnavailablePeriodForm(request.POST)
        if period_form.is_valid():
            period = period_form.save(commit=False)
            period.team = group
            period.person = reviewer
            period.save()
            update_change_reason(period, "Added unavailability period: {}".format(period))

            today = date_today()

            in_the_past = period.end_date and period.end_date < today

            if not in_the_past:
                msg = "{} -- {} {}\n                         {}".format(
                    period.start_date.isoformat() if period.start_date else "indefinite",
                    period.end_date.isoformat() if period.end_date else "indefinite",
                    period.get_availability_display(),
                    period.reason,
                )

                if period.availability == "unavailable":
                    # the secretary might need to reassign
                    # assignments, so mention the current ones

                    review_assignments = ReviewAssignment.objects.filter(state__in=["assigned", "accepted"], reviewer=reviewer_role.email, review_request__team=group)
                    msg += "\n\n"

                    if review_assignments:
                        msg += "{} is currently assigned to review:".format(reviewer_role.person)
                        for r in review_assignments:
                            msg += "\n\n"
                            msg += "{} (deadline: {})".format(r.review_request.doc.name, r.review_request.deadline.isoformat())
                    else:
                        msg += "{} does not have any assignments currently.".format(reviewer_role.person)

                email_reviewer_availability_change(request, group, reviewer_role, msg, request.user.person)

            return HttpResponseRedirect(request.get_full_path())
    else:
        period_form = AddUnavailablePeriodForm()

    if request.method == "POST" and request.POST.get("action") == "delete_period":
        period_id = request.POST.get("period_id")
        if period_id is not None:
            for period in unavailable_periods:
                if str(period.pk) == period_id:
                    period.delete()
                    update_change_reason(period, "Removed unavailability period: {}".format(period))

                    today = date_today()

                    in_the_past = period.end_date and period.end_date < today

                    if not in_the_past:
                        msg = "Removed unavailable period: {} - {} ({})".format(
                            period.start_date.isoformat() if period.start_date else "indefinite",
                            period.end_date.isoformat() if period.end_date else "indefinite",
                            period.get_availability_display(),
                        )

                        email_reviewer_availability_change(request, group, reviewer_role, msg, request.user.person)

            return HttpResponseRedirect(request.get_full_path())

    for p in unavailable_periods:
        if not p.end_date:
            p.end_form = EndUnavailablePeriodForm(p.start_date, request.POST if request.method == "POST" and request.POST.get("action") == "end_period" else None)

    if request.method == "POST" and request.POST.get("action") == "end_period":
        period_id = request.POST.get("period_id")
        for period in unavailable_periods:
            if str(period.pk) == period_id:
                if not period.end_date and period.end_form.is_valid():
                    period.end_date = period.end_form.cleaned_data["end_date"]
                    period.save()
                    update_change_reason(period, "Set end date of unavailability period: {}".format(period))

                    msg = "Set end date of unavailable period: {} - {} ({})".format(
                        period.start_date.isoformat() if period.start_date else "indefinite",
                        period.end_date.isoformat() if period.end_date else "indefinite",
                        period.get_availability_display(),
                    )

                    email_reviewer_availability_change(request, group, reviewer_role, msg, request.user.person)

                    return HttpResponseRedirect(request.get_full_path())


    return render(request, 'group/change_reviewer_settings.html', {
        'group': group,
        'reviewer_email': reviewer_email,
        'back_url': back_url,
        'settings_form': settings_form,
        'period_form': period_form,
        'unavailable_periods': unavailable_periods,
        'unavailable_periods_history': UnavailablePeriod.history.filter(person=reviewer, team=group),
        'reviewersettings': settings,
    })


@login_required
def change_review_secretary_settings(request, acronym, group_type=None):
    group = get_group_or_404(acronym, group_type)
    if not group.features.has_reviews:
        raise Http404
    if not Role.objects.filter(name="secr", group=group, person__user=request.user).exists():
        raise Http404

    person = request.user.person

    settings = (ReviewSecretarySettings.objects.filter(person=person, team=group).first()
                or ReviewSecretarySettings(person=person, team=group))

    import ietf.group.views
    back_url = urlreverse(ietf.group.views.review_requests, kwargs={ "acronym": acronym, "group_type": group.type_id })

    # settings
    if request.method == "POST":
        settings_form = ReviewSecretarySettingsForm(request.POST, instance=settings)
        if settings_form.is_valid():
            settings_form.save()
            return HttpResponseRedirect(back_url)
    else:
        settings_form = ReviewSecretarySettingsForm(instance=settings)

    return render(request, 'group/change_review_secretary_settings.html', {
        'group': group,
        'back_url': back_url,
        'settings_form': settings_form,
    })

class AddCommentForm(forms.Form):
    comment = forms.CharField(required=True, widget=forms.Textarea, strip=False)

def add_comment(request, acronym, group_type=None):
    group = get_group_or_404(acronym, group_type)

    if not is_authorized_in_group(request.user,group):
        permission_denied(request, "You need to a chair, secretary, or delegate of this group to add a comment.")
    
    if request.method == 'POST':
        form = AddCommentForm(request.POST)
        if form.is_valid():
            comment = form.cleaned_data['comment']
            event = GroupEvent.objects.create(group=group,desc=comment,type="added_comment",by=request.user.person)
            email_comment(request,event)
            return redirect('ietf.group.views.history', acronym=group.acronym)
    else:
        form = AddCommentForm()

    return render(request, 'group/add_comment.html', { 'group':group, 'form':form, })

class ResetNextReviewerForm(forms.Form):
    next_reviewer = forms.ChoiceField()

    def __init__(self, *args, **kwargs):
        instance = kwargs.pop('instance')
        super(ResetNextReviewerForm, self).__init__(*args, **kwargs)
        self.fields['next_reviewer'].choices = [ (p.pk, p.plain_name()) for p in get_reviewer_queue_policy(instance.team).default_reviewer_rotation_list(include_unavailable=True)]

@login_required
def reset_next_reviewer(request, acronym, group_type=None):
    group = get_group_or_404(acronym, group_type)
    if not group.features.has_reviews:
        raise Http404
    if group.reviewteamsettings.reviewer_queue_policy_id != 'RotateAlphabetically':
        raise Http404

    if not Role.objects.filter(name="secr", group=group, person__user=request.user).exists() and not has_role(request.user, "Secretariat"):
        permission_denied(request, "You don't have permission to access this view")

    instance = group.nextreviewerinteam_set.first()
    if not instance:
        raise Http404

    if request.method == 'POST':
        form = ResetNextReviewerForm(request.POST,instance=instance)
        if form.is_valid():
            instance.next_reviewer = Person.objects.get(pk=form.cleaned_data['next_reviewer'])
            instance.save()
            return redirect('ietf.group.views.reviewer_overview', acronym = group.acronym )
    else:
        form = ResetNextReviewerForm(instance=instance)

    return render(request, 'group/reset_next_reviewer.html', { 'group':group, 'form': form,})

def statements(request, acronym, group_type=None):
    if not acronym in ["iab", "iesg"]:
        raise Http404
    group = get_group_or_404(acronym, group_type)
    statements = (
        group.document_set.filter(type_id="statement")
        .annotate(
            published=Subquery(
                DocEvent.objects.filter(doc=OuterRef("pk"), type="published_statement")
                .order_by("-time")
                .values("time")[:1]
            )
        )
        .annotate(
            status=Subquery(
                Document.states.through.objects.filter(
                    document_id=OuterRef("pk"), state__type="statement"
                ).values_list("state__slug", flat=True)[:1]
            )
        )
        .order_by("-published")
    )
    return render(
        request,
        "group/statements.html",
        construct_group_menu_context(
            request,
            group,
            "statements",
            group_type,
            {
                "group": group,
                "statements": statements,
            },
        ),
    )

def appeals(request, acronym, group_type=None):
    if not acronym in ["iab", "iesg"]:
        raise Http404
    group = get_group_or_404(acronym, group_type)
    appeals = group.appeal_set.all()
    return render(
        request,
        "group/appeals.html",
        construct_group_menu_context(
            request,
            group,
            "appeals",
            group_type,
            {
                "group": group,
                "appeals": appeals,
            },
        ),
    )

@ignore_view_kwargs("group_type")
def appeal_artifact(request, acronym, artifact_id):
    artifact = get_object_or_404(AppealArtifact, pk=artifact_id)
    if artifact.is_markdown():
        artifact_html = markdown.markdown(artifact.bits.tobytes().decode("utf-8"))
        return render(
            request,
            "group/appeal_artifact.html",
            dict(artifact=artifact, artifact_html=artifact_html)
        )
    else:
        return HttpResponse(
            artifact.bits, 
            headers = {
                "Content-Type": artifact.content_type,
                "Content-Disposition": f'attachment; filename="{artifact.download_name()}"'
            }
        )
    
@role_required("Secretariat")
@ignore_view_kwargs("group_type")
def appeal_artifact_markdown(request, acronym, artifact_id):
    artifact = get_object_or_404(AppealArtifact, pk=artifact_id)
    if artifact.is_markdown():
        return HttpResponse(artifact.bits, content_type=artifact.content_type)
    else:
        raise Http404
