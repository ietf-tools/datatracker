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
from ietf.idtracker.models import IDInternal, BallotInfo
from ietf.idrfc.idrfc_wrapper import position_to_string, BALLOT_ACTIVE_STATES
from ietf.idtracker.templatetags.ietf_filters import in_group, timesince_days

register = template.Library()

def get_user_adid(context):
    if 'user' in context and in_group(context['user'], "Area_Director"):
        return context['user'].get_profile().iesg_login_id()
    else:
        return None

def get_user_name(context):
    if 'user' in context and context['user'].is_authenticated():
        person = context['user'].get_profile().person()
        if person:
            return str(person)
    return None
    
def render_ballot_icon(context, doc):
    if isinstance(doc,IDInternal):
        try:
            ballot = doc.ballot
            if not ballot.ballot_issued:
                return ""
        except BallotInfo.DoesNotExist:
            return ""
        if str(doc.cur_state) not in BALLOT_ACTIVE_STATES:
            return ""
        if doc.rfc_flag:
            name = doc.document().filename()
        else:
            name = doc.document().filename
        tracker_id = doc.draft_id
    else:
        if doc.in_ietf_process() and doc.ietf_process.has_active_iesg_ballot():
            ballot = doc._idinternal.ballot
        else:
            return ""
        if doc.is_rfc_wrapper:
            name = "rfc"+str(doc.rfc_number)
            tracker_id = doc.rfc_number
        else:
            name = doc.draft_name
            tracker_id = doc.tracker_id
    adId = get_user_adid(context)
    red = 0
    green = 0
    yellow = 0
    gray = 0
    blank = 0
    my = None
    for p in ballot.active_positions():
        if not p['pos']:
            blank = blank + 1
        elif (p['pos'].yes > 0) or (p['pos'].noobj > 0):
            green = green + 1
        elif (p['pos'].discuss > 0):
            red = red + 1
        elif (p['pos'].abstain > 0):
            yellow = yellow + 1
        elif (p['pos'].recuse > 0):
            gray = gray + 1
        else:
            blank = blank + 1
        if adId and (p['ad'].id == adId):
            my = position_to_string(p['pos'])
    return render_ballot_icon2(name, tracker_id, red,yellow,green,gray,blank, my, adId)+"<!-- adId="+str(adId)+" my="+str(my)+"-->"

def render_ballot_icon2(draft_name, tracker_id, red,yellow,green,gray,blank, my,adId):
    edit_position_url = urlreverse('doc_edit_position', kwargs=dict(name=draft_name))
    if adId:
        res_cm = ' oncontextmenu="editBallot(\''+str(edit_position_url)+'\');return false;"'
    else:
        res_cm = ''
    res = '<table class="ballot_icon" title="IESG Evaluation Record (click to show more, right-click to edit position)" onclick="showBallot(\'' + draft_name + '\',\'' + str(edit_position_url) + '\')"'+res_cm+'>'
    for y in range(3):
        res = res + "<tr>"
        for x in range(5):
            myMark = False
            if red > 0:
                c = "ballot_icon_red"
                red = red - 1
                myMark = (my == "Discuss")
            elif yellow > 0:
                c = "ballot_icon_yellow"
                yellow = yellow - 1
                myMark = (my == "Abstain")
            elif green > 0:
                c = "ballot_icon_green"
                green = green - 1
                myMark = (my == "Yes") or (my == "No Objection")
            elif gray > 0:
                c = "ballot_icon_gray"
                gray = gray - 1
                myMark = (my == "Recuse")
            else:
                c = ""
                myMark = (y == 2) and (x == 4) and (my == "No Record")
            if myMark:
                res = res + '<td class="'+c+' ballot_icon_my" />' 
                my = None
            else:
                res = res + '<td class="'+c+'" />'
        res = res + '</tr>'
    res = res + '</table>'
    return res

       
class BallotIconNode(template.Node):
    def __init__(self, doc_var):
        self.doc_var = doc_var
    def render(self, context):
        doc = template.resolve_variable(self.doc_var, context)
        return render_ballot_icon(context, doc)

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
