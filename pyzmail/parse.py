#
# pyzmail/parse.py
# (c) Alain Spineux <alain.spineux@gmail.com>
# http://www.magiksys.net/pyzmail
# Released under LGPL

"""
Useful functions to parse emails

@var email_address_re: a regex that match well formed email address (from perlfaq9)
@undocumented: atom_rfc2822
@undocumented: atom_posfix_restricted
@undocumented: atom
@undocumented: dot_atom
@undocumented: local
@undocumented: domain_lit
@undocumented: domain
@undocumented: addr_spec
"""

import re
import io
import email
import email.errors
import email.header
import email.message
import mimetypes

from .utils import *

# email address REGEX matching the RFC 2822 spec from perlfaq9
#    my $atom       = qr{[a-zA-Z0-9_!#\$\%&'*+/=?\^`{}~|\-]+};
#    my $dot_atom   = qr{$atom(?:\.$atom)*};
#    my $quoted     = qr{"(?:\\[^\r\n]|[^\\"])*"};
#    my $local      = qr{(?:$dot_atom|$quoted)};
#    my $domain_lit = qr{\[(?:\\\S|[\x21-\x5a\x5e-\x7e])*\]};
#    my $domain     = qr{(?:$dot_atom|$domain_lit)};
#    my $addr_spec  = qr{$local\@$domain};
# 
# Python's translation
atom_rfc2822=r"[a-zA-Z0-9_!#\$\%&'*+/=?\^`{}~|\-]+"
atom_posfix_restricted=r"[a-zA-Z0-9_#\$&'*+/=?\^`{}~|\-]+" # without '!' and '%'
atom=atom_rfc2822
dot_atom=atom  +  r"(?:\."  +  atom  +  ")*"
quoted=r'"(?:\\[^\r\n]|[^\\"])*"'
local="(?:"  +  dot_atom  +  "|"  +  quoted  +  ")"
domain_lit=r"\[(?:\\\S|[\x21-\x5a\x5e-\x7e])*\]"
domain="(?:"  +  dot_atom  +  "|"  +  domain_lit  +  ")"
addr_spec=local  +  "@"  +  domain
# and the result
email_address_re=re.compile('^'+addr_spec+'$')

class MailPart:
    """
    Data related to a mail part (aka message content, attachment or  
    embedded content in an email)
    
    @type charset: str or None
    @ivar charset: the encoding of the I{get_payload()} content if I{type} is 'text/*'
    and charset has been specified in the message
    @type content_id: str or None
    @ivar content_id: the MIME Content-ID if specified in the message.
    @type description: str or None
    @ivar description: the MIME Content-Description if specified in the message.
    @type disposition: str or None
    @ivar disposition: C{None}, C{'inline'} or C{'attachment'} depending
    the MIME Content-Disposition value
    @type filename: unicode or None
    @ivar filename: the name of the file, if specified in the message. 
    @type part: inherit from email.mime.base.MIMEBase
    @ivar part: the related part inside the message.
    @type is_body: str or None
    @ivar is_body: None if this part is not the mail content itself (an 
        attachment or embedded content), C{'text/plain'} if this part is the 
        text content or C{'text/html'} if this part is the HTML version. 
    @type sanitized_filename: str or None
    @ivar sanitized_filename: This field is filled by L{PyzMessage} to store 
    a valid unique filename related or not with the original filename.
    @type type: str
    @ivar type: the MIME type, like 'text/plain', 'image/png', 'application/msword' ...
    """
            
    def __init__(self, part, filename=None, type=None, charset=None, content_id=None, description=None, disposition=None, sanitized_filename=None, is_body=None):
        """
        Create an mail part and initialize all attributes
        """
        self.part=part          # original python part
        self.filename=filename  # filename in unicode (if any) 
        self.type=type          # the mime-type
        self.charset=charset    # the charset (if any) 
        self.description=description    # if any 
        self.disposition=disposition    # 'inline', 'attachment' or None
        self.sanitized_filename=sanitized_filename # cleanup your filename here (TODO)  
        self.is_body=is_body        # usually in (None, 'text/plain' or 'text/html')
        self.content_id=content_id  # if any
        if self.content_id:
            # strip '<>' to ease search and replace in "root" content (TODO) 
            if self.content_id.startswith('<') and self.content_id.endswith('>'):
                self.content_id=self.content_id[1:-1]

    def get_payload(self):
        """
        decode and return part payload. if I{type} is 'text/*' and I{charset} 
        not C{None}, be careful to take care of the text encoding. Use 
        something like C{part.get_payload().decode(part.charset)}
        """
        
        payload=None
        if self.type.startswith('message/'): 
            # I don't use msg.as_string() because I want to use mangle_from_=False
            if sys.version_info<(3, 0):
                # python 2.x  
                from email.generator import Generator
                fp = io.StringIO()
                g = Generator(fp, mangle_from_=False)
                g.flatten(self.part, unixfrom=False)
                payload=fp.getvalue()
            else:
                # support only for python >= 3.2
                from email.generator import BytesGenerator
                import io
                fp = io.BytesIO()
                g = BytesGenerator(fp, mangle_from_=False)
                g.flatten(self.part, unixfrom=False)
                payload=fp.getvalue()
                
        else:
            payload=self.part.get_payload(decode=True)
        return payload
                        
    def __repr__(self):
        st='MailPart<'
        if self.is_body:
            st+='*'
        st+=self.type
        if self.charset:
            st+=' charset='+self.charset
        if self.filename:
            st+=' filename='+self.filename
        if self.content_id:
            st+=' content_id='+self.content_id
        st+=' len=%d' % (len(self.get_payload()), )
        st+='>'
        return st



_line_end_re=re.compile('\r\n|\n\r|\n|\r')

def _friendly_header(header):
    """
    Convert header returned by C{email.message.Message.get()} into a 
    user friendly string. 

    Py3k C{email.message.Message.get()} return C{header.Header()} with charset 
    set to C{charset.UNKNOWN8BIT} when the header contains invalid characters, 
    else it return I{str} as  Python 2.X does   
    
    @type header: str or email.header.Header
    @param header: the header to convert into a user friendly string
    
    @rtype: str
    @returns: the converter header 
    """
    
    save=header
    if isinstance(header, email.header.Header):
        header=str(header)
        
    return re.sub(_line_end_re, ' ', header)
        
def decode_mail_header(value, default_charset='us-ascii'):
    """
    Decode a header value into a unicode string. 
    Works like a more smarter python 
    C{u"".join(email.header.decode_header()} function
    
    @type value: str
    @param value: the value of the header. 
    @type default_charset: str
    @keyword default_charset: if one charset used in the header (multiple charset 
    can be mixed) is unknown, then use this charset instead.  
    
    >>> decode_mail_header('=?iso-8859-1?q?Courrier_=E8lectronique_en_Fran=E7ais?=')
    u'Courrier \\xe8lectronique en Fran\\xe7ais'
    """

#    value=_friendly_header(value)
    try:
        headers=email.header.decode_header(value)
    except email.errors.HeaderParseError:
        # this can append in email.base64mime.decode(), for example for this value:
        # '=?UTF-8?B?15HXmdeh15jXqNeVINeY15DXpteUINeTJ9eV16jXlSDXkdeg15XXldeUINem15PXpywg15TXptei16bXldei15nXnSDXqdecINek15zXmdeZ?==?UTF-8?B?157XldeR15nXnCwg157Xldek16Ig157Xl9eV15wg15HXodeV15bXnyDXk9ec15DXnCDXldeh15gg157Xl9eR16rXldeqINep15wg15HXmdeQ?==?UTF-8?B?15zXmNeZ?='
        # then return a sanitized ascii string
        # TODO: some improvements are possible here, but a failure here is
        # unlikely
        return value.encode('us-ascii', 'replace').decode('us-ascii')
    else:
        for i, (text, charset) in enumerate(headers):
            # python 3.x
            # email.header.decode_header('a') -> [('a', None)]
            # email.header.decode_header('a =?ISO-8859-1?Q?foo?= b')
            # --> [(b'a', None), (b'foo', 'iso-8859-1'), (b'b', None)]
            # in Py3 text is sometime str and sometime byte :-(
            # python 2.x
            # email.header.decode_header('a') -> [('a', None)]
            # email.header.decode_header('a =?ISO-8859-1?Q?foo?= b')
            # --> [('a', None), ('foo', 'iso-8859-1'), ('b', None)]
            if (charset is None and sys.version_info>=(3, 0)):
                # Py3
                if isinstance(text, str):
                    # convert Py3 string into bytes string to be sure their is no 
                    # non us-ascii chars and because next line expect byte string
                    text=text.encode('us-ascii', 'replace')
            try:
                headers[i]=text.decode(charset or 'us-ascii', 'replace')
            except LookupError:
                # if the charset is unknown, force default 
                headers[i]=text.decode(default_charset, 'replace')

        return "".join(headers)
    
def get_mail_addresses(message, header_name):
    """
    retrieve all email addresses from one message header

    @type message: email.message.Message
    @param message: the email message
    @type header_name: str
    @param header_name: the name of the header, can be 'from', 'to', 'cc' or 
    any other header containing one or more email addresses
    @rtype: list
    @returns: a list of the addresses in the form of tuples 
    C{[(u'Name', 'addresse@domain.com'), ...]}

    >>> import email
    >>> import email.mime.text
    >>> msg=email.mime.text.MIMEText('The text.', 'plain', 'us-ascii')
    >>> msg['From']=email.email.utils.formataddr(('Me', 'me@foo.com'))
    >>> msg['To']=email.email.utils.formataddr(('A', 'a@foo.com'))+', '+email.email.utils.formataddr(('B', 'b@foo.com'))
    >>> print msg.as_string(unixfrom=False)
    Content-Type: text/plain; charset="us-ascii"
    MIME-Version: 1.0
    Content-Transfer-Encoding: 7bit
    From: Me <me@foo.com>
    To: A <a@foo.com>, B <b@foo.com>
    <BLANKLINE>
    The text.
    >>> get_mail_addresses(msg, 'from')
    [(u'Me', 'me@foo.com')]
    >>> get_mail_addresses(msg, 'to')
    [(u'A', 'a@foo.com'), (u'B', 'b@foo.com')]
    """ 
    addrs=email.utils.getaddresses([ _friendly_header(h) for h in message.get_all(header_name, [])])
    for i, (addr_name, addr) in enumerate(addrs):
        if not addr_name and addr:
            # only one string! Is it the address or the  address name ?
            # use the same for both and see later
            addr_name=addr
            
        if is_usascii(addr):
            # address must be ascii only and must match address regex
            if not email_address_re.match(addr):
                addr=''
        else:
            addr=''
        addrs[i]=(decode_mail_header(addr_name), addr)
    return addrs

def get_filename(part):
    """
    Find the filename of a mail part. Many MUA send attachments with the 
    filename in the I{name} parameter of the I{Content-type} header instead 
    of in the I{filename} parameter of the I{Content-Disposition} header.
    
    @type part: inherit from email.mime.base.MIMEBase
    @param part: the mail part 
    @rtype: None or unicode
    @returns: the filename or None if not found
    
    >>> import email.mime.image
    >>> attach=email.mime.image.MIMEImage('data', 'png')
    >>> attach.add_header('Content-Disposition', 'attachment', filename='image.png')
    >>> get_filename(attach)
    u'image.png'
    >>> print attach.as_string(unixfrom=False)
    Content-Type: image/png
    MIME-Version: 1.0
    Content-Transfer-Encoding: base64
    Content-Disposition: attachment; filename="image.png"
    <BLANKLINE>
    ZGF0YQ==
    >>> import email.mime.text
    >>> attach=email.mime.text.MIMEText('The text.', 'plain', 'us-ascii')
    >>> attach.add_header('Content-Disposition', 'attachment', filename=('iso-8859-1', 'fr', u'Fran\\xe7ais.txt'.encode('iso-8859-1')))
    >>> get_filename(attach)
    u'Fran\\xe7ais.txt'
    >>> print attach.as_string(unixfrom=False)
    Content-Type: text/plain; charset="us-ascii"
    MIME-Version: 1.0
    Content-Transfer-Encoding: 7bit
    Content-Disposition: attachment; filename*="iso-8859-1'fr'Fran%E7ais.txt"
    <BLANKLINE>
    The text.
    """
    filename=part.get_param('filename', None, 'content-disposition')
    if not filename:
        filename=part.get_param('name', None) # default is 'content-type'
        
    if filename:
        if isinstance(filename, tuple):
            # RFC 2231 must be used to encode parameters inside MIME header
            filename=email.utils.collapse_rfc2231_value(filename).strip()
        else:
            # But a lot of MUA erroneously use RFC 2047 instead of RFC 2231
            # in fact anybody missuse RFC2047 here !!!
            filename=decode_mail_header(filename)
        
    return filename

def _search_message_content(contents, part):
    """
    recursive search of message content (text or HTML) inside 
    the structure of the email. Used by L{search_message_content()}
    
    @type contents: dict
    @param contents: contents already found in parents or brothers I{parts}. 
    The dictionary will be completed as and when. key is the MIME type of the part.  
    @type part: inherit email.mime.base.MIMEBase
    @param part: the part of the mail to look inside recursively.    
    """
    type=part.get_content_type()
    if part.is_multipart(): # type.startswith('multipart/'):
        # explore only True 'multipart/*' 
        # because 'messages/rfc822' are 'multipart/*' too but
        # must not be explored here 
        if type=='multipart/related':
            # the first part or the one pointed by start 
            start=part.get_param('start', None)
            related_type=part.get_param('type', None)
            for i, subpart in enumerate(part.get_payload()):
                if (not start and i==0) or (start and start==subpart.get('Content-Id')):
                    _search_message_content(contents, subpart)
                    return
        elif type=='multipart/alternative':
            # all parts are candidates and latest is the best
            for subpart in part.get_payload():
                _search_message_content(contents, subpart)
        elif type in ('multipart/report',  'multipart/signed'):
            # only the first part is candidate
            try:
                subpart=part.get_payload()[0]
            except IndexError:
                return
            else:
                _search_message_content(contents, subpart)
                return

        elif type=='multipart/encrypted':
            # the second part is the good one, but we need to de-crypt it 
            # using the first part. Do nothing
            return
            
        else: 
            # unknown types must be handled as 'multipart/mixed'
            # This is the peace of code that could probably be improved, 
            # I use a heuristic : if not already found, use first valid non 
            # 'attachment' parts found
            for subpart in part.get_payload():
                tmp_contents=dict()
                _search_message_content(tmp_contents, subpart)
                for k, v in tmp_contents.items():
                    if not subpart.get_param('attachment', None, 'content-disposition')=='':
                        # if not an attachment, initiate value if not already found
                        contents.setdefault(k, v)
            return
    else:
        contents[part.get_content_type().lower()]=part
        return
    
    return

def search_message_content(mail):
    """
    search of message content (text or HTML) inside 
    the structure of the mail. This function is used by L{get_mail_parts()}
    to set the C{is_body} part of the L{MailPart}s
    
    @type mail: inherit from email.message.Message
    @param mail: the message to search in.
    @rtype: dict
    @returns: a dictionary of the form C{{'text/plain': text_part, 'text/html': html_part}}
    where text_part and html_part inherite from C{email.mime.text.MIMEText} 
    and are respectively the I{text} and I{HTML} version of the message content. 
    One part can be missing. The dictionay can aven be empty if none of the
    parts math the requirements to be considered as the content.     
    """
    contents=dict()
    _search_message_content(contents, mail)
    return contents

def get_mail_parts(msg):
    """
    return a list of all parts of the message as a list of L{MailPart}.
    Retrieve parts attributes to fill in L{MailPart} object.
    
    @type msg: inherit email.message.Message
    @param msg: the message
    @rtype: list
    @returns: list of mail parts

    >>> import email.mime.multipart
    >>> msg=email.mime.multipart.MIMEMultipart(boundary='===limit1==')
    >>> import email.mime.text
    >>> txt=email.mime.text.MIMEText('The text.', 'plain', 'us-ascii')
    >>> msg.attach(txt)
    >>> import email.mime.image
    >>> image=email.mime.image.MIMEImage('data', 'png')
    >>> image.add_header('Content-Disposition', 'attachment', filename='image.png')
    >>> msg.attach(image)
    >>> print msg.as_string(unixfrom=False)    
    Content-Type: multipart/mixed; boundary="===limit1=="
    MIME-Version: 1.0
    <BLANKLINE>
    --===limit1==
    Content-Type: text/plain; charset="us-ascii"
    MIME-Version: 1.0
    Content-Transfer-Encoding: 7bit
    <BLANKLINE>
    The text.
    --===limit1==
    Content-Type: image/png
    MIME-Version: 1.0
    Content-Transfer-Encoding: base64
    Content-Disposition: attachment; filename="image.png"
    <BLANKLINE>
    ZGF0YQ==
    --===limit1==--
    >>> parts=get_mail_parts(msg)
    >>> parts
    [MailPart<*text/plain charset=us-ascii len=9>, MailPart<image/png filename=image.png len=4>]
    >>> # the star "*" means this is the mail content, not an attachment 
    >>> parts[0].get_payload().decode(parts[0].charset)
    u'The text.'
    >>> parts[1].filename, len(parts[1].get_payload())
    (u'image.png', 4)

    """
    mailparts=[]

    # retrieve messages of the email
    contents=search_message_content(msg)
    # reverse contents dict
    parts=dict((v,k) for k, v in contents.items())

    # organize the stack to handle deep first search
    stack=[ msg, ]
    while stack:
        part=stack.pop(0)
        type=part.get_content_type()
        if type.startswith('message/'): 
            # ('message/delivery-status', 'message/rfc822', 'message/disposition-notification'):
            # I don't want to explore the tree deeper her and just save source using msg.as_string()
            # but I don't use msg.as_string() because I want to use mangle_from_=False 
            filename='message.eml'
            mailparts.append(MailPart(part, filename=filename, type=type, charset=part.get_param('charset'), description=part.get('Content-Description')))
        elif part.is_multipart():
            # insert new parts at the beginning of the stack (deep first search)
            stack[:0]=part.get_payload()
        else:
            charset=part.get_param('charset')
            filename=get_filename(part)
                
            disposition=None
            if part.get_param('inline', None, 'content-disposition')=='':
                disposition='inline'
            elif part.get_param('attachment', None, 'content-disposition')=='':
                disposition='attachment'
                
            mailparts.append(MailPart(part, filename=filename, type=type, charset=charset, content_id=part.get('Content-Id'), description=part.get('Content-Description'), disposition=disposition, is_body=parts.get(part, False)))

    return mailparts


def decode_text(payload, charset, default_charset):
    """
    Try to decode text content by trying multiple charset until success.
    First try I{charset}, else try I{default_charset} finally
    try popular charsets in order : ascii, utf-8, utf-16, windows-1252, cp850
    If all fail then use I{default_charset} and replace wrong characters
    
    @type payload: str
    @param payload: the content to decode
    @type charset: str or None
    @param charset: the first charset to try if != C{None}
    @type default_charset: str or None
    @param default_charset: the second charset to try if != C{None}
    
    @rtype: tuple
    @returns: a tuple of the form C{(payload, charset)}
        - I{payload}: this is the decoded payload if charset is not None and
        payload is a unicode string
        - I{charset}: the charset that was used to decode I{payload} If charset is
        C{None} then something goes wrong: if I{payload} is unicode then
        invalid characters have been replaced and the used charset is I{default_charset}
        else, if I{payload} is still byte string then nothing has been done. 
             
     
    """
    for chset in [ charset, default_charset, 'ascii', 'utf-8', 'utf-16', 'windows-1252', 'cp850' ]:
        if chset:
            try: 
                return payload.decode(chset), chset
            except UnicodeError:
                pass

    if default_charset:
        return payload.decode(chset, 'replace'), None 

    return payload, None

class PyzMessage(email.message.Message):
    """
    Inherit from email.message.Message. Combine L{get_mail_parts()},
    L{get_mail_addresses()} and L{decode_mail_header()} into a
    B{convenient} object to access mail contents and attributes.
    This class also B{sanitize} part filenames.
    
    @type mailparts: list of L{MailPart}
    @ivar mailparts: list of L{MailPart} objects composing the email, I{text_part}
    and I{html_part} are part of this list as are other attachements and embedded
    contents.
    @type text_part: L{MailPart} or None
    @ivar text_part: the L{MailPart} object that contains the I{text}
    version of the message, None if the mail has not I{text} content.
    @type html_part: L{MailPart} or None
    @ivar html_part: the L{MailPart} object that contains the I{HTML}
    version of the message, None if the mail has not I{HTML} content.

    @note: Sample:
    
    >>> raw='''Content-Type: text/plain; charset="us-ascii"
    ... MIME-Version: 1.0
    ... Content-Transfer-Encoding: 7bit
    ... Subject: The subject
    ... From: Me <me@foo.com>
    ... To: A <a@foo.com>, B <b@foo.com>
    ...  
    ... The text.
    ... '''
    >>> msg=PyzMessage.factory(raw)
    >>> print 'Subject: %r' % (msg.get_subject(), )
    Subject: u'The subject'
    >>> print 'From: %r' % (msg.get_address('from'), )
    From: (u'Me', 'me@foo.com')
    >>> print 'To: %r' % (msg.get_addresses('to'), )
    To: [(u'A', 'a@foo.com'), (u'B', 'b@foo.com')]
    >>> print 'Cc: %r' % (msg.get_addresses('cc'), )
    Cc: []
    >>> for mailpart in msg.mailparts:
    ...   print '    %sfilename=%r sanitized_filename=%r type=%s charset=%s desc=%s size=%d' % ('*'if mailpart.is_body else ' ', mailpart.filename, mailpart.sanitized_filename, mailpart.type, mailpart.charset, mailpart.part.get('Content-Description'), 0 if mailpart.get_payload()==None else len(mailpart.get_payload()))
    ...   if mailpart.is_body=='text/plain':
    ...     payload, used_charset=decode_text(mailpart.get_payload(), mailpart.charset, None) 
    ...     print '        >', payload.split('\\n')[0]
    ...
        *filename=None sanitized_filename='text.txt' type=text/plain charset=us-ascii desc=None size=10
            > The text.
    """

    @staticmethod
    def smart_parser(input):
        """
        Use the appropriate parser and return a email.message.Message object
        (this is not a L{PyzMessage} object)
        
        @type input: string, file, bytes, binary_file or  email.message.Message
        @param input: the source of the message
        @rtype: email.message.Message
        @returns: the message
        """
        if isinstance(input, email.message.Message):
            return input
        
        if sys.version_info<(3, 0):
            # python 2.x 
            if isinstance(input, str):
                return email.message_from_string(input)
            elif hasattr(input, 'read') and hasattr(input, 'readline'):
                return email.message_from_file(input)
            else:
                raise ValueError('input must be a string, a file or a Message')
        else:
            # python 3.x 
            if isinstance(input, str):
                return email.message_from_string(input)
            elif isinstance(input, bytes):
                # python >= 3.2 only
                return email.message_from_bytes(input)
            elif hasattr(input, 'read') and hasattr(input, 'readline'):
                if hasattr(input, 'encoding'):
                    # python >= 3.2 only
                    return email.message_from_file(input)
                else:
                    return email.message_from_binary_file(input)
            else:
                raise ValueError('input must be a string a bytes, a file or a Message')
    
    @staticmethod
    def factory(input):
        """
        Use the appropriate parser and return a L{PyzMessage} object
        see L{smart_parser}
        @type input: string, file, bytes, binary_file or  email.message.Message
        @param input: the source of the message
        @rtype: L{PyzMessage}
        @returns: the L{PyzMessage} message
        """
        return PyzMessage(PyzMessage.smart_parser(input))
        
    
    def __init__(self, message):
        """
        Initialize the object with data coming from I{message}. 
        
        @type message: inherit email.message.Message
        @param message: The message
        """
        if not isinstance(message, email.message.Message):
            raise ValueError("message must inherit from email.message.Message use PyzMessage.factory() instead")
        self.__dict__.update(message.__dict__)  

        self.mailparts=get_mail_parts(self)
        self.text_part=None
        self.html_part=None
        
        filenames=[]
        for part in self.mailparts:
            ext=mimetypes.guess_extension(part.type)
            if not ext:
                 # default to .bin
                ext='.bin'
            elif ext=='.ksh':
                # guess_extension() is not very accurate, .txt is more
                # appropriate than .ksh 
                ext='.txt'
            
            sanitized_filename=sanitize_filename(part.filename, part.type.split('/', 1)[0], ext)
            sanitized_filename=handle_filename_collision(sanitized_filename, filenames)
            filenames.append(sanitized_filename.lower())
            part.sanitized_filename=sanitized_filename
            
            if part.is_body=='text/plain': 
                self.text_part=part
                
            if part.is_body=='text/html': 
                self.html_part=part
    
    def get_addresses(self, name):
        """
        return the I{name} header value as an list of addresses tuple as 
        returned by L{get_mail_addresses()}
        
        @type name: str
        @param name: the name of the header to read value from: 'to', 'cc' are
        valid I{name} here.
        @rtype: tuple
        @returns: a tuple of the form C{('Sender Name', 'sender.address@domain.com')}
        or C{('', '')} if no header match that I{name}.
        """ 
        return get_mail_addresses(self, name)
    
    def get_address(self, name):
        """
        return the I{name} header value as an address tuple as returned by 
        L{get_mail_addresses()} 

        @type name: str
        @param name: the name of the header to read value from: : C{'from'} can
        be used to return the sender address. 
        @rtype: list of tuple
        @returns: a list of tuple of the form C{[('Recipient Name', 'recipient.address@domain.com'), ...]}
        or an empty list if no header match that I{name}.
        """ 
        value=get_mail_addresses(self, name)
        if value:
            return value[0]
        else:
            return ('', '')
    
    def get_subject(self, default=''):
        """
        return the RFC2047 decoded subject.
        
        @type default: any
        @param default: The value to return if the message has no I{Subject}
        @rtype: unicode
        @returns: the subject or C{default}
        """
        return self.get_decoded_header('subject', default)

    def get_decoded_header(self, name, default=''):
        """
        return decoded header I{name} using RFC2047. Always use this function 
        to access header, because any header can contain invalid characters 
        and this function sanitize the string and avoid unicode exception later
        in your program. 
        EVEN for date, I already saw a "Center box bar horizontal" instead
        of a minus character. 

        @type name: str
        @param name: the name of the header to read value from.
        @type default: any
        @param default: The value to return if the I{name} field don't exist
        in this message.
        @rtype: unicode
        @returns: the value of the header having that I{name} or C{default} if no
        header have that name.
        """
        value=self.get(name)
        if value==None:
            value=default
        else:
            value=decode_mail_header(value)
        return value
    
class PzMessage(PyzMessage):
    """
    Old name and interface for PyzMessage. 
    B{Deprecated}
    """

    def __init__(self, input):
        """
        Initialize the object with data coming from I{input}. 
        
        @type input: str or file or email.message.Message
        @param input: used as the raw content for the email, can be a string,  
        a file object or an email.message.Message object. 
        """
        PyzMessage.__init__(self, self.smart_parser(input))
        

def message_from_string(s, *args, **kws):
    """
    Parse a string into a L{PyzMessage} object model.
    @type s: str
    @param s: the input string 
    @rtype: L{PyzMessage}
    @return: the L{PyzMessage} object
    """
    return PyzMessage(email.message_from_string(s, *args, **kws))

def message_from_file(fp, *args, **kws):
    """
    Read a file and parse its contents into a L{PyzMessage} object model.
    @type fp: text_file
    @param fp: the input file (must be open in text mode if Python >= 3.0)
    @rtype: L{PyzMessage}
    @return: the L{PyzMessage} object
    """
    return PyzMessage(email.message_from_file(fp, *args, **kws))

def message_from_bytes(s, *args, **kws):
    """
    Parse a bytes string into a L{PyzMessage} object model.
    B{(Python >= 3.2)}
    @type s: bytes
    @param s: the input bytes string 
    @rtype: L{PyzMessage}
    @return: the L{PyzMessage} object
    """
    return PyzMessage(email.message_from_bytes(s, *args, **kws))

def message_from_binary_file(fp, *args, **kws):
    """
    Read a binary file and parse its contents into a L{PyzMessage} object model.
    B{(Python >= 3.2)}
    @type fp: binary_file
    @param fp: the input file, must be open in binary mode 
    @rtype: L{PyzMessage}
    @return: the L{PyzMessage} object
    """
    return PyzMessage(email.message_from_binary_file(fp, *args, **kws))


if __name__ == "__main__":
    import sys

    if len(sys.argv)<=1:
        print('usage : %s filename' % sys.argv[0])
        print('read an email from file and display a resume of its content')
        sys.exit(1)
        
    msg=PyzMessage.factory(open(sys.argv[1], 'rb'))
    
    print('Subject: %r' % (msg.get_subject(), ))
    print('From: %r' % (msg.get_address('from'), ))
    print('To: %r' % (msg.get_addresses('to'), ))
    print('Cc: %r' % (msg.get_addresses('cc'), ))
    print('Date: %r' % (msg.get_decoded_header('date', ''), ))
    print('Message-Id: %r' % (msg.get_decoded_header('message-id', ''), ))
    
    for mailpart in msg.mailparts:
        # dont forget to be careful to sanitize 'filename' and be carefull
        # for filename collision, to before to save :
        print('   %sfilename=%r type=%s charset=%s desc=%s size=%d' % ('*'if mailpart.is_body else ' ', mailpart.filename, mailpart.type, mailpart.charset, mailpart.part.get('Content-Description'), 0 if mailpart.get_payload()==None else len(mailpart.get_payload())))

        if mailpart.is_body=='text/plain':
            # print first 3 lines
            payload, used_charset=decode_text(mailpart.get_payload(), mailpart.charset, None) 
            for line in payload.split('\n')[:3]:
                # be careful console can be unable to display unicode characters
                if line:
                    print('       >', line)

        

