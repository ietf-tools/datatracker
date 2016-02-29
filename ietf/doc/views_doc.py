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

import os, datetime, urllib, json, glob, re

from django.http import HttpResponse, Http404 , HttpResponseForbidden
from django.shortcuts import render, render_to_response, get_object_or_404, redirect
from django.template import RequestContext
from django.template.loader import render_to_string
from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse as urlreverse
from django.conf import settings
from django import forms

import debug                            # pyflakes:ignore

from ietf.doc.models import ( Document, DocAlias, DocHistory, DocEvent, BallotDocEvent,
    ConsensusDocEvent, NewRevisionDocEvent, TelechatDocEvent, WriteupDocEvent,
    IESG_BALLOT_ACTIVE_STATES, STATUSCHANGE_RELATIONS )
from ietf.doc.utils import ( add_links_in_new_revision_events, augment_events_with_revision,
    can_adopt_draft, get_chartering_type, get_document_content, get_tags_for_stream_id,
    needed_ballot_positions, nice_consensus, prettify_std_name, update_telechat, has_same_ballot,
    get_initial_notify, make_notify_changed_event, crawl_history)
from ietf.community.models import CommunityList
from ietf.group.models import Role
from ietf.group.utils import can_manage_group_type, can_manage_materials
from ietf.ietfauth.utils import has_role, is_authorized_in_doc_stream, user_is_person, role_required
from ietf.name.models import StreamName, BallotPositionName
from ietf.person.models import Email
from ietf.utils.history import find_history_active_at
from ietf.doc.forms import TelechatForm, NotifyForm
from ietf.doc.mails import email_comment 
from ietf.mailtrigger.utils import gather_relevant_expansions
from ietf.meeting.models import Session
from ietf.meeting.utils import group_sessions, get_upcoming_manageable_sessions, sort_sessions

def render_document_top(request, doc, tab, name):
    tabs = []
    tabs.append(("Document", "document", urlreverse("doc_view", kwargs=dict(name=name)), True))

    ballot = doc.latest_event(BallotDocEvent, type="created_ballot")
    if doc.type_id in ("draft","conflrev", "statchg"):
        tabs.append(("IESG Evaluation Record", "ballot", urlreverse("doc_ballot", kwargs=dict(name=name)), ballot,  None if ballot else "IESG Evaluation Ballot has not been created yet"))
    elif doc.type_id == "charter" and doc.group.type_id == "wg":
        tabs.append(("IESG Review", "ballot", urlreverse("doc_ballot", kwargs=dict(name=name)), ballot, None if ballot else "IESG Review Ballot has not been created yet"))

    if doc.type_id == "draft" or (doc.type_id == "charter" and doc.group.type_id == "wg"):
        tabs.append(("IESG Writeups", "writeup", urlreverse("doc_writeup", kwargs=dict(name=name)), True))

    tabs.append(("Email expansions","email",urlreverse("doc_email", kwargs=dict(name=name)), True))
    tabs.append(("History", "history", urlreverse("doc_history", kwargs=dict(name=name)), True))

    if name.startswith("rfc"):
        name = "RFC %s" % name[3:]
    else:
        name += "-" + doc.rev

    return render_to_string("doc/document_top.html",
                            dict(doc=doc,
                                 tabs=tabs,
                                 selected=tab,
                                 name=name))


def document_main(request, name, rev=None):
    doc = get_object_or_404(Document.objects.select_related(), docalias__name=name)

    # take care of possible redirections
    aliases = DocAlias.objects.filter(document=doc).values_list("name", flat=True)
    if rev==None and doc.type_id == "draft" and not name.startswith("rfc"):
        for a in aliases:
            if a.startswith("rfc"):
                return redirect("doc_view", name=a)

    if doc.type_id == 'conflrev':
        conflictdoc = doc.related_that_doc('conflrev')[0].document
    
    revisions = []
    for h in doc.history_set.order_by("time", "id"):
        if h.rev and not h.rev in revisions:
            revisions.append(h.rev)
    if not doc.rev in revisions:
        revisions.append(doc.rev)
    latest_rev = doc.rev

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

    # set this after we've found the right doc instance
    group = doc.group

    top = render_document_top(request, doc, "document", name)


    telechat = doc.latest_event(TelechatDocEvent, type="scheduled_for_telechat")
    if telechat and (not telechat.telechat_date or telechat.telechat_date < datetime.date.today()):
       telechat = None


    # specific document types
    if doc.type_id == "draft":
        split_content = not ( request.GET.get('include_text') or request.COOKIES.get("full_draft", settings.USER_PREFERENCE_DEFAULTS["full_draft"]) == "on" )

        iesg_state = doc.get_state("draft-iesg")
        iesg_state_summary = doc.friendly_state()
        can_edit = has_role(request.user, ("Area Director", "Secretariat"))
        stream_slugs = StreamName.objects.values_list("slug", flat=True)
        can_change_stream = bool(can_edit or (
                request.user.is_authenticated() and
                Role.objects.filter(name__in=("chair", "secr", "auth", "delegate"),
                                    group__acronym__in=stream_slugs,
                                    person__user=request.user)))
        can_edit_iana_state = has_role(request.user, ("Secretariat", "IANA"))

        can_edit_replaces = has_role(request.user, ("Area Director", "Secretariat", "IRTF Chair", "WG Chair", "RG Chair", "WG Secretary", "RG Secretary"))

        is_author = unicode(request.user) in set([email.address for email in doc.authors.all()])
        can_view_possibly_replaces = can_edit_replaces or is_author

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

            base = "https://www.rfc-editor.org/rfc/"

            file_urls = []
            for t in found_types:
                label = "plain text" if t == "txt" else t
                file_urls.append((label, base + name + "." + t))

            if "pdf" not in found_types and "txt" in found_types:
                file_urls.append(("pdf", base + "pdfrfc/" + name + ".txt.pdf"))

            if "txt" in found_types:
                file_urls.append(("html", settings.TOOLS_ID_HTML_URL + name))

            if not found_types:
                content = "This RFC is not currently available online."
                split_content = False
            elif "txt" not in found_types:
                content = "This RFC is not available in plain text format."
                split_content = False
        else:
            filename = "%s-%s.txt" % (draft_name, doc.rev)

            content = get_document_content(filename, os.path.join(settings.INTERNET_ALL_DRAFTS_ARCHIVE_DIR, filename),
                                           split_content, markup=True)

            # file types
            base_path = os.path.join(settings.INTERNET_DRAFT_PATH, doc.name + "-" + doc.rev + ".")
            possible_types = ["pdf", "xml", "ps"]
            found_types = ["txt"] + [t for t in possible_types if os.path.exists(base_path + t)]

            if not snapshot and doc.get_state_slug() == "active":
                base = settings.IETF_ID_URL
            else:
                base = settings.IETF_ID_ARCHIVE_URL

            file_urls = []
            for t in found_types:
                label = "plain text" if t == "txt" else t
                file_urls.append((label, base + doc.name + "-" + doc.rev + "." + t))

            if "pdf" not in found_types:
                file_urls.append(("pdf", settings.TOOLS_ID_PDF_URL + doc.name + "-" + doc.rev + ".pdf"))
            file_urls.append(("html", settings.TOOLS_ID_HTML_URL + doc.name + "-" + doc.rev))

            # latest revision
            latest_revision = doc.latest_event(NewRevisionDocEvent, type="new_revision")

        # bibtex
        file_urls.append(("bibtex", "bibtex"))

        # ballot
        ballot_summary = None
        if iesg_state and iesg_state.slug in IESG_BALLOT_ACTIVE_STATES:
            active_ballot = doc.active_ballot()
            if active_ballot:
                ballot_summary = needed_ballot_positions(doc, active_ballot.active_ad_positions().values())

        # submission
        submission = ""
        if group is None:
            submission = "unknown"
        elif group.type_id == "individ":
            submission = "individual"
        elif group.type_id == "area" and doc.stream_id == "ietf":
            submission = "individual in %s area" % group.acronym
        elif group.type_id in ("rg", "wg"):
            submission = "%s %s" % (group.acronym, group.type)
            if group.type_id == "wg":
                submission = "<a href=\"%s\">%s</a>" % (urlreverse("group_home", kwargs=dict(group_type=group.type_id, acronym=group.acronym)), submission)
            if doc.stream_id and doc.get_state_slug("draft-stream-%s" % doc.stream_id) == "c-adopt":
                submission = "candidate for %s" % submission

        # resurrection
        resurrected_by = None
        if doc.get_state_slug() == "expired":
            e = doc.latest_event(type__in=("requested_resurrect", "completed_resurrect"))
            if e and e.type == "requested_resurrect":
                resurrected_by = e.by

        # stream info
        stream_state_type_slug = None
        stream_state = None
        if doc.stream:
            stream_state_type_slug = "draft-stream-%s" % doc.stream_id
            stream_state = doc.get_state(stream_state_type_slug)
        stream_tags = doc.tags.filter(slug__in=get_tags_for_stream_id(doc.stream_id))

        shepherd_writeup = doc.latest_event(WriteupDocEvent, type="changed_protocol_writeup")

        can_edit_stream_info = is_authorized_in_doc_stream(request.user, doc)
        can_edit_shepherd_writeup = can_edit_stream_info or user_is_person(request.user, doc.shepherd and doc.shepherd.person) or has_role(request.user, ["Area Director"])
        can_edit_notify = can_edit_shepherd_writeup
        can_edit_consensus = False

        consensus = None
        if doc.stream_id == "ietf" and iesg_state:
            show_in_states = set(IESG_BALLOT_ACTIVE_STATES)
            show_in_states.update(('approved','ann','rfcqueue','pub'))
            if iesg_state.slug in show_in_states: 
                can_edit_consensus = can_edit
                e = doc.latest_event(ConsensusDocEvent, type="changed_consensus")
                consensus = nice_consensus(e and e.consensus)
        elif doc.stream_id in ("irtf", "iab"):
            can_edit_consensus = can_edit or can_edit_stream_info
            e = doc.latest_event(ConsensusDocEvent, type="changed_consensus")
            consensus = nice_consensus(e and e.consensus)

        # mailing list search archive
        search_archive = "www.ietf.org/mail-archive/web/"
        if doc.stream_id == "ietf" and group.type_id == "wg" and group.list_archive:
            search_archive = group.list_archive

        search_archive = urllib.quote(search_archive, safe="~")

        # conflict reviews
        conflict_reviews = [d.document.name for d in doc.related_that("conflrev")]

        status_change_docs = doc.related_that(STATUSCHANGE_RELATIONS)
        status_changes = [ rel.document for rel in status_change_docs  if rel.document.get_state_slug() in ('appr-sent','appr-pend')]
        proposed_status_changes = [ rel.document for rel in status_change_docs  if rel.document.get_state_slug() in ('needshep','adrev','iesgeval','defer','appr-pr')]

        presentations = doc.future_presentations()

        # remaining actions
        actions = []

        if can_adopt_draft(request.user, doc) and not doc.get_state_slug() in ["rfc"]:
            actions.append(("Manage Document Adoption in Group", urlreverse('doc_adopt_draft', kwargs=dict(name=doc.name))))

        if doc.get_state_slug() == "expired" and not resurrected_by and can_edit:
            actions.append(("Request Resurrect", urlreverse('doc_request_resurrect', kwargs=dict(name=doc.name))))

        if doc.get_state_slug() == "expired" and has_role(request.user, ("Secretariat",)):
            actions.append(("Resurrect", urlreverse('doc_resurrect', kwargs=dict(name=doc.name))))

        if (doc.get_state_slug() not in ["rfc", "expired"] and doc.stream_id in ("ise", "irtf")
            and can_edit_stream_info and not conflict_reviews):
            label = "Begin IETF Conflict Review"
            if not doc.intended_std_level:
                label += " (note that intended status is not set)"
            actions.append((label, urlreverse('conflict_review_start', kwargs=dict(name=doc.name))))

        if (doc.get_state_slug() not in ["rfc", "expired"] and doc.stream_id in ("iab", "ise", "irtf")
            and can_edit_stream_info):
            label = "Request Publication"
            if not doc.intended_std_level:
                label += " (note that intended status is not set)"
            if iesg_state and iesg_state.slug != 'dead':
                label += " (Warning: the IESG state indicates ongoing IESG processing)"
            actions.append((label, urlreverse('doc_request_publication', kwargs=dict(name=doc.name))))

        if doc.get_state_slug() not in ["rfc", "expired"] and doc.stream_id in ("ietf",):
            if not iesg_state and can_edit:
                actions.append(("Begin IESG Processing", urlreverse('doc_edit_info', kwargs=dict(name=doc.name)) + "?new=1"))
            elif can_edit_stream_info and (not iesg_state or iesg_state.slug == 'watching'):
                actions.append(("Submit to IESG for Publication", urlreverse('doc_to_iesg', kwargs=dict(name=doc.name))))

        tracking_document = False
        if request.user.is_authenticated():
            try:
                clist = CommunityList.objects.get(user=request.user)
                clist.update()
                if clist.get_documents().filter(name=doc.name).count() > 0:
                    tracking_document = True
            except ObjectDoesNotExist:
                pass

        replaces = [d.name for d in doc.related_that_doc("replaces")]
        replaced_by = [d.name for d in doc.related_that("replaces")]
        possibly_replaces = [d.name for d in doc.related_that_doc("possibly-replaces")]
        possibly_replaced_by = [d.name for d in doc.related_that("possibly-replaces")]
        published = doc.latest_event(type="published_rfc")
        started_iesg_process = doc.latest_event(type="started_iesg_process")

        return render_to_response("doc/document_draft.html",
                                  dict(doc=doc,
                                       group=group,
                                       top=top,
                                       name=name,
                                       content=content,
                                       split_content=split_content,
                                       revisions=revisions,
                                       snapshot=snapshot,
                                       latest_revision=latest_revision,
                                       latest_rev=latest_rev,
                                       can_edit=can_edit,
                                       can_change_stream=can_change_stream,
                                       can_edit_stream_info=can_edit_stream_info,
                                       is_shepherd = user_is_person(request.user, doc.shepherd and doc.shepherd.person),
                                       can_edit_shepherd_writeup=can_edit_shepherd_writeup,
                                       can_edit_notify=can_edit_notify,
                                       can_edit_iana_state=can_edit_iana_state,
                                       can_edit_consensus=can_edit_consensus,
                                       can_edit_replaces=can_edit_replaces,
                                       can_view_possibly_replaces=can_view_possibly_replaces,

                                       rfc_number=rfc_number,
                                       draft_name=draft_name,
                                       telechat=telechat,
                                       ballot_summary=ballot_summary,
                                       submission=submission,
                                       resurrected_by=resurrected_by,

                                       replaces=replaces,
                                       replaced_by=replaced_by,
                                       possibly_replaces=possibly_replaces,
                                       possibly_replaced_by=possibly_replaced_by,
                                       updates=[prettify_std_name(d.name) for d in doc.related_that_doc("updates")],
                                       updated_by=[prettify_std_name(d.document.canonical_name()) for d in doc.related_that("updates")],
                                       obsoletes=[prettify_std_name(d.name) for d in doc.related_that_doc("obs")],
                                       obsoleted_by=[prettify_std_name(d.document.canonical_name()) for d in doc.related_that("obs")],
                                       conflict_reviews=conflict_reviews,
                                       status_changes=status_changes,
                                       proposed_status_changes=proposed_status_changes,
                                       rfc_aliases=rfc_aliases,
                                       has_errata=doc.tags.filter(slug="errata"),
                                       published=published,
                                       file_urls=file_urls,
                                       stream_state_type_slug=stream_state_type_slug,
                                       stream_state=stream_state,
                                       stream_tags=stream_tags,
                                       milestones=doc.groupmilestone_set.filter(state="active"),
                                       consensus=consensus,
                                       iesg_state=iesg_state,
                                       iesg_state_summary=iesg_state_summary,
                                       rfc_editor_state=doc.get_state("draft-rfceditor"),
                                       iana_review_state=doc.get_state("draft-iana-review"),
                                       iana_action_state=doc.get_state("draft-iana-action"),
                                       started_iesg_process=started_iesg_process,
                                       shepherd_writeup=shepherd_writeup,
                                       search_archive=search_archive,
                                       actions=actions,
                                       tracking_document=tracking_document,
                                       presentations=presentations,
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

        can_manage = can_manage_group_type(request.user, doc.group.type_id)

        return render_to_response("doc/document_charter.html",
                                  dict(doc=doc,
                                       top=top,
                                       chartering=chartering,
                                       content=content,
                                       txt_url=doc.href(),
                                       revisions=revisions,
                                       latest_rev=latest_rev,
                                       snapshot=snapshot,
                                       telechat=telechat,
                                       ballot_summary=ballot_summary,
                                       group=group,
                                       milestones=milestones,
                                       can_manage=can_manage,
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
        if doc.get_state_slug() in ("iesgeval") and doc.active_ballot():
            ballot_summary = needed_ballot_positions(doc, doc.active_ballot().active_ad_positions().values())

        return render_to_response("doc/document_conflict_review.html",
                                  dict(doc=doc,
                                       top=top,
                                       content=content,
                                       revisions=revisions,
                                       latest_rev=latest_rev,
                                       snapshot=snapshot,
                                       telechat=telechat,
                                       conflictdoc=conflictdoc,
                                       ballot_summary=ballot_summary,
                                       approved_states=('appr-reqnopub-pend','appr-reqnopub-sent','appr-noprob-pend','appr-noprob-sent'),
                                       ),
                                  context_instance=RequestContext(request))

    if doc.type_id == "statchg":
        filename = "%s-%s.txt" % (doc.canonical_name(), doc.rev)
        pathname = os.path.join(settings.STATUS_CHANGE_PATH,filename)

        if doc.rev == "00" and not os.path.isfile(pathname):
            # This could move to a template
            content = "Status change text has not yet been proposed."
        else:     
            content = get_document_content(filename, pathname, split=False)

        ballot_summary = None
        if doc.get_state_slug() in ("iesgeval"):
            ballot_summary = needed_ballot_positions(doc, doc.active_ballot().active_ad_positions().values())
     
        if isinstance(doc,Document):
            sorted_relations=doc.relateddocument_set.all().order_by('relationship__name')
        elif isinstance(doc,DocHistory):
            sorted_relations=doc.relateddochistory_set.all().order_by('relationship__name')
        else:
            sorted_relations=None

        return render_to_response("doc/document_status_change.html",
                                  dict(doc=doc,
                                       top=top,
                                       content=content,
                                       revisions=revisions,
                                       latest_rev=latest_rev,
                                       snapshot=snapshot,
                                       telechat=telechat,
                                       ballot_summary=ballot_summary,
                                       approved_states=('appr-pend','appr-sent'),
                                       sorted_relations=sorted_relations,
                                       ),
                                  context_instance=RequestContext(request))

    # TODO : Add "recording", and "bluesheets" here when those documents are appropriately
    #        created and content is made available on disk
    if doc.type_id in ("slides", "agenda", "minutes"):
        can_manage_material = can_manage_materials(request.user, doc.group)
        presentations = doc.future_presentations()
        if doc.meeting_related():
            basename = doc.canonical_name() # meeting materials are unversioned at the moment
            if doc.external_url:
                # we need to remove the extension for the globbing below to work
                basename = os.path.splitext(doc.external_url)[0]
        else:
            basename = "%s-%s" % (doc.canonical_name(), doc.rev)

        pathname = os.path.join(doc.get_file_path(), basename)

        content = None
        other_types = []
        globs = glob.glob(pathname + ".*")
        for g in globs:
            extension = os.path.splitext(g)[1]
            t = os.path.splitext(g)[1].lstrip(".")
            url = doc.href()
            if not url.endswith("/") and not url.endswith(extension):
                url += extension

            if extension == ".txt":
                content = get_document_content(basename, pathname + extension, split=False)
                t = "plain text"

            other_types.append((t, url))

        return render_to_response("doc/document_material.html",
                                  dict(doc=doc,
                                       top=top,
                                       content=content,
                                       revisions=revisions,
                                       latest_rev=latest_rev,
                                       snapshot=snapshot,
                                       can_manage_material=can_manage_material,
                                       in_group_materials_types = doc.group and doc.group.features.has_materials and doc.type_id in doc.group.features.material_types,
                                       other_types=other_types,
                                       presentations=presentations,
                                       ),
                                  context_instance=RequestContext(request))

    raise Http404


def check_doc_email_aliases():
    pattern = re.compile('^expand-(.*?)(\..*?)?@.*? +(.*)$')
    good_count = 0
    tot_count = 0
    with open(settings.DRAFT_VIRTUAL_PATH,"r") as virtual_file:
        for line in virtual_file.readlines():
            m = pattern.match(line)
            tot_count += 1
            if m:
                good_count += 1
            if good_count > 50 and tot_count < 3*good_count:
                return True
    return False

def get_doc_email_aliases(name):
    if name:
        pattern = re.compile('^expand-(%s)(\..*?)?@.*? +(.*)$'%name)
    else:
        pattern = re.compile('^expand-(.*?)(\..*?)?@.*? +(.*)$')
    aliases = []
    with open(settings.DRAFT_VIRTUAL_PATH,"r") as virtual_file:
        for line in virtual_file.readlines():
            m = pattern.match(line)
            if m:
                aliases.append({'doc_name':m.group(1),'alias_type':m.group(2),'expansion':m.group(3)})
    return aliases

def document_email(request,name):
    doc = get_object_or_404(Document, docalias__name=name)
    top = render_document_top(request, doc, "email", name)

    aliases = get_doc_email_aliases(name) if doc.type_id=='draft' else None

    expansions = gather_relevant_expansions(doc=doc)
    
    return render(request, "doc/document_email.html",
                            dict(doc=doc,
                                 top=top,
                                 aliases=aliases,
                                 expansions=expansions,
                                 ietf_domain=settings.IETF_DOMAIN,
                                )
                 )


def document_history(request, name):
    doc = get_object_or_404(Document, docalias__name=name)
    top = render_document_top(request, doc, "history", name)

    # pick up revisions from events
    diff_revisions = []

    diffable = [ name.startswith(prefix) for prefix in ["rfc", "draft", "charter", "conflict-review", "status-change", ]]
    if any(diffable):
        diff_documents = [ doc ]
        diff_documents.extend(Document.objects.filter(docalias__relateddocument__source=doc, docalias__relateddocument__relationship="replaces"))

        if doc.get_state_slug() == "rfc":
            e = doc.latest_event(type="published_rfc")
            aliases = doc.docalias_set.filter(name__startswith="rfc")
            if aliases:
                name = aliases[0].name
            diff_revisions.append((name, "", e.time if e else doc.time, name))

        seen = set()
        for e in NewRevisionDocEvent.objects.filter(type="new_revision", doc__in=diff_documents).select_related('doc').order_by("-time", "-id"):
            if (e.doc.name, e.rev) in seen:
                continue

            seen.add((e.doc.name, e.rev))

            url = ""
            if name.startswith("charter"):
                url = request.build_absolute_uri(urlreverse("charter_with_milestones_txt", kwargs=dict(name=e.doc.name, rev=e.rev)))
            elif name.startswith("conflict-review"):
                url = find_history_active_at(e.doc, e.time).href()
            elif name.startswith("status-change"):
                url = find_history_active_at(e.doc, e.time).href()
            elif name.startswith("draft") or name.startswith("rfc"):
                # rfcdiff tool has special support for IDs
                url = e.doc.name + "-" + e.rev

            diff_revisions.append((e.doc.name, e.rev, e.time, url))

    # grab event history
    events = doc.docevent_set.all().order_by("-time", "-id").select_related("by")

    augment_events_with_revision(doc, events)
    add_links_in_new_revision_events(doc, events, diff_revisions)

    # figure out if the current user can add a comment to the history
    if doc.type_id == "draft" and doc.group != None:
        can_add_comment = bool(has_role(request.user, ("Area Director", "Secretariat", "IRTF Chair", "IANA", "RFC Editor")) or (
            request.user.is_authenticated() and
            Role.objects.filter(name__in=("chair", "secr"),
                group__acronym=doc.group.acronym,
                person__user=request.user)))
    else:
        can_add_comment = has_role(request.user, ("Area Director", "Secretariat", "IRTF Chair"))

    return render_to_response("doc/document_history.html",
                              dict(doc=doc,
                                   top=top,
                                   diff_revisions=diff_revisions,
                                   events=events,
                                   can_add_comment=can_add_comment,
                                   ),
                              context_instance=RequestContext(request))


def document_bibtex(request, name, rev=None):
    doc = get_object_or_404(Document, docalias__name=name)

    latest_revision = doc.latest_event(NewRevisionDocEvent, type="new_revision")
    replaced_by = [d.name for d in doc.related_that("replaces")]
    published = doc.latest_event(type="published_rfc")
    rfc = latest_revision.doc if latest_revision and latest_revision.doc.get_state_slug() == "rfc" else None

    if rev != None and rev != doc.rev:
        # find the entry in the history
        for h in doc.history_set.order_by("-time"):
            if rev == h.rev:
                doc = h
                break

    return render_to_response("doc/document_bibtex.bib",
                              dict(doc=doc,
                                   replaced_by=replaced_by,
                                   published=published,
                                   rfc=rfc,
                                   latest_revision=latest_revision),
                              content_type="text/plain; charset=utf-8",
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

        writeups.append(("RFC Editor Note",
                         text_from_writeup("changed_rfc_editor_note_text"),
                         urlreverse("doc_ballot_rfceditornote", kwargs=dict(name=doc.name))))

    elif doc.type_id == "charter":
        sections.append(("WG Review Announcement",
                         "",
                         [("WG Review Announcement",
                           text_from_writeup("changed_review_announcement"),
                           urlreverse("ietf.doc.views_charter.review_announcement_text", kwargs=dict(name=doc.name)))]
                         ))

        sections.append(("WG Action Announcement",
                         "",
                         [("WG Action Announcement",
                           text_from_writeup("changed_action_announcement"),
                           urlreverse("ietf.doc.views_charter.action_announcement_text", kwargs=dict(name=doc.name)))]
                         ))

        if doc.latest_event(BallotDocEvent, type="created_ballot"):
            sections.append(("Ballot Announcement",
                             "",
                             [("Ballot Announcement",
                               text_from_writeup("changed_ballot_writeup_text"),
                               urlreverse("ietf.doc.views_charter.ballot_writeupnotes", kwargs=dict(name=doc.name)))]
                             ))

    if not sections:
        raise Http404

    return render_to_response("doc/document_writeup.html",
                              dict(doc=doc,
                                   top=top,
                                   sections=sections,
                                   can_edit=has_role(request.user, ("Area Director", "Secretariat")),
                                   ),
                              context_instance=RequestContext(request))

def document_shepherd_writeup(request, name):
    doc = get_object_or_404(Document, docalias__name=name)
    lastwriteup = doc.latest_event(WriteupDocEvent,type="changed_protocol_writeup")
    if lastwriteup:
        writeup_text = lastwriteup.text
    else:
        writeup_text = "(There is no shepherd's writeup available for this document)"

    can_edit_stream_info = is_authorized_in_doc_stream(request.user, doc)
    can_edit_shepherd_writeup = can_edit_stream_info or user_is_person(request.user, doc.shepherd and doc.shepherd.person) or has_role(request.user, ["Area Director"])

    return render_to_response("doc/shepherd_writeup.html",
                               dict(doc=doc,
                                    writeup=writeup_text,
                                    can_edit=can_edit_shepherd_writeup
                                   ),
                              context_instance=RequestContext(request))

def document_references(request, name):
    doc = get_object_or_404(Document,docalias__name=name)
    refs = doc.relations_that_doc(['refnorm','refinfo','refunk','refold'])
    return render_to_response("doc/document_references.html",dict(doc=doc,refs=sorted(refs,key=lambda x:x.target.name),),context_instance=RequestContext(request))

def document_referenced_by(request, name):
    doc = get_object_or_404(Document,docalias__name=name)
    refs = doc.relations_that(['refnorm','refinfo','refunk','refold']).filter(source__states__type__slug='draft',source__states__slug__in=['rfc','active'])
    full = ( request.GET.get('full') != None )
    numdocs = refs.count()
    if not full and numdocs>250:
       refs=refs[:250]
    else:
       numdocs=None
    refs=sorted(refs,key=lambda x:(['refnorm','refinfo','refunk','refold'].index(x.relationship.slug),x.source.canonical_name()))
    return render_to_response("doc/document_referenced_by.html",
               dict(alias_name=name,
                    doc=doc,
                    numdocs=numdocs,
                    refs=refs,
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
        return "<p>No ballots are available for this document at this time.</p>"

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

    return render_to_string("doc/document_ballot_content.html",
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

    request.session['ballot_edit_return_point'] = request.path_info

    return render_to_response("doc/document_ballot.html",
                              dict(doc=doc,
                                   top=top,
                                   ballot_content=c,
                                   ),
                              context_instance=RequestContext(request))

def ballot_popup(request, name, ballot_id):
    doc = get_object_or_404(Document, docalias__name=name)
    c = document_ballot_content(request, doc, ballot_id=ballot_id, editable=False)
    return render_to_response("doc/ballot_popup.html",
                              dict(doc=doc,
                                   ballot_content=c,
                                   ballot_id=ballot_id,
                                   ),
                              context_instance=RequestContext(request))


def document_json(request, name, rev=None):
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

    latest_revision = doc.latest_event(NewRevisionDocEvent, type="new_revision")
    data["rev_history"] = crawl_history(latest_revision.doc if latest_revision else doc)

    if doc.type_id == "draft":
        data["iesg_state"] = extract_name(doc.get_state("draft-iesg"))
        data["rfceditor_state"] = extract_name(doc.get_state("draft-rfceditor"))
        data["iana_review_state"] = extract_name(doc.get_state("draft-iana-review"))
        data["iana_action_state"] = extract_name(doc.get_state("draft-iana-action"))

        if doc.stream_id in ("ietf", "irtf", "iab"):
            e = doc.latest_event(ConsensusDocEvent, type="changed_consensus")
            data["consensus"] = e.consensus if e else None
        data["stream"] = extract_name(doc.stream)

    return HttpResponse(json.dumps(data, indent=2), content_type='application/json')

class AddCommentForm(forms.Form):
    comment = forms.CharField(required=True, widget=forms.Textarea)

@role_required('Area Director', 'Secretariat', 'IRTF Chair', 'WG Chair', 'RG Chair', 'WG Secretary', 'RG Secretary', 'IANA', 'RFC Editor')
def add_comment(request, name):
    """Add comment to history of document."""
    doc = get_object_or_404(Document, docalias__name=name)

    login = request.user.person

    if doc.type_id == "draft" and doc.group != None:
        can_add_comment = bool(has_role(request.user, ("Area Director", "Secretariat", "IRTF Chair", "IANA", "RFC Editor")) or (
            request.user.is_authenticated() and
            Role.objects.filter(name__in=("chair", "secr"),
                group__acronym=doc.group.acronym,
                person__user=request.user)))
    else:
        can_add_comment = has_role(request.user, ("Area Director", "Secretariat", "IRTF Chair"))
    if not can_add_comment:
        # The user is a chair or secretary, but not for this WG or RG
        return HttpResponseForbidden("You need to be a chair or secretary of this group to add a comment.")

    if request.method == 'POST':
        form = AddCommentForm(request.POST)
        if form.is_valid():
            c = form.cleaned_data['comment']
            
            e = DocEvent(doc=doc, by=login)
            e.type = "added_comment"
            e.desc = c
            e.save()

            email_comment(request, doc, e)

            return redirect("doc_history", name=doc.name)
    else:
        form = AddCommentForm()
  
    return render_to_response('doc/add_comment.html',
                              dict(doc=doc,
                                   form=form),
                              context_instance=RequestContext(request))

@role_required("Area Director", "Secretariat")
def telechat_date(request, name):
    doc = get_object_or_404(Document, name=name)
    login = request.user.person

    e = doc.latest_event(TelechatDocEvent, type="scheduled_for_telechat")
    initial_returning_item = bool(e and e.returning_item)

    warnings = []
    if e and e.telechat_date and doc.type.slug != 'charter':
        if e.telechat_date==datetime.date.today():
            warnings.append( "This document is currently scheduled for today's telechat. "
                            +"Please set the returning item bit carefully.")

        elif e.telechat_date<datetime.date.today() and has_same_ballot(doc,e.telechat_date):
            initial_returning_item = True
            warnings.append(  "This document appears to have been on a previous telechat with the same ballot, "
                            +"so the returning item bit has been set. Clear it if that is not appropriate.")

    initial = dict(telechat_date=e.telechat_date if e else None,
                   returning_item = initial_returning_item,
                  )
    if request.method == "POST":
        form = TelechatForm(request.POST, initial=initial)

        if form.is_valid():
            if doc.type.slug=='charter':
                cleaned_returning_item = None
            else:
                cleaned_returning_item = form.cleaned_data['returning_item']
            update_telechat(request, doc, login, form.cleaned_data['telechat_date'],cleaned_returning_item)
            return redirect('doc_view', name=doc.name)
    else:
        form = TelechatForm(initial=initial)
        if doc.type.slug=='charter':
            del form.fields['returning_item']

    return render(request, 'doc/edit_telechat_date.html',
                              dict(doc=doc,
                                   form=form,
                                   user=request.user,
                                   warnings=warnings,
                                   login=login))

def edit_notify(request, name):
    """Change the set of email addresses document change notificaitions go to."""

    login = request.user
    doc = get_object_or_404(Document, name=name)

    if not ( is_authorized_in_doc_stream(request.user, doc) or user_is_person(request.user, doc.shepherd and doc.shepherd.person) or has_role(request.user, ["Area Director"]) ):
        return HttpResponseForbidden("You do not have permission to perform this action")

    init = { "notify" : doc.notify }

    if request.method == 'POST':

        if "save_addresses" in request.POST:
            form = NotifyForm(request.POST)
            if form.is_valid():
                new_notify = form.cleaned_data['notify']
                if set(new_notify.split(',')) != set(doc.notify.split(',')):
                    e = make_notify_changed_event(request, doc, login.person, new_notify)
                    doc.notify = new_notify
                    doc.time = e.time
                    doc.save()
                return redirect('doc_view', name=doc.name)

        elif "regenerate_addresses" in request.POST:
            init = { "notify" : get_initial_notify(doc) }
            form = NotifyForm(initial=init)

        # Protect from handcrufted POST
        else:
            form = NotifyForm(initial=init)

    else:

        init = { "notify" : doc.notify }
        form = NotifyForm(initial=init)

    if doc.type.slug=='conflrev':
        conflictdoc = doc.relateddocument_set.get(relationship__slug='conflrev').target.document
        titletext = 'the conflict review of %s' % conflictdoc.canonical_name()
    else:
        titletext = '%s' % doc.canonical_name()
    return render_to_response('doc/edit_notify.html',
                              {'form':   form,
                               'doc': doc,
                               'titletext': titletext,
                              },
                              context_instance = RequestContext(request))

def email_aliases(request,name=''):
    doc = get_object_or_404(Document, name=name) if name else None
    if not name:
        # require login for the overview page, but not for the
        # document-specific pages 
        if not request.user.is_authenticated():
                return redirect('%s?next=%s' % (settings.LOGIN_URL, request.path))
    aliases = get_doc_email_aliases(name)

    return render(request,'doc/email_aliases.html',{'aliases':aliases,'ietf_domain':settings.IETF_DOMAIN,'doc':doc})

class VersionForm(forms.Form):

    version = forms.ChoiceField(required=True,
                                label='Which version of this document will be discussed at this session?')

    def __init__(self, *args, **kwargs):
        choices = kwargs.pop('choices')
        super(VersionForm,self).__init__(*args,**kwargs)
        self.fields['version'].choices = choices

def edit_sessionpresentation(request,name,session_id):
    doc = get_object_or_404(Document, name=name)
    sp = get_object_or_404(doc.sessionpresentation_set, session_id=session_id)

    if not sp.session.can_manage_materials(request.user):
        raise Http404

    if sp.session.is_material_submission_cutoff() and not has_role(request.user, "Secretariat"):
        raise Http404

    choices = [(x,x) for x in doc.docevent_set.filter(type='new_revision').values_list('newrevisiondocevent__rev',flat=True)]
    choices.insert(0,('current','Current at the time of the session'))
    initial = {'version' : sp.rev if sp.rev else 'current'}

    if request.method == 'POST':
        form = VersionForm(request.POST,choices=choices)
        if form.is_valid():
            new_selection = form.cleaned_data['version']
            if initial['version'] != new_selection:
                doc.sessionpresentation_set.filter(pk=sp.pk).update(rev=None if new_selection=='current' else new_selection)
                c = DocEvent(type="added_comment", doc=doc, by=request.user.person)
                c.desc = "Revision for session %s changed to  %s" % (sp.session,new_selection)
                c.save()
            return redirect('ietf.doc.views_doc.all_presentations', name=name)
    else:
        form = VersionForm(choices=choices,initial=initial)

    return render(request,'doc/edit_sessionpresentation.html', {'sp': sp, 'form': form })

def remove_sessionpresentation(request,name,session_id):
    doc = get_object_or_404(Document, name=name)
    sp = get_object_or_404(doc.sessionpresentation_set, session_id=session_id)

    if not sp.session.can_manage_materials(request.user):
        raise Http404

    if sp.session.is_material_submission_cutoff() and not has_role(request.user, "Secretariat"):
        raise Http404

    if request.method == 'POST':
        doc.sessionpresentation_set.filter(pk=sp.pk).delete()
        c = DocEvent(type="added_comment", doc=doc, by=request.user.person)
        c.desc = "Removed from session: %s" % (sp.session)
        c.save()
        return redirect('ietf.doc.views_doc.all_presentations', name=name)

    return render(request,'doc/remove_sessionpresentation.html', {'sp': sp })

class SessionChooserForm(forms.Form):
    session = forms.ChoiceField(label="Which session should this document be added to?",required=True)

    def __init__(self, *args, **kwargs):
        choices = kwargs.pop('choices')
        super(SessionChooserForm,self).__init__(*args,**kwargs)
        self.fields['session'].choices = choices

@role_required("Secretariat","Area Director","WG Chair","WG Secretary","RG Chair","RG Secretary","IRTF Chair","Team Chair")
def add_sessionpresentation(request,name):
    doc = get_object_or_404(Document, name=name)
    
    version_choices = [(x,x) for x in doc.docevent_set.filter(type='new_revision').values_list('newrevisiondocevent__rev',flat=True)]
    version_choices.insert(0,('current','Current at the time of the session'))

    sessions = get_upcoming_manageable_sessions(request.user)
    sessions = sort_sessions([s for s in sessions if not s.sessionpresentation_set.filter(document=doc).exists()])
    if doc.group:
        sessions = sorted(sessions,key=lambda x:0 if x.group==doc.group else 1)

    session_choices = [(s.pk,unicode(s)) for s in sessions]

    if request.method == 'POST':
        version_form = VersionForm(request.POST,choices=version_choices)
        session_form = SessionChooserForm(request.POST,choices=session_choices)
        if version_form.is_valid() and session_form.is_valid():
            session_id = session_form.cleaned_data['session']
            version = version_form.cleaned_data['version']
            rev = None if version=='current' else version
            doc.sessionpresentation_set.create(session_id=session_id,rev=rev)
            c = DocEvent(type="added_comment", doc=doc, by=request.user.person)
            c.desc = "%s to session: %s" % ('Added -%s'%rev if rev else 'Added', Session.objects.get(pk=session_id))
            c.save()
            return redirect('ietf.doc.views_doc.all_presentations', name=name)

    else: 
        version_form = VersionForm(choices=version_choices,initial={'version':'current'})
        session_form = SessionChooserForm(choices=session_choices)

    return render(request,'doc/add_sessionpresentation.html',{'doc':doc,'version_form':version_form,'session_form':session_form})

def all_presentations(request, name):
    doc = get_object_or_404(Document, name=name)


    sessions = doc.session_set.filter(status__in=['sched','schedw','appr','canceled'],
                                      type__in=['session','plenary','other'])

    future, in_progress, past = group_sessions(sessions)

    return render(request, 'doc/material/all_presentations.html', {
        'user': request.user,
        'doc': doc,
        'future': future,
        'in_progress': in_progress,
        'past' : past,
        })
