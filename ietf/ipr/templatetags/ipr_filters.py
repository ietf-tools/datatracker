# Copyright The IETF Trust 2014, All Rights Reserved

from django import template
from django.utils.safestring import mark_safe


register = template.Library()


# @register.filter
# def first_type(queryset, type):
#     first = queryset.filter(type_id=type).first()
#     return first.time if first else None

@register.filter
def render_message_for_history(msg):
    """Format message for display in history.  Suppress the 'To' line for incoming responses
    """
    if msg.to.startswith('ietf-ipr+'):
        text = u'''Date: {}
From: {}
Subject: {}
Cc: {}

<pre>{}</pre>'''.format(msg.time,msg.frm,msg.subject,msg.cc,msg.body)
    else:
        text = u'''Date: {}
From: {}
To: {}
Subject: {}
Cc: {}

<pre>{}</pre>'''.format(msg.time,msg.frm,msg.to,msg.subject,msg.cc,msg.body)
    return mark_safe(text)

@register.filter
def to_class_name(value):
    return value.__class__.__name__
