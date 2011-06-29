import re, datetime, email

from django.conf import settings

from ietf.utils.mail import send_mail_text, send_mail_mime

first_dot_on_line_re = re.compile(r'^\.', re.MULTILINE)

def send_scheduled_announcement(announcement):
    # for some reason, the old Perl code base substituted away . on line starts
    body = first_dot_on_line_re.sub("", announcement.body)
    
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


def send_scheduled_announcementREDESIGN(send_queue):
    message = send_queue.message
    
    # for some reason, the old Perl code base substituted away . on line starts
    body = first_dot_on_line_re.sub("", message.body)
    
    extra = {}
    if message.reply_to:
        extra['Reply-To'] = message.reply_to

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
        
        msg = email.message_from_string(body.encode("utf-8"))
        send_mail_mime(None, message.to, message.frm, message.subject,
                       msg, cc=message.cc, bcc=message.bcc)

    send_queue.sent_at = datetime.datetime.now()
    send_queue.save()

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    send_scheduled_announcement = send_scheduled_announcementREDESIGN
