# Copyright The IETF Trust 2011, All Rights Reserved

from django import template
from django.core.urlresolvers import reverse as urlreverse
from django.conf import settings
from ietf.idtracker.templatetags.ietf_filters import in_group, timesince_days
from redesign.doc.models import GroupBallotPositionDocEvent
from redesign.person.models import Person
from redesign.group.models import Group

register = template.Library()

def get_user_adid(context):
    if 'user' in context and in_group(context['user'], "Area_Director"):
        return context['user'].get_profile().id
    else:
        return None

def get_user_name(context):
    if 'user' in context and context['user'].is_authenticated():
        from person.models import Person
        try:
            return context['user'].get_profile().plain_name()
        except Person.DoesNotExist:
            return None
    
def render_ballot_icon(context, name):
    wg = Group.objects.get(acronym=name)
    doc = wg.charter
    adId = get_user_adid(context)
    red = 0
    green = 0
    yellow = 0
    gray = 0
    blank = 0
    my = None

    active_ads = list(Person.objects.filter(email__role__name="ad",
                                            email__role__group__type="area",
                                            email__role__group__state="active").distinct())
    started_process = doc.latest_event(type="started_iesg_process")
    latest_positions = []
    for p in active_ads:
        p_pos = list(GroupBallotPositionDocEvent.objects.filter(doc=doc, ad=p).order_by("-time"))
        if p_pos != []:
            latest_positions.append(p_pos[0])
    for p in latest_positions:
        if not p.pos_id:
            blank = blank + 1
        elif (p.pos_id == "yes"):
            green = green + 1
        elif (p.pos_id == "no"):
            green = green + 1
        elif (p.pos_id == "block"):
            red = red + 1
        elif (p.pos_id == "abstain"):
            yellow = yellow + 1
        else:
            blank = blank + 1
        if adId and (p.ad_id == adId):
            my = p.pos.name
    return render_ballot_icon2(wg.acronym, red,yellow,green,gray,blank, my, adId)+"<!-- adId="+str(adId)+" my="+str(my)+"-->"

def render_ballot_icon2(acronym, red,yellow,green,gray,blank, my, adId):
    edit_position_url = urlreverse('wg_edit_position', kwargs=dict(name=acronym))
    if adId:
        res_cm = ' oncontextmenu="editWGBallot(\''+str(edit_position_url)+'\');return false;"'
    else:
        res_cm = ''
    res = '<table class="ballot_icon" title="IESG Review (click to show more, right-click to edit position)" onclick="showWGBallot(\'' + acronym + '\',\'' + str(edit_position_url) + '\')"'+res_cm+'>'
    for y in range(3):
        res = res + "<tr>"
        for x in range(5):
            myMark = False
            if red > 0:
                c = "ballot_icon_red"
                red = red - 1
                myMark = (my == "Block")
            elif yellow > 0:
                c = "ballot_icon_yellow"
                yellow = yellow - 1
                myMark = (my == "Abstain")
            elif green > 0:
                c = "ballot_icon_green"
                green = green - 1
                myMark = (my == "Yes") or (my == "No")
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

register.tag('wg_ballot_icon', do_ballot_icon)

@register.filter
def my_position(doc, user):
    user_name = get_user_name({'user':user})
    p_pos = list(GroupBallotPositionDocEvent.objects.filter(doc=doc, ad=Person.objects.get(user__name=user_name)).order_by("-time"))
    if p_pos == []:
        return "No record"
    else:
        return p_pos[0].pos.name

