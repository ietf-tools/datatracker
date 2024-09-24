# Copyright The IETF Trust 2012-2021, All Rights Reserved
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

import datetime

import debug      # pyflakes:ignore

from django import template
from django.urls import reverse as urlreverse
from django.db.models import Q
from django.utils import timezone
from django.utils.safestring import mark_safe

from ietf.ietfauth.utils import user_is_person, has_role
from ietf.doc.models import BallotPositionDocEvent, IESG_BALLOT_ACTIVE_STATES
from ietf.name.models import BallotPositionName


register = template.Library()

@register.filter
def showballoticon(doc):
    if doc.type_id == "draft":
        if doc.stream_id == 'ietf' and doc.get_state_slug("draft-iesg") not in IESG_BALLOT_ACTIVE_STATES:
            return False
        elif doc.stream_id == 'irtf' and doc.get_state_slug("draft-stream-irtf") != "irsgpoll":
            return False
        elif doc.stream_id == 'editorial' and doc.get_state_slug("draft-stream-rsab") != "rsabpoll":
            return False
    elif doc.type_id == "charter":
        if doc.get_state_slug() not in ("intrev", "extrev", "iesgrev"):
            return False
    elif doc.type_id == "conflrev":
       if doc.get_state_slug() not in ("iesgeval","defer"):
           return False
    elif doc.type_id == "statchg":
       if doc.get_state_slug() not in ("iesgeval","defer", "in-lc"):
           return False

    return True

@register.simple_tag(takes_context=True)
def ballot_icon(context, doc):
    user = context.get("user")

    if not doc:
        return ""

    if not showballoticon(doc):
        return ""

    ballot = doc.ballot if hasattr(doc, 'ballot') else doc.active_ballot()

    if not ballot:
        return ""

    def sort_key(t):
        _, pos = t
        if not pos:
            return (2, 0)
        elif pos.pos.blocking:
            return (0, pos.pos.order)
        else:
            return (1, pos.pos.order)

    positions = list(ballot.active_balloter_positions().items())
    positions.sort(key=sort_key)

    request = context.get("request")
    ballot_edit_return_point_param = f"ballot_edit_return_point={request.path}"

    right_click_string = ''
    if has_role(user, "Area Director"):
        right_click_string = 'oncontextmenu="window.location.href=\'{}?{}\';return false;"'.format(
            urlreverse('ietf.doc.views_ballot.edit_position', kwargs=dict(name=doc.name, ballot_id=ballot.pk)),
            ballot_edit_return_point_param)

    my_blocking = False
    for i, (balloter, pos) in enumerate(positions):
        if user_is_person(user,balloter) and pos and pos.pos.blocking:
            my_blocking = True
            break

    typename = "Unknown"
    if ballot.ballot_type.slug == "irsg-approve":
        typename = "IRSG"
    elif ballot.ballot_type.slug == "rsab-approve":
        typename = "RSAB"
    else:
        typename = "IESG"
    
    modal_url = "{}?{}".format(
        urlreverse("ietf.doc.views_doc.ballot_popup", kwargs=dict(name=doc.name, ballot_id=ballot.pk)),
        ballot_edit_return_point_param)

    res = ['<a %s href="%s" data-bs-toggle="modal" data-bs-target="#modal-%d" aria-label="%s positions" title="%s positions (click to show more)" class="ballot-icon"><table' % (
            right_click_string,
            modal_url,
            ballot.pk,
            typename,
            typename,)]
    if my_blocking:
        res.append(' class="is-blocking" ')
    res.append('><tbody>')

    res.append("<tr>")

    for i, (ad, pos) in enumerate(positions):
        # The IRSG has many more members than the IESG, so make the table wider
        if i > 0 and i % (5 if len(positions) <= 15 else 10) == 0:
            res.append("</tr><tr>")

        c = "position-%s" % (pos.pos.slug if pos else "norecord")

        if user_is_person(user, ad):
            c += " my"

        res.append('<td class="%s"></td>' % c)

    # add sufficient table calls to last row to avoid HTML validation warning
    while (i + 1) % 5 != 0:
        res.append('<td class="position-empty"></td>')
        i = i + 1

    res.append("</tr></tbody></table></a>")
    res.append('<div id="modal-%d" class="modal fade" tabindex="-1" role="dialog" aria-hidden="true"><div class="modal-dialog modal-dialog-scrollable modal-xl modal-fullscreen-lg-down"><div class="modal-content"></div></div></div>' % ballot.pk)

    return mark_safe("".join(res))

@register.filter
def ballotposition(doc, user):
    if not showballoticon(doc) or not has_role(user, "Area Director"):
        return None

    ballot = doc.active_ballot()
    if not ballot:
        return None

    changed_pos = doc.latest_event(BallotPositionDocEvent, type="changed_ballot_position", balloter__user=user, ballot=ballot)
    if changed_pos:
        pos = changed_pos.pos
    else:
        pos = BallotPositionName.objects.get(slug="norecord")
    return pos


@register.filter
def state_age_colored(doc):
    if doc.type_id == "draft":
        if not doc.get_state_slug() in ["active", "rfc"]:
            # Don't show anything for expired/withdrawn/replaced drafts
            return ""
        iesg_state = doc.get_state_slug("draft-iesg")
        if not iesg_state:
            return ""

        if iesg_state in ["dead", "pub", "idexists"]:
            return ""
        try:
            state_datetime = (
                doc.docevent_set.filter(
                    Q(type="started_iesg_process")
                    | Q(type="changed_state", statedocevent__state_type="draft-iesg")
                )
                .order_by("-time")[0]
                .time
            )
        except IndexError:
            state_datetime = datetime.datetime(1990, 1, 1, tzinfo=datetime.timezone.utc)
        days = (timezone.now() - state_datetime).days
        # loosely based on the Publish Path page at the iesg wiki
        if iesg_state == "lc":
            goal1 = 30
            goal2 = 30
        elif iesg_state == "rfcqueue":
            goal1 = 60
            goal2 = 120
        elif iesg_state in ["lc-req", "ann"]:
            goal1 = 4
            goal2 = 7
        elif "need-rev" in [x.slug for x in doc.tags.all()]:
            goal1 = 14
            goal2 = 28
        elif iesg_state == "pub-req":
            goal1 = 7
            goal2 = 14
        elif iesg_state == "ad-eval":
            goal1 = 14
            goal2 = 28
        else:
            goal1 = 14
            goal2 = 28
        if days > goal2:
            class_name = "text-bg-danger"
        elif days > goal1:
            class_name = "text-bg-warning"
        else:
            # don't show a badge when things are in the green; clutters display
            # class_name = "text-success"
            return ""
        if days > goal1:
            title = ' title="In state for %d day%s; goal is &lt;%d days."' % (
                days,
                "s" if days != 1 else "",
                goal1,
            )
        else:
            title = ""
        return mark_safe(
            '<span class="badge rounded-pill %s" %s><i class="bi bi-clock-fill"></i> %d</span>'
            % (class_name, title, days)
        )
    else:
        return ""


@register.filter
def auth48_alert_badge(doc):
    """Return alert badge, if any, for a document"""
    if doc.type_id != 'draft':
        return ''

    iesg_state = doc.get_state_slug('draft-iesg')
    if iesg_state != 'rfcqueue':
        return ''

    rfced_state = doc.get_state_slug('draft-rfceditor')
    if rfced_state == 'auth48':
        return mark_safe('<span class="badge rounded-pill text-bg-info" title="AUTH48">AUTH48</span>')

    return ''
