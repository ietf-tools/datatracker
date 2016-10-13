# Copyright The IETF Trust 2007, All Rights Reserved

from email.utils import make_msgid, formatdate, formataddr, parseaddr, getaddresses
from email.mime.text import MIMEText
from email.mime.message import MIMEMessage
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email import message_from_string
from email import charset as Charset

import smtplib
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ImproperlyConfigured
from django.template.loader import render_to_string
from django.template import Context,RequestContext
import ietf
from ietf.utils.log import log
import sys
import time
import copy
import textwrap
import traceback
import datetime

# Testing mode:
# import ietf.utils.mail
# ietf.utils.mail.test_mode = True
# ... send some mail ...
# ... inspect ietf.utils.mail.outbox ...
# ... call ietf.utils.mail.empty_outbox() ...
test_mode = False
outbox = []

SMTP_ADDR = { 'ip4':settings.EMAIL_HOST, 'port':settings.EMAIL_PORT}

# Don't BASE64-encode UTF-8 messages so that we avoid unwanted attention from
# some spam filters.
Charset.add_charset('utf-8', Charset.SHORTEST, None, 'utf-8')

def empty_outbox():
    outbox[:] = []

def add_headers(msg):
    if not(msg.has_key('Message-ID')):
	msg['Message-ID'] = make_msgid('idtracker')
    if not(msg.has_key('Date')):
	msg['Date'] = formatdate(time.time(), True)
    if not(msg.has_key('From')):
	msg['From'] = settings.DEFAULT_FROM_EMAIL
    return msg

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
    add_headers(msg)
    (fname, frm) = parseaddr(msg.get('From'))
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
            unhandled = server.sendmail(frm, to, msg.as_string())
            if unhandled != {}:
                raise SMTPSomeRefusedRecipients(message="%d addresses were refused"%len(unhandled),original_msg=msg,refusals=unhandled)
        except Exception as e:
            # need to improve log message
            log("Exception while trying to send email from '%s' to %s subject '%s'" % (frm, to, msg.get('Subject', '[no subject]')))
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
        log("sent email from '%s' to %s subject '%s'" % (frm, to, msg.get('Subject', '[no subject]')))
    
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
    new['Subject'] = '[Django %s] %s' % (settings.SERVER_MODE, msg.get('Subject', '[no subject]'))
    new['To'] = to
    send_smtp(new)

def mail_context(request):
    if request:
        return RequestContext(request)
    else:
        return Context()
  
def send_mail_subj(request, to, frm, stemplate, template, context, *args, **kwargs):
    '''
    Send an email message, exactly as send_mail(), but the
    subject field is a template.
    '''
    subject = render_to_string(stemplate, context, context_instance=mail_context(request)).replace("\n"," ").strip()
    return send_mail(request, to, frm, subject, template, context, *args, **kwargs)

def send_mail(request, to, frm, subject, template, context, *args, **kwargs):
    '''
    Send an email to the destination [list], with the given return
    address (or "None" to use the default in settings.py).
    The body is a text/plain rendering of the template with the context.
    extra is a dict of extra headers to add.
    '''
    txt = render_to_string(template, context, context_instance=mail_context(request))
    return send_mail_text(request, to, frm, subject, txt, *args, **kwargs)

def encode_message(txt):
    if isinstance(txt, unicode):
        msg = MIMEText(txt.encode('utf-8'), 'plain', 'UTF-8')
    else:
        msg = MIMEText(txt)
    return msg

def send_mail_text(request, to, frm, subject, txt, cc=None, extra=None, toUser=False, bcc=None):
    """Send plain text message."""
    msg = encode_message(txt)
    return send_mail_mime(request, to, frm, subject, msg, cc, extra, toUser, bcc)
        
def condition_message(to, frm, subject, msg, cc, extra):
    if isinstance(frm, tuple):
	frm = formataddr(frm)
    if isinstance(to, list) or isinstance(to, tuple):
        to = ", ".join([isinstance(addr, tuple) and formataddr(addr) or addr for addr in to if addr])
    if isinstance(cc, list) or isinstance(cc, tuple):
        cc = ", ".join([isinstance(addr, tuple) and formataddr(addr) or addr for addr in cc if addr])
    if frm:
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
                msg[k] = v

def show_that_mail_was_sent(request,leadline,msg,bcc):
        if request and request.user:
            from ietf.ietfauth.utils import has_role
            if has_role(request.user,['Area Director','Secretariat','IANA','RFC Editor','ISE','IAD','IRTF Chair','WG Chair','RG Chair','WG Secretary','RG Secretary']):
                info =  "%s at %s %s\n" % (leadline,datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),settings.TIME_ZONE)
                info += "Subject: %s\n" % msg.get('Subject','[no subject]')
                info += "To: %s\n" % msg.get('To','[no to]')
                if msg.get('Cc'):
                    info += "Cc: %s\n" % msg.get('Cc')
                if bcc:
                    info += "Bcc: %s\n" % bcc
                messages.info(request,info,extra_tags='preformatted',fail_silently=True)

def send_mail_mime(request, to, frm, subject, msg, cc=None, extra=None, toUser=False, bcc=None):
    """Send MIME message with content already filled in."""
    
    condition_message(to, frm, subject, msg, cc, extra)

    # start debug server with python -m smtpd -n -c DebuggingServer localhost:2025
    # then put USING_DEBUG_EMAIL_SERVER=True and EMAIL_HOST='localhost'
    # and EMAIL_PORT=2025 in settings_local.py
    debugging = getattr(settings, "USING_DEBUG_EMAIL_SERVER", False) and settings.EMAIL_HOST == 'localhost' and settings.EMAIL_PORT == 2025

    if settings.SERVER_MODE == 'development':
        show_that_mail_was_sent(request,'In production, email would have been sent',msg,bcc)

    if test_mode or debugging or settings.SERVER_MODE == 'production':
        try:
            send_smtp(msg,bcc)
        except smtplib.SMTPException as e:
            log_smtp_exception(e)
            build_warning_message(request, e)
            send_error_email(e)

        show_that_mail_was_sent(request,'Email was sent',msg,bcc)
            
    elif settings.SERVER_MODE == 'test':
	if toUser:
	    copy_email(msg, to, toUser=True, originalBcc=bcc)
	elif request and request.COOKIES.has_key( 'testmailcc' ):
	    copy_email(msg, request.COOKIES[ 'testmailcc' ],originalBcc=bcc)
    try:
	copy_to = settings.EMAIL_COPY_TO
    except AttributeError:
        copy_to = "ietf.tracker.archive+%s@gmail.com" % settings.SERVER_MODE
    if copy_to and not test_mode and not debugging: # if we're running automated tests, this copy is just annoying
        if bcc:
            msg['X-Tracker-Bcc']=bcc
        try:
            copy_email(msg, copy_to, originalBcc=bcc)
        except smtplib.SMTPException as e:
            log_smtp_exception(e)
            build_warning_message(request, e)
            send_error_email(e)

    return msg

def parse_preformatted(preformatted, extra={}, override={}):
    """Parse preformatted string containing mail with From:, To:, ...,"""
    msg = message_from_string(preformatted.encode("utf-8"))

    for k, v in override.iteritems():
         if k in msg:
              del msg[k]
         msg[k] = v

    headers = copy.copy(msg)
    for key in ['To', 'From', 'Subject', 'Bcc']:
        del headers[key]
    for k, v in extra.iteritems():
         if k in headers:
              del headers[k]
         headers[k] = v

    bcc = msg['Bcc']
    del msg['Bcc']

    return (msg, headers, bcc)

def send_mail_preformatted(request, preformatted, extra={}, override={}):
    """Parse preformatted string containing mail with From:, To:, ...,
    and send it through the standard IETF mail interface (inserting
    extra headers as needed)."""

    (msg,headers,bcc) = parse_preformatted(preformatted, extra, override)
    send_mail_text(request, msg['To'], msg["From"], msg["Subject"], msg.get_payload(), extra=headers, bcc=bcc)
    return msg

def send_mail_message(request, message, extra={}):
    """Send a Message object."""
    # note that this doesn't handle MIME messages at the moment

    e = extra.copy()
    if message.reply_to:
        e['Reply-to'] = message.reply_to

    return send_mail_text(request, message.to, message.frm, message.subject,
                          message.body, cc=message.cc, bcc=message.bcc, extra=e)

def exception_components(e):
    # See if it's a non-smtplib exception that we faked
    if len(e.args)==1 and isinstance(e.args[0],dict) and e.args[0].has_key('really'):
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
    log("SMTP Exception: %s : %s" % (extype,value))
    if isinstance(e,SMTPSomeRefusedRecipients):
        log("     SomeRefused: %s"%(e.summary_refusals()))
    log("     Traceback: %s" % tb) 
    return (extype, value, tb)

def build_warning_message(request, e):
    (extype, value, tb) = exception_components(e)
    if request:
        warning =  "An error occured while sending email:\n"
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
            copy_to = "ietf.tracker.archive+%s@gmail.com" % settings.SERVER_MODE
        if copy_to and not test_mode and not debugging: # if we're running automated tests, this copy is just annoying
            copy_email(msg, copy_to,originalBcc=None)
    except smtplib.SMTPException:
        log("Exception encountered while sending a ticket to the secretariat")
        (extype,value) = sys.exc_info()[:2]
        log("SMTP Exception: %s : %s" % (extype,value))
    
