# generation of mails 

import textwrap
from datetime import datetime, date, time, timedelta

from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.core.urlresolvers import reverse as urlreverse

from ietf.utils.mail import send_mail, send_mail_text
from ietf.idtracker.models import *
from ietf.ipr.search import iprs_from_docs
from redesign.doc.models import WriteupDocEvent, DocAlias, GroupBallotPositionDocEvent
from redesign.person.models import Person

# These become part of the subject of the email
types = {}
types['state'] = "State changed"
types['state-notrev'] = "State changed to Not currently under review"
types['state-infrev'] = "State changed to Informal review"
types['state-intrev'] = "State changed to Internal review"
types['state-extrev'] = "State changed to External review"
types['state-iesgrev'] = "State changed to IESG review"
types['state-approved'] = "Charter approved"
types['conclude'] = "Request closing of WG"

def email_secretariat(request, wg, type, text):
    to = ["iesg-secretary@ietf.org"]
    
    text = strip_tags(text)
    send_mail(request, to, None,
              "Regarding WG %s: %s" % (wg.acronym, types[type]),
              "wgcharter/email_secretariat.txt",
              dict(text=text,
                   url=settings.IDTRACKER_BASE_URL + urlreverse('wg_view', kwargs=dict(name=wg.acronym))))

def generate_ballot_writeup(request, doc):
    e = WriteupDocEvent()
    e.type = "changed_ballot_writeup_text"
    e.by = request.user.get_profile()
    e.doc = doc
    e.desc = u"Ballot writeup was generated"
    e.text = unicode(render_to_string("wgcharter/ballot_writeup.txt"))
    e.save()
    
    return e

def generate_issue_ballot_mail(request, charter):
    active_ads = Person.objects.filter(email__role__name="ad", email__role__group__state="active").distinct()
    
    e = charter.latest_event(type="started_iesg_process")
    seen = []
    positions = []
    for p in GroupBallotPositionDocEvent.objects.filter(doc=charter, type="changed_ballot_position", time__gte=e.time).order_by("-time", '-id').select_related('ad'):
        if p.ad not in seen:
            positions.append(p)
            seen.append(p.ad)

    # format positions and setup blocking and non-blocking comments
    ad_feedback = []
    seen = set()
    active_ad_positions = []
    inactive_ad_positions = []
    for p in positions:
        if p.ad in seen:
            continue

        seen.add(p.ad)
        
        def formatted(val):
            if val:
                return "[ X ]"
            else:
                return "[   ]"

        fmt = u"%-21s%-6s%-6s%-8s%-7s" % (
            p.ad.plain_name(),
            formatted(p.pos_id == "yes"),
            formatted(p.pos_id == "no"),
            formatted(p.pos_id == "block"),
            formatted(p.pos_id == "abstain"),
            )

        if p.ad in active_ads:
            active_ad_positions.append(fmt)
            if not p.pos_id == "block":
                p.block_comment = ""
            if p.comment or p.block_comment:
                ad_feedback.append(p)
        else:
            inactive_ad_positions.append(fmt)
        
    active_ad_positions.sort()
    inactive_ad_positions.sort()
    ad_feedback.sort(key=lambda p: p.ad.plain_name())

    e = charter.latest_event(WriteupDocEvent, type="changed_action_announcement")
    approval_text = e.text if e else ""

    e = charter.latest_event(WriteupDocEvent, type="changed_ballot_writeup_text")
    ballot_writeup = e.text if e else ""

    return render_to_string("wgcharter/issue_ballot_mail.txt",
                            dict(charter=charter,
                                 charter_url=settings.IDTRACKER_BASE_URL + charter.get_absolute_url(),
                                 active_ad_positions=active_ad_positions,
                                 inactive_ad_positions=inactive_ad_positions,
                                 ad_feedback=ad_feedback,
                                 approval_text=approval_text,
                                 ballot_writeup=ballot_writeup,
                                 )
                            )

