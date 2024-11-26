# Copyright The IETF Trust 2014-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import base64
import datetime
from dateutil.tz import tzoffset
import os
import re

from email import message_from_bytes
from email.utils import parsedate_tz

from django.template.loader import render_to_string
from django.utils.encoding import force_str, force_bytes

import debug                            # pyflakes:ignore

from ietf.ipr.models import IprEvent
from ietf.message.models import Message
from ietf.person.models import Person
from ietf.utils.log import log
from ietf.mailtrigger.utils import get_base_ipr_request_address

# ----------------------------------------------------------------
# Date Functions
# ----------------------------------------------------------------
def get_body(msg):
    """Returns the body of the message.  A Basic routine to walk parts of a MIME message
    concatenating text/plain parts"""
    body = ''
    for part in msg.walk():
        if part.get_content_type() == 'text/plain':
            body = body + part.get_payload() + '\n'
    return body
    
def is_aware(date):
    """Returns True if the date object passed in timezone aware, False if naive.
    See http://docs.python.org/2/library/datetime.html section 8.1.1
    """
    if not isinstance(date,datetime.datetime):
        return False
    if date.tzinfo and date.tzinfo.utcoffset(date) is not None:
        return True
    return False
    
def parsedate_to_datetime(date):
    """Returns a datetime object from string.  May return naive or aware datetime.

    This function is from email standard library v3.3, converted to 2.x
    http://python.readthedocs.org/en/latest/library/email.util.html
    """
    try:
        tuple = parsedate_tz(date)
        if not tuple:
            return None
        tz = tuple[-1]
        if tz is None:
            return datetime.datetime(*tuple[:6])
        return datetime.datetime(*tuple[:6],tzinfo=tzoffset(None,tz))
    except ValueError:
        return None

def utc_from_string(s):
    date = parsedate_to_datetime(s)
    if date is None:
        return None
    elif is_aware(date):
        return date.astimezone(datetime.timezone.utc)
    else:
        return date.replace(tzinfo=datetime.timezone.utc)

# ----------------------------------------------------------------
# Email Functions
# ----------------------------------------------------------------
def get_holders(ipr):
    """Recursive function to follow chain of disclosure updates and return holder emails"""
    items = []
    for x in [ y.target.get_child() for y in ipr.updates]:
        items.extend(get_holders(x))
    return ([ipr.holder_contact_email] if hasattr(ipr,'holder_contact_email') else []) + items
    
def get_pseudo_submitter(ipr):
    """Returns a tuple (name, email) contact for this disclosure.  Order of preference
    is submitter, ietfer, holder (per legacy app)"""
    name = 'UNKNOWN NAME - NEED ASSISTANCE HERE'
    email = 'UNKNOWN EMAIL - NEED ASSISTANCE HERE'
    if ipr.submitter_email:
        name = ipr.submitter_name
        email = ipr.submitter_email
    elif hasattr(ipr, 'ietfer_contact_email') and ipr.ietfer_contact_email:
        name = ipr.ietfer_name
        email = ipr.ietfer_contact_email
    elif hasattr(ipr, 'holder_contact_email') and ipr.holder_contact_email:
        name = ipr.holder_contact_name
        email = ipr.holder_contact_email
    
    return (name,email)

def get_reply_to():
    """Returns a new reply-to address for use with an outgoing message.  This is an
    address with "plus addressing" using a random string.  Guaranteed to be unique"""
    local,domain = get_base_ipr_request_address().split('@')
    while True:
        rand = force_str(base64.urlsafe_b64encode(os.urandom(12)))
        address = "{}+{}@{}".format(local,rand,domain)
        q = Message.objects.filter(reply_to=address)
        if not q:
            break
    return address

def get_update_cc_addrs(ipr):
    """Returns list (as a string) of email addresses to use in CC: for an IPR update.
    Logic is from legacy tool.  Append submitter or ietfer email of first-order updated
    IPR, append holder of updated IPR, follow chain of updates, appending holder emails
    """
    emails = []
    if not ipr.updates:
        return ''
    for rel in ipr.updates:
        if rel.target.submitter_email:
            emails.append(rel.target.submitter_email)
        elif hasattr(rel.target,'ietfer_email') and rel.target.ietfer_email:
            emails.append(rel.target.ietfer_email)
    emails = emails + get_holders(ipr)
    
    return ','.join(list(set(emails)))
    
def get_update_submitter_emails(ipr):
    """Returns list of messages, as flat strings, to submitters of IPR(s) being
    updated"""
    messages = []
    email_to_iprs = {}
    email_to_name = {}
    for related in ipr.updates:
        name, email = get_pseudo_submitter(related.target)
        email_to_name[email] = name
        if email in email_to_iprs:
            email_to_iprs[email].append(related.target)
        else:
            email_to_iprs[email] = [related.target]
        
    # TODO: This has not been converted to use mailtrigger. It is complicated.
    # When converting it, it will need something like ipr_submitter_ietfer_or_holder perhaps
    for email in email_to_iprs:
        context = dict(
            to_email=email,
            to_name=email_to_name[email],
            iprs=email_to_iprs[email],
            new_ipr=ipr,
            reply_to=get_reply_to())
        text = render_to_string('ipr/update_submitter_email.txt',context)
        messages.append(text)
    return messages
    
def message_from_message(message,by=None):
    """Returns a ietf.message.models.Message.  msg=email.Message"""
    if not by:
        by = Person.objects.get(name="(System)")
    msg = Message.objects.create(
        by = by,
        subject = message.get('subject',''),
        frm = message.get('from',''),
        to = message.get('to',''),
        cc = message.get('cc',''),
        bcc = message.get('bcc',''),
        reply_to = message.get('reply_to',''),
        body = get_body(message),
        time = utc_from_string(message['date']),
        content_type = message.get('content_type', 'text/plain'),
    )
    return msg


class UndeliverableIprResponseError(Exception):
    """Response email could not be delivered and should be treated as an error"""


def process_response_email(msg):
    """Save an incoming IPR response email message
    
    Message "To" field is expected to be in the format ietf-ipr+[identifier]@ietf.org. If
    the address or identifier is missing, the message will be silently dropped.

    Expect to find a message with a matching value in the reply_to field, associated to an
    IPR disclosure through IprEvent. If it cannot be matched, raises UndeliverableIprResponseError 
    
    Creates a Message object for the incoming message and associates it to
    the original message via new IprEvent
    """
    message = message_from_bytes(force_bytes(msg))
    to = message.get('To', '')

    # exit if this isn't a response we're interested in (with plus addressing)
    local, domain = get_base_ipr_request_address().split('@')
    if not re.match(r'^{}\+[a-zA-Z0-9_\-]{}@{}'.format(local,'{16}',domain),to):
        _from = message.get("From", "<unknown>")
        log(f"Ignoring IPR email without a message identifier from {_from} to {to}")
        return

    try:
        to_message = Message.objects.get(reply_to=to)
    except Message.DoesNotExist:
        log('Error finding matching message ({})'.format(to))
        raise UndeliverableIprResponseError(f"Unable to find message matching {to}")

    try:
        disclosure = to_message.msgevents.first().disclosure
    except:
        log('Error processing message ({})'.format(to))
        raise UndeliverableIprResponseError("Error processing message for {to}")

    ietf_message = message_from_message(message)
    IprEvent.objects.create(
        type_id = 'msgin',
        by = Person.objects.get(name="(System)"),
        disclosure = disclosure,
        message = ietf_message,
        in_reply_to = to_message
    )
    
    log("Received IPR email from %s" % ietf_message.frm)

