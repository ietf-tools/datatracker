# Copyright The IETF Trust 2007, All Rights Reserved

from email.Utils import make_msgid, formatdate, formataddr, parseaddr, getaddresses
from email.MIMEText import MIMEText
from email.MIMEMessage import MIMEMessage
from email.MIMEMultipart import MIMEMultipart
from email import message_from_string
import smtplib
from django.conf import settings
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
from contextlib import contextmanager

# Testing mode:
# import ietf.utils.mail
# ietf.utils.mail.test_mode = True
# ... send some mail ...
# ... inspect ietf.utils.mail.outbox ...
# ... call ietf.utils.mail.empty_outbox() ...
test_mode = False
outbox = []

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

    If someone has set test_mode=True, then just append the msg to
    the outbox.
    '''
    add_headers(msg)
    (fname, frm) = parseaddr(msg.get('From'))
    addrlist = msg.get_all('To') + msg.get_all('Cc', [])
    if bcc:
        addrlist += [bcc]
    to = [addr for name, addr in getaddresses(addrlist) if addr != '' ]
    if not to:
        log("No addressees for email from '%s', subject '%s'.  Nothing sent." % (frm, msg.get('Subject', '[no subject]')))
    else:
        if test_mode:
            outbox.append(msg)
            return
        server = None
        try:
            server = smtplib.SMTP()
            #log("SMTP server: %s" % repr(server))
            #if settings.DEBUG:
            #    server.set_debuglevel(1)
            conn_code, conn_msg = server.connect(settings.EMAIL_HOST, settings.EMAIL_PORT)
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


def send_mail_text(request, to, frm, subject, txt, cc=None, extra=None, toUser=False, bcc=None):
    """Send plain text message."""
    if isinstance(txt, unicode):
        msg = MIMEText(txt.encode('utf-8'), 'plain', 'UTF-8')
    else:
        msg = MIMEText(txt)
    send_mail_mime(request, to, frm, subject, msg, cc, extra, toUser, bcc)
        
def send_mail_mime(request, to, frm, subject, msg, cc=None, extra=None, toUser=False, bcc=None):
    """Send MIME message with content already filled in."""
    if isinstance(frm, tuple):
	frm = formataddr(frm)
    if isinstance(to, list) or isinstance(to, tuple):
        to = ", ".join([isinstance(addr, tuple) and formataddr(addr) or addr for addr in to if addr])
    if isinstance(cc, list) or isinstance(cc, tuple):
        cc = ", ".join([isinstance(addr, tuple) and formataddr(addr) or addr for addr in cc if addr])
    if frm:
	msg['From'] = frm
    msg['To'] = to
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
    # start debug server with python -m smtpd -n -c DebuggingServer localhost:2025
    # then put USING_DEBUG_EMAIL_SERVER=True and EMAIL_HOST='localhost'
    # and EMAIL_PORT=2025 in settings_local.py
    debugging = getattr(settings, "USING_DEBUG_EMAIL_SERVER", False) and settings.EMAIL_HOST == 'localhost' and settings.EMAIL_PORT == 2025

    if test_mode or debugging or settings.SERVER_MODE == 'production':
	send_smtp(msg, bcc)
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
        copy_email(msg, copy_to,originalBcc=bcc)

def send_mail_preformatted(request, preformatted, extra={}, override={}):
    """Parse preformatted string containing mail with From:, To:, ...,
    and send it through the standard IETF mail interface (inserting
    extra headers as needed)."""
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
    
    send_mail_text(request, msg['To'], msg["From"], msg["Subject"], msg.get_payload(), extra=headers, bcc=bcc)
    return msg

def send_mail_message(request, message, extra={}):
    """Send a Message object."""
    # note that this doesn't handle MIME messages at the moment

    e = extra.copy()
    if message.reply_to:
        e['Reply-to'] = message.reply_to

    send_mail_text(request, message.to, message.frm, message.subject,
                   message.body, cc=message.cc, bcc=message.bcc, extra=e)

def log_smtp_exception(e):

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
        

    log("SMTP Exception: %s : %s" % (extype,value))
    if isinstance(e,SMTPSomeRefusedRecipients):
        log("     SomeRefused: %s"%(e.summary_refusals()))
    log("     Traceback: %s" % tb) 
    return (extype, value, tb)

@contextmanager
def smtp_error_logging(thing):
    try:
        yield thing
    except smtplib.SMTPException as e:
        (extype, value, tb) = log_smtp_exception(e)

        msg = textwrap.dedent("""\
                  To: <action@ietf.org> 
                  From: %s
                  """) % settings.SERVER_EMAIL
        if isinstance(e,SMTPSomeRefusedRecipients):
            msg += textwrap.dedent("""\
                      Subject: Some recipients were refused while sending mail with Subject: %s

                      This is a message from the datatracker to IETF-Action about an email
                      delivery failure, when sending email from the datatracker.

                      %s

                      The original message follows:
                      -------- BEGIN ORIGINAL MESSAGE --------
                      %s
                      --------- END ORIGINAL MESSAGE ---------
                      """) % (e.original_msg.get('Subject', '[no subject]'),e.detailed_refusals(),e.original_msg.as_string())
        else:
            msg += textwrap.dedent("""\
                      Subject: Datatracker error while sending email

                      This is a message from the datatracker to IETF-Action about an email
                      delivery failure, when sending email from the datatracker.

                      The original message was not delivered to anyone.

                      SMTP Exception: %s

                      Error Message: %s
                     
                      """) % (extype,value)
            if hasattr(e,'original_msg'):
                msg += textwrap.dedent("""\
                      The original message follows:
                      -------- BEGIN ORIGINAL MESSAGE --------
                      %s
                      --------- END ORIGINAL MESSAGE ---------
                      """) % e.original_msg.as_string()
        try:
            send_mail_preformatted(request=None, preformatted=msg)
        except smtplib.SMTPException:
            log("Exception encountered while sending a ticket to the secretariat")
            (extype,value) = sys.exc_info()[:2]
            log("SMTP Exception: %s : %s" % (extype,value))
