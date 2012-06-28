# generation of mails 

import textwrap, datetime

from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils.text import wrap
from django.conf import settings
from django.core.urlresolvers import reverse as urlreverse

from ietf.utils.mail import send_mail, send_mail_text

def email_milestones_changed(request, group, text):
    to = []
    if group.ad:
        to.append(group.ad.role_email("ad").formatted_email())

    for r in group.role_set.filter(name="chair"):
        to.append(r.formatted_email())

    text = wrap(strip_tags(text), 70)
    text += "\n\n"
    text += "URL: %s" % (settings.IDTRACKER_BASE_URL + urlreverse("wg_charter", kwargs=dict(acronym=group.acronym)))

    send_mail_text(request, to, None,
                   "Milestones changed for %s %s" % (group.acronym, group.type.name),
                   text)
