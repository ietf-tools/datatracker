# Copyright (C) 2009 Nokia Corporation and/or its subsidiary(-ies).
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
from ietf.idtracker.models import BallotInfo
from ietf.idrfc.idrfc_wrapper import position_to_string

register = template.Library()

def render_ballot_icon(context, doc):
    if not doc.has_active_iesg_ballot():
        return ""
    ballot = BallotInfo.objects.get(ballot=doc.iesg_ballot_id())
    if 'adId' in context:
        adId = context['adId']
    else:
        adId = None
    red = 0
    green = 0
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
        else:
            gray = gray + 1
        if adId and (p['ad'].id == adId):
            my = position_to_string(p['pos'])
    return render_ballot_icon2(doc.draft_name, doc.tracker_id, red,green,gray,blank,my)+"<!-- adId="+str(adId)+" my="+str(my)+"-->"

def render_ballot_icon2(draft_name, tracker_id, red,green,gray,blank,my):
    res = '<span class="ballot_icon_wrapper"><table class="ballot_icon" title="IESG Evaluation Record (click to show more)" onclick="showBallot(\'' + draft_name + '\',' + str(tracker_id) + ')">'
    for y in range(3):
        res = res + "<tr>"
        for x in range(5):
            myMark = False
            if red > 0:
                c = "ballot_icon_red"
                red = red - 1
                myMark = (my == "Discuss")
            elif green > 0:
                c = "ballot_icon_green"
                green = green - 1
                myMark = (my == "Yes") or (my == "No Objection")
            elif gray > 0:
                c = "ballot_icon_gray"
                gray = gray - 1
                myMark = (my == "Abstain") or (my == "Recuse")
            else:
                c = ""
                myMark = (y == 2) and (x == 4) and (my == "No Record")
            if myMark:
                res = res + '<td class="'+c+' ballot_icon_my" />' 
                my = None
            else:
                res = res + '<td class="'+c+'" />'
        res = res + '</tr>'
    res = res + '</table></span>'
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
