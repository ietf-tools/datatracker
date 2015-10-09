import datetime

from django.conf import settings
from django.template.loader import render_to_string

from ietf.utils.mail import send_mail_text
from ietf.liaisons.utils import approval_roles
from ietf.group.models import Role

def send_liaison_by_email(request, liaison):
    subject = u'New Liaison Statement, "%s"' % (liaison.title)
    from_email = settings.LIAISON_UNIVERSAL_FROM
    to_email = liaison.to_contacts.split(',')
    cc = liaison.cc_contacts.split(',')
    if liaison.technical_contacts:
        cc += liaison.technical_contacts.split(',')
    if liaison.response_contacts:
        cc += liaison.response_contacts.split(',')
    bcc = ['statements@ietf.org']
    body = render_to_string('liaisons/liaison_mail.txt', dict(liaison=liaison))

    send_mail_text(request, to_email, from_email, subject, body, cc=", ".join(cc), bcc=", ".join(bcc))

def notify_pending_by_email(request, liaison):
    '''Send mail requesting approval of pending liaison statement.  Send mail to
    the intersection of approvers for all from_groups
    '''
    approval_set = set(approval_roles(liaison.from_groups.first()))
    if liaison.from_groups.count() > 1:
        for group in liaison.from_groups.all():
            approval_set.intersection_update(approval_roles(group))
    to_emails = [ r.email.address for r in approval_set ]

    subject = u'New Liaison Statement, "%s" needs your approval' % (liaison.title)
    from_email = settings.LIAISON_UNIVERSAL_FROM
    body = render_to_string('liaisons/pending_liaison_mail.txt', dict(liaison=liaison))
    send_mail_text(request, to_emails, from_email, subject, body)

def send_sdo_reminder(sdo):
    roles = Role.objects.filter(name="liaiman", group=sdo)
    if not roles: # no manager to contact
        return None
    manager_role = roles[0]

    subject = 'Request for update of list of authorized individuals'
    to_email = manager_role.email.address
    name = manager_role.person.plain_name()
    authorized_list = Role.objects.filter(group=sdo, name='auth').select_related("person").distinct()
    body = render_to_string('liaisons/sdo_reminder.txt', dict(
            manager_name=name,
            sdo_name=sdo.name,
            individuals=authorized_list,
            ))

    send_mail_text(None, to_email, settings.LIAISON_UNIVERSAL_FROM, subject, body)

    return body

def possibly_send_deadline_reminder(liaison):
    PREVIOUS_DAYS = {
        14: 'in two weeks',
        7: 'in one week',
        4: 'in four days',
        3: 'in three days',
        2: 'in two days',
        1: 'tomorrow',
        0: 'today'
        }

    days_to_go = (liaison.deadline - datetime.date.today()).days
    if not (days_to_go < 0 or days_to_go in PREVIOUS_DAYS.keys()):
        return None # no reminder

    if days_to_go < 0:
        subject = '[Liaison OUT OF DATE] %s' % liaison.title
        days_msg = 'is out of date for %s days' % (-days_to_go)
    else:
        subject = '[Liaison deadline %s] %s' % (PREVIOUS_DAYS[days_to_go], liaison.title)
        days_msg = 'expires %s' % PREVIOUS_DAYS[days_to_go]

    from_email = settings.LIAISON_UNIVERSAL_FROM
    to_email = liaison.to_contacts.split(',')
    cc = liaison.cc_contacts.split(',')
    if liaison.technical_contacts:
        cc += liaison.technical_contacts.split(',')
    if liaison.response_contacts:
        cc += liaison.response_contacts.split(',')
    bcc = 'statements@ietf.org'
    body = render_to_string('liaisons/liaison_deadline_mail.txt',
        dict(liaison=liaison,days_msg=days_msg,))

    send_mail_text(None, to_email, from_email, subject, body, cc=cc, bcc=bcc)

    return body
