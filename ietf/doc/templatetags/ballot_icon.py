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
from django.core.urlresolvers import reverse as urlreverse
from django.db.models import Q
from django.utils.safestring import mark_safe

from ietf.ietfauth.utils import user_is_person, has_role
from ietf.doc.models import BallotPositionDocEvent, IESG_BALLOT_ACTIVE_STATES
from ietf.name.models import BallotPositionName


register = template.Library()

@register.filter
def showballoticon(doc):
    if doc.type_id == "draft":
        if doc.get_state_slug("draft-iesg") not in IESG_BALLOT_ACTIVE_STATES:
            return False
    elif doc.type_id == "charter":
        if doc.get_state_slug() not in ("intrev", "extrev", "iesgrev"):
            return False
    elif doc.type_id == "conflrev":
       if doc.get_state_slug() not in ("iesgeval","defer"):
           return False
    elif doc.type_id == "statchg":
       if doc.get_state_slug() not in ("iesgeval","defer"):
           return False

    return True

@register.simple_tag(takes_context=True)
def ballot_icon(context, doc):
    user = context.get("user")

    if not doc:
        return ""

    if not showballoticon(doc):
        return ""

    ballot = doc.active_ballot()
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

    positions = list(doc.active_ballot().active_ad_positions().items())
    positions.sort(key=sort_key)

    right_click_string = ''
    if has_role(user, "Area Director"):
        right_click_string = 'oncontextmenu="window.location.href=\'%s\';return false;"' %  urlreverse('ietf.doc.views_ballot.edit_position', kwargs=dict(name=doc.name, ballot_id=ballot.pk))

    my_blocking = False
    for i, (ad, pos) in enumerate(positions):
        if user_is_person(user,ad) and pos and pos.pos.blocking:
            my_blocking = True
            break

    res = ['<a %s href="%s" data-toggle="modal" data-target="#modal-%d" title="IESG positions (click to show more)" class="ballot-icon"><table' % (
            right_click_string,
            urlreverse("ietf.doc.views_doc.ballot_popup", kwargs=dict(name=doc.name, ballot_id=ballot.pk)),
            ballot.pk,)]
    if my_blocking:
        res.append(' class="is-blocking" ')
    res.append('>')

    res.append("<tr>")

    for i, (ad, pos) in enumerate(positions):
        if i > 0 and i % 5 == 0:
            res.append("</tr><tr>")

        c = "position-%s" % (pos.pos.slug if pos else "norecord")

        if user_is_person(user, ad):
            c += " my"

        res.append('<td class="%s"></td>' % c)

    # add sufficient table calls to last row to avoid HTML validation warning
    while (i + 1) % 5 != 0:
        res.append('<td class="empty"></td>')
        i = i + 1

    res.append("</tr></table></a>")
    # XXX FACELIFT: Loading via href will go away in bootstrap 4.
    # See http://getbootstrap.com/javascript/#modals-usage
    res.append('<div id="modal-%d" class="modal fade" tabindex="-1" role="dialog" aria-hidden="true"><div class="modal-dialog modal-lg"><div class="modal-content"></div></div></div>' % ballot.pk)

    return "".join(res)

@register.filter
def ballotposition(doc, user):
    if not showballoticon(doc) or not has_role(user, "Area Director"):
        return None

    ballot = doc.active_ballot()
    if not ballot:
        return None

    changed_pos = doc.latest_event(BallotPositionDocEvent, type="changed_ballot_position", ad__user=user, ballot=ballot)
    if changed_pos:
        pos = changed_pos.pos
    else:
        pos = BallotPositionName.objects.get(slug="norecord")
    return pos


@register.filter
def state_age_colored(doc):
    if doc.type_id == 'draft':
        if not doc.get_state_slug() in ["active", "rfc"]:
            # Don't show anything for expired/withdrawn/replaced drafts
            return ""
        iesg_state = doc.get_state_slug('draft-iesg')
        if not iesg_state:
            return ""

        if iesg_state in ["dead", "watching", "pub"]:
            return ""
        try:
            state_date = doc.docevent_set.filter(
                              Q(type="started_iesg_process")|
                              Q(type="changed_state", statedocevent__state_type="draft-iesg")
            ).order_by('-time')[0].time.date()
        except IndexError:
            state_date = datetime.date(1990,1,1)
        days = (datetime.date.today() - state_date).days
        # loosely based on
        # http://trac.tools.ietf.org/group/iesg/trac/wiki/PublishPath
        if iesg_state == "lc":
            goal1 = 30
            goal2 = 30
        elif iesg_state == "rfcqueue":
            goal1 = 60
            goal2 = 120
        elif iesg_state in ["lc-req", "ann"]:
            goal1 = 4
            goal2 = 7
        elif 'need-rev' in [x.slug for x in doc.tags.all()]:
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
            class_name = "label label-danger"
        elif days > goal1:
            class_name = "label label-warning"
        else:
            class_name = "ietf-small"
        if days > goal1:
            title = ' title="Goal is &lt;%d days"' % (goal1,)
        else:
            title = ''
        return mark_safe('<span class="%s"%s>for %d day%s</span>' % (
                class_name, title, days,
                's' if days != 1 else ''))
    else:
        return ""
