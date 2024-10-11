# Copyright The IETF Trust 2009-2024, All Rights Reserved
# -*- coding: utf-8 -*-
#
# Parts Copyright (C) 2009-2010 Nokia Corporation and/or its subsidiary(-ies).
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


import glob
import json
import os
import re

from pathlib import Path

from django.core.cache import caches
from django.core.exceptions import PermissionDenied
from django.db.models import Max
from django.http import HttpResponse, Http404, HttpResponseBadRequest
from django.shortcuts import render, get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import reverse as urlreverse
from django.conf import settings
from django import forms
from django.contrib.auth.decorators import login_required
from django.contrib.staticfiles import finders

import debug                            # pyflakes:ignore

from ietf.doc.models import ( Document, DocHistory, DocEvent, BallotDocEvent, BallotType,
    ConsensusDocEvent, NewRevisionDocEvent, TelechatDocEvent, WriteupDocEvent, IanaExpertDocEvent,
    IESG_BALLOT_ACTIVE_STATES, STATUSCHANGE_RELATIONS, DocumentActionHolder, DocumentAuthor,
    RelatedDocument, RelatedDocHistory)
from ietf.doc.utils import (augment_events_with_revision,
    can_adopt_draft, can_unadopt_draft, get_chartering_type, get_tags_for_stream_id, investigate_fragment,
    needed_ballot_positions, nice_consensus, update_telechat, has_same_ballot,
    get_initial_notify, make_notify_changed_event, make_rev_history, default_consensus,
    add_events_message_info, get_unicode_document_content,
    augment_docs_and_person_with_person_info, irsg_needed_ballot_positions, add_action_holder_change_event,
    build_file_urls, update_documentauthors, fuzzy_find_documents,
    bibxml_for_draft, get_doc_email_aliases)
from ietf.doc.utils_bofreq import bofreq_editors, bofreq_responsible
from ietf.group.models import Role, Group
from ietf.group.utils import can_manage_all_groups_of_type, can_manage_materials, group_features_role_filter
from ietf.ietfauth.utils import ( has_role, is_authorized_in_doc_stream, user_is_person,
    role_required, is_individual_draft_author, can_request_rfc_publication)
from ietf.name.models import StreamName, BallotPositionName
from ietf.utils.history import find_history_active_at
from ietf.doc.views_ballot import parse_ballot_edit_return_point
from ietf.doc.forms import InvestigateForm, TelechatForm, NotifyForm, ActionHoldersForm, DocAuthorForm, DocAuthorChangeBasisForm
from ietf.doc.mails import email_comment, email_remind_action_holders
from ietf.mailtrigger.utils import gather_relevant_expansions
from ietf.meeting.models import Session, SessionPresentation
from ietf.meeting.utils import group_sessions, get_upcoming_manageable_sessions, sort_sessions, add_event_info_to_session_qs
from ietf.review.models import ReviewAssignment
from ietf.review.utils import can_request_review_of_doc, review_assignments_to_list_for_docs, review_requests_to_list_for_docs
from ietf.review.utils import no_review_from_teams_on_doc
from ietf.utils import markup_txt, log, markdown
from ietf.utils.draft import PlaintextDraft
from ietf.utils.meetecho import MeetechoAPIError, SlidesManager
from ietf.utils.response import permission_denied
from ietf.utils.text import maybe_split
from ietf.utils.timezone import date_today


def render_document_top(request, doc, tab, name):
    tabs = []
    tabs.append(("Status", "status", urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=name)), True, None))

    iesg_type_slugs = set(BallotType.objects.exclude(slug__in=("irsg-approve","rsab-approve")).values_list('slug',flat=True)) 
    iesg_ballot = doc.latest_event(BallotDocEvent, type="created_ballot", ballot_type__slug__in=iesg_type_slugs)
    irsg_ballot = doc.latest_event(BallotDocEvent, type="created_ballot", ballot_type__slug='irsg-approve')
    rsab_ballot = doc.latest_event(BallotDocEvent, type="created_ballot", ballot_type__slug='rsab-approve')

    if doc.type_id == "draft":
        if doc.get_state("draft-stream-irtf"):
            tabs.append((
                "IRSG Evaluation Record", 
                "irsgballot", 
                urlreverse("ietf.doc.views_doc.document_irsg_ballot", kwargs=dict(name=name)), 
                irsg_ballot,  
                None if irsg_ballot else "IRSG Evaluation Ballot has not been created yet"
            ))
        if  doc.get_state("draft-stream-editorial"):
            tabs.append((
                "RSAB Evaluation Record", 
                "rsabballot", 
                urlreverse("ietf.doc.views_doc.document_rsab_ballot", kwargs=dict(name=name)), 
                rsab_ballot,  
                None if rsab_ballot else "RSAB Evaluation Ballot has not been created yet"
            ))

    if iesg_ballot or (doc.group and doc.group.type_id == "wg"):
        if doc.type_id in ("draft", "conflrev", "statchg"):
            tabs.append(
                (
                    "IESG Evaluation Record",
                    "ballot",
                    urlreverse(
                        "ietf.doc.views_doc.document_ballot", kwargs=dict(name=name)
                    ),
                    iesg_ballot,
                    None,
                )
            )
        elif doc.type_id == "charter" and doc.group and doc.group.type_id == "wg":
            tabs.append(
                (
                    "IESG Review",
                    "ballot",
                    urlreverse(
                        "ietf.doc.views_doc.document_ballot", kwargs=dict(name=name)
                    ),
                    iesg_ballot,
                    None,
                )
            )
        if doc.type_id == "draft" or (
            doc.type_id == "charter" and doc.group and doc.group.type_id == "wg"
        ):
            tabs.append(
                (
                    "IESG Writeups",
                    "writeup",
                    urlreverse(
                        "ietf.doc.views_doc.document_writeup", kwargs=dict(name=name)
                    ),
                    True,
                    None,
                )
            )
    if not doc.type_id in ["bcp", "std", "fyi"]:
        tabs.append(("Email expansions","email",urlreverse('ietf.doc.views_doc.document_email', kwargs=dict(name=name)), True, None))
    tabs.append(("History", "history", urlreverse('ietf.doc.views_doc.document_history', kwargs=dict(name=name)), True, None))

    if name.startswith("rfc"):
        name = "RFC %s" % name[3:]
    else:
        name += "-" + doc.rev

    return render_to_string("doc/document_top.html" if not doc.type_id in ["bcp", "std", "fyi"] else "doc/document_subseries_top.html",
                            dict(doc=doc,
                                 tabs=tabs,
                                 selected=tab,
                                 name=name))

def interesting_doc_relations(doc):

    if isinstance(doc, Document):
        cls = RelatedDocument
        target = doc
    elif isinstance(doc, DocHistory):
        cls = RelatedDocHistory
        target = doc.doc
    else:
        raise TypeError("Expected this method to be called with a Document or DocHistory object")

    that_relationships = STATUSCHANGE_RELATIONS + ('conflrev', 'replaces', 'possibly_replaces', 'updates', 'obs', 'became_rfc') 

    that_doc_relationships = ('replaces', 'possibly_replaces', 'updates', 'obs', 'became_rfc')

    interesting_relations_that = cls.objects.filter(target=target, relationship__in=that_relationships).select_related('source')
    interesting_relations_that_doc = cls.objects.filter(source=doc, relationship__in=that_doc_relationships).prefetch_related('target')

    return interesting_relations_that, interesting_relations_that_doc

def document_main(request, name, rev=None, document_html=False):

    doc = get_object_or_404(Document.objects.select_related(), name=name)

    if doc.type_id == "rfc" and rev is not None:
        raise Http404()

    log.assertion('doc.type_id!="rfc" or doc.name.startswith("rfc")')

    # take care of possible redirections
    if document_html is False and rev is None:
        became_rfc = doc.became_rfc()
        if became_rfc:
            return redirect("ietf.doc.views_doc.document_main", name=became_rfc.name)

    revisions = doc.revisions_by_dochistory()
    latest_rev = doc.rev

    snapshot = False

    gh = None
    if rev and rev != doc.rev:
        # find the entry in the history if the rev requested is not the current rev
        for h in doc.history_set.order_by("-time"):
            if rev == h.rev:
                snapshot = True
                doc = h
                break

        if not snapshot and document_html is False:
            return redirect('ietf.doc.views_doc.document_main', name=name)

        if doc.type_id == "charter":
            # find old group, too
            gh = find_history_active_at(doc.group, doc.time)

    # set this after we've found the right doc instance
    if gh:
        group = gh
    else:
        group = doc.group

    top = render_document_top(request, doc, "status", name)

    telechat = doc.latest_event(TelechatDocEvent, type="scheduled_for_telechat")
    if telechat and (not telechat.telechat_date or telechat.telechat_date < date_today(settings.TIME_ZONE)):
       telechat = None

    # specific document types
    if doc.type_id == "rfc":
        split_content = request.COOKIES.get("full_draft", settings.USER_PREFERENCE_DEFAULTS["full_draft"]) == "off"
        if request.GET.get('include_text') == "0":
            split_content = True
        elif request.GET.get('include_text') == "1":
            split_content = False
        else:
            pass

        interesting_relations_that, interesting_relations_that_doc = interesting_doc_relations(doc)

        can_edit = has_role(request.user, ("Area Director", "Secretariat"))
        can_edit_authors = has_role(request.user, ("Secretariat"))

        stream_slugs = StreamName.objects.values_list("slug", flat=True)
        # For some reason, AnonymousUser has __iter__, but is not iterable,
        # which causes problems in the filter() below.  Work around this:  
        if request.user.is_authenticated:
            roles = Role.objects.filter(group__acronym__in=stream_slugs, person__user=request.user)
            roles = group_features_role_filter(roles, request.user.person, 'docman_roles')
        else:
            roles = []

        can_change_stream = bool(can_edit or roles)

        file_urls, found_types = build_file_urls(doc)
        if not request.user.is_authenticated:
            file_urls = [fu for fu in file_urls if fu[0] != "pdfized"]
        content = doc.text_or_error() # pyflakes:ignore
        content = markup_txt.markup(maybe_split(content, split=split_content))

        if not found_types:
            content = "This RFC is not currently available online."
            split_content = False
        elif "txt" not in found_types:
            content = "This RFC is not available in plain text format."
            split_content = False

        # status changes
        status_changes = []
        proposed_status_changes = []
        for r in interesting_relations_that.filter(relationship__in=STATUSCHANGE_RELATIONS):
            state_slug = r.source.get_state_slug()
            if state_slug in ('appr-sent', 'appr-pend'):
                status_changes.append(r)
            elif state_slug in ('needshep','adrev','iesgeval','defer','appr-pr'):
                proposed_status_changes.append(r)
            else:
                pass

        presentations = doc.future_presentations()

        if request.user.is_authenticated and hasattr(request.user, "person"):
            augment_docs_and_person_with_person_info([doc], request.user.person)

        exp_comment = doc.latest_event(IanaExpertDocEvent,type="comment")
        iana_experts_comment = exp_comment and exp_comment.desc

        html = None
        js = None
        css = None
        diff_revisions = None
        simple_diff_revisions = None
        if document_html:
            diff_revisions=get_diff_revisions(request, name, doc)
            simple_diff_revisions = [t[1] for t in diff_revisions if t[0] == doc.name]
            simple_diff_revisions.reverse()
            html = doc.html_body()
            if request.COOKIES.get("pagedeps") == "inline":
                js = Path(finders.find("ietf/js/document_html.js")).read_text()
                css = Path(finders.find("ietf/css/document_html_inline.css")).read_text()
                if html:
                    css += Path(finders.find("ietf/css/document_html_txt.css")).read_text()

        # submission
        submission = ""
        if group is None:
            submission = "unknown"
        elif group.type_id == "individ":
            submission = "individual"
        elif group.type_id == "area" and doc.stream_id == "ietf":
            submission = "individual in %s area" % group.acronym
        else:
            if group.features.acts_like_wg and not group.type_id == "edwg":
                submission = "%s %s" % (group.acronym, group.type)
            else:
                submission = group.acronym
            submission = '<a href="%s">%s</a>' % (group.about_url(), submission)

        draft = doc.came_from_draft()
        mailto_name = draft.name if draft else None

        return render(request, "doc/document_rfc.html" if document_html is False else "doc/document_html.html",
                                  dict(doc=doc,
                                       document_html=document_html,
                                       css=css,
                                       js=js,
                                       html=html,
                                       group=group,
                                       top=top,
                                       name=doc.name,
                                       content=content,
                                       split_content=split_content,
                                       revisions=simple_diff_revisions if document_html else revisions,
                                       latest_rev=latest_rev,
                                       can_edit=can_edit,
                                       can_edit_authors=can_edit_authors,
                                       can_change_stream=can_change_stream,
                                       rfc_number=doc.rfc_number,
                                       updates=interesting_relations_that_doc.filter(relationship="updates"),
                                       updated_by=interesting_relations_that.filter(relationship="updates"),
                                       obsoletes=interesting_relations_that_doc.filter(relationship="obs"),
                                       obsoleted_by=interesting_relations_that.filter(relationship="obs"),
                                       status_changes=status_changes,
                                       proposed_status_changes=proposed_status_changes,
                                       has_errata=doc.pk and doc.tags.filter(slug="errata"), # doc.pk == None if using a fake_history_obj
                                       file_urls=file_urls,
                                       rfc_editor_state=doc.get_state("draft-rfceditor"),
                                       iana_review_state=doc.get_state("draft-iana-review"),
                                       iana_action_state=doc.get_state("draft-iana-action"),
                                       iana_experts_state=doc.get_state("draft-iana-experts"),
                                       iana_experts_comment=iana_experts_comment,
                                       presentations=presentations,
                                       diff_revisions=diff_revisions,
                                       submission=submission,
                                       mailto_name=mailto_name,
                                       ))

    elif doc.type_id == "draft":
        split_content = request.COOKIES.get("full_draft", settings.USER_PREFERENCE_DEFAULTS["full_draft"]) == "off"
        if request.GET.get('include_text') == "0":
            split_content = True
        elif request.GET.get('include_text') == "1":
            split_content = False
        else:
            pass

        interesting_relations_that, interesting_relations_that_doc = interesting_doc_relations(doc)

        iesg_state = doc.get_state("draft-iesg")
        if isinstance(doc, Document):
            log.assertion('iesg_state', note="A document's 'draft-iesg' state should never be unset'.  Failed for %s"%doc.name)
        iesg_state_slug = iesg_state.slug if iesg_state else None
        iesg_state_summary = doc.friendly_state()
        irsg_state = doc.get_state("draft-stream-irtf")

        can_edit = has_role(request.user, ("Area Director", "Secretariat"))
        can_edit_authors = has_role(request.user, ("Secretariat"))

        stream_slugs = StreamName.objects.values_list("slug", flat=True)
        # For some reason, AnonymousUser has __iter__, but is not iterable,
        # which causes problems in the filter() below.  Work around this:  
        if request.user.is_authenticated:
            roles = Role.objects.filter(group__acronym__in=stream_slugs, person__user=request.user)
            roles = group_features_role_filter(roles, request.user.person, 'docman_roles')
        else:
            roles = []

        can_change_stream = bool(can_edit or roles)
        can_edit_iana_state = has_role(request.user, ("Secretariat", "IANA"))

        can_edit_replaces = has_role(request.user, ("Area Director", "Secretariat", "IRTF Chair", "WG Chair", "RG Chair", "WG Secretary", "RG Secretary"))

        can_edit_action_holders = can_edit or (
            request.user.is_authenticated and group.has_role(request.user, group.features.docman_roles)
        )

        is_author = request.user.is_authenticated and doc.documentauthor_set.filter(person__user=request.user).exists()
        can_view_possibly_replaces = can_edit_replaces or is_author

        latest_revision = None

        file_urls, found_types = build_file_urls(doc)
        if not request.user.is_authenticated:
            file_urls = [fu for fu in file_urls if fu[0] != "pdfized"]
        content = doc.text_or_error() # pyflakes:ignore
        content = markup_txt.markup(maybe_split(content, split=split_content))

        latest_revision = doc.latest_event(NewRevisionDocEvent, type="new_revision")

        # ballot
        iesg_ballot_summary = None
        due_date = None
        if (iesg_state_slug in IESG_BALLOT_ACTIVE_STATES) or irsg_state:
            active_ballot = doc.active_ballot()
            if active_ballot:
                if irsg_state:
                    due_date=active_ballot.irsgballotdocevent.duedate
                else:
                    iesg_ballot_summary = needed_ballot_positions(doc, list(active_ballot.active_balloter_positions().values()))

        # submission
        submission = ""
        if group is None:
            submission = "unknown"
        elif group.type_id == "individ":
            submission = "individual"
        elif group.type_id == "area" and doc.stream_id == "ietf":
            submission = "individual in %s area" % group.acronym
        else:
            if group.features.acts_like_wg and not group.type_id=="edwg":
                submission = "%s %s" % (group.acronym, group.type)
            else:
                submission = group.acronym
            submission = "<a href=\"%s\">%s</a>" % (group.about_url(), submission)
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

        is_shepherd = user_is_person(request.user, doc.shepherd and doc.shepherd.person)
        can_edit_stream_info = is_authorized_in_doc_stream(request.user, doc)
        can_edit_shepherd_writeup = can_edit_stream_info or is_shepherd or has_role(request.user, ["Area Director"])
        can_edit_notify = can_edit_shepherd_writeup
        can_edit_individual = is_individual_draft_author(request.user, doc)

        can_edit_consensus = False
        consensus = nice_consensus(default_consensus(doc))
        if doc.stream_id == "ietf" and iesg_state:
            show_in_states = set(IESG_BALLOT_ACTIVE_STATES)
            show_in_states.update(('approved','ann','rfcqueue','pub'))
            if iesg_state_slug in show_in_states: 
                can_edit_consensus = can_edit
                e = doc.latest_event(ConsensusDocEvent, type="changed_consensus")
                consensus = nice_consensus(e and e.consensus)
        elif doc.stream_id in ("irtf", "iab"):
            can_edit_consensus = can_edit or can_edit_stream_info
            e = doc.latest_event(ConsensusDocEvent, type="changed_consensus")
            consensus = nice_consensus(e and e.consensus)

        can_request_review = can_request_review_of_doc(request.user, doc)
        can_submit_unsolicited_review_for_teams = None
        if request.user.is_authenticated:
            can_submit_unsolicited_review_for_teams = Group.objects.filter(
                reviewteamsettings__isnull=False, role__person__user=request.user, role__name='secr')

        # conflict reviews
        conflict_reviews = [r.source.name for r in interesting_relations_that.filter(relationship="conflrev")]

        # status changes
        status_changes = []
        proposed_status_changes = []
        for r in interesting_relations_that.filter(relationship__in=STATUSCHANGE_RELATIONS):
            state_slug = r.source.get_state_slug()
            if state_slug in ('appr-sent', 'appr-pend'):
                status_changes.append(r)
            elif state_slug in ('needshep','adrev','iesgeval','defer','appr-pr'):
                proposed_status_changes.append(r)
            else:
                pass

        presentations = doc.future_presentations()

        # remaining actions
        actions = []

        if can_adopt_draft(request.user, doc) and not doc.get_state_slug() in ["rfc"] and not snapshot:
            if doc.group and doc.group.acronym != 'none': # individual submission
                # already adopted in one group
                button_text = "Switch adoption"
            else:
                button_text = "Manage adoption"
            actions.append((button_text, urlreverse('ietf.doc.views_draft.adopt_draft', kwargs=dict(name=doc.name))))

        if can_unadopt_draft(request.user, doc) and not doc.get_state_slug() in ["rfc"] and not snapshot:
            if doc.get_state_slug('draft-iesg') == 'idexists':
                if doc.group and doc.group.acronym != 'none':
                    actions.append(("Release document from group", urlreverse('ietf.doc.views_draft.release_draft', kwargs=dict(name=doc.name))))
                elif doc.stream_id == 'ise':
                    actions.append(("Release document from stream", urlreverse('ietf.doc.views_draft.release_draft', kwargs=dict(name=doc.name))))
                else:
                    pass

        if doc.get_state_slug() == "expired" and not resurrected_by and can_edit and not snapshot:
            actions.append(("Request Resurrect", urlreverse('ietf.doc.views_draft.request_resurrect', kwargs=dict(name=doc.name))))

        if doc.get_state_slug() == "expired" and has_role(request.user, ("Secretariat",)) and not snapshot:
            actions.append(("Resurrect", urlreverse('ietf.doc.views_draft.resurrect', kwargs=dict(name=doc.name))))
        
        if doc.get_state_slug() not in ["rfc", "expired"] and not snapshot:
            if doc.stream_id == "irtf" and has_role(request.user, ("Secretariat", "IRTF Chair")):
                if not doc.ballot_open('irsg-approve'):
                    actions.append((
                        "Issue IRSG Ballot",
                        urlreverse('ietf.doc.views_ballot.issue_irsg_ballot', kwargs=dict(name=doc.name))
                    ))
                else:
                    actions.append((
                        "Close IRSG Ballot",
                        urlreverse('ietf.doc.views_ballot.close_irsg_ballot', kwargs=dict(name=doc.name))
                    ))
            elif doc.stream_id == "editorial" and has_role(request.user, ("Secretariat", "RSAB Chair")): 
                if not doc.ballot_open('rsab-approve'):
                    actions.append((
                        "Issue RSAB Ballot",
                        urlreverse('ietf.doc.views_ballot.issue_rsab_ballot', kwargs=dict(name=doc.name))
                        ))
                else:
                    actions.append((
                        "Close RSAB Ballot",
                        urlreverse('ietf.doc.views_ballot.close_rsab_ballot', kwargs=dict(name=doc.name))
                    ))

        if (
            doc.get_state_slug() not in ["rfc", "expired"]
            and not conflict_reviews
            and not snapshot
        ):
            if (
                doc.stream_id == "ise" and has_role(request.user, ("Secretariat", "ISE"))
            ) or (
                doc.stream_id == "irtf" and has_role(request.user, ("Secretariat", "IRTF Chair"))
            ):
                label = "Begin IETF conflict review" # Note that the template feeds this through capfirst_allcaps
                if not doc.intended_std_level:
                    label += " (note that intended status is not set)"
                actions.append((label, urlreverse('ietf.doc.views_conflict_review.start_review', kwargs=dict(name=doc.name))))

        if doc.get_state_slug() not in ["rfc", "expired"] and not snapshot:
            if can_request_rfc_publication(request.user, doc):
                if doc.get_state_slug('draft-stream-%s' % doc.stream_id) not in ('rfc-edit', 'pub', 'dead'):
                    label = "Request Publication"
                    if not doc.intended_std_level:
                        label += " (note that intended status is not set)"
                    if iesg_state and iesg_state_slug not in ('idexists','dead'):
                        label += " (Warning: the IESG state indicates ongoing IESG processing)"
                    actions.append((label, urlreverse('ietf.doc.views_draft.request_publication', kwargs=dict(name=doc.name))))

        if doc.get_state_slug() not in ["rfc", "expired"] and doc.stream_id in ("ietf",) and not snapshot:
            if iesg_state_slug == 'idexists' and can_edit:
                actions.append(("Begin IESG Processing", urlreverse('ietf.doc.views_draft.edit_info', kwargs=dict(name=doc.name)) + "?new=1"))
            elif can_edit_stream_info and (iesg_state_slug == 'idexists'):
                actions.append(("Submit to IESG for Publication", urlreverse('ietf.doc.views_draft.to_iesg', kwargs=dict(name=doc.name))))

        if request.user.is_authenticated and hasattr(request.user, "person"):
            augment_docs_and_person_with_person_info([doc], request.user.person)

        published = doc.latest_event(type="published_rfc")  # todo rethink this now that published_rfc is on rfc
        started_iesg_process = doc.latest_event(type="started_iesg_process")

        review_assignments = review_assignments_to_list_for_docs([doc]).get(doc.name, [])
        review_requests = review_requests_to_list_for_docs([doc]).get(doc.name, [])
        no_review_from_teams = no_review_from_teams_on_doc(doc, rev or doc.rev)

        exp_comment = doc.latest_event(IanaExpertDocEvent,type="comment")
        iana_experts_comment = exp_comment and exp_comment.desc

        # See if we should show an Auth48 URL
        auth48_url = None  # stays None unless we are in the auth48 state
        if doc.get_state_slug('draft-rfceditor') == 'auth48':
            document_url = doc.documenturl_set.filter(tag_id='auth48').first()
            auth48_url = document_url.url if document_url else ''

        # Do not show the Auth48 URL in the "Additional URLs" section
        additional_urls = doc.documenturl_set.exclude(tag_id='auth48')

        # Stream description and name passing test
        stream = ("draft-stream-" + doc.stream.slug) if doc.stream != None else "(None)"

        html = None
        js = None
        css = None
        diff_revisions = None
        simple_diff_revisions = None
        if document_html:
            diff_revisions=get_diff_revisions(request, name, doc if isinstance(doc,Document) else doc.doc)
            simple_diff_revisions = [t[1] for t in diff_revisions if t[0] == doc.name]
            simple_diff_revisions.reverse()
            if rev and rev != doc.rev: 
                # No DocHistory was found matching rev - snapshot will be false
                # and doc will be a Document object, not a DocHistory
                snapshot = True
                doc = doc.fake_history_obj(rev)
            else:
                html = doc.html_body()
                if request.COOKIES.get("pagedeps") == "inline":
                    js = Path(finders.find("ietf/js/document_html.js")).read_text()
                    js += Path(finders.find("ietf/js/theme.js")).read_text()
                    css = Path(finders.find("ietf/css/document_html_inline.css")).read_text()
                    if html:
                        css += Path(finders.find("ietf/css/document_html_txt.css")).read_text()

        return render(request, "doc/document_draft.html" if document_html is False else "doc/document_html.html",
                                  dict(doc=doc,
                                       document_html=document_html,
                                       css=css,
                                       js=js,
                                       html=html,
                                       group=group,
                                       top=top,
                                       name=doc.name,
                                       content=content,
                                       split_content=split_content,
                                       revisions=simple_diff_revisions if document_html else revisions,
                                       snapshot=snapshot,
                                       stream=stream,
                                       latest_revision=latest_revision,
                                       latest_rev=latest_rev,
                                       can_edit=can_edit,
                                       can_edit_authors=can_edit_authors,
                                       can_change_stream=can_change_stream,
                                       can_edit_stream_info=can_edit_stream_info,
                                       can_edit_individual=can_edit_individual,
                                       is_shepherd = is_shepherd,
                                       can_edit_shepherd_writeup=can_edit_shepherd_writeup,
                                       can_edit_notify=can_edit_notify,
                                       can_edit_iana_state=can_edit_iana_state,
                                       can_edit_consensus=can_edit_consensus,
                                       can_edit_replaces=can_edit_replaces,
                                       can_edit_action_holders=can_edit_action_holders,
                                       can_view_possibly_replaces=can_view_possibly_replaces,
                                       can_request_review=can_request_review,
                                       can_submit_unsolicited_review_for_teams=can_submit_unsolicited_review_for_teams,

                                       telechat=telechat,
                                       iesg_ballot_summary=iesg_ballot_summary,
                                       submission=submission,
                                       resurrected_by=resurrected_by,

                                       replaces=interesting_relations_that_doc.filter(relationship="replaces"),
                                       replaced_by=interesting_relations_that.filter(relationship="replaces"),
                                       possibly_replaces=interesting_relations_that_doc.filter(relationship="possibly_replaces"),
                                       possibly_replaced_by=interesting_relations_that.filter(relationship="possibly_replaces"),
                                       updates=interesting_relations_that_doc.filter(relationship="updates"),
                                       updated_by=interesting_relations_that.filter(relationship="updates"),
                                       obsoletes=interesting_relations_that_doc.filter(relationship="obs"),
                                       obsoleted_by=interesting_relations_that.filter(relationship="obs"),
                                       conflict_reviews=conflict_reviews,
                                       status_changes=status_changes,
                                       proposed_status_changes=proposed_status_changes,
                                       has_errata=doc.pk and doc.tags.filter(slug="errata"), # doc.pk == None if using a fake_history_obj
                                       published=published,
                                       file_urls=file_urls,
                                       additional_urls=additional_urls,
                                       stream_state_type_slug=stream_state_type_slug,
                                       stream_state=stream_state,
                                       stream_tags=stream_tags,
                                       milestones=doc.groupmilestone_set.filter(state="active"),
                                       consensus=consensus,
                                       iesg_state=iesg_state,
                                       iesg_state_summary=iesg_state_summary,
                                       rfc_editor_state=doc.get_state("draft-rfceditor"),
                                       rfc_editor_auth48_url=auth48_url,
                                       iana_review_state=doc.get_state("draft-iana-review"),
                                       iana_action_state=doc.get_state("draft-iana-action"),
                                       iana_experts_state=doc.get_state("draft-iana-experts"),
                                       iana_experts_comment=iana_experts_comment,
                                       started_iesg_process=started_iesg_process,
                                       shepherd_writeup=shepherd_writeup,
                                       actions=actions,
                                       presentations=presentations,
                                       review_assignments=review_assignments,
                                       review_requests=review_requests,
                                       no_review_from_teams=no_review_from_teams,
                                       due_date=due_date,
                                       diff_revisions=diff_revisions
                                       ))

    elif doc.type_id == "charter":
        content = doc.text_or_error()     # pyflakes:ignore
        content = markdown.markdown(content)

        ballot_summary = None
        if doc.get_state_slug() in ("intrev", "iesgrev"):
            active_ballot = doc.active_ballot()
            if active_ballot:
                ballot_summary = needed_ballot_positions(doc, list(active_ballot.active_balloter_positions().values()))
            else:
                ballot_summary = "No active ballot found."

        chartering = get_chartering_type(doc)

        # inject milestones from group
        milestones = None
        if chartering and not snapshot:
            milestones = doc.group.groupmilestone_set.filter(state="charter")

        can_manage = can_manage_all_groups_of_type(request.user, doc.group.type_id)

        return render(request, "doc/document_charter.html",
                                  dict(doc=doc,
                                       top=top,
                                       chartering=chartering,
                                       content=content,
                                       txt_url=doc.get_href(),
                                       revisions=revisions,
                                       latest_rev=latest_rev,
                                       snapshot=snapshot,
                                       telechat=telechat,
                                       ballot_summary=ballot_summary,
                                       group=group,
                                       milestones=milestones,
                                       can_manage=can_manage,
                                       ))

    elif doc.type_id == "bofreq":
        content = markdown.markdown(doc.text_or_error())
        editors = bofreq_editors(doc)
        responsible = bofreq_responsible(doc)
        can_manage = has_role(request.user,['Secretariat', 'Area Director', 'IAB'])
        editor_can_manage =  doc.get_state_slug('bofreq')=='proposed' and request.user.is_authenticated and request.user.person in editors

        return render(request, "doc/document_bofreq.html",
                                  dict(doc=doc,
                                       top=top,
                                       revisions=revisions,
                                       latest_rev=latest_rev,
                                       content=content,
                                       snapshot=snapshot,
                                       can_manage=can_manage,
                                       editors=editors,
                                       responsible=responsible,
                                       editor_can_manage=editor_can_manage,
                                       ))

    elif doc.type_id == "conflrev":
        filename = "%s-%s.txt" % (doc.name, doc.rev)
        pathname = os.path.join(settings.CONFLICT_REVIEW_PATH,filename)

        if doc.rev == "00" and not os.path.isfile(pathname):
            # This could move to a template
            content = "A conflict review response has not yet been proposed."
        else:     
            content = doc.text_or_error() # pyflakes:ignore
            content = markup_txt.markup(content)

        ballot_summary = None
        if doc.get_state_slug() in ("iesgeval", ) and doc.active_ballot():
            ballot_summary = needed_ballot_positions(doc, list(doc.active_ballot().active_balloter_positions().values()))

        conflictdoc = doc.related_that_doc('conflrev')[0]

        return render(request, "doc/document_conflict_review.html",
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
                                       ))

    elif doc.type_id == "statchg":
        filename = "%s-%s.txt" % (doc.name, doc.rev)
        pathname = os.path.join(settings.STATUS_CHANGE_PATH,filename)

        if doc.rev == "00" and not os.path.isfile(pathname):
            # This could move to a template
            content = "Status change text has not yet been proposed."
        else:     
            content = doc.text_or_error() # pyflakes:ignore

        ballot_summary = None
        if doc.get_state_slug() in ("iesgeval"):
            ballot_summary = needed_ballot_positions(doc, list(doc.active_ballot().active_balloter_positions().values()))
     
        if isinstance(doc,Document):
            sorted_relations=doc.relateddocument_set.all().order_by("relationship__name", "target__name")
        elif isinstance(doc,DocHistory):
            sorted_relations=doc.relateddochistory_set.all().order_by("relationship__name", "target__name")
        else:
            sorted_relations=None

        return render(request, "doc/document_status_change.html",
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
                                       ))

    elif doc.type_id in ("slides", "agenda", "minutes", "narrativeminutes", "bluesheets", "procmaterials",):
        can_manage_material = can_manage_materials(request.user, doc.group)
        presentations = doc.future_presentations()
        if doc.uploaded_filename:
            # we need to remove the extension for the globbing below to work
            basename = os.path.splitext(doc.uploaded_filename)[0]
        else:
            basename = "%s-%s" % (doc.name, doc.rev)

        pathname = os.path.join(doc.get_file_path(), basename)

        content = None
        content_is_html = False
        other_types = []
        globs = glob.glob(pathname + ".*")
        url = doc.get_href()
        urlbase, urlext = os.path.splitext(url) 
        for g in globs:
            extension = os.path.splitext(g)[1]
            t = os.path.splitext(g)[1].lstrip(".")
            if not url.endswith("/") and not url.endswith(extension): 
                url = urlbase + extension 
            if extension == ".txt":
                content = doc.text_or_error()
                t = "plain text"
            elif extension == ".md":
                content = markdown.markdown(doc.text_or_error())
                content_is_html = True
                t = "markdown"
            other_types.append((t, url))

        # determine whether uploads are allowed
        can_upload = can_manage_material and not snapshot
        if doc.group is None:
            can_upload = can_upload and (doc.type_id == 'procmaterials')
        else:
            can_upload = (
                    can_upload
                    and doc.group.features.has_nonsession_materials
                    and doc.type_id in doc.group.features.material_types
            )

        session_statusid = None
        actual_doc = doc if isinstance(doc,Document) else doc.doc
        if actual_doc.session_set.count() == 1:
            if actual_doc.session_set.get().schedulingevent_set.exists():
                session_statusid = actual_doc.session_set.get().schedulingevent_set.order_by("-time").first().status_id

        return render(request, "doc/document_material.html",
                                  dict(doc=doc,
                                       top=top,
                                       content=content,
                                       content_is_html=content_is_html,
                                       revisions=revisions,
                                       latest_rev=latest_rev,
                                       snapshot=snapshot,
                                       can_manage_material=can_manage_material,
                                       can_upload = can_upload,
                                       other_types=other_types,
                                       presentations=presentations,
                                       session_statusid=session_statusid,
                                       ))


    elif doc.type_id == "review":
        basename = "{}.txt".format(doc.name)
        pathname = os.path.join(doc.get_file_path(), basename)
        content = get_unicode_document_content(basename, pathname)
        # If we want to go back to using markup_txt.markup_unicode, call it explicitly here like this:
        # content = markup_txt.markup_unicode(content, split=False, width=80)
       
        assignments = ReviewAssignment.objects.filter(review__name=doc.name)
        review_assignment = assignments.first()

        other_reviews = []
        if review_assignment:
            other_reviews = [r for r in review_assignments_to_list_for_docs([review_assignment.review_request.doc]).get(doc.name, []) if r != review_assignment]

        return render(request, "doc/document_review.html",
                      dict(doc=doc,
                           top=top,
                           content=content,
                           revisions=revisions,
                           latest_rev=latest_rev,
                           snapshot=snapshot,
                           review_req=review_assignment.review_request if review_assignment else None,
                           other_reviews=other_reviews,
                           assignments=assignments,
                      ))

    elif doc.type_id in ("chatlog", "polls"):
        if isinstance(doc,DocHistory):
            session = doc.doc.presentations.last().session
        else:
            session = doc.presentations.last().session
        pathname = Path(session.meeting.get_materials_path()) / doc.type_id / doc.uploaded_filename
        content = get_unicode_document_content(doc.name, str(pathname))
        return render(
            request, 
            f"doc/document_{doc.type_id}.html",
            dict(
                doc=doc,
                top=top,
                content=content,
                revisions=revisions,
                latest_rev=latest_rev,
                snapshot=snapshot,
                session=session,
            )
        )

    elif doc.type_id == "statement":
        if doc.uploaded_filename:
            basename = doc.uploaded_filename.split(".")[0] # strip extension
        else:
            basename = f"{doc.name}-{doc.rev}"
        variants = set([match.name.split(".")[1] for match in Path(doc.get_file_path()).glob(f"{basename}.*")])
        inlineable = any([ext in variants for ext in ["md", "txt"]])
        if inlineable:
            content = markdown.liberal_markdown(doc.text_or_error())
        else:
            content = "No format available to display inline"
            if "pdf" in variants:
                pdf_url = urlreverse(
                    "ietf.doc.views_statement.serve_pdf",
                    kwargs=dict(name=doc.name, rev=doc.rev),
                )
                content += f" - Download [pdf]({pdf_url})"
            content = markdown.markdown(content)
        can_manage = has_role(request.user,["Secretariat"]) # Add IAB or IESG as appropriate
        interesting_relations_that, interesting_relations_that_doc = interesting_doc_relations(doc)
        published = doc.latest_event(type="published_statement").time
        return render(request, "doc/document_statement.html",
                                  dict(doc=doc,
                                       top=top,
                                       revisions=revisions,
                                       latest_rev=latest_rev,
                                       published=published,
                                       content=content,
                                       snapshot=snapshot,
                                       replaces=interesting_relations_that_doc.filter(relationship="replaces"),
                                       replaced_by=interesting_relations_that.filter(relationship="replaces"),
                                       can_manage=can_manage,
                                       ))
    elif doc.type_id in ["bcp", "std", "fyi"]:
        return render(request, "doc/document_subseries.html", {"doc": doc, "top": top})


    raise Http404("Document not found: %s" % (name + ("-%s"%rev if rev else "")))


def document_raw_id(request, name, rev=None, ext=None):
    if not name.startswith('draft-'):
        raise Http404
    found = fuzzy_find_documents(name, rev)
    num_found = found.documents.count()
    if num_found == 0:
        raise Http404("Document not found: %s" % name)
    if num_found > 1:
        raise Http404("Multiple documents matched: %s" % name)

    doc = found.documents.get()

    if found.matched_rev or found.matched_name.startswith('rfc'):
        rev = found.matched_rev
    else:
        rev = doc.rev
    if rev:
        doc = doc.history_set.filter(rev=rev).first() or doc.fake_history_obj(rev)

    base_path = os.path.join(settings.INTERNET_ALL_DRAFTS_ARCHIVE_DIR, doc.name + "-" + doc.rev + ".")
    possible_types = settings.IDSUBMIT_FILE_TYPES
    found_types=dict()
    for t in possible_types:
        if os.path.exists(base_path + t):
            found_types[t]=base_path+t
    if ext is None:
        ext = 'txt'
    if not ext in found_types:
        raise Http404('dont have the file for that extension')
    mimetypes = {'txt':'text/plain','html':'text/html','xml':'application/xml'}
    try:
        with open(found_types[ext],'rb') as f:
            blob = f.read()
            return HttpResponse(blob,content_type=f'{mimetypes[ext]};charset=utf-8')
    except:
        raise Http404

def document_html(request, name, rev=None):
    requested_rev = rev
    found = fuzzy_find_documents(name, rev)
    num_found = found.documents.count()
    if num_found == 0:
        raise Http404("Document not found: %s" % name)
    if num_found > 1:
        raise Http404("Multiple documents matched: %s" % name)

    doc = found.documents.get()
    rev = found.matched_rev

    if not requested_rev and doc.type_id == "rfc": # Someone asked for /doc/html/8989
        if not name.startswith('rfc'):
            return redirect('ietf.doc.views_doc.document_html', name=doc.name)

    if rev:
        doc = doc.history_set.filter(rev=rev).first() or doc.fake_history_obj(rev)

    if not os.path.exists(doc.get_file_name()):
        raise Http404("File not found: %s" % doc.get_file_name())

    return document_main(
        request,
        name=doc.name if requested_rev else doc.name,
        rev=doc.rev if requested_rev or doc.type_id != "rfc" else None,
        document_html=True,
    )


@login_required
def document_pdfized(request, name, rev=None, ext=None):

    found = fuzzy_find_documents(name, rev)
    num_found = found.documents.count()
    if num_found == 0:
        raise Http404("Document not found: %s" % name)
    if num_found > 1:
        raise Http404("Multiple documents matched: %s" % name)

    if found.matched_name.startswith('rfc') and name != found.matched_name:
         return redirect('ietf.doc.views_doc.document_pdfized', name=found.matched_name)

    doc = found.documents.get()

    if found.matched_rev or found.matched_name.startswith('rfc'):
        rev = found.matched_rev
    else:
        rev = doc.rev
    if rev:
        doc = doc.history_set.filter(rev=rev).first() or doc.fake_history_obj(rev)

    if not os.path.exists(doc.get_file_name()):
        raise Http404("File not found: %s" % doc.get_file_name())

    try:
        pdf = doc.pdfized()
    except Exception:
        return render(request, "doc/weasyprint_failed.html")
    if pdf:
        return HttpResponse(pdf,content_type='application/pdf')
    else:
        raise Http404


def document_email(request,name):
    doc = get_object_or_404(Document, name=name)
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


def get_diff_revisions(request, name, doc):
    """ Calculate what to offer for diff comparisons

    returns list of (name, rev, time, url, is_this_doc, is_previous_doc)
    ordered by -time for use by forms used to get to the diff tools.
    """
    diffable = any(
        [
            name.startswith(prefix)
            for prefix in [
                "rfc",
                "draft",
                "charter",
                "conflict-review",
                "status-change",
            ]
        ]
    )

    if not diffable:
        return []

    # pick up revisions from events
    diff_revisions = []

    diff_documents = [doc]
    diff_documents.extend(
        Document.objects.filter(
            relateddocument__source=doc,
            relateddocument__relationship="replaces",
        )
    )
    if doc.came_from_draft():
        diff_documents.append(doc.came_from_draft())

    if doc.became_rfc():
        rfc = doc.became_rfc()
        e = rfc.latest_event(type="published_rfc")
        diff_revisions.append((rfc.name, "", e.time if e else rfc.time, rfc.name, False, False))

    if doc.type_id == "rfc":
        e = doc.latest_event(type="published_rfc")
        diff_revisions.append((name, "", e.time if e else doc.time, name, True, False))

    seen = set()
    for e in (
        NewRevisionDocEvent.objects.filter(type="new_revision", doc__in=diff_documents)
        .select_related("doc")
        .order_by("-time", "-id")
    ):
        if (e.doc.name, e.rev) in seen:
            continue

        seen.add((e.doc.name, e.rev))

        url = ""
        if name.startswith("charter"):
            url = request.build_absolute_uri(
                urlreverse(
                    "ietf.doc.views_charter.charter_with_milestones_txt",
                    kwargs=dict(name=e.doc.name, rev=e.rev),
                )
            )
        elif name.startswith("conflict-review"):
            url = find_history_active_at(e.doc, e.time).get_href()
        elif name.startswith("status-change"):
            url = find_history_active_at(e.doc, e.time).get_href()
        elif name.startswith("draft") or name.startswith("rfc"):
            # rfcdiff tool has special support for IDs
            url = e.doc.name + "-" + e.rev

        diff_revisions.append((e.doc.name, e.rev, e.time, url, e.doc == doc and e.rev == doc.rev, False))
    
    diff_revisions.sort(key=lambda t: t[2], reverse=True)
    for index, t in enumerate(diff_revisions):
        if t[4]: # is_this_doc
            n = index+1
            if n < len(diff_revisions):
                t_name, rev, time, url, _, _ = diff_revisions[n]
                diff_revisions[n] = (t_name, rev, time, url, False, True)
                break

    return diff_revisions


def document_history(request, name):
    doc = get_object_or_404(Document, name=name)
    top = render_document_top(request, doc, "history", name)
    diff_revisions = get_diff_revisions(request, name, doc)

    # grab event history
    events = doc.docevent_set.all().order_by("-time", "-id").select_related("by")

    augment_events_with_revision(doc, events)
    add_events_message_info(events)

    # figure out if the current user can add a comment to the history
    if doc.type_id in ("draft", "rfc") and doc.group is not None:
        can_add_comment = bool(
            has_role(
                request.user,
                ("Area Director", "Secretariat", "IRTF Chair", "IANA", "RFC Editor"),
            )
            or (
                request.user.is_authenticated
                and Role.objects.filter(
                    name__in=("chair", "secr"),
                    group__acronym=doc.group.acronym,
                    person__user=request.user,
                )
            )
        )
    else:
        can_add_comment = has_role(
            request.user, ("Area Director", "Secretariat", "IRTF Chair")
        )


    return render(
        request,
        "doc/document_history.html",
        {
            "doc": doc,
            "top": top,
            "diff_revisions": diff_revisions,
            "events": events,
            "can_add_comment": can_add_comment,
        },
    )


def document_bibtex(request, name, rev=None):
    if name.startswith('rfc') and rev is not None:
        raise Http404()

    # Make sure URL_REGEXPS did not grab too much for the rev number
    if rev is not None and len(rev) != 2:
        mo = re.search(r"^(?P<m>[0-9]{1,2})-(?P<n>[0-9]{2})$", rev)
        if mo:
            name = name+"-"+mo.group(1)
            rev = mo.group(2)
        else:
            name = name+"-"+rev
            rev = None

    doc = get_object_or_404(Document, name=name)

    if doc.type_id not in ["rfc", "draft"]:
        raise Http404()

    doi = None
    draft_became_rfc = None
    replaced_by = None
    latest_revision = None
    if doc.type_id == "draft":
        latest_revision = doc.latest_event(NewRevisionDocEvent, type="new_revision")
        replaced_by = [d.name for d in doc.related_that("replaces")]
        draft_became_rfc = doc.became_rfc()

        if rev is not None and rev != doc.rev:
            # find the entry in the history
            for h in doc.history_set.order_by("-time"):
                if rev == h.rev:
                    doc = h
                    break

    elif doc.type_id == "rfc":
        # This needs to be replaced with a lookup, as the mapping may change
        # over time.
        doi = f"10.17487/RFC{doc.rfc_number:04d}"

    if doc.is_dochistory():
        latest_event = doc.latest_event(type='new_revision', rev=rev)
        if latest_event:
            doc.pub_date = latest_event.time

    return render(request, "doc/document_bibtex.bib",
                              dict(doc=doc,
                                   replaced_by=replaced_by,
                                   published_as=draft_became_rfc,
                                   latest_revision=latest_revision,
                                   doi=doi,
                               ),
                              content_type="text/plain; charset=utf-8",
                          )

def document_bibxml_ref(request, name, rev=None):
    if re.search(r'^rfc\d+$', name):
        raise Http404()
    if not name.startswith('draft-'):
        name = 'draft-'+name
    return document_bibxml(request, name, rev=rev)
    
def document_bibxml(request, name, rev=None):
    # This only deals with drafts, as bibxml entries for RFCs should come from
    # the RFC-Editor.
    if re.search(r'^rfc\d+$', name):
        raise Http404()

    # Make sure URL_REGEXPS did not grab too much for the rev number
    if rev is not None and len(rev) != 2:
        mo = re.search(r"^(?P<m>[0-9]{1,2})-(?P<n>[0-9]{2})$", rev)
        if mo:
            name = name+"-"+mo.group(1)
            rev = mo.group(2)
        else:
            name = name+"-"+rev
            rev = None

    doc = get_object_or_404(Document, name=name, type_id='draft')
        
    return HttpResponse(bibxml_for_draft(doc, rev), content_type="application/xml; charset=utf-8")



def document_writeup(request, name):
    doc = get_object_or_404(Document, name=name)
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

        if doc.get_state("draft-iesg"):
            writeups.append(("Announcement",
                             text_from_writeup("changed_ballot_approval_text"),
                             urlreverse('ietf.doc.views_ballot.ballot_approvaltext', kwargs=dict(name=doc.name))))

        writeups.append(("Ballot Text",
                         text_from_writeup("changed_ballot_writeup_text"),
                         urlreverse('ietf.doc.views_ballot.ballot_writeupnotes', kwargs=dict(name=doc.name))))

        writeups.append(("RFC Editor Note",
                         text_from_writeup("changed_rfc_editor_note_text"),
                         urlreverse('ietf.doc.views_ballot.ballot_rfceditornote', kwargs=dict(name=doc.name))))

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

    return render(request, "doc/document_writeup.html",
                              dict(doc=doc,
                                   top=top,
                                   sections=sections,
                                   can_edit=has_role(request.user, ("Area Director", "Secretariat")),
                                   ))

def document_shepherd_writeup(request, name):
    doc = get_object_or_404(Document, name=name)
    lastwriteup = doc.latest_event(WriteupDocEvent,type="changed_protocol_writeup")
    if lastwriteup:
        writeup_text = lastwriteup.text
    else:
        writeup_text = "(There is no shepherd's writeup available for this document)"

    can_edit_stream_info = is_authorized_in_doc_stream(request.user, doc)
    can_edit_shepherd_writeup = can_edit_stream_info or user_is_person(request.user, doc.shepherd and doc.shepherd.person) or has_role(request.user, ["Area Director"])

    return render(request, "doc/shepherd_writeup.html",
                               dict(doc=doc,
                                    writeup=writeup_text,
                                    can_edit=can_edit_shepherd_writeup
                                   ),
                              )


def document_shepherd_writeup_template(request, type):
    writeup = markdown.markdown(
        render_to_string(
            "doc/shepherd_writeup.txt",
            dict(stream="ietf", type="individ" if type == "individual" else "group"),
        )
    )
    return render(
        request,
        "doc/shepherd_writeup_template.html",
        dict(
            writeup=writeup,
            stream="ietf",
            type="individ" if type == "individual" else "group",
        ),
    )


def document_references(request, name):
    doc = get_object_or_404(Document,name=name)
    refs = doc.references()
    if doc.type_id in ["bcp","std","fyi"]:
        for rfc in doc.contains():
            refs |= rfc.references()    
    return render(request, "doc/document_references.html",dict(doc=doc,refs=sorted(refs,key=lambda x:x.target.name),))

def document_referenced_by(request, name):
    """View documents that reference the named document
    
    The view lists both direct references to a the named document, plus references to
    related other documents. For a draft that became an RFC, this will include references
    to the RFC. For an RFC, this will include references to the draft it came from, if any.
    For a subseries document, this will include references to any of the RFC documents it
    contains. 
    
    In the rendered output, a badge is applied to indicate the name of the document the
    reference actually targeted. E.g., on the display for a draft that became RFC NNN,
    references included because they point to that RFC would be shown with a tag "As RFC NNN".
    The intention is to make the "Referenced By" page useful for finding related work while
    accurately reflecting the actual reference relationships.     
    """
    doc = get_object_or_404(Document,name=name)
    refs = doc.referenced_by()
    if doc.came_from_draft():
        refs |= doc.came_from_draft().referenced_by()
    if doc.became_rfc():
        refs |= doc.became_rfc().referenced_by()
    if doc.type_id in ["bcp","std","fyi"]:
        for rfc in doc.contains():
            refs |= rfc.referenced_by()
    full = ( request.GET.get('full') is not None )
    numdocs = refs.count()
    if not full and numdocs>250:
       refs=refs[:250]
    else:
       numdocs=None
    refs=sorted(refs,key=lambda x:(['refnorm','refinfo','refunk','refold'].index(x.relationship.slug),x.source.name))
    return render(request, "doc/document_referenced_by.html",
               dict(name=name,
                    doc=doc,
                    numdocs=numdocs,
                    refs=refs,
                    ))

def document_ballot_content(request, doc, ballot_id, editable=True):
    """Render HTML string with content of ballot page."""
    all_ballots = list(BallotDocEvent.objects.filter(doc=doc, type="created_ballot").order_by("time"))
    augment_events_with_revision(doc, all_ballots)

    ballot = None
    if ballot_id is not None:
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
    #
    # Each position group is a tuple (BallotPositionName, [BallotPositionDocEvent, ...])
    # THe list contains the latest entry for each AD, possibly with a fake 'no record' entry
    # for any ADs without an event. Blocking positions are earlier in the list than non-blocking.
    position_groups = []
    for n in BallotPositionName.objects.filter(slug__in=[p.pos_id for p in positions]).order_by('order'):
        g = (n, [p for p in positions if p.pos_id == n.slug])
        g[1].sort(key=lambda p: (p.is_old_pos, p.balloter.plain_name()))
        if n.blocking:
            position_groups.insert(0, g)
        else:
            position_groups.append(g)

    iesg = doc.get_state("draft-iesg")
    iesg_state = iesg.slug if iesg else None
    if (ballot.ballot_type.slug == "irsg-approve"):
        summary = irsg_needed_ballot_positions(doc, [p for p in positions if not p.is_old_pos])
    else:
        summary = needed_ballot_positions(doc, [p for p in positions if not p.is_old_pos])

    text_positions = [p for p in positions if p.discuss or p.comment]
    text_positions.sort(key=lambda p: (p.is_old_pos, p.balloter.last_name()))

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
                                   iesg_state=iesg_state,
                                   ),
                              request=request)

def document_ballot(request, name, ballot_id=None):
    doc = get_object_or_404(Document, name=name)
    ballots = BallotDocEvent.objects.filter(doc=doc, type="created_ballot").order_by("time")
    if ballot_id is not None:
        ballot = ballots.filter(id=ballot_id).first()
    else:
        ballot = ballots.last()
    if not ballot:
        raise Http404("Ballot not found for: %s" % name)

    if ballot.ballot_type.slug == "irsg-approve":
        ballot_tab = "irsgballot"
    else:
        ballot_tab = "ballot"

    top = render_document_top(request, doc, ballot_tab, name)

    c = document_ballot_content(request, doc, ballot.id, editable=True)

    return render(request, "doc/document_ballot.html",
                              dict(doc=doc,
                                   top=top,
                                   ballot_content=c,
                                   ))

def document_irsg_ballot(request, name, ballot_id=None):
    doc = get_object_or_404(Document, name=name)
    top = render_document_top(request, doc, "irsgballot", name)
    if not ballot_id:
        ballot = doc.latest_event(BallotDocEvent, type="created_ballot", ballot_type__slug='irsg-approve')
        if ballot:
            ballot_id = ballot.id

    c = document_ballot_content(request, doc, ballot_id, editable=True)

    return render(request, "doc/document_ballot.html",
                              dict(doc=doc,
                                   top=top,
                                   ballot_content=c,
                                   # ballot_type_slug=ballot.ballot_type.slug,
                                   ))

def document_rsab_ballot(request, name, ballot_id=None):
    doc = get_object_or_404(Document, name=name)
    top = render_document_top(request, doc, "rsabballot", name)
    if not ballot_id:
        ballot = doc.latest_event(BallotDocEvent, type="created_ballot", ballot_type__slug='rsab-approve')
        if ballot:
            ballot_id = ballot.id

    c = document_ballot_content(request, doc, ballot_id, editable=True)

    return render(
        request,
        "doc/document_ballot.html",
        dict(
            doc=doc,
            top=top,
            ballot_content=c,
        )
    )

def ballot_popup(request, name, ballot_id):
    doc = get_object_or_404(Document, name=name)
    c = document_ballot_content(request, doc, ballot_id=ballot_id, editable=False)
    ballot = get_object_or_404(BallotDocEvent,id=ballot_id)
    
    try:
        return_to_url = parse_ballot_edit_return_point(request.GET.get('ballot_edit_return_point'), name, ballot_id)
    except ValueError:
        return HttpResponseBadRequest('ballot_edit_return_point is invalid')
    
    return render(request, "doc/ballot_popup.html",
                              dict(doc=doc,
                                   ballot_content=c,
                                   ballot_id=ballot_id,
                                   ballot_type_slug=ballot.ballot_type.slug,
                                   ballot_edit_return_point=return_to_url,
                                   editable=True,
                                   ))


def document_json(request, name, rev=None):
    doc = get_object_or_404(Document, name=name)

    def extract_name(s):
        return s.name if s else None

    data = {}

    data["name"] = doc.name
    data["rev"] = doc.rev
    data["pages"] = doc.pages
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
    data["state"] = extract_name(doc.get_state())
    data["intended_std_level"] = extract_name(doc.intended_std_level)
    data["std_level"] = extract_name(doc.std_level)
    data["authors"] = [
        dict(name=author.person.name,
             email=author.email.address if author.email else None,
             affiliation=author.affiliation)
        for author in doc.documentauthor_set.all().select_related("person", "email").order_by("order")
    ]
    data["shepherd"] = doc.shepherd.formatted_email() if doc.shepherd else None
    data["ad"] = doc.ad.role_email("ad").formatted_email() if doc.ad else None

    latest_revision = doc.latest_event(NewRevisionDocEvent, type="new_revision")
    data["rev_history"] = make_rev_history(latest_revision.doc if latest_revision else doc)

    if doc.type_id == "draft": # These live only on drafts
        data["iesg_state"] = extract_name(doc.get_state("draft-iesg"))
        data["rfceditor_state"] = extract_name(doc.get_state("draft-rfceditor"))
        data["iana_review_state"] = extract_name(doc.get_state("draft-iana-review"))
        data["iana_action_state"] = extract_name(doc.get_state("draft-iana-action"))

        if doc.stream_id in ("ietf", "irtf", "iab"):
            e = doc.latest_event(ConsensusDocEvent, type="changed_consensus")
            data["consensus"] = e.consensus if e else None

    if doc.type_id in ["draft", "rfc"]:
        data["stream"] = extract_name(doc.stream)

    return HttpResponse(json.dumps(data, indent=2), content_type='application/json')

class AddCommentForm(forms.Form):
    comment = forms.CharField(required=True, widget=forms.Textarea, strip=False)

@role_required('Area Director', 'Secretariat', 'IRTF Chair', 'WG Chair', 'RG Chair', 'WG Secretary', 'RG Secretary', 'IANA', 'RFC Editor')
def add_comment(request, name):
    """Add comment to history of document."""
    doc = get_object_or_404(Document, name=name)

    login = request.user.person

    if doc.type_id == "draft" and doc.group is not None:
        can_add_comment = bool(has_role(request.user, ("Area Director", "Secretariat", "IRTF Chair", "IANA", "RFC Editor")) or (
            request.user.is_authenticated and
            Role.objects.filter(name__in=("chair", "secr"),
                group__acronym=doc.group.acronym,
                person__user=request.user)))
    else:
        can_add_comment = has_role(request.user, ("Area Director", "Secretariat", "IRTF Chair"))
    if not can_add_comment:
        # The user is a chair or secretary, but not for this WG or RG
        permission_denied(request, "You need to be a chair or secretary of this group to add a comment.")

    if request.method == 'POST':
        form = AddCommentForm(request.POST)
        if form.is_valid():
            c = form.cleaned_data['comment']
            
            e = DocEvent(doc=doc, rev=doc.rev, by=login)
            e.type = "added_comment"
            e.desc = c
            e.save()

            email_comment(request, doc, e)

            return redirect('ietf.doc.views_doc.document_history', name=doc.name)
    else:
        form = AddCommentForm()
  
    return render(request, 'doc/add_comment.html',
                              dict(doc=doc,
                                   form=form))

@role_required("Area Director", "Secretariat")
def telechat_date(request, name):
    doc = get_object_or_404(Document, name=name)
    login = request.user.person

    e = doc.latest_event(TelechatDocEvent, type="scheduled_for_telechat")
    initial_returning_item = bool(e and e.returning_item)

    warnings = []
    if e and e.telechat_date and doc.type.slug != 'charter':
        today = date_today(settings.TIME_ZONE)
        if e.telechat_date == today:
            warnings.append( "This document is currently scheduled for today's telechat. "
                            +"Please set the returning item bit carefully.")

        elif e.telechat_date < today and has_same_ballot(doc,e.telechat_date):
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
            return redirect('ietf.doc.views_doc.document_main', name=doc.name)
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


def doc_titletext(doc):
    if doc.type.slug=='conflrev':
        conflictdoc = doc.relateddocument_set.get(relationship__slug='conflrev').target
        return 'the conflict review of %s' % conflictdoc.name
    return doc.name
    
    
def edit_notify(request, name):
    """Change the set of email addresses document change notificaitions go to."""

    login = request.user
    doc = get_object_or_404(Document, name=name)

    if not ( is_authorized_in_doc_stream(request.user, doc) or user_is_person(request.user, doc.shepherd and doc.shepherd.person) or has_role(request.user, ["Area Director"]) ):
        permission_denied(request, "You do not have permission to perform this action")

    init = { "notify" : doc.notify }

    if request.method == 'POST':

        if "save_addresses" in request.POST:
            form = NotifyForm(request.POST)
            if form.is_valid():
                new_notify = form.cleaned_data['notify']
                if set(new_notify.split(',')) != set(doc.notify.split(',')):
                    e = make_notify_changed_event(request, doc, login.person, new_notify)
                    doc.notify = new_notify
                    doc.save_with_history([e])
                return redirect('ietf.doc.views_doc.document_main', name=doc.name)

        elif "regenerate_addresses" in request.POST:
            init = { "notify" : get_initial_notify(doc) }
            form = NotifyForm(initial=init)

        # Protect from handcrufted POST
        else:
            form = NotifyForm(initial=init)

    else:

        init = { "notify" : doc.notify }
        form = NotifyForm(initial=init)

    return render(request, 'doc/edit_notify.html',
                              {'form':   form,
                               'doc': doc,
                               'titletext': doc_titletext(doc),
                              },
                          )


@role_required('Secretariat')
def edit_authors(request, name):
    """Edit the authors of a doc"""
    class _AuthorsBaseFormSet(forms.BaseFormSet):
        HIDE_FIELDS = ['ORDER']

        def __init__(self, *args, **kwargs):
            kwargs['prefix'] = 'author'
            super(_AuthorsBaseFormSet, self).__init__(*args, **kwargs)

        def add_fields(self, form, index):
            super(_AuthorsBaseFormSet, self).add_fields(form, index)
            for fh in self.HIDE_FIELDS:
                if fh in form.fields:
                    form.fields[fh].widget = forms.HiddenInput()

    AuthorFormSet = forms.formset_factory(DocAuthorForm,
                                          formset=_AuthorsBaseFormSet,
                                          can_delete=True,
                                          can_order=True,
                                          extra=0)
    doc = get_object_or_404(Document, name=name)
    
    if request.method == 'POST':
        change_basis_form = DocAuthorChangeBasisForm(request.POST)
        author_formset = AuthorFormSet(request.POST)
        if change_basis_form.is_valid() and author_formset.is_valid():
            docauthors = []
            for form in author_formset.ordered_forms:
                if not form.cleaned_data['DELETE']:
                    docauthors.append(
                        DocumentAuthor(
                            # update_documentauthors() will fill in document and order for us
                            person=form.cleaned_data['person'],
                            email=form.cleaned_data['email'],
                            affiliation=form.cleaned_data['affiliation'],
                            country=form.cleaned_data['country']
                        )
                    )
            change_events = update_documentauthors(
                doc,
                docauthors,
                request.user.person,
                change_basis_form.cleaned_data['basis']
            )
            for event in change_events:
                event.save()
            return redirect('ietf.doc.views_doc.document_main', name=doc.name)
    else:
        change_basis_form = DocAuthorChangeBasisForm() 
        author_formset = AuthorFormSet(
            initial=[{
                'person': author.person,
                'email': author.email,
                'affiliation': author.affiliation,
                'country': author.country,
                'order': author.order,
            } for author in doc.documentauthor_set.all()]
        )
    return render(
        request, 
        'doc/edit_authors.html',
        {
            'doc': doc,
            'change_basis_form': change_basis_form,
            'formset': author_formset,
            'titletext': doc_titletext(doc),
        })


@login_required
def edit_action_holders(request, name):
    """Change the set of action holders for a doc"""
    doc = get_object_or_404(Document, name=name)

    can_edit = has_role(request.user, ("Area Director", "Secretariat")) or (
        doc.group and doc.group.has_role(request.user, doc.group.features.docman_roles)
    )
    if not can_edit:
        # Keep the list of roles in this message up-to-date with the can_edit logic
        message = "Restricted to roles: Area Director, Secretariat"
        if doc.group and doc.group.acronym != "none":
            message += f", and document managers for the {doc.group.acronym} group"
        raise PermissionDenied(message)

    if request.method == 'POST':
        form = ActionHoldersForm(request.POST)
        if form.is_valid():
            new_action_holders = form.cleaned_data['action_holders']  # Person queryset
            prev_action_holders = list(doc.action_holders.all())
            
            # Now update the action holders. We can't use the simple approach of clearing
            # the set and then adding back the entire new_action_holders. If we did that,
            # the timestamps that track when each person became an action holder would
            # reset every time the list was modified. So we need to be careful only
            # to delete the ones that are really being removed.
            #
            # Also need to take care not to delete the people! doc.action_holders.all()
            # (and other querysets) give the Person objects. We only want to add/delete
            # the DocumentActionHolder 'through' model objects. That means working directly
            # with the model or using doc.action_holders.add() and .remove(), which take
            # Person objects as arguments.
            existing = DocumentActionHolder.objects.filter(document=doc)  # through model  
            to_remove = existing.exclude(person__in=new_action_holders)  # through model
            to_remove.delete()  # deletes the DocumentActionHolder objects, leaves the Person objects

            # Get all the Persons who do not have a DocumentActionHolder for this document
            added_people = new_action_holders.exclude(documentactionholder__document=doc)
            doc.action_holders.add(*added_people)
            
            add_action_holder_change_event(doc, request.user.person, prev_action_holders,
                                           form.cleaned_data['reason'])

        return redirect('ietf.doc.views_doc.document_main', name=doc.name)
    
    # When not a POST
    # Data for quick add/remove of various related Persons
    doc_role_labels = []  # labels for document-related roles
    group_role_labels = []  # labels for group-related roles
    role_ids = dict()  # maps role slug to list of Person IDs (assumed numeric in the JavaScript)
    extra_prefetch = []  # list of Person objects to prefetch for select2 field

    if len(doc.authors()) > 0:
        doc_role_labels.append(dict(slug='authors', label='Authors'))
        authors = doc.authors()
        role_ids['authors'] = [p.pk for p in authors]
        extra_prefetch += authors

    if doc.ad:
        doc_role_labels.append(dict(slug='ad', label='Responsible AD'))
        role_ids['ad'] = [doc.ad.pk]
        extra_prefetch.append(doc.ad)
        
    if doc.shepherd:
        # doc.shepherd is an Email, which is allowed not to have a Person.
        # The Emails used for shepherds should always have one, though. If not, log the
        # event and move on without the shepherd. This just means there will not be
        # add/remove shepherd buttons.
        log.assertion('doc.shepherd.person',
                      note="A document's shepherd should always have a Person'.  Failed for %s"%doc.name)
        if doc.shepherd.person:
            doc_role_labels.append(dict(slug='shep', label='Shepherd'))
            role_ids['shep'] = [doc.shepherd.person.pk]
            extra_prefetch.append(doc.shepherd.person)

    if doc.group:
        # UI buttons to add / remove will appear in same order as this list
        group_roles = doc.group.role_set.filter(
            name__in=DocumentActionHolder.GROUP_ROLES_OF_INTEREST,
        ).select_related('name', 'person')  # name is a RoleName

        # Gather all the roles for this group
        for role in group_roles:
            key = 'group_%s' % role.name.slug
            existing_list = role_ids.get(key)
            if existing_list:
                existing_list.append(role.person.pk)
            else:
                role_ids[key] = [role.person.pk]
                group_role_labels.append(dict(
                    sort_order=DocumentActionHolder.GROUP_ROLES_OF_INTEREST.index(role.name.slug),
                    slug=key,
                    label='Group ' + role.name.name,  # friendly role name
                ))
            extra_prefetch.append(role.person)
    
    # Ensure group role button order is stable
    group_role_labels.sort(key=lambda r: r['sort_order'])

    form = ActionHoldersForm(initial={'action_holders': doc.action_holders.all()})
    form.fields['action_holders'].extra_prefetch = extra_prefetch
    form.fields['action_holders'].widget.attrs["data-role-ids"] = json.dumps(role_ids)

    return render(
        request,
        'doc/edit_action_holders.html',
        {
            'form': form, 
            'doc': doc, 
            'titletext': doc_titletext(doc),
            'role_labels': doc_role_labels + group_role_labels,
        }
    )


class ReminderEmailForm(forms.Form):
    note = forms.CharField(
        widget=forms.Textarea, 
        label='Note to action holders',
        help_text='Optional message to the action holders',
        required=False,
        strip=True,
    )

@login_required
def remind_action_holders(request, name):
    doc = get_object_or_404(Document, name=name)

    can_edit = has_role(request.user, ("Area Director", "Secretariat")) or (
        doc.group and doc.group.has_role(request.user, doc.group.features.docman_roles)
    )
    if not can_edit:
        # Keep the list of roles in this message up-to-date with the can_edit logic
        message = "Restricted to roles: Area Director, Secretariat"
        if doc.group and doc.group.acronym != "none":
            message += f", and document managers for the {doc.group.acronym} group"
        raise PermissionDenied(message)

    if request.method == 'POST':
        form = ReminderEmailForm(request.POST)
        if form.is_valid():
            email_remind_action_holders(request, doc, form.cleaned_data['note'])
        return redirect('ietf.doc.views_doc.document_main', name=doc.name)

    form = ReminderEmailForm()
    return render(
        request,
        'doc/remind_action_holders.html',
        {
            'form': form,
            'doc': doc,
            'titletext': doc_titletext(doc),
        }
    )


@login_required
def email_aliases(request):
    """List of all email aliases
    
    This is currently slow except when cached
    """
    slowcache = caches["slowpages"]
    cache_key = "emailaliasesview"
    aliases = slowcache.get(cache_key)
    if not aliases:
        aliases = get_doc_email_aliases()  # gets all aliases
        slowcache.set(cache_key, aliases, 3600)
    return render(
        request,
        "doc/email_aliases.html",
        {
            "aliases": aliases,
            "ietf_domain": settings.IETF_DOMAIN,
        },
    )

class VersionForm(forms.Form):

    version = forms.ChoiceField(required=True,
                                label='Which version of this document will be discussed at this session?')

    def __init__(self, *args, **kwargs):
        choices = kwargs.pop('choices')
        super(VersionForm,self).__init__(*args,**kwargs)
        self.fields['version'].choices = choices

def edit_sessionpresentation(request,name,session_id):
    doc = get_object_or_404(Document, name=name)
    sp = get_object_or_404(doc.presentations, session_id=session_id)

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
                doc.presentations.filter(pk=sp.pk).update(rev=None if new_selection=='current' else new_selection)
                if doc.type_id == "slides" and hasattr(settings, "MEETECHO_API_CONFIG"):
                    sm = SlidesManager(api_config=settings.MEETECHO_API_CONFIG)
                    try:
                        sm.send_update(sp.session)
                    except MeetechoAPIError as err:
                        log.log(f"Error in SlidesManager.send_update(): {err}")
                c = DocEvent(type="added_comment", doc=doc, rev=doc.rev, by=request.user.person)
                c.desc = "Revision for session %s changed to  %s" % (sp.session,new_selection)
                c.save()
            return redirect('ietf.doc.views_doc.all_presentations', name=name)
    else:
        form = VersionForm(choices=choices,initial=initial)

    return render(request,'doc/edit_sessionpresentation.html', {'sp': sp, 'form': form })

def remove_sessionpresentation(request,name,session_id):
    doc = get_object_or_404(Document, name=name)
    sp = get_object_or_404(doc.presentations, session_id=session_id)

    if not sp.session.can_manage_materials(request.user):
        raise Http404

    if sp.session.is_material_submission_cutoff() and not has_role(request.user, "Secretariat"):
        raise Http404

    if request.method == 'POST':
        doc.presentations.filter(pk=sp.pk).delete()
        if doc.type_id == "slides" and hasattr(settings, "MEETECHO_API_CONFIG"):
            sm = SlidesManager(api_config=settings.MEETECHO_API_CONFIG)
            try:
                sm.delete(sp.session, doc)
            except MeetechoAPIError as err:
                log.log(f"Error in SlidesManager.delete(): {err}")
        c = DocEvent(type="added_comment", doc=doc, rev=doc.rev, by=request.user.person)
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
    sessions = sort_sessions([s for s in sessions if not s.presentations.filter(document=doc).exists()])
    if doc.group:
        sessions = sorted(sessions,key=lambda x:0 if x.group==doc.group else 1)

    session_choices = [(s.pk, str(s)) for s in sessions]

    if request.method == 'POST':
        version_form = VersionForm(request.POST,choices=version_choices)
        session_form = SessionChooserForm(request.POST,choices=session_choices)
        if version_form.is_valid() and session_form.is_valid():
            session_id = session_form.cleaned_data['session']
            version = version_form.cleaned_data['version']
            rev = None if version=='current' else version
            if doc.type_id == "slides":
                max_order = SessionPresentation.objects.filter(
                    document__type='slides',
                    session__pk=session_id,
                ).aggregate(Max('order'))['order__max'] or 0
                order = max_order + 1
            else:
                order = 0
            sp = doc.presentations.create(
                session_id=session_id,
                rev=rev,
                order=order,
            )
            if doc.type_id == "slides" and hasattr(settings, "MEETECHO_API_CONFIG"):
                sm = SlidesManager(api_config=settings.MEETECHO_API_CONFIG)
                try:
                    sm.add(sp.session, doc, order=sp.order)
                except MeetechoAPIError as err:
                    log.log(f"Error in SlidesManager.add(): {err}")
            c = DocEvent(type="added_comment", doc=doc, rev=doc.rev, by=request.user.person)
            c.desc = "%s to session: %s" % ('Added -%s'%rev if rev else 'Added', Session.objects.get(pk=session_id))
            c.save()
            return redirect('ietf.doc.views_doc.all_presentations', name=name)

    else: 
        version_form = VersionForm(choices=version_choices,initial={'version':'current'})
        session_form = SessionChooserForm(choices=session_choices)

    return render(request,'doc/add_sessionpresentation.html',{'doc':doc,'version_form':version_form,'session_form':session_form})

def all_presentations(request, name):
    doc = get_object_or_404(Document, name=name)

    sessions = add_event_info_to_session_qs(
        doc.session_set.filter(type__in=['regular','plenary','other'])
    ).filter(current_status__in=['sched','schedw','appr','canceled'])

    future, in_progress, recent, past = group_sessions(sessions)

    return render(request, 'doc/material/all_presentations.html', {
        'user': request.user,
        'doc': doc,
        'future': future,
        'in_progress': in_progress,
        'past' : past+recent,
        })


def idnits2_rfcs_obsoleted(request):
    filename = os.path.join(settings.DERIVED_DIR,'idnits2-rfcs-obsoleted')
    try:
        with open(filename,'rb') as f:
            blob = f.read()
            return HttpResponse(blob,content_type='text/plain;charset=utf-8')
    except Exception as e:
        log.log('Failed to read idnits2-rfcs-obsoleted:'+str(e))
        raise Http404


def idnits2_rfc_status(request):
    filename = os.path.join(settings.DERIVED_DIR,'idnits2-rfc-status')
    try:
        with open(filename,'rb') as f:
            blob = f.read()
            return HttpResponse(blob,content_type='text/plain;charset=utf-8')
    except Exception as e:
        log.log('Failed to read idnits2-rfc-status:'+str(e))
        raise Http404


def idnits2_state(request, name, rev=None):
    doc = get_object_or_404(Document, name=name)
    if doc.type_id not in ["draft", "rfc"]:
        raise Http404
    zero_revision = None
    if doc.type_id == "rfc":
        draft = doc.came_from_draft()
        if draft:
            zero_revision = NewRevisionDocEvent.objects.filter(
                doc=draft, rev="00"
            ).first()
    else:
        zero_revision = NewRevisionDocEvent.objects.filter(doc=doc, rev="00").first()
    if zero_revision:
        doc.created = zero_revision.time
    else:
        if doc.type_id == "draft":
            if doc.became_rfc():
                interesting_event = (
                    doc.became_rfc()
                    .docevent_set.filter(type="published_rfc")
                    .order_by("-time")
                    .first()
                )
            else:
                interesting_event = doc.docevent_set.order_by(
                    "-time"
                ).first()  # Is taking the most _recent_ instead of the oldest event correct?
        else:  # doc.type_id == "rfc"
            interesting_event = (
                doc.docevent_set.filter(type="published_rfc").order_by("-time").first()
            )
        doc.created = interesting_event.time
    if doc.std_level:
        doc.deststatus = doc.std_level.name
    elif doc.intended_std_level:
        doc.deststatus = doc.intended_std_level.name
    else:
        text = doc.text()
        if text:
            parsed_draft = PlaintextDraft(
                text=doc.text(), source=name, name_from_source=False
            )
            doc.deststatus = parsed_draft.get_status()
        else:
            doc.deststatus = "Unknown"
    return render(
        request,
        "doc/idnits2-state.txt",
        context={"doc": doc},
        content_type="text/plain;charset=utf-8",
    )

@role_required("Secretariat")
def investigate(request):
    results = None
    if request.method == "POST":
        form = InvestigateForm(request.POST)
        if form.is_valid():
            name_fragment = form.cleaned_data["name_fragment"]
            results = investigate_fragment(name_fragment)
    else:
        form = InvestigateForm()
    return render(
        request, "doc/investigate.html", context=dict(form=form, results=results)
    )
