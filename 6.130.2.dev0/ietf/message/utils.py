# Copyright The IETF Trust 2012-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import re, datetime, email

from django.utils.encoding import force_str

from ietf.utils.mail import send_mail_text, send_mail_mime
from ietf.message.models import Message

first_dot_on_line_re = re.compile(r'^\.', re.MULTILINE)

def infer_message(s):
    parsed = email.message_from_string(s)

    m = Message(
        subject = parsed.get("Subject", ""),
        frm = parsed.get("From", ""),
        to = parsed.get("To", ""),
        cc = parsed.get("Cc", ""),
        bcc = parsed.get("Bcc", ""),
        reply_to = parsed.get("Reply-To", ""),
        body = parsed.get_payload(),
        content_type = parsed.get_content_type(),
    )

    return m

def send_scheduled_message_from_send_queue(queue_item):
    message = queue_item.message

    # for some reason, the old Perl code base substituted away . on line starts
    body = first_dot_on_line_re.sub("", message.body)
    
    extra = {}
    if message.reply_to:
        extra['Reply-To'] = message.get('reply_to')

    # announcement.content_type can contain a case-sensitive parts separator,
    # so we need to keep it as is, not lowercased, but we want a lowercased
    # version for the coming comparisons.
    content_type_lowercase = message.content_type.lower()
    if not content_type_lowercase or 'text/plain' in content_type_lowercase:
        send_mail_text(None, message.to, message.frm, message.subject,
                       body, cc=message.cc, bcc=message.bcc)
    elif 'multipart' in content_type_lowercase:
        # make body a real message so we can parse it
        body = ("MIME-Version: 1.0\r\nContent-Type: %s\r\n" % message.content_type) + body
        
        msg = email.message_from_string(force_str(body))
        send_mail_mime(None, message.to, message.frm, message.subject,
                       msg, cc=message.cc, bcc=message.bcc)

    queue_item.sent_at = datetime.datetime.now()
    queue_item.save()

    queue_item.message.sent = queue_item.sent_at
    queue_item.message.save()
