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
from redesign.doc.models import WriteupDocEvent, BallotPositionDocEvent, LastCallDocEvent, DocAlias
from redesign.person.models import Person

# These become part of the subject of the email
types = {}
types['state'] = "State changed"
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
              "wgrecord/email_secretariat.txt",
              dict(text=text,
                   url=settings.IDTRACKER_BASE_URL + urlreverse('wg_view_record', kwargs=dict(name=wg.acronym))))

