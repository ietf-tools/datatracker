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

from django import template
from django.core.urlresolvers import reverse as urlreverse
from django.conf import settings
from ietf.idtracker.models import IDInternal, BallotInfo
from ietf.idrfc.idrfc_wrapper import position_to_string, BALLOT_ACTIVE_STATES
from ietf.idtracker.templatetags.ietf_filters import in_group, timesince_days
from ietf.ietfauth.decorators import has_role
from ietf.doc.models import BallotDocEvent

register = template.Library()

def get_user_name(context):
    if 'user' in context and context['user'].is_authenticated():
        if settings.USE_DB_REDESIGN_PROXY_CLASSES:
            from ietf.person.models import Person
            try:
                return context['user'].get_profile().plain_name()
            except Person.DoesNotExist:
                return None

        person = context['user'].get_profile().person()
        if person:
            return str(person)
    return None

def render_ballot_icon(user, doc):
    if not doc:
        return ""

    if doc.type_id == "draft":
        s = doc.get_state("draft-iesg")
        if s and s.name not in BALLOT_ACTIVE_STATES:
            return ""
    elif doc.type_id == "charter":
        if doc.get_state_slug() not in ("intrev", "iesgrev"):
            return ""

    ballot = doc.latest_event(BallotDocEvent, type="created_ballot")
    if not ballot:
        return ""

    edit_position_url = urlreverse('ietf.idrfc.views_ballot.edit_position', kwargs=dict(name=doc.name, ballot_id=ballot.pk))

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

    cm = ""
    if has_role(user, "Area Director"):
        cm = ' oncontextmenu="editBallot(\''+str(edit_position_url)+'\');return false;"'

    res = ['<table class="ballot_icon" title="IESG Evaluation Record (click to show more, right-click to edit position)" onclick="showBallot(\'' + doc.name + '\',\'' + str(edit_position_url) + '\')"' + cm + '>']

    res.append("<tr>")

    for i, (ad, pos) in enumerate(positions):
        if i > 0 and i % 5 == 0:
            res.append("</tr>")
            res.append("<tr>")

        c = "position-%s" % (pos.pos.slug if pos else "norecord")

        if ad.user_id == user.id:
            c += " my"

        res.append('<td class="%s" />' % c)

    res.append("</tr>")
    res.append("</table>")

    return "".join(res)

class BallotIconNode(template.Node):
    def __init__(self, doc_var):
        self.doc_var = doc_var
    def render(self, context):
        doc = template.resolve_variable(self.doc_var, context)
        if hasattr(doc, "_idinternal"):
            # hack for old schema
            doc = doc._idinternal
        return render_ballot_icon(context.get("user"), doc)

def do_ballot_icon(parser, token):
    try:
        tagName, docName = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError, "%r tag requires exactly two arguments" % token.contents.split()[0]
    return BallotIconNode(docName)

register.tag('ballot_icon', do_ballot_icon)

@register.filter
def my_position(doc, user):
    user_name = get_user_name({'user':user})
    if not user_name:
        return None
    if not in_group(user, "Area_Director"):
        return None
    if not doc.in_ietf_process():
        return None
    if not doc.ietf_process.has_iesg_ballot():
        return None
    ballot = doc.ietf_process.iesg_ballot()
    return ballot.position_for_ad(user_name)

@register.filter
def state_age_colored(doc):
    if not doc.in_ietf_process():
        return ""
    if doc.is_id_wrapper and not doc.draft_status in ["Active", "RFC"]:
        # Don't show anything for expired/withdrawn/replaced drafts
        return ""
    main_state = doc.ietf_process.main_state
    sub_state = doc.ietf_process.sub_state
    if main_state in ["Dead","AD is watching","RFC Published"]:
        return ""
    days = timesince_days(doc.ietf_process.state_date())
    # loosely based on 
    # http://trac.tools.ietf.org/group/iesg/trac/wiki/PublishPath
    if main_state == "In Last Call":
        goal1 = 30
        goal2 = 30
    elif main_state == "RFC Ed Queue":
        goal1 = 60
        goal2 = 120
    elif main_state in ["Last Call Requested", "Approved-announcement to be sent"]:
        goal1 = 4
        goal2 = 7
    elif sub_state == "Revised ID Needed":
        goal1 = 14
        goal2 = 28
    elif main_state == "Publication Requested":
        goal1 = 7
        goal2 = 14
    elif main_state == "AD Evaluation":
        goal1 = 14
        goal2 = 28
    else:
        goal1 = 14
        goal2 = 28
    if days > goal2:
        class_name = "ietf-small ietf-highlight-r"
    elif days > goal1:
        class_name = "ietf-small ietf-highlight-y"
    else:
        class_name = "ietf-small"
    if days > goal1:
        title = ' title="Goal is &lt;%d days"' % (goal1,)
    else:
        title = ''
    return '<span class="%s"%s>(for&nbsp;%d&nbsp;day%s)</span>' % (class_name,title,days,('','s')[days != 1])
