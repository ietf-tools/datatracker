# generation of mails 

import textwrap, datetime

from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.core.urlresolvers import reverse as urlreverse

from ietf.utils.mail import send_mail, send_mail_text
from ietf.ipr.search import iprs_from_docs
from ietf.doc.models import WriteupDocEvent, DocAlias, BallotPositionDocEvent
from ietf.person.models import Person
from ietf.wgcharter.utils import *

def email_secretariat(request, wg, type, text):
    to = ["iesg-secretary@ietf.org"]

    types = {}
    types['state'] = "State changed"
    types['state-notrev'] = "State changed to Not currently under review"
    types['state-infrev'] = "State changed to Informal review"
    types['state-intrev'] = "State changed to Internal review"
    types['state-extrev'] = "State changed to External review"
    types['state-iesgrev'] = "State changed to IESG review"
    types['state-approved'] = "Charter approved"
    types['conclude'] = "Request closing of WG"

    subject = u"Regarding WG %s: %s" % (wg.acronym, types[type])
    
    text = strip_tags(text)
    send_mail(request, to, None, subject,
              "wgcharter/email_secretariat.txt",
              dict(text=text,
                   wg_url=settings.IDTRACKER_BASE_URL + urlreverse('wg_charter', kwargs=dict(acronym=wg.acronym)),
                   charter_url=settings.IDTRACKER_BASE_URL + urlreverse('doc_view', kwargs=dict(name=wg.charter.name)),
                   )
              )

def email_state_changed(request, doc, text):
    to = [e.strip() for e in doc.notify.replace(';', ',').split(',')]
    if not to:
        return
    
    text = strip_tags(text)
    text += "\n\n"
    text += "URL: %s" % (settings.IDTRACKER_BASE_URL + doc.get_absolute_url())

    send_mail_text(request, to, None,
                   "State changed: %s-%s" % (doc.canonical_name(), doc.rev),
                   text)

    
def generate_ballot_writeup(request, doc):
    e = WriteupDocEvent()
    e.type = "changed_ballot_writeup_text"
    e.by = request.user.get_profile()
    e.doc = doc
    e.desc = u"Ballot writeup was generated"
    e.text = unicode(render_to_string("wgcharter/ballot_writeup.txt"))
    e.save()
    
    return e

def default_action_text(wg, charter, user):
    if next_approved_revision(wg.charter.rev) == "01":
        action = "Formed"
    else:
        action = "Rechartered"

    e = WriteupDocEvent(doc=charter, by=user)
    e.by = user
    e.type = "changed_action_announcement"
    e.desc = "WG action text was changed"
    e.text = render_to_string("wgcharter/action_text.txt",
                              dict(wg=wg,
                                   charter_url=settings.IDTRACKER_BASE_URL + charter.get_absolute_url(),
                                   charter_text=read_charter_text(charter),
                                   chairs=wg.role_set.filter(name="chair"),
                                   secr=wg.role_set.filter(name="secr"),
                                   techadv=wg.role_set.filter(name="techadv"),
                                   milestones=wg.groupmilestone_set.all(),
                                   ad_email=wg.ad.role_email("ad") if wg.ad else None,
                                   action_type=action,
                                   ))

    e.save()
    return e

def default_review_text(wg, charter, user):
    e = WriteupDocEvent(doc=charter, by=user)
    e.by = user
    e.type = "changed_review_announcement"
    e.desc = "WG review text was changed"
    e.text = render_to_string("wgcharter/review_text.txt",
                              dict(wg=wg,
                                   charter_url=settings.IDTRACKER_BASE_URL + charter.get_absolute_url(),
                                   charter_text=read_charter_text(charter),
                                   chairs=wg.role_set.filter(name="chair"),
                                   secr=wg.role_set.filter(name="secr"),
                                   techadv=wg.role_set.filter(name="techadv"),
                                   milestones=wg.groupmilestone_set.all(),
                                   ad_email=wg.ad.role_email("ad") if wg.ad else None,
                                   review_date=(datetime.date.today() + datetime.timedelta(weeks=1)).isoformat(),
                                   review_type="new" if wg.state_id == "proposed" else "recharter",
                                   )
                              )
    e.save()
    return e

def generate_issue_ballot_mail(request, doc, ballot):
    active_ads = Person.objects.filter(email__role__name="ad", email__role__group__state="active").distinct()
    
    seen = []
    positions = []
    for p in BallotPositionDocEvent.objects.filter(doc=doc, type="changed_ballot_position", ballot=ballot).order_by("-time", '-id').select_related('ad'):
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
            if not p.pos or not p.pos.blocking:
                p.discuss = ""
            if p.comment or p.discuss:
                ad_feedback.append(p)
        else:
            inactive_ad_positions.append(fmt)
        
    active_ad_positions.sort()
    inactive_ad_positions.sort()
    ad_feedback.sort(key=lambda p: p.ad.plain_name())

    e = doc.latest_event(WriteupDocEvent, type="changed_action_announcement")
    approval_text = e.text if e else ""

    e = doc.latest_event(WriteupDocEvent, type="changed_ballot_writeup_text")
    ballot_writeup = e.text if e else ""

    return render_to_string("wgcharter/issue_ballot_mail.txt",
                            dict(doc=doc,
                                 doc_url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url(),
                                 active_ad_positions=active_ad_positions,
                                 inactive_ad_positions=inactive_ad_positions,
                                 ad_feedback=ad_feedback,
                                 approval_text=approval_text,
                                 ballot_writeup=ballot_writeup,
                                 )
                            )

