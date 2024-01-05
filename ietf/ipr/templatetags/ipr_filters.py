# Copyright The IETF Trust 2014-2023, All Rights Reserved
# -*- coding: utf-8 -*-


import debug    # pyflakes: ignore

from django import template
from django.utils.html import format_html

from ietf.doc.models import NewRevisionDocEvent

register = template.Library()


@register.filter
def render_message_for_history(msg):
    """Format message for display in history.  Suppress the 'To' line for incoming responses
    """
    from ietf.message.models import Message
    if isinstance(msg, Message):
        if msg.to.startswith('ietf-ipr+'):
            return format_html('Date: {}<br>From: {}<br>Subject: {}<br>Cc: {}<br><br>{}',
                msg.time,msg.frm,msg.subject,msg.cc,msg.body)
        else:
            return format_html('Date: {}<br>From: {}<br>To: {}<br>Subject: {}<br>Cc: {}<br><br>{}',
                msg.time,msg.frm,msg.to,msg.subject,msg.cc,msg.body)
    else:
        return msg

@register.filter
def to_class_name(value):
    return value.__class__.__name__

def draft_rev_at_time(iprdocrel):
    draft = iprdocrel.document
    event = iprdocrel.disclosure.get_latest_event_posted()
    if event is None:
        return ("","The Internet-Draft's revision at the time this disclosure was posted could not be determined.")
    time = event.time
    if not NewRevisionDocEvent.objects.filter(doc=draft).exists():
        return ("","The Internet-Draft's revision at the time this disclosure was posted could not be determined.")
    rev_event_before = NewRevisionDocEvent.objects.filter(doc=draft, time__lte=time).order_by('-time').first()
    if rev_event_before is None:
        return ("","The Internet-Draft's initial submission was after this disclosure was posted.")
    else:
        return(rev_event_before.rev, "")

@register.filter
def no_revisions_message(iprdocrel):
    draft = iprdocrel.document
    if draft.type_id != "draft" or iprdocrel.revisions.strip() != "":
        return ""
    rev_at_time, exception = draft_rev_at_time(iprdocrel)
    current_rev = draft.rev

    first_line = "No revisions for this Internet-Draft were specified in this disclosure."
    contact_line = "Contact the discloser or patent holder if there are questions about which revisions this disclosure pertains to."

    if current_rev == "00":
        return f"{first_line} However, there is only one revision of this Internet-Draft."

    if rev_at_time:
        return f"{first_line} The Internet-Draft's revision was {rev_at_time} at the time this disclosure was posted. {contact_line}"
    else:
        return f"{first_line} {exception} {contact_line}"
    
