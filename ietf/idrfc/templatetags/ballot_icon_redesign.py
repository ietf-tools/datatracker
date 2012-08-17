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
from django.db.models import Q
from ietf.idtracker.models import IDInternal, BallotInfo
from ietf.idrfc.idrfc_wrapper import position_to_string, BALLOT_ACTIVE_STATES
from ietf.idtracker.templatetags.ietf_filters import in_group, timesince_days
from ietf.ietfauth.decorators import has_role
from ietf.doc.models import BallotDocEvent, BallotPositionDocEvent

from datetime import date


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
    elif doc.type_id == "conflrev":
       if doc.get_state_slug() not in ("iesgeval","defer"):
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

        if hasattr(user, "get_profile") and ad == user.get_profile():
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
        #if hasattr(doc, "_idinternal"):
        #    # hack for old schema
        #    doc = doc._idinternal
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
    ballot = doc.active_ballot()
    pos = "No Record"
    if ballot:
      changed_pos = doc.latest_event(BallotPositionDocEvent, type="changed_ballot_position", ad__name=user_name, ballot=ballot)
      if changed_pos:
        pos = changed_pos.pos.name;
    return pos

@register.filter
def state_age_colored(doc):
    if doc.type.slug == 'draft':
        if not doc.latest_event(type='started_iesg_process'):
            return ""
        if not doc.get_state_slug() in ["active", "rfc"]:
            # Don't show anything for expired/withdrawn/replaced drafts
            return ""
        main_state = doc.get_state('draft-iesg')
        IESG_SUBSTATE_TAGS = ('point', 'ad-f-up', 'need-rev', 'extpty')
        sub_states = doc.tags.filter(slug__in=IESG_SUBSTATE_TAGS)

        if main_state.slug in ["dead","watching","pub"]:
            return ""
        try:
            state_date = doc.docevent_set.filter(
                              Q(desc__istartswith="Draft Added by ")|
                              Q(desc__istartswith="Draft Added in state ")|
                              Q(desc__istartswith="Draft added in state ")|
                              Q(desc__istartswith="State changed to ")|
                              Q(desc__istartswith="State Changes to ")|
                              Q(desc__istartswith="Sub state has been changed to ")|
                              Q(desc__istartswith="State has been changed to ")|
                              Q(desc__istartswith="IESG has approved and state has been changed to")|
                              Q(desc__istartswith="IESG process started in state")
                          ).order_by('-time')[0].time.date() 
        except IndexError:
            state_date = date(1990,1,1)
        days = timesince_days(state_date)
        # loosely based on 
        # http://trac.tools.ietf.org/group/iesg/trac/wiki/PublishPath
        if main_state.slug == "lc":
            goal1 = 30
            goal2 = 30
        elif main_state.slug == "rfcqueue":
            goal1 = 60
            goal2 = 120
        elif main_state.slug in ["lc-req", "ann"]:
            goal1 = 4
            goal2 = 7
        elif 'need-rev' in [x.slug for x in sub_states]:
            goal1 = 14
            goal2 = 28
        elif main_state.slug == "pub-req":
            goal1 = 7
            goal2 = 14
        elif main_state.slug == "ad-eval":
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
    else:
        return ""
