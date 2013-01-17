# Copyright (C) 2009-2010 Nokia Corporation and/or its subsidiary(-ies).
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

import re, os, datetime, urllib

from django.http import HttpResponse, Http404
from django.shortcuts import render_to_response, get_object_or_404, redirect
from django.template import RequestContext
from django.template.loader import render_to_string
from django.template.defaultfilters import truncatewords_html
from django.utils import simplejson as json
from django.utils.decorators import decorator_from_middleware
from django.middleware.gzip import GZipMiddleware
from django.core.urlresolvers import reverse as urlreverse, NoReverseMatch
from django.conf import settings

from ietf.idtracker.models import InternetDraft, IDInternal, BallotInfo, DocumentComment
from ietf.idtracker.templatetags.ietf_filters import format_textarea, fill
from ietf.idrfc import markup_txt
from ietf.idrfc.utils import *
from ietf.idrfc.models import RfcIndex, DraftVersions
from ietf.idrfc.idrfc_wrapper import BallotWrapper, IdWrapper, RfcWrapper
from ietf.ietfworkflows.utils import get_full_info_for_draft
from ietf.doc.models import *
from ietf.doc.utils import *
from ietf.utils.history import find_history_active_at
from ietf.ietfauth.utils import *

def render_document_top(request, doc, tab, name):
    tabs = []
    tabs.append(("Document", "document", urlreverse("ietf.idrfc.views_doc.document_main", kwargs=dict(name=name)), True))

    ballot = doc.latest_event(BallotDocEvent, type="created_ballot")
    if doc.type_id in ("draft","conflrev"):
        # if doc.in_ietf_process and doc.ietf_process.has_iesg_ballot:
        tabs.append(("IESG Evaluation Record", "ballot", urlreverse("ietf.idrfc.views_doc.document_ballot", kwargs=dict(name=name)), ballot))
    elif doc.type_id == "charter":
        tabs.append(("IESG Review", "ballot", urlreverse("ietf.idrfc.views_doc.document_ballot", kwargs=dict(name=name)), ballot))

    # FIXME: if doc.in_ietf_process and doc.ietf_process.has_iesg_ballot:
    if doc.type_id != "conflrev":
        tabs.append(("IESG Writeups", "writeup", urlreverse("ietf.idrfc.views_doc.document_writeup", kwargs=dict(name=name)), True))

    tabs.append(("History", "history", urlreverse("ietf.idrfc.views_doc.document_history", kwargs=dict(name=name)), True))

    if name.startswith("rfc"):
        name = "RFC %s" % name[3:]
    else:
        name += "-" + doc.rev

    return render_to_string("idrfc/document_top.html",
                            dict(doc=doc,
                                 tabs=tabs,
                                 selected=tab,
                                 name=name))


def document_main(request, name, rev=None):
    if "old" in request.GET and (name.lower().startswith("draft") or name.lower().startswith("rfc")):
        if rev != None: # no support for old revisions at the moment
            raise Http404()
        return document_main_idrfc(request, name, tab="document")
    # generic part

    doc = get_object_or_404(Document, docalias__name=name)

    # take care of possible redirections
    aliases = DocAlias.objects.filter(document=doc).values_list("name", flat=True)
    if doc.type_id == "draft" and not name.startswith("rfc"):
        for a in aliases:
            if a.startswith("rfc"):
                return redirect("doc_view", name=a)

    group = doc.group
    if doc.type_id == 'conflrev':
        conflictdoc = doc.related_that_doc('conflrev').get().document
    
    revisions = []
    for h in doc.history_set.order_by("time", "id"):
        if h.rev and not h.rev in revisions:
            revisions.append(h.rev)
    if not doc.rev in revisions:
        revisions.append(doc.rev)

    snapshot = False

    if rev != None:
        if rev == doc.rev:
            return redirect('doc_view', name=name)

        # find the entry in the history
        for h in doc.history_set.order_by("-time"):
            if rev == h.rev:
                snapshot = True
                doc = h
                break

        if not snapshot:
            return redirect('doc_view', name=name)

        if doc.type_id == "charter":
            # find old group, too
            gh = find_history_active_at(doc.group, doc.time)
            if gh:
                group = gh

    top = render_document_top(request, doc, "document", name)


    telechat = doc.latest_event(TelechatDocEvent, type="scheduled_for_telechat")
    if telechat and (not telechat.telechat_date or telechat.telechat_date < datetime.date.today()):
       telechat = None


    # specific document types
    if doc.type_id == "draft":
        split_content = not request.GET.get('include_text')
        if request.COOKIES.get("full_draft", "") == "on":
            split = False

        iesg_state = doc.get_state("draft-iesg")

        can_edit = has_role(request.user, ("Area Director", "Secretariat"))
        stream_slugs = StreamName.objects.values_list("slug", flat=True)
        can_change_stream = bool(can_edit or (request.user.is_authenticated() and
                                              Role.objects.filter(name__in=("chair", "auth"),
                                                                  group__acronym__in=stream_slugs,
                                                                  person__user=request.user)))
        can_edit_iana_state = has_role(request.user, ("Secretariat", "IANA"))

        rfc_number = name[3:] if name.startswith("") else None
        draft_name = None
        for a in aliases:
            if a.startswith("draft"):
                draft_name = a

        rfc_aliases = [prettify_std_name(a) for a in aliases
                       if a.startswith("fyi") or a.startswith("std") or a.startswith("bcp")]

        latest_revision = None

        if doc.get_state_slug() == "rfc":
            # content
            filename = name + ".txt"

            content = get_document_content(filename, os.path.join(settings.RFC_PATH, filename),
                                           split_content, markup=True)

            # file types
            base_path = os.path.join(settings.RFC_PATH, name + ".")
            possible_types = ["txt", "pdf", "ps"]
            found_types = [t for t in possible_types if os.path.exists(base_path + t)]

            base = "http://www.rfc-editor.org/rfc/"

            file_urls = []
            for t in found_types:
                label = "plain text" if t == "txt" else t
                file_urls.append((label, base + name + "." + t))

            if "pdf" not in found_types and "txt" in found_types:
                file_urls.append(("pdf", base + "pdfrfc/" + name + ".txt.pdf"))

            if "txt" in found_types:
                file_urls.append(("html", "http://tools.ietf.org/html/" + name))

            if not found_types:
                content = "This RFC is not currently available online."
                split_content = False
            elif "txt" not in found_types:
                content = "This RFC is not available in plain text format."
                split_content = False
        else:
            filename = "%s-%s.txt" % (draft_name, doc.rev)

            content = get_document_content(filename, os.path.join(settings.INTERNET_DRAFT_PATH, filename),
                                           split_content, markup=True)

            # file types
            base_path = os.path.join(settings.INTERNET_DRAFT_PATH, doc.name + "-" + doc.rev + ".")
            possible_types = ["pdf", "xml", "ps"]
            found_types = ["txt"] + [t for t in possible_types if os.path.exists(base_path + t)]

            tools_base = "http://tools.ietf.org/"

            if doc.get_state_slug() == "active":
                base = "http://www.ietf.org/id/"
            else:
                base = tools_base + "id/"

            file_urls = []
            for t in found_types:
                label = "plain text" if t == "txt" else t
                file_urls.append((label, base + doc.name + "-" + doc.rev + "." + t))

            if "pdf" not in found_types:
                file_urls.append(("pdf", tools_base + "pdf/" + doc.name + "-" + doc.rev + ".pdf"))
            file_urls.append(("html", tools_base + "html/" + doc.name + "-" + doc.rev))

            # latest revision
            latest_revision = doc.latest_event(NewRevisionDocEvent, type="new_revision")

        # ballot
        ballot_summary = None
        if iesg_state and iesg_state.slug in ("lc", "writeupw", "goaheadw", "iesg-eva", "defer"):
            active_ballot = doc.active_ballot()
            if active_ballot:
                ballot_summary = needed_ballot_positions(doc, active_ballot.active_ad_positions().values())

        # submission
        submission = ""
        if group.type_id == "individ":
            submission = "individual"
        elif group.type_id == "area" and doc.stream_id == "ietf":
            submission = "individual in %s area" % group.acronym
        elif group.type_id in ("rg", "wg"):
            submission = "%s %s" % (group.acronym, group.type)
            if group.type_id == "wg":
                submission = "<a href=\"%s\">%s</a>" % (urlreverse("wg_docs", kwargs=dict(acronym=doc.group.acronym)), submission)
            if doc.stream_id and doc.get_state_slug("draft-stream-%s" % doc.stream_id) == "c-adopt":
                submission = "candidate for %s" % submission

        # resurrection
        resurrected_by = None
        if doc.get_state_slug() == "expired":
            e = doc.latest_event(type__in=("requested_resurrect", "completed_resurrect"))
            if e and e.type == "requested_resurrect":
                resurrected_by = e.by

        # stream info
        stream_state = None
        if doc.stream:
            stream_state = doc.get_state("draft-stream-%s" % doc.stream_id)
        stream_tags = doc.tags.filter(slug__in=get_tags_for_stream_id(doc.stream_id))

        shepherd_writeup = doc.latest_event(WriteupDocEvent, type="changed_protocol_writeup")

        can_edit_stream_info = is_authorized_in_doc_stream(request.user, doc)
        can_edit_shepherd_writeup = can_edit_stream_info or user_is_person(request.user, doc.shepherd) or has_role(request.user, ["Area Director"])

        consensus = None
        if doc.stream_id in ("ietf", "irtf", "iab"):
            e = doc.latest_event(ConsensusDocEvent, type="changed_consensus")
            consensus = nice_consensus(e and e.consensus)

        # mailing list search archive
        search_archive = "www.ietf.org/mail-archive/web/"
        if doc.stream_id == "ietf" and group.type_id == "wg" and group.list_archive:
            search_archive = group.list_archive

        search_archive = urllib.quote(search_archive, safe="~")

        # conflict reviews
        conflict_reviews = [d.name for d in doc.related_that("conflrev")]

        # remaining actions
        actions = []

        if ((not doc.stream_id or doc.stream_id in ("ietf", "irtf")) and group.type_id == "individ" and
            (Role.objects.filter(person__user=request.user, name__in=("chair", "delegate"), group__type__in=("wg",), group__state="active")
             or has_role(request.user, "Secretariat"))):
            actions.append(("Adopt in Group", urlreverse('edit_adopt', kwargs=dict(name=doc.name))))

        if doc.get_state_slug() == "expired" and not resurrected_by and can_edit:
            actions.append(("Request Resurrect", urlreverse('doc_request_resurrect', kwargs=dict(name=doc.name))))

        if doc.get_state_slug() == "expired" and has_role(request.user, ("Secretariat",)):
            actions.append(("Resurrect", urlreverse('doc_resurrect', kwargs=dict(name=doc.name))))

        if doc.get_state_slug() != "expired" and doc.stream_id in ("ise", "irtf") and has_role(request.user, ("Secretariat",)) and not conflict_reviews:
            label = "Begin IETF Conflict Review"
            if not doc.intended_std_level:
                label += " (note that intended status is not set)"
            actions.append((label, urlreverse('conflict_review_start', kwargs=dict(name=doc.name))))

        if doc.get_state_slug() != "expired" and doc.stream_id in ("ietf",) and can_edit and not iesg_state:
            actions.append(("Begin IESG Processing", urlreverse('doc_edit_info', kwargs=dict(name=doc.name)) + "?new=1"))

        return render_to_response("idrfc/document_draft.html",
                                  dict(doc=doc,
                                       group=group,
                                       top=top,
                                       name=name,
                                       content=content,
                                       split_content=split_content,
                                       revisions=revisions,
                                       snapshot=snapshot,
                                       latest_revision=latest_revision,

                                       can_edit=can_edit,
                                       can_change_stream=can_change_stream,
                                       can_edit_stream_info=can_edit_stream_info,
                                       can_edit_shepherd_writeup=can_edit_shepherd_writeup,
                                       can_edit_intended_std_level=can_edit_intended_std_level(request.user, doc),
                                       can_edit_consensus=can_edit_consensus(request.user, doc),
                                       can_edit_iana_state=can_edit_iana_state,

                                       rfc_number=rfc_number,
                                       draft_name=draft_name,
                                       telechat=telechat,
                                       ballot_summary=ballot_summary,
                                       submission=submission,
                                       resurrected_by=resurrected_by,

                                       replaces=[d.name for d in doc.related_that_doc("replaces")],
                                       replaced_by=[d.name for d in doc.related_that("replaces")],
                                       updates=[prettify_std_name(d.name) for d in doc.related_that_doc("updates")],
                                       updated_by=[prettify_std_name(d.canonical_name()) for d in doc.related_that("updates")],
                                       obsoletes=[prettify_std_name(d.name) for d in doc.related_that_doc("obs")],
                                       obsoleted_by=[prettify_std_name(d.canonical_name()) for d in doc.related_that("obs")],
                                       conflict_reviews=conflict_reviews,
                                       rfc_aliases=rfc_aliases,
                                       has_errata=doc.tags.filter(slug="errata"),
                                       published=doc.latest_event(type="published_rfc"),
                                       file_urls=file_urls,
                                       stream_state=stream_state,
                                       stream_tags=stream_tags,
                                       milestones=doc.groupmilestone_set.filter(state="active"),
                                       consensus=consensus,
                                       iesg_state=iesg_state,
                                       rfc_editor_state=doc.get_state("draft-rfceditor"),
                                       iana_review_state=doc.get_state("draft-iana-review"),
                                       iana_action_state=doc.get_state("draft-iana-action"),
                                       shepherd_writeup=shepherd_writeup,
                                       search_archive=search_archive,
                                       actions=actions,
                                       ),
                                  context_instance=RequestContext(request))

    if doc.type_id == "charter":
        filename = "%s-%s.txt" % (doc.canonical_name(), doc.rev)

        content = get_document_content(filename, os.path.join(settings.CHARTER_PATH, filename), split=False, markup=True)

        ballot_summary = None
        if doc.get_state_slug() in ("intrev", "iesgrev"):
            active_ballot = doc.active_ballot()
            if active_ballot:
                ballot_summary = needed_ballot_positions(doc, active_ballot.active_ad_positions().values())
            else:
                ballot_summary = "No active ballot found."

        chartering = get_chartering_type(doc)

        # inject milestones from group
        milestones = None
        if chartering and not snapshot:
            milestones = doc.group.groupmilestone_set.filter(state="charter")

        return render_to_response("idrfc/document_charter.html",
                                  dict(doc=doc,
                                       top=top,
                                       chartering=chartering,
                                       content=content,
                                       txt_url=settings.CHARTER_TXT_URL + filename,
                                       revisions=revisions,
                                       snapshot=snapshot,
                                       telechat=telechat,
                                       ballot_summary=ballot_summary,
                                       group=group,
                                       milestones=milestones,
                                       ),
                                  context_instance=RequestContext(request))

    if doc.type_id == "conflrev":
        filename = "%s-%s.txt" % (doc.canonical_name(), doc.rev)
        pathname = os.path.join(settings.CONFLICT_REVIEW_PATH,filename)

        if doc.rev == "00" and not os.path.isfile(pathname):
            # This could move to a template
            content = "A conflict review response has not yet been proposed."
        else:     
            content = get_document_content(filename, pathname, split=False, markup=True)

        ballot_summary = None
        if doc.get_state_slug() in ("iesgeval"):
            ballot_summary = needed_ballot_positions(doc, doc.active_ballot().active_ad_positions().values())

        return render_to_response("idrfc/document_conflict_review.html",
                                  dict(doc=doc,
                                       top=top,
                                       content=content,
                                       revisions=revisions,
                                       snapshot=snapshot,
                                       telechat=telechat,
                                       conflictdoc=conflictdoc,
                                       ballot_summary=ballot_summary,
                                       approved_states=('appr-reqnopub-pend','appr-reqnopub-sent','appr-noprob-pend','appr-noprob-sent')
                                       ),
                                  context_instance=RequestContext(request))

    raise Http404


def document_history(request, name):
    doc = get_object_or_404(Document, docalias__name=name)
    top = render_document_top(request, doc, "history", name)

    # pick up revisions from events
    diff_revisions = []

    diffable = name.startswith("draft") or name.startswith("charter") or name.startswith("conflict-review")
    if diffable:
        diff_documents = [ doc ]
        diff_documents.extend(Document.objects.filter(docalias__relateddocument__source=doc, docalias__relateddocument__relationship="replaces"))

        seen = set()
        for e in NewRevisionDocEvent.objects.filter(type="new_revision", doc__in=diff_documents).select_related('doc').order_by("-time", "-id"):
            if (e.doc.name, e.rev) in seen:
                continue

            seen.add((e.doc.name, e.rev))

            url = ""
            if name.startswith("charter"):
                url = request.build_absolute_uri(urlreverse("charter_with_milestones_txt", kwargs=dict(name=e.doc.name, rev=e.rev)))
            elif name.startswith("conflict-review"):
                h = find_history_active_at(e.doc, e.time)
                url = settings.CONFLICT_REVIEW_TXT_URL + ("%s-%s.txt" % ((h or doc).canonical_name(), e.rev))
            elif name.startswith("draft"):
                # rfcdiff tool has special support for IDs
                url = e.doc.name + "-" + e.rev

            diff_revisions.append((e.doc.name, e.rev, e.time, url))

    # grab event history
    events = doc.docevent_set.all().order_by("-time", "-id").select_related("by")

    augment_events_with_revision(doc, events)
    add_links_in_new_revision_events(doc, events, diff_revisions)

    return render_to_response("idrfc/document_history.html",
                              dict(doc=doc,
                                   top=top,
                                   diff_revisions=diff_revisions,
                                   events=events,
                                   ),
                              context_instance=RequestContext(request))

def document_writeup(request, name):
    doc = get_object_or_404(Document, docalias__name=name)
    top = render_document_top(request, doc, "writeup", name)

    def text_from_writeup(event_type):
        e = doc.latest_event(WriteupDocEvent, type=event_type)
        if e:
            return e.text
        else:
            return ""

    sections = []
    if doc.type_id == "draft":
        writeups = []
        sections.append(("Approval Announcement",
                         "<em>Draft</em> of message to be sent <em>after</em> approval:",
                         writeups))

        writeups.append(("Announcement",
                         text_from_writeup("changed_ballot_approval_text"),
                         urlreverse("doc_ballot_approvaltext", kwargs=dict(name=doc.name))))

        writeups.append(("Ballot Text",
                         text_from_writeup("changed_ballot_writeup_text"),
                         urlreverse("doc_ballot_writeupnotes", kwargs=dict(name=doc.name))))

    elif doc.type_id == "charter":
        sections.append(("WG Review Announcement",
                         "",
                         [("WG Review Announcement",
                           text_from_writeup("changed_review_announcement"),
                           urlreverse("ietf.wgcharter.views.announcement_text", kwargs=dict(name=doc.name, ann="review")))]
                         ))

        sections.append(("WG Action Announcement",
                         "",
                         [("WG Action Announcement",
                           text_from_writeup("changed_action_announcement"),
                           urlreverse("ietf.wgcharter.views.announcement_text", kwargs=dict(name=doc.name, ann="action")))]
                         ))

        if doc.latest_event(BallotDocEvent, type="created_ballot"):
            sections.append(("Ballot Announcement",
                             "",
                             [("Ballot Announcement",
                               text_from_writeup("changed_ballot_writeup_text"),
                               urlreverse("ietf.wgcharter.views.ballot_writeupnotes", kwargs=dict(name=doc.name)))]
                             ))

    if not sections:
        raise Http404()

    return render_to_response("idrfc/document_writeup.html",
                              dict(doc=doc,
                                   top=top,
                                   sections=sections,
                                   can_edit=has_role(request.user, ("Area Director", "Secretariat")),
                                   ),
                              context_instance=RequestContext(request))

def document_ballot_content(request, doc, ballot_id, editable=True):
    """Render HTML string with content of ballot page."""
    all_ballots = list(BallotDocEvent.objects.filter(doc=doc, type="created_ballot").order_by("time"))
    augment_events_with_revision(doc, all_ballots)

    ballot = None
    if ballot_id != None:
        ballot_id = int(ballot_id)
        for b in all_ballots:
            if b.id == ballot_id:
                ballot = b
                break
    elif all_ballots:
        ballot = all_ballots[-1]

    if not ballot:
        raise Http404

    deferred = doc.active_defer_event()

    positions = ballot.all_positions()

    # put into position groups
    position_groups = []
    for n in BallotPositionName.objects.filter(slug__in=[p.pos_id for p in positions]).order_by('order'):
        g = (n, [p for p in positions if p.pos_id == n.slug])
        g[1].sort(key=lambda p: (p.old_ad, p.ad.plain_name()))
        if n.blocking:
            position_groups.insert(0, g)
        else:
            position_groups.append(g)

    summary = needed_ballot_positions(doc, [p for p in positions if not p.old_ad])

    text_positions = [p for p in positions if p.discuss or p.comment]
    text_positions.sort(key=lambda p: (p.old_ad, p.ad.plain_name()))

    ballot_open = not BallotDocEvent.objects.filter(doc=doc,
                                                    type__in=("closed_ballot", "created_ballot"),
                                                    time__gt=ballot.time,
                                                    ballot_type=ballot.ballot_type)
    if not ballot_open:
        editable = False

    return render_to_string("idrfc/document_ballot_content.html",
                              dict(doc=doc,
                                   ballot=ballot,
                                   position_groups=position_groups,
                                   text_positions=text_positions,
                                   editable=editable,
                                   ballot_open=ballot_open,
                                   deferred=deferred,
                                   summary=summary,
                                   all_ballots=all_ballots,
                                   ),
                              context_instance=RequestContext(request))

def document_ballot(request, name, ballot_id=None):
    doc = get_object_or_404(Document, docalias__name=name)
    top = render_document_top(request, doc, "ballot", name)

    c = document_ballot_content(request, doc, ballot_id, editable=True)

    return render_to_response("idrfc/document_ballot.html",
                              dict(doc=doc,
                                   top=top,
                                   ballot_content=c,
                                   ),
                              context_instance=RequestContext(request))

def document_json(request, name):
    doc = get_object_or_404(Document, docalias__name=name)

    def extract_name(s):
        return s.name if s else None

    data = {}

    data["name"] = doc.name
    data["rev"] = doc.rev
    data["time"] = doc.time.strftime("%Y-%m-%d %H:%M:%S")
    data["group"] = None
    if doc.group:
        data["group"] = dict(
            name=doc.group.name,
            type=extract_name(doc.group.type),
            acronym=doc.group.acronym)
    data["expires"] = doc.expires.strftime("%Y-%m-%d %H:%M:%S") if doc.expires else None
    data["title"] = doc.title
    data["abstract"] = doc.abstract
    data["aliases"] = list(doc.docalias_set.values_list("name", flat=True))
    data["state"] = extract_name(doc.get_state())
    data["intended_std_level"] = extract_name(doc.intended_std_level)
    data["std_level"] = extract_name(doc.std_level)
    data["authors"] = [
        dict(name=e.person.name,
             email=e.address,
             affiliation=e.person.affiliation)
        for e in Email.objects.filter(documentauthor__document=doc).select_related("person").order_by("documentauthor__order")
        ]
    data["shepherd"] = doc.shepherd.formatted_email() if doc.shepherd else None
    data["ad"] = doc.ad.role_email("ad").formatted_email() if doc.ad else None

    if doc.type_id == "draft":
        data["iesg_state"] = extract_name(doc.get_state("draft-iesg"))
        data["rfceditor_state"] = extract_name(doc.get_state("draft-rfceditor"))
        data["iana_review_state"] = extract_name(doc.get_state("draft-iana-review"))
        data["iana_action_state"] = extract_name(doc.get_state("draft-iana-action"))

        if doc.stream_id in ("ietf", "irtf", "iab"):
            e = doc.latest_event(ConsensusDocEvent, type="changed_consensus")
            data["consensus"] = e.consensus if e else None
        data["stream"] = extract_name(doc.stream)

    return HttpResponse(json.dumps(data, indent=2), mimetype='text/plain')

def _get_html(key, filename, split=True):
    # FIXME
    return get_document_content(key, filename, split=split, markup=True), ""

def include_text(request):
    # FIXME
    include_text = request.GET.get( 'include_text' )
    if "full_draft" in request.COOKIES:
        if request.COOKIES["full_draft"] == "on":
            include_text = 1
    return include_text

def document_main_rfc(request, rfc_number, tab):
    # FIXME
    rfci = get_object_or_404(RfcIndex, rfc_number=rfc_number, states__type="draft", states__slug="rfc")
    rfci.viewing_as_rfc = True
    doc = RfcWrapper(rfci)

    info = {}
    info['is_rfc'] = True
    info['has_pdf'] = (".pdf" in doc.file_types())
    info['has_txt'] = (".txt" in doc.file_types())
    info['has_ps'] = (".ps" in doc.file_types())
    if info['has_txt']:
        (content1, content2) = _get_html(
            "rfc"+str(rfc_number)+",html", 
            os.path.join(settings.RFC_PATH, "rfc"+str(rfc_number)+".txt"))
    else:
        content1 = ""
        content2 = ""

    history = _get_history(doc, None)
            
    template = "idrfc/doc_tab_%s" % tab
    if tab == "document":
	template += "_rfc"
    return render_to_response(template + ".html",
                              {'content1':content1, 'content2':content2,
                               'doc':doc, 'info':info, 'tab':tab,
			       'include_text':include_text(request),
                               'history':history},
                              context_instance=RequestContext(request));

@decorator_from_middleware(GZipMiddleware)
def document_main_idrfc(request, name, tab):
    # FIXME
    r = re.compile("^rfc([1-9][0-9]*)$")
    m = r.match(name)
    if m:
        return document_main_rfc(request, int(m.group(1)), tab)
    id = get_object_or_404(InternetDraft, filename=name)
    doc = IdWrapper(id) 

    info = {}
    info['has_pdf'] = (".pdf" in doc.file_types())
    info['is_rfc'] = False

    info['conflict_reviews'] = [ rel.source for alias in id.docalias_set.all() for rel in alias.relateddocument_set.filter(relationship='conflrev') ]
    info['rfc_editor_state'] = id.get_state("draft-rfceditor")
    info['iana_review_state'] = id.get_state("draft-iana-review")
    info['iana_action_state'] = id.get_state("draft-iana-action")
    info["consensus"] = None
    if id.stream_id in ("ietf", "irtf", "iab"):
        e = id.latest_event(ConsensusDocEvent, type="changed_consensus")
        info["consensus"] = nice_consensus(e and e.consensus)
        info["can_edit_consensus"] = can_edit_consensus(request.user, id)
    info["can_edit_intended_std_level"] = can_edit_intended_std_level(request.user, id)

    (content1, content2) = _get_html(
        str(name)+","+str(id.revision)+",html",
        os.path.join(settings.INTERNET_DRAFT_PATH, name+"-"+id.revision+".txt"))

    versions = _get_versions(id)
    history = _get_history(doc, versions)
            
    template = "idrfc/doc_tab_%s" % tab
    if tab == "document":
	template += "_id"
    return render_to_response(template + ".html",
                              {'content1':content1, 'content2':content2,
                               'doc':doc, 'info':info, 'tab':tab,
			       'include_text':include_text(request),
                               'stream_info': get_full_info_for_draft(id),
                               'milestones': id.groupmilestone_set.filter(state="active"),
                               'versions':versions, 'history':history},
                              context_instance=RequestContext(request));

# doc is either IdWrapper or RfcWrapper
def _get_history(doc, versions):
    results = []
    if settings.USE_DB_REDESIGN_PROXY_CLASSES:
        versions = [] # clear versions
        event_holder = doc._draft if hasattr(doc, "_draft") else doc._rfcindex
        for e in event_holder.docevent_set.all().select_related('by').order_by('-time', 'id'):
            info = {}
            if e.type == "new_revision":
                filename = u"%s-%s" % (e.doc.name, e.newrevisiondocevent.rev)
                e.desc = 'New version available: <a href="http://tools.ietf.org/id/%s.txt">%s</a>' % (filename, filename)
                if int(e.newrevisiondocevent.rev) != 0:
                    e.desc += ' (<a href="http:%s?url2=%s">diff from -%02d</a>)' % (settings.RFCDIFF_PREFIX, filename, int(e.newrevisiondocevent.rev) - 1)
                info["dontmolest"] = True

            multiset_ballot_text = "This was part of a ballot set with: "
            if e.desc.startswith(multiset_ballot_text):
                names = [ n.strip() for n in e.desc[len(multiset_ballot_text):].split(",") ]
                e.desc = multiset_ballot_text + ", ".join(u'<a href="%s">%s</a>' % (urlreverse("doc_view", kwargs={'name': n }), n) for n in names)
                info["dontmolest"] = True
                    
            info['text'] = e.desc
            info['by'] = e.by.plain_name()
            info['textSnippet'] = truncatewords_html(format_textarea(fill(info['text'], 80)), 25)
            info['snipped'] = info['textSnippet'][-3:] == "..." and e.type != "new_revision"
            results.append({'comment':e, 'info':info, 'date':e.time, 'is_com':True})

        prev_rev = "00"
        # actually, we're already sorted and this ruins the sort from
        # the ids which is sometimes needed, so the function should be
        # rewritten to not rely on a resort
        results.sort(key=lambda x: x['date'])
        for o in results:
            e = o["comment"]
            if e.type == "new_revision":
                e.version = e.newrevisiondocevent.rev
            else:
                e.version = prev_rev
            prev_rev = e.version
    else:
        if doc.is_id_wrapper:
            comments = DocumentComment.objects.filter(document=doc.tracker_id).exclude(rfc_flag=1)
        else:
            comments = DocumentComment.objects.filter(document=doc.rfc_number,rfc_flag=1)
            if len(comments) > 0:
                # also include rfc_flag=NULL, but only if at least one
                # comment with rfc_flag=1 exists (usually NULL means same as 0)
                comments = DocumentComment.objects.filter(document=doc.rfc_number).exclude(rfc_flag=0)
        for comment in comments.order_by('-date','-time','-id').filter(public_flag=1).select_related('created_by'):
            info = {}
            info['text'] = comment.comment_text
            info['by'] = comment.get_fullname()
            info['textSnippet'] = truncatewords_html(format_textarea(fill(info['text'], 80)), 25)
            info['snipped'] = info['textSnippet'][-3:] == "..."
            results.append({'comment':comment, 'info':info, 'date':comment.datetime(), 'is_com':True})
    
    if doc.is_id_wrapper and versions:
        for v in versions:
            if v['draft_name'] == doc.draft_name:
                v = dict(v) # copy it, since we're modifying datetimes later
                v['is_rev'] = True
                results.insert(0, v)    
    if not settings.USE_DB_REDESIGN_PROXY_CLASSES and doc.is_id_wrapper and doc.draft_status == "Expired" and doc._draft.expiration_date:
        results.append({'is_text':True, 'date':doc._draft.expiration_date, 'text':'Draft expired'})
    if not settings.USE_DB_REDESIGN_PROXY_CLASSES and doc.is_rfc_wrapper:
        text = 'RFC Published'
        if doc.draft_name:
            try:
                text = 'RFC Published (see <a href="%s">%s</a> for earlier history)' % (urlreverse('doc_view', args=[doc.draft_name]),doc.draft_name)
            except NoReverseMatch:
                pass
        results.append({'is_text':True, 'date':doc.publication_date, 'text':text})

    # convert plain dates to datetimes (required for sorting)
    for x in results:
        if not isinstance(x['date'], datetime.datetime):
            if x['date']:
                x['date'] = datetime.datetime.combine(x['date'], datetime.time(0,0,0))
            else:
                x['date'] = datetime.datetime(1970,1,1)

    results.sort(key=lambda x: x['date'])
    results.reverse()
    return results

# takes InternetDraft instance
def _get_versions(draft, include_replaced=True):
    ov = []
    ov.append({"draft_name":draft.filename, "revision":draft.revision_display(), "date":draft.revision_date})
    if include_replaced:
        draft_list = [draft]+list(draft.replaces_set.all())
    else:
        draft_list = [draft]

    if settings.USE_DB_REDESIGN_PROXY_CLASSES:
        from ietf.doc.models import NewRevisionDocEvent
        for e in NewRevisionDocEvent.objects.filter(type="new_revision", doc__in=draft_list).select_related('doc').order_by("-time", "-id"):
            if not (e.doc.name == draft.name and e.rev == draft.rev):
                ov.append(dict(draft_name=e.doc.name, revision=e.rev, date=e.time.date()))
                
        return ov
        
    for d in draft_list:
        for v in DraftVersions.objects.filter(filename=d.filename).order_by('-revision'):
            if (d.filename == draft.filename) and (draft.revision_display() == v.revision):
                continue
            ov.append({"draft_name":d.filename, "revision":v.revision, "date":v.revision_date})
    return ov

def get_ballot(name):
    from ietf.doc.models import DocAlias
    alias = get_object_or_404(DocAlias, name=name)
    d = alias.document
    id = None
    bw = None
    dw = None
    if (d.type_id=='draft'):
        id = get_object_or_404(InternetDraft, name=d.name)
        try:
            if not id.ballot.ballot_issued:
                raise Http404
        except BallotInfo.DoesNotExist:
            raise Http404

        bw = BallotWrapper(id)               # XXX Fixme: Eliminate this as we go forward
        # Python caches ~100 regex'es -- explicitly compiling it inside a method
        # (where you then throw away the compiled version!) doesn't make sense at
        # all.
        if re.search("^rfc([1-9][0-9]*)$", name):
            id.viewing_as_rfc = True
            dw = RfcWrapper(id)
        else:
            dw = IdWrapper(id)
        # XXX Fixme: Eliminate 'dw' as we go forward

    try:
        b = d.latest_event(BallotDocEvent, type="created_ballot")
    except BallotDocEvent.DoesNotExist:
        raise Http404

    return (bw, dw, b, d)


def ballot_for_popup(request, name):
    doc = get_object_or_404(Document, docalias__name=name)
    return HttpResponse(document_ballot_content(request, doc, ballot_id=None, editable=False))

def ballot_html(request, name):
    bw, dw, ballot, doc = get_ballot(name)
    content = document_ballot_content(request, doc, ballot.pk, editable=True)
    return HttpResponse(content)

def ballot_tsv(request, name):
    ballot, doc, b, d = get_ballot(name)
    return HttpResponse(render_to_string('idrfc/ballot.tsv', {'ballot':ballot}, RequestContext(request)), content_type="text/plain")

def ballot_json(request, name):
    ballot, doc, b, d = get_ballot(name)
    response = HttpResponse(mimetype='text/plain')
    response.write(json.dumps(ballot.dict(), indent=2))
    return response

