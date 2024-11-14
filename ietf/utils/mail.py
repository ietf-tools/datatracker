# Copyright The IETF Trust 2007-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import copy
#import logging
import re
import smtplib
import sys
import textwrap
import time
import traceback

from email.utils import make_msgid, formatdate, formataddr as simple_formataddr, parseaddr as simple_parseaddr, getaddresses
from email.message import Message       # pyflakes:ignore
from email.mime.text import MIMEText
from email.mime.message import MIMEMessage
from email.mime.multipart import MIMEMultipart
from email.header import Header, decode_header
from email import message_from_bytes, message_from_string
from email import charset as Charset
from typing import Optional

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.validators import validate_email
from django.http import HttpRequest
from django.template.loader import render_to_string
from django.template import Context,RequestContext
from django.utils import timezone
from django.utils.encoding import force_str, force_bytes

import debug                            # pyflakes:ignore

import ietf
from ietf.utils.log import log, assertion
from ietf.utils.text import isascii

from typing import Any, Dict, List  # pyflakes:ignore

# Testing mode:
# import ietf.utils.mail
# ietf.utils.mail.test_mode = True
# ... send some mail ...
# ... inspect ietf.utils.mail.outbox ...
# ... call ietf.utils.mail.empty_outbox() ...
test_mode = False
outbox = []                             # type: List[Message]

SMTP_ADDR = { 'ip4':settings.EMAIL_HOST, 'port':settings.EMAIL_PORT}

# Don't BASE64-encode UTF-8 messages so that we avoid unwanted attention from
# some spam filters.
Charset.add_charset('utf-8', Charset.SHORTEST, None, 'utf-8')

def empty_outbox():
    outbox[:] = []

def add_headers(msg):
    if not('Message-ID' in msg):
        msg['Message-ID'] = make_msgid()
    if not('Date' in msg):
        msg['Date'] = formatdate(time.time(), True)
    if not('From' in msg):
        msg['From'] = settings.DEFAULT_FROM_EMAIL
    return msg


def decode_header_value(value: str) -> str:
    """Decode a header value
    
    Easier-to-use wrapper around email.message.decode_header()
    """
    return "".join(
        part.decode(charset if charset else "utf-8") if isinstance(part, bytes) else part
        for part, charset in decode_header(value)
    )


class SMTPSomeRefusedRecipients(smtplib.SMTPException):

    def __init__(self, message, original_msg, refusals):
        smtplib.SMTPException.__init__(self, message)
        self.original_msg = original_msg
        self.refusals = refusals

    def detailed_refusals(self):
        details = "The following recipients were refused:\n"
        for recipient in self.refusals:
             details += "\n%s: %s" % (recipient,self.refusals[recipient])
        return details

    def summary_refusals(self):
        return ", ".join(["%s (%s)"%(x,self.refusals[x][0]) for x in self.refusals])

def send_smtp(msg, bcc=None):
    '''
    Send a Message via SMTP, based on the django email server settings.
    The destination list will be taken from the To:/Cc: headers in the
    Message.  The From address will be used if present or will default
    to the django setting DEFAULT_FROM_EMAIL

    If someone has set test_mode=True, then append the msg to
    the outbox.
    '''
    mark = time.time()
    add_headers(msg)
    # N.B. We have a disconnect with most of this code assuming a From header value will only
    # have one address.
    # The frm computed here is only used as the envelope from. 
    # Previous code simply ran `parseaddr(msg.get('From'))`, getting lucky if the string returned
    # from the get had more than one address in it. Python 3.9.20 changes the behavior of parseaddr
    # and that erroneous use of the function no longer gets lucky.
    # For the short term, to match behavior to date as closely as possible, if we get a message
    # that has multiple addresses in the From header, we will use the first for the envelope from
    from_tuples = getaddresses(msg.get_all('From', [settings.DEFAULT_FROM_EMAIL]))
    assertion('len(from_tuples)==1', note=f"send_smtp received multiple From addresses: {from_tuples}")
    _ , frm = from_tuples[0]
    addrlist = msg.get_all('To') + msg.get_all('Cc', [])
    if bcc:
        addrlist += [bcc]
    to = [addr for name, addr in getaddresses(addrlist) if ( addr != '' and not addr.startswith('unknown-email-') )]
    if not to:
        log("No addressees for email from '%s', subject '%s'.  Nothing sent." % (frm, msg.get('Subject', '[no subject]')))
    else:
        if test_mode:
            outbox.append(msg)
        server = None
        try:
            server = smtplib.SMTP()
            #log("SMTP server: %s" % repr(server))
            #if settings.DEBUG:
            #    server.set_debuglevel(1)
            conn_code, conn_msg = server.connect(SMTP_ADDR['ip4'], SMTP_ADDR['port'])
            #log("SMTP connect: code: %s; msg: %s" % (conn_code, conn_msg))
            if settings.EMAIL_HOST_USER and settings.EMAIL_HOST_PASSWORD:
                server.ehlo()
                if 'starttls' not in server.esmtp_features:
                    raise ImproperlyConfigured('password configured but starttls not supported')
                (retval, retmsg) = server.starttls()
                if retval != 220:
                    raise ImproperlyConfigured('password configured but tls failed: %d %s' % ( retval, retmsg ))
                # Send a new EHLO, since without TLS the server might not
                # advertise the AUTH capability.
                server.ehlo()
                server.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
            unhandled = server.sendmail(frm, to, force_bytes(msg.as_string()))
            if unhandled != {}:
                raise SMTPSomeRefusedRecipients(message="%d addresses were refused"%len(unhandled),original_msg=msg,refusals=unhandled)
        except Exception as e:
            # need to improve log message
            log("Exception while trying to send email from '%s' to %s subject '%s'" % (frm, to, msg.get('Subject', '[no subject]')), e=e)
            if isinstance(e, smtplib.SMTPException):
                e.original_msg=msg
                raise 
            else:
                raise smtplib.SMTPException({'really': sys.exc_info()[0], 'value': sys.exc_info()[1], 'tb': traceback.format_tb(sys.exc_info()[2])})
        finally:
            try:
                server.quit()
            except smtplib.SMTPServerDisconnected:
                pass
        subj = force_str(msg.get('Subject', '[no subject]'))
        tau = time.time() - mark
        log("sent email (%.3fs) from '%s' to %s id %s subject '%s'" % (tau, frm, to, msg.get('Message-ID', ''), subj))
    
def copy_email(msg, to, toUser=False, originalBcc=None):
    '''
    Send a copy of the given email message to the given recipient.
    '''
    add_headers(msg)
    new = MIMEMultipart()
    # get info for first part.
    # Mode: if it's production, then "copy of a message", otherwise
    #  "this is a message that would have been sent from"
    # hostname?
    # django settings if debugging?
    # Should this be a template?
    if settings.SERVER_MODE == 'production':
        explanation = "This is a copy of a message sent from the I-D tracker."
    elif settings.SERVER_MODE == 'test' and toUser:
        explanation = "The attached message was generated by an instance of the tracker\nin test mode.  It is being sent to you because you, or someone acting\non your behalf, is testing the system.  If you do not recognize\nthis action, please accept our apologies and do not be concerned as\nthe action is being taken in a test context."
    else:
        explanation = "The attached message would have been sent, but the tracker is in %s mode.\nIt was not sent to anybody." % settings.SERVER_MODE
        if originalBcc:
          explanation += ("\nIn addition to the destinations derived from the header below, the message would have been sent Bcc to %s" % originalBcc)
    new.attach(MIMEText(explanation + "\n\n"))
    new.attach(MIMEMessage(msg))
    # Overwrite the From: header, so that the copy from a development or
    # test server doesn't look like spam.
    new['From'] = settings.DEFAULT_FROM_EMAIL
    new['Subject'] = '[Django %s] %s' % (settings.SERVER_MODE, force_str(msg.get('Subject', '[no subject]')))
    new['To'] = to
    send_smtp(new)

def mail_context(request):
    if request:
        return RequestContext(request)
    else:
        return Context()

def send_mail(request, to, frm, subject, template, context, *args, **kwargs):
    '''
    Send an email to the destination [list], with the given return
    address (or "None" to use the default in settings.py).
    The body is a text/plain rendering of the template with the context.
    extra is a dict of extra headers to add.
    '''
    context["settings"] = settings
    txt = render_to_string(template, context, request=request)
    return send_mail_text(request, to, frm, subject, txt, *args, **kwargs)

def encode_message(txt):
    assert isinstance(txt, str)
    return MIMEText(txt.encode('utf-8'), 'plain', 'UTF-8')

def send_mail_text(request, to, frm, subject, txt, cc=None, extra=None, toUser=False, bcc=None, copy=True, save=True):
    """Send plain text message.

    request can be None unless it is needed by the template
    """
    msg = encode_message(txt)
    return send_mail_mime(request, to, frm, subject, msg, cc, extra, toUser, bcc, copy=copy, save=save)
        
def on_behalf_of(frm):
    if isinstance(frm, tuple):
        name, addr = frm
    else:
        name, addr = parseaddr(frm)
    domain = addr.rsplit('@', 1)[-1]
    if domain in settings.UTILS_FROM_EMAIL_DOMAINS:
        return frm
    if not name:
        name = addr
    name = "%s via Datatracker" % name
    addr = settings.UTILS_ON_BEHALF_EMAIL
    return formataddr((name, addr))

def maybe_on_behalf_of(frm):
    if isinstance(frm, tuple):
        name, addr = frm
    else:
        name, addr = parseaddr(frm)
    domain = addr.rsplit('@', 1)[-1]
    if not domain in settings.UTILS_FROM_EMAIL_DOMAINS:
        frm = on_behalf_of(frm)
    return frm

def formataddr(addrtuple):
    """
    Takes a name and email address, and inspects the name to see if it needs
    to be encoded in an email.header.Header before being used in an email.message
    address field.  Does what's needed, and returns a string value suitable for
    use in a To: or Cc: email header field.
    """
    return simple_formataddr(addrtuple)

def parseaddr(addr):
    """
    Takes an address (which should be the value of some address-containing
    field such as To or Cc) into its constituent realname and email address
    parts. Returns a tuple of that information, unless the parse fails, in
    which case a 2-tuple of ('', '') is returned.

    """

    name, addr = simple_parseaddr(decode_header_value(addr))
    return name, addr

def excludeaddrs(addrlist, exlist):
    """
    Takes a list or set of email address strings in 2822 format, and
    eliminates entries whose address part occurs in the given exclusion list.
    """
    exlist = set([ parseaddr(a)[1] for a in exlist ])
    filtered = []
    for a in addrlist:
        if not parseaddr(a)[1] in exlist:
            filtered.append(a)
    filtered = type(addrlist)(filtered)
    return filtered

def condition_message(to, frm, subject, msg, cc, extra):
    if extra:
        assertion("isinstance(extra, (dict, Message))")
        if 'Reply-To' in extra:
            assertion("isinstance(extra['Reply-To'], list)")

    if isinstance(frm, tuple):
        frm = formataddr(frm)
    if isinstance(to, list) or isinstance(to, tuple):
        to = ", ".join([isinstance(addr, tuple) and formataddr(addr) or addr for addr in to if addr])
    if isinstance(cc, list) or isinstance(cc, tuple):
        cc = ", ".join([isinstance(addr, tuple) and formataddr(addr) or addr for addr in cc if addr])
    if frm:
        n, a = parseaddr(frm)
        domain = a.rsplit('@', 1)[-1]
        if not domain in settings.UTILS_FROM_EMAIL_DOMAINS:
            extra = extra or {}
            if 'Reply-To' in extra:
                extra['Reply-To'].append(frm)
            else:
                extra['Reply-To'] = [frm, ]
            frm = on_behalf_of(frm)
        msg['From'] = frm

    # The following is a hack to avoid an issue with how the email module (as of version 4.0.3)
    # breaks lines when encoding header fields with anything other than the us-ascii codec.
    # This allows the Header implementation to encode each display name as a separate chunk. 
    # The resulting encode produces a string that is us-ascii and has a good density of 
    # "higher-level syntactic breaks"
    to_hdr = Header(header_name='To')
    for name, addr in getaddresses([to]):
        if addr != '' and not addr.startswith('unknown-email-'):
            if name:
                to_hdr.append('"%s"' % name)
            to_hdr.append("<%s>," % addr)
    # Please note: The following .encode() does _not_ take a charset argument
    to_str = to_hdr.encode()
    if to_str and to_str[-1] == ',':
        to_str=to_str[:-1]
    # It's important to use this string, and not assign the Header object.
    # Code downstream from this assumes that the msg['To'] will return a string, not an instance
    msg['To'] = to_str

    if cc:
        msg['Cc'] = cc
    msg['Subject'] = subject
    msg['X-Test-IDTracker'] = (settings.SERVER_MODE == 'production') and 'no' or 'yes'
    msg['X-IETF-IDTracker'] = ietf.__version__
    msg['Auto-Submitted'] = "auto-generated"
    msg['Precedence'] = "bulk"
    if extra:
        for k, v in extra.items():
            if v:
                assertion('len(list(set(v))) == len(v)')
                try:
                    msg[k] = ", ".join(v)
                except Exception:
                    raise
    if not msg.get('Message-ID', None):
        msg['Message-ID'] = make_msgid()


def show_that_mail_was_sent(request: HttpRequest, leadline: str, msg: Message, bcc: Optional[str]):
    if request and request.user:
        from ietf.ietfauth.utils import has_role

        if has_role(
            request.user,
            [
                "Area Director",
                "Secretariat",
                "IANA",
                "RFC Editor",
                "ISE",
                "IAD",
                "IRTF Chair",
                "WG Chair",
                "RG Chair",
                "WG Secretary",
                "RG Secretary",
            ],
        ):
            subject = decode_header_value(msg.get("Subject", "[no subject]"))
            _to = decode_header_value(msg.get("To", "[no to]"))
            info_lines = [
                f"{leadline} at {timezone.now():%Y-%m-%d %H:%M:%S %Z}",
                f"Subject: {subject}",
                f"To: {_to}",
            ]
            cc = msg.get("Cc", None)
            if cc:
                info_lines.append(f"Cc: {decode_header_value(cc)}")
            if bcc:
                info_lines.append(f"Bcc: {decode_header_value(bcc)}")
            messages.info(
                request,
                "\n".join(info_lines),
                extra_tags="preformatted",
                fail_silently=True,
            )


def save_as_message(request, msg, bcc):
    by = ((request and request.user and not request.user.is_anonymous and request.user.person)
            or ietf.person.models.Person.objects.get(name="(System)"))
    headers, body = force_str(str(msg)).split('\n\n', 1)
    kwargs = {'by': by, 'body': body, 'content_type': msg.get_content_type(), 'bcc': bcc or '' }
    for (arg, field) in [
            ('cc',              'Cc'),
            ('frm',             'From'),
            ('msgid',           'Message-ID'),
            ('reply_to',        'Reply-To'),
            ('subject',         'Subject'),
            ('to',              'To'),
        ]:
        kwargs[arg] = msg.get(field, '')
    m = ietf.message.models.Message.objects.create(**kwargs)
    log("Saved outgoing email from '%s' to %s id %s subject '%s as Message[%s]'" % (m.frm, m.to, m.msgid, m.subject, m.pk))
    return m

def send_mail_mime(request, to, frm, subject, msg, cc=None, extra=None, toUser=False, bcc=None, copy=True, save=True):
    """Send MIME message with content already filled in."""
    
    condition_message(to, frm, subject, msg, cc, extra)

    # start debug server with python -m smtpd -n -c DebuggingServer localhost:2025
    # then put USING_DEBUG_EMAIL_SERVER=True and EMAIL_HOST='localhost'
    # and EMAIL_PORT=2025 in settings_local.py
    debugging = getattr(settings, "USING_DEBUG_EMAIL_SERVER", False) and settings.EMAIL_HOST == 'localhost' and settings.EMAIL_PORT == 2025
    production = settings.SERVER_MODE == 'production'

    if settings.SERVER_MODE == 'repair':
        return msg

    if settings.SERVER_MODE == 'development':
        show_that_mail_was_sent(request,'In production, email would have been sent',msg,bcc)

    # Maybe save in the database as a Message object
    if save:
        message = save_as_message(request, msg, bcc)
    else:
        message = None

    if test_mode or debugging or production:
        try:
            send_smtp(msg, bcc)
            if save:
                message.sent = timezone.now()
                message.save()
            if settings.SERVER_MODE != 'development':
                show_that_mail_was_sent(request,'Email was sent',msg,bcc)
        except smtplib.SMTPException as e:
            log_smtp_exception(e)
            build_warning_message(request, e)
            send_error_email(e)

    elif settings.SERVER_MODE == 'test':
        if toUser:
            copy_email(msg, to, toUser=True, originalBcc=bcc)
        elif request and 'testmailcc' in request.COOKIES:
            copy_email(msg, request.COOKIES[ 'testmailcc' ],originalBcc=bcc)
    try:
        copy_to = settings.EMAIL_COPY_TO
    except AttributeError:
        copy_to = None
    if copy_to and (copy or not production) and not (test_mode or debugging): # if we're running automated tests, this copy is just annoying
        if bcc:
            msg['X-Tracker-Bcc']=bcc
        try:
            copy_email(msg, copy_to, originalBcc=bcc)
        except smtplib.SMTPException as e:
            log_smtp_exception(e)
            build_warning_message(request, e)
            send_error_email(e)

    return msg

def parse_preformatted(preformatted, extra=None, override=None):
    """Parse preformatted string containing mail with From:, To:, ...,"""
    if extra is None:
        extra = {}
    if override is None:
        override = {}
    assert isinstance(preformatted, str)
    msg = message_from_bytes(preformatted.encode('utf-8'))
    msg.set_charset('UTF-8')

    for k, v in override.items():
        if k in msg:
            del msg[k]
        if v:
            if isinstance(v, list):
                msg[k] = ', '.join(v)
            else:
                msg[k] = v 

    extra = copy.deepcopy(extra)        # don't modify the caller's extra obj
    headers = copy.copy(msg)            # don't modify the message
    for key in ['To', 'From', 'Subject', 'Bcc']:
        del headers[key]
    for k in list(headers.keys()):
        v = headers.get_all(k, [])
        if k in extra:
            ev = extra[k]
            if not isinstance(ev, list):
                ev = [ ev, ]
            extra[k] = list(set(v + ev))
        else:
            extra[k] = v

    # Handle non-ascii address names and some other fields
    for key in ['To', 'From', 'Cc', 'Bcc']:
        values = msg.get_all(key, [])
        if values:
            values = getaddresses(values)
            if key=='From':
                assertion('len(values)<2', note=f'parse_preformatted is constructing a From with multiple values: {values}')
            del msg[key]
            msg[key] = ',\n    '.join(formataddr(v) for v in values)
    for key in ['Subject', ]:
        values = msg.get_all(key)
        if values:
            del msg[key]
            for v in values:
                if isascii(v):
                    msg[key] = v
                else:
                    msg[key] = Header(v, 'utf-8')

    bcc = msg['Bcc']
    del msg['Bcc']

    for v in list(extra.values()):
        assertion('len(list(set(v))) == len(v)')
    return (msg, extra, bcc)

def send_mail_preformatted(request, preformatted, extra=None, override=None):
    """Parse preformatted string containing mail with From:, To:, ...,
    and send it through the standard IETF mail interface (inserting
    extra headers as needed)."""

    if extra is None:
        extra = {}
    if override is None:
        override = {}

    (msg, extra, bcc) = parse_preformatted(preformatted, extra, override)
    txt = msg.get_payload()
    send_mail_text(request, msg['To'], msg["From"], msg["Subject"], txt, extra=extra, bcc=bcc)
    return msg

def send_mail_message(request, message, extra=None):
    """Send a Message object."""
    # note that this doesn't handle MIME messages at the moment
    if extra is None:
        extra = {}
    assertion('isinstance(message.to, str) and isinstance(message.cc, str) and isinstance(message.bcc, str)')

    e = extra.copy()
    if message.reply_to:
        e['Reply-To'] = message.get('reply_to')
    if message.msgid:
        e['Message-ID'] = [ message.msgid, ]

    content_type = message.content_type or 'text/plain'
    if 'multipart' in content_type:
        body = ("MIME-Version: 1.0\r\nContent-Type: %s\r\n\r\n" % content_type) + message.body
        msg = message_from_string(force_str(body))
    else:
        msg = encode_message(message.body)

    msg = send_mail_mime(request, message.to, message.frm, message.subject,
                          msg, cc=message.cc, bcc=message.bcc, extra=e, save=False)

#     msg = send_mail_text(request, message.to, message.frm, message.subject,
#                           message.body, cc=message.cc, bcc=message.bcc, extra=e, save=False)
    message.sent = timezone.now()
    message.save()
    return msg

def exception_components(e):
    # See if it's a non-smtplib exception that we faked
    if len(e.args)==1 and isinstance(e.args[0],dict) and 'really' in e.args[0]:
        orig = e.args[0]
        extype = orig['really']
        tb = orig['tb']
        value = orig['value']
    else:
        extype = sys.exc_info()[0]
        value = sys.exc_info()[1]
        tb = traceback.format_tb(sys.exc_info()[2])
    return (extype, value, tb)
        
def log_smtp_exception(e):
    (extype, value, tb) = exception_components(e)
    log("SMTP Exception: %s : %s" % (extype,value), e)
    if isinstance(e,SMTPSomeRefusedRecipients):
        log("     SomeRefused: %s"%(e.summary_refusals()), e)
    log("     Traceback: %s" % tb, e) 
    return (extype, value, tb)

def build_warning_message(request, e):
    (extype, value, tb) = exception_components(e)
    if request:
        warning =  "An error occurred while sending email:\n"
        if getattr(e,'original_msg',None):
            warning += "Subject: %s\n" % e.original_msg.get('Subject','[no subject]')
            warning += "To: %s\n" % e.original_msg.get('To','[no to]')
            warning += "Cc: %s\n" % e.original_msg.get('Cc','[no cc]')
        if isinstance(e,SMTPSomeRefusedRecipients):
            warning += e.detailed_refusals()
        else:
            warning += "SMTP Exception: %s\n"%extype
            warning += "Error Message: %s\n\n"%value
            warning += "The message was not delivered to anyone."
        messages.warning(request,warning,extra_tags='preformatted',fail_silently=True)

def send_error_email(e):
    (extype, value, tb) = exception_components(e)
    msg = MIMEMultipart()
    msg['To'] = '<action@ietf.org>'
    msg['From'] = settings.SERVER_EMAIL
    if isinstance(e,SMTPSomeRefusedRecipients):
        msg['Subject'] = 'Subject: Some recipients were refused while sending mail with Subject: %s' % e.original_msg.get('Subject','[no subject]')
        textpart = textwrap.dedent("""\
            This is a message from the datatracker to IETF-Action about an email
            delivery failure, when sending email from the datatracker.

            %s

            """) % e.detailed_refusals()
    else:
        msg['Subject'] = 'Datatracker error while sending email'
        textpart = textwrap.dedent("""\
            This is a message from the datatracker to IETF-Action about an email
            delivery failure, when sending email from the datatracker.

            The original message was not delivered to anyone.

            SMTP Exception: %s

            Error Message: %s
                 
            """) % (extype,value)
    if hasattr(e,'original_msg'):
        textpart += "The original message follows:\n"
    msg.attach(MIMEText(textpart,_charset='utf-8'))
    if hasattr(e,'original_msg'):
        msg.attach(MIMEMessage(e.original_msg))

    send_error_to_secretariat(msg)

def send_error_to_secretariat(msg):

    debugging = getattr(settings, "USING_DEBUG_EMAIL_SERVER", False) and settings.EMAIL_HOST == 'localhost' and settings.EMAIL_PORT == 2025

    try:
        if test_mode or debugging or settings.SERVER_MODE == 'production':
            send_smtp(msg, bcc=None)
        try:
            copy_to = settings.EMAIL_COPY_TO
        except AttributeError:
            copy_to = None
        if copy_to and not test_mode and not debugging: # if we're running automated tests, this copy is just annoying
            copy_email(msg, copy_to,originalBcc=None)
    except smtplib.SMTPException:
        log("Exception encountered while sending a ticket to the secretariat")
        (extype,value) = sys.exc_info()[:2]
        log("SMTP Exception: %s : %s" % (extype,value))
    
def is_valid_email(address):
    try:
        validate_email(address)
        return True
    except ValidationError:
        return False

#logger = logging.getLogger('django')
def get_email_addresses_from_text(text):
    """

    Expects a string with one or more email addresses, each in 2822-compatible
    form, separated by comma (as in an RFC2822, Section 3.4 address-list)
    Could be as simple as 'foo@example.com' or as complex as 'Some Person
    <some.person@example.com>, "list@ietf.org"\n\t<list@ietf.org>'.

    Returns a list of properly formatted email address strings.

    """
    def valid(email):
        name, addr = email
        try:
            validate_email(addr)
            return True
        except ValidationError:
#             logger.error('Bad data: get_email_addresses_from_text() got an '
#                 'invalid email address tuple: {email}, in "{text}".'.format(email=email, text=text))
            log('Bad data: get_email_addresses_from_text() got an '
                'invalid email address tuple: {email}, in "{text}".'.format(email=email, text=text))
            return False
    # whitespace normalization -- getaddresses doesn't do this
    text = re.sub(r'(?u)\s+', ' ', text)
    return [ formataddr(e) for e in getaddresses([text, ]) if valid(e) ]
    


# def get_payload(msg, decode=False):
#     return msg.get_payload(decode=decode)

def get_payload_text(msg, decode=True, default_charset="utf-8"):
    charset = msg.get_charset() or default_charset
    payload = msg.get_payload(decode=decode)
    payload = payload.decode(str(charset))
    return payload
        
