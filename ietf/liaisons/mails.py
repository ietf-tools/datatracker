from django.conf import settings
from django.template.loader import render_to_string
from django.core.urlresolvers import reverse as urlreverse

from ietf.liaisons.mail import IETFEmailMessage

def send_liaison_by_email(liaison, fake=False):
    if not liaison.is_pending(): # this conditional should definitely be at the caller, not here
        return notify_pending_by_email(liaison, fake)

    subject = u'New Liaison Statement, "%s"' % (liaison.title)
    from_email = settings.LIAISON_UNIVERSAL_FROM
    to_email = liaison.to_poc.split(',')
    cc = liaison.cc1.split(',')
    if liaison.technical_contact:
        cc += liaison.technical_contact.split(',')
    if liaison.response_contact:
        cc += liaison.response_contact.split(',')
    bcc = ['statements@ietf.org']
    body = render_to_string('liaisons/liaison_mail.txt',
                            {'liaison': liaison,
                             'url': settings.IDTRACKER_BASE_URL + urlreverse("liaison_detail", kwargs=dict(object_id=liaison.pk))
                            })
    mail = IETFEmailMessage(subject=subject,
                            to=to_email,
                            from_email=from_email,
                            cc = cc,
                            bcc = bcc,
                            body = body)
    # rather than this fake stuff, it's probably better to start a
    # debug SMTP server as explained in the Django docs
    if not fake:
        mail.send()         
    return mail                                                     

def notify_pending_by_email(liaison, fake):
    from ietf.liaisons.utils import IETFHM

    from_entity = IETFHM.get_entity_by_key(liaison.from_raw_code)
    if not from_entity:
        return None
    to_email = []
    for person in from_entity.can_approve():
        to_email.append('%s <%s>' % person.email())
    subject = u'New Liaison Statement, "%s" needs your approval' % (liaison.title)
    from_email = settings.LIAISON_UNIVERSAL_FROM
    body = render_to_string('liaisons/pending_liaison_mail.txt',
                            {'liaison': liaison,
                             'url': settings.IDTRACKER_BASE_URL + urlreverse("liaison_detail", kwargs=dict(object_id=liaison.pk)),
                             'approve_url': settings.IDTRACKER_BASE_URL + urlreverse("liaison_approval_detail", kwargs=dict(object_id=liaison.pk))
                            })
    mail = IETFEmailMessage(subject=subject,
                            to=to_email,
                            from_email=from_email,
                            body = body)
    if not fake:
        mail.send()         
    return mail                                                     

