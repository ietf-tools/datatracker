import datetime

from django.conf import settings
from django.template.loader import render_to_string

from ietf.utils.mail import send_mail_text
from ietf.group.models import Role
from ietf.mailtrigger.utils import gather_address_lists

def send_liaison_by_email(request, liaison):
    subject = u'New Liaison Statement, "%s"' % (liaison.title)
    from_email = settings.LIAISON_UNIVERSAL_FROM
    (to_email, cc) = gather_address_lists('liaison_statement_posted',liaison=liaison)
    bcc = ['statements@ietf.org']
    body = render_to_string('liaisons/liaison_mail.txt', dict(liaison=liaison))

    send_mail_text(request, to_email, from_email, subject, body, cc=", ".join(cc), bcc=", ".join(bcc))

def notify_pending_by_email(request, liaison):
    '''Send mail requesting approval of pending liaison statement.  Send mail to
    the intersection of approvers for all from_groups
    '''
    subject = u'New Liaison Statement, "%s" needs your approval' % (liaison.title)
    from_email = settings.LIAISON_UNIVERSAL_FROM
    (to, cc) = gather_address_lists('liaison_approval_requested',liaison=liaison)
    body = render_to_string('liaisons/pending_liaison_mail.txt', dict(liaison=liaison))
    send_mail_text(request, to, from_email, subject, body, cc=cc)

def send_sdo_reminder(sdo):
    roles = Role.objects.filter(name="liaiman", group=sdo)
    if not roles: # no manager to contact
        return None
    manager_role = roles[0]

    subject = 'Request for update of list of authorized individuals'
    (to_email,cc) = gather_address_lists('liaison_manager_update_request',group=sdo)
    name = manager_role.person.plain_name()
    authorized_list = Role.objects.filter(group=sdo, name='auth').select_related("person").distinct()
    body = render_to_string('liaisons/sdo_reminder.txt', dict(
            manager_name=name,
            sdo_name=sdo.name,
            individuals=authorized_list,
            ))

    send_mail_text(None, to_email, settings.LIAISON_UNIVERSAL_FROM, subject, body, cc=cc)

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
    (to_email, cc) = gather_address_lists('liaison_deadline_soon',liaison=liaison)
    bcc = 'statements@ietf.org'
    body = render_to_string('liaisons/liaison_deadline_mail.txt',
        dict(liaison=liaison,days_msg=days_msg,))

    send_mail_text(None, to_email, from_email, subject, body, cc=cc, bcc=bcc)

    return body
