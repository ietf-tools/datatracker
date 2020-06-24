#
# pyzmail/generate.py
# (c) Alain Spineux <alain.spineux@gmail.com>
# http://www.magiksys.net/pyzmail
# Released under LGPL

"""
Useful functions to compose and send emails.

For short:

>>> payload, mail_from, rcpt_to, msg_id=compose_mail((u'Me', 'me@foo.com'),
... [(u'Him', 'him@bar.com')], u'the subject', 'iso-8859-1', ('Hello world', 'us-ascii'),
... attachments=[('attached', 'text', 'plain', 'text.txt', 'us-ascii')])
... #doctest: +SKIP
>>> error=send_mail(payload, mail_from, rcpt_to, 'localhost', smtp_port=25)
... #doctest: +SKIP
"""

import os, sys
import time
import base64
import smtplib, socket
import email
import email.encoders
import email.header
import email.utils
import email.mime
import email.mime.base
import email.mime.text
import email.mime.image
import email.mime.multipart

from . import utils

def format_addresses(addresses, header_name=None, charset=None):
    """
    Convert a list of addresses into a MIME-compliant header for a From, To, Cc,
    or any other I{address} related field. 
    This mixes the use of email.utils.formataddr() and email.header.Header().
    
    @type addresses: list
    @param addresses: list of addresses, can be a mix of string a tuple  of the form 
        C{[ 'address@domain', (u'Name', 'name@domain'), ...]}. 
        If C{u'Name'} contains non us-ascii characters, it must be a 
        unicode string or encoded using the I{charset} argument.
    @type header_name: string or None
    @keyword header_name: the name of the header. Its length is used to limit 
        the length of the first line of the header according the RFC's 
        requirements. (not very important, but it's better to match the 
        requirements when possible)
    @type charset: str
    @keyword charset: the encoding charset for non unicode I{name} and a B{hint}
        for encoding of unicode string. In other words,
        if the I{name} of an address in a byte string containing non 
        I{us-ascii} characters, then C{name.decode(charset)}
        must generate the expected result. If a unicode string
        is used instead, charset will be tried to encode the
        string, if it fail, I{utf-8} will be used.
        With B{Python 3.x} I{charset} is no more a hint and an exception will
        be raised instead of using I{utf-8} has a fall back.
    @rtype: str    
    @return: the encoded list of formated addresses separated by commas, 
    ready to use as I{Header} value.

    >>> print format_addresses([('John', 'john@foo.com') ], 'From', 'us-ascii').encode()
    John <john@foo.com>
    >>> print format_addresses([(u'l\\xe9o', 'leo@foo.com') ], 'To', 'iso-8859-1').encode()
    =?iso-8859-1?q?l=E9o?= <leo@foo.com>
    >>> print format_addresses([(u'l\\xe9o', 'leo@foo.com') ], 'To', 'us-ascii').encode() 
    ... # don't work in 3.X because charset is more than a hint 
    ... #doctest: +SKIP
    =?utf-8?q?l=C3=A9o?= <leo@foo.com>
    >>> # because u'l\xe9o' cannot be encoded into us-ascii, utf8 is used instead
    >>> print format_addresses([('No\\xe9', 'noe@f.com'), (u'M\\u0101ori', 'maori@b.com')  ], 'Cc', 'iso-8859-1').encode()
    ... # don't work in 3.X because charset is more than a hint 
    ... #doctest: +SKIP
    =?iso-8859-1?q?No=E9?= <noe@f.com> , =?utf-8?b?TcSBb3Jp?= <maori@b.com>
    >>> # 'No\xe9' is already encoded into iso-8859-1, but u'M\\u0101ori' cannot be encoded into iso-8859-1 
    >>> # then utf8 is used here
    >>> print format_addresses(['a@bar.com', ('John', 'john@foo.com') ], 'From', 'us-ascii').encode()
    a@bar.com , John <john@foo.com>
    """
    header=email.header.Header(charset=charset, header_name=header_name)
    for i, address in enumerate(addresses):
        if i!=0:
            # add separator between addresses
            header.append(',', charset='us-ascii') 

        try:
            name, addr=address
        except ValueError:
            # address is not a tuple, their is no name, only email address
            header.append(address, charset='us-ascii') 
        else:
            # check if address name is a unicode or byte string in "pure" us-ascii
            if utils.is_usascii(name):
                # name is a us-ascii byte string, i can use formataddr
                formated_addr=email.utils.formataddr((name, addr))
                # us-ascii must be used and not default 'charset'  
                header.append(formated_addr, charset='us-ascii')
            else:
                # this is not as "pure" us-ascii string
                # Header will use "RFC2047" to encode the address name
                # if name is byte string, charset will be used to decode it first
                header.append(name)
                # here us-ascii must be used and not default 'charset'  
                header.append('<%s>' % (addr,), charset='us-ascii') 
                    
    return header


def build_mail(text, html=None, attachments=[], embeddeds=[]):
    """
    Generate the core of the email message regarding the parameters.
    The structure of the MIME email may vary, but the general one is as follow::

        multipart/mixed (only if attachments are included)
         |
         +-- multipart/related (only if embedded contents are included) 
         |    |
         |    +-- multipart/alternative (only if text AND html are available)
         |    |    |
         |    |    +-- text/plain (text version of the message)
         |    |    +-- text/html  (html version of the message)
         |    |     
         |    +-- image/gif  (where to include embedded contents)
         |
         +-- application/msword (where to add attachments)

    @param text: the text version of the message, under the form of a tuple:
        C{(encoded_content, encoding)} where I{encoded_content} is a byte string
        encoded using I{encoding}.
        I{text} can be None if the message has no text version. 
    @type text: tuple or None
    @keyword html: the HTML version of the message, under the form of a tuple:
        C{(encoded_content, encoding)} where I{encoded_content} is a byte string
        encoded using I{encoding}
        I{html} can be None if the message has no HTML version. 
    @type html: tuple or None
    @keyword attachments: the list of attachments to include into the mail, in the
        form [(data, maintype, subtype, filename, charset), ..] where :
            - I{data} : is the raw data, or a I{charset} encoded string for 'text'
            content. 
            - I{maintype} : is a MIME main type like : 'text', 'image', 'application' ....
            - I{subtype} : is a MIME sub type of the above I{maintype} for example :
            'plain', 'png', 'msword' for respectively 'text/plain', 'image/png',
            'application/msword'.
            - I{filename} this is the filename of the attachment, it must be a
            'us-ascii' string or a tuple of the form
            C{(encoding, language, encoded_filename)} 
            following the RFC2231 requirement, for example 
            C{('iso-8859-1', 'fr', u'r\\xe9pertoir.png'.encode('iso-8859-1'))}
            - I{charset} : if I{maintype} is 'text', then I{data} must be encoded
            using this I{charset}. It can be None for non 'text' content.
    @type attachments: list
    @keyword embeddeds: is a list of documents embedded inside the HTML or text 
        version of the message. It is similar to the I{attachments} list,  
        but I{filename} is replaced by I{content_id} that is related to
        the B{cid} reference into the HTML or text version of the message.
    @type embeddeds: list
    @rtype: inherit from email.Message 
    @return: the message in a MIME object 

    >>> mail=build_mail(('Hello world', 'us-ascii'), attachments=[('attached', 'text', 'plain', 'text.txt', 'us-ascii')])
    >>> mail.set_boundary('===limit1==')
    >>> print mail.as_string(unixfrom=False)    
    Content-Type: multipart/mixed; boundary="===limit1=="
    MIME-Version: 1.0
    <BLANKLINE>
    --===limit1==
    Content-Type: text/plain; charset="us-ascii"
    MIME-Version: 1.0
    Content-Transfer-Encoding: 7bit
    <BLANKLINE>
    Hello world
    --===limit1==
    Content-Type: text/plain; charset="us-ascii"
    MIME-Version: 1.0
    Content-Transfer-Encoding: 7bit
    Content-Disposition: attachment; filename="text.txt"
    <BLANKLINE>
    attached
    --===limit1==--
    """

    main=text_part=html_part=None
    if text:
        content, charset=text
        main=text_part=email.mime.text.MIMEText(content, 'plain', charset)
    
    if html:
        content, charset=html
        main=html_part=email.mime.text.MIMEText(content, 'html', charset)
        
    if not text_part and not html_part:
        main=text_part=email.mime.text.MIMEText('', 'plain', 'us-ascii')
    elif text_part and html_part:
        # need to create a multipart/alternative to include text and html version
        main=email.mime.multipart.MIMEMultipart('alternative', None, [text_part, html_part])
    
    if embeddeds:
        related=email.mime.multipart.MIMEMultipart('related')
        related.attach(main)
        for part in embeddeds:
            if not isinstance(part, email.mime.base.MIMEBase):
                data, maintype, subtype, content_id, charset=part
                if (maintype=='text'):
                    part=email.mime.text.MIMEText(data, subtype, charset)
                else:
                    part=email.mime.base.MIMEBase(maintype, subtype)
                    part.set_payload(data)
                    email.encoders.encode_base64(part)
                part.add_header('Content-ID', '<'+content_id+'>')
                part.add_header('Content-Disposition', 'inline')
            related.attach(part)
        main=related
            
    if attachments:
        mixed=email.mime.multipart.MIMEMultipart('mixed')
        mixed.attach(main)
        for part in attachments:
            if not isinstance(part, email.mime.base.MIMEBase):
                data, maintype, subtype, filename, charset=part
                if (maintype=='text'):
                    part=email.mime.text.MIMEText(data, subtype, charset)
                else:
                    part=email.mime.base.MIMEBase(maintype, subtype)
                    part.set_payload(data)
                    email.encoders.encode_base64(part)
                part.add_header('Content-Disposition', 'attachment', filename=filename)
            mixed.attach(part)
        main=mixed
        
    return main

def complete_mail(message, sender, recipients, subject, default_charset, cc=[], bcc=[], message_id_string=None, date=None, headers=[]):
    """
    Fill in the From, To, Cc, Subject, Date and Message-Id I{headers} of 
    one existing message regarding the parameters.

    @type message:email.Message 
    @param message: the message to fill in
    @type sender: tuple
    @param sender: a tuple of the form (u'Sender Name', 'sender.address@domain.com')
    @type recipients: list
    @param recipients: a list of addresses. Address can be tuple or string like
    expected by L{format_addresses()}, for example: C{[ 'address@dmain.com', 
    (u'Recipient Name', 'recipient.address@domain.com'), ... ]}
    @type subject: str
    @param subject: The subject of the message, can be a unicode string or a
    string encoded using I{default_charset} encoding. Prefert unicode to
    byte string here.
    @type default_charset: str  
    @param default_charset: The default charset for this email. Arguments
    that are non unicode string are supposed to be encoded using this charset. 
    This I{charset} will be used has an hint when encoding mail content. 
    @type cc: list
    @keyword cc: The I{carbone copy} addresses. Same format as the I{recipients}
    argument.
    @type bcc: list
    @keyword bcc: The I{blind carbone copy} addresses. Same format as the I{recipients}
    argument.
    @type message_id_string: str or None
    @keyword message_id_string: if None, don't append any I{Message-ID} to the 
    mail, let the SMTP do the job, else use the string to generate a unique 
    I{ID} using C{email.utils.make_msgid()}. The generated value is 
    returned as last argument. For example use the name of your application.
    @type date: int or None
    @keyword date: utc time in second from the epoch or None. If None then
    use curent time C{time.time()} instead.
    @type headers: list of tuple
    @keyword headers: a list of C{(field, value)} tuples to fill in the mail 
    header fields. Values are encoded using I{default_charset}.
    @rtype: tuple
    @return: B{(payload, mail_from, rcpt_to, msg_id)}
        - I{payload} (str) is the content of the email, generated from the message
        - I{mail_from} (str) is the address of the sender to pass to the SMTP host
        - I{rcpt_to} (list) is a list of the recipients addresses to pass to the SMTP host
        of the form C{[ 'a@b.com', c@d.com', ]}. This combine all recipients, 
        I{carbone copy} addresses and I{blind carbone copy} addresses.
        - I{msg_id} (None or str) None if message_id_string==None else the generated value for 
        the message-id. If not None, this I{Message-ID} is already written 
        into the payload.
        
    >>> import email.mime.text
    >>> msg=email.mime.text.MIMEText('The text.', 'plain', 'us-ascii')
    >>> # I could use build_mail() instead
    >>> payload, mail_from, rcpt_to, msg_id=complete_mail(msg, ('Me', 'me@foo.com'),
    ... [ ('Him', 'him@bar.com'), ], 'Non unicode subject', 'iso-8859-1',
    ... cc=['her@bar.com',], date=1313558269, headers=[('User-Agent', u'pyzmail'), ])
    >>> print payload
    ... # 3.X encode  User-Agent: using 'iso-8859-1' even if it contains only us-asccii
    ... # doctest: +ELLIPSIS  
    Content-Type: text/plain; charset="us-ascii"
    MIME-Version: 1.0
    Content-Transfer-Encoding: 7bit
    From: Me <me@foo.com>
    To: Him <him@bar.com>
    Cc: her@bar.com
    Subject: =?iso-8859-1?q?Non_unicode_subject?=
    Date: ...
    User-Agent: ...pyzmail...
    <BLANKLINE>
    The text.
    >>> print 'mail_from=%r rcpt_to=%r' % (mail_from, rcpt_to)
    mail_from='me@foo.com' rcpt_to=['him@bar.com', 'her@bar.com']
    """
    def getaddr(address):
        if isinstance(address, tuple):
            return address[1]
        else:
            return address

    mail_from=getaddr(sender[1])
    rcpt_to=list(map(getaddr, recipients))
    rcpt_to.extend(list(map(getaddr, cc)))
    rcpt_to.extend(list(map(getaddr, bcc)))

    message['From'] = format_addresses([ sender, ], header_name='from', charset=default_charset)
    if recipients:
        message['To'] = format_addresses(recipients, header_name='to', charset=default_charset)
    if cc:
        message['Cc'] = format_addresses(cc, header_name='cc', charset=default_charset)
    message['Subject'] = email.header.Header(subject, default_charset)
    if date:
        utc_from_epoch=date
    else:
        utc_from_epoch=time.time()
    message['Date'] = email.utils.formatdate(utc_from_epoch, localtime=True)
    
    if message_id_string:
        msg_id=message['Message-Id']=email.utils.make_msgid(message_id_string)
    else:
        msg_id=None
        
    for field, value in headers:
        message[field]=email.header.Header(value, default_charset)

    payload=message.as_string()
    
    return payload, mail_from, rcpt_to, msg_id

def compose_mail(sender, recipients, subject, default_charset, text, html=None, attachments=[], embeddeds=[], cc=[], bcc=[], message_id_string=None, date=None, headers=[]):
    """
    Compose an email regarding the arguments. Call L{build_mail()} and 
    L{complete_mail()} at once.
    
    Read the B{parameters} descriptions of both functions L{build_mail()} and L{complete_mail()}. 
    
    Returned value is the same as for L{build_mail()} and L{complete_mail()}.
    You can pass the returned values to L{send_mail()} or L{send_mail2()}.

    @rtype: tuple
    @return: B{(payload, mail_from, rcpt_to, msg_id)}

    >>> payload, mail_from, rcpt_to, msg_id=compose_mail((u'Me', 'me@foo.com'), [(u'Him', 'him@bar.com')], u'the subject', 'iso-8859-1', ('Hello world', 'us-ascii'), attachments=[('attached', 'text', 'plain', 'text.txt', 'us-ascii')])
    """
    message=build_mail(text, html, attachments, embeddeds)
    return complete_mail(message, sender, recipients, subject, default_charset, cc, bcc, message_id_string, date, headers)
        

def send_mail2(payload, mail_from, rcpt_to, smtp_host, smtp_port=25, smtp_mode='normal', smtp_login=None, smtp_password=None):
    """
    Send the message to a SMTP host. Look at the L{send_mail()} documentation.
    L{send_mail()} call this function and catch all exceptions to convert them
    into a user friendly error message. The returned value 
    is always a dictionary. It can be empty if all recipients have been
    accepted. 

    @rtype: dict
    @return: This function return the value returnd by C{smtplib.SMTP.sendmail()}
    or raise the same exceptions.  
    
    This method will return normally if the mail is accepted for at least one 
    recipient. Otherwise it will raise an exception. That is, if this 
    method does not raise an exception, then someone should get your mail. 
    If this method does not raise an exception, it returns a dictionary, 
    with one entry for each recipient that was refused. Each entry contains a
    tuple of the SMTP error code and the accompanying error message sent by the server.
    
    @raise smtplib.SMTPException: Look at the standard C{smtplib.SMTP.sendmail()} documentation.
    
    """
    if smtp_mode=='ssl':
        smtp=smtplib.SMTP_SSL(smtp_host, smtp_port)
    else:
        smtp=smtplib.SMTP(smtp_host, smtp_port)
        if smtp_mode=='tls':
            smtp.starttls()
            
    if smtp_login and smtp_password:
        if sys.version_info<(3, 0):
            # python 2.x  
            # login and password must be encoded 
            # because HMAC used in CRAM_MD5 require non unicode string
            smtp.login(smtp_login.encode('utf-8'), smtp_password.encode('utf-8'))
        else:
            #python 3.x
            smtp.login(smtp_login, smtp_password)
    try:
        ret=smtp.sendmail(mail_from, rcpt_to, payload)
    finally:
        try:
            smtp.quit()
        except Exception as e:
            pass
            
    return ret

def send_mail(payload, mail_from, rcpt_to, smtp_host, smtp_port=25, smtp_mode='normal', smtp_login=None, smtp_password=None):
    """
    Send the message to a SMTP host. Handle SSL, TLS and authentication.
    I{payload}, I{mail_from} and I{rcpt_to} can come from values returned by
    L{complete_mail()}. This function call L{send_mail2()} but catch all
    exceptions and return friendly error message instead. 
     
    @type payload: str
    @param payload: the mail content.
    @type mail_from: str
    @param mail_from: the sender address, for example: C{'me@domain.com'}.
    @type rcpt_to: list
    @param rcpt_to: The list of the recipient addresses in the form 
    C{[ 'a@b.com', c@d.com', ]}. No names here, only email addresses.
    @type smtp_host: str
    @param smtp_host: the IP address or the name of the SMTP host.
    @type smtp_port: int
    @keyword smtp_port: the port to connect to on the SMTP host. Default is C{25}.
    @type smtp_mode: str
    @keyword smtp_mode: the way to connect to the SMTP host, can be:  
                      C{'normal'}, C{'ssl'} or C{'tls'}. default is C{'normal'}
    @type smtp_login: str or None
    @keyword smtp_login: If authentication is required, this is the login. 
                       Be carefull to I{UTF8} encode your login if it contains
                       non I{us-ascii} characters.
    @type smtp_password: str or None
    @keyword smtp_password: If authentication is required, this is the password.
                          Be carefull to I{UTF8} encode your password if it 
                          contains non I{us-ascii} characters.

    @rtype: dict or str
    @return: This function return a dictionary of failed recipients 
    or a string with an error message. 
    
    If all recipients have been accepted the dictionary is empty. If the
    returned value is a string, none of the recipients will get the message.
    
    The dictionary is exactly of the same sort as 
    smtplib.SMTP.sendmail() returns with one entry for each recipient that 
    was refused. Each entry contains a tuple of the SMTP error code and 
    the accompanying error message sent by the server. 
    
    Example:
    
    >>> send_mail('Subject: hello\\n\\nmessage', 'a@foo.com', [ 'b@bar.com', ], 'localhost') #doctest: +SKIP
    {}
    
    Here is how to use the returned value::
        if isinstance(ret, dict):
          if ret:
            print 'failed' recipients:
            for recipient, (code, msg) in ret.iteritems():
                print 'code=%d recipient=%s\terror=%s' % (code, recipient, msg)
          else:
            print 'success'
        else:
          print 'Error:', ret

    To use your GMail account to send your mail::
        smtp_host='smtp.gmail.com'
        smtp_port=587
        smtp_mode='tls'
        smtp_login='your.gmail.addresse@gmail.com'
        smtp_password='your.gmail.password'
        
    Use your GMail address for the sender ! 

    """

    error=dict()
    try:
        ret=send_mail2(payload, mail_from, rcpt_to, smtp_host, smtp_port, smtp_mode, smtp_login, smtp_password)
    except (socket.error, ) as e:
        error='server %s:%s not responding: %s' % (smtp_host, smtp_port, e)
    except smtplib.SMTPAuthenticationError as e:
        error='authentication error: %s' % (e, )
    except smtplib.SMTPRecipientsRefused as e:
        # code, error=e.recipients[recipient_addr]
        error='all recipients refused: '+', '.join(list(e.recipients.keys()))
    except smtplib.SMTPSenderRefused as e:
        # e.sender, e.smtp_code, e.smtp_error
        error='sender refused: %s' % (e.sender, )
    except smtplib.SMTPDataError as e:
        error='SMTP protocol mismatch: %s' % (e, )
    except smtplib.SMTPHeloError as e:
        error="server didn't reply properly to the HELO greeting: %s" % (e, )
    except smtplib.SMTPException as e:
        error='SMTP error: %s' % (e, )
#    except Exception, e:
#        raise # unknown error
    else:
        # failed addresses and error messages
        error=ret
        
    return error

