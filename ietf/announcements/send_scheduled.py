import re, datetime, email

from ietf.utils.mail import send_mail_text, send_mail_mime

first_dot_on_line_re = re.compile(r'^\.', re.MULTILINE)

def send_scheduled_announcement(announcement):
    # for some reason, the old Perl code base substituted away . on line starts
    body = first_dot_on_line_re.sub("", announcement.body)
    
    announcement.content_type
    extra = {}
    if announcement.replyto:
        extra['Reply-To'] = announcement.replyto

    # announcement.content_type can contain a case-sensitive parts separator,
    # so we need to keep it as is, not lowercased, but we want a lowercased
    # version for the coming comparisons.
    content_type_lowercase = announcement.content_type.lower()
    if not content_type_lowercase or 'text/plain' in content_type_lowercase:
        send_mail_text(None, announcement.to_val, announcement.from_val, announcement.subject,
                       body, cc=announcement.cc_val, bcc=announcement.bcc_val)
    elif 'multipart/' in content_type_lowercase:
        # make body a real message so we can parse it.
        body = ("MIME-Version: 1.0\r\nContent-Type: %s\r\n" % announcement.content_type) + body
        
        msg = email.message_from_string(body.encode("utf-8"))
        send_mail_mime(None, announcement.to_val, announcement.from_val, announcement.subject,
                       msg, cc=announcement.cc_val, bcc=announcement.bcc_val)

    now = datetime.datetime.now()
    announcement.actual_sent_date = now.date()
    announcement.actual_sent_time = str(now.time())
    announcement.mail_sent = True
    announcement.save()
