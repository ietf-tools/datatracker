import unittest, doctest
import pyzmail
from pyzmail.parse import *


class Msg:
    """mimic a email.Message"""
    def __init__(self, value):
        self.value=value
        
    def get_all(self, header_name, default):
        if self.value:
            return [self.value, ]
        else:
            return []

class TestParse(unittest.TestCase):

    def setUp(self):
        pass
    
    def test_decode_mail_header(self):
        """test decode_mail_header()"""
        self.assertEqual(decode_mail_header(''), '')
        self.assertEqual(decode_mail_header('hello'), 'hello')
        self.assertEqual(decode_mail_header('hello '), 'hello ')
        self.assertEqual(decode_mail_header('=?iso-8859-1?q?Courrier_=E8lectronique_Fran=E7ais?='), 'Courrier \xe8lectronique Fran\xe7ais')
        self.assertEqual(decode_mail_header('=?utf8?q?Courrier_=C3=A8lectronique_Fran=C3=A7ais?='), 'Courrier \xe8lectronique Fran\xe7ais')
        self.assertEqual(decode_mail_header('=?utf-8?b?RnJhbsOnYWlz?='), 'Fran\xe7ais')
        self.assertEqual(decode_mail_header('=?iso-8859-1?q?Courrier_=E8lectronique_?= =?utf8?q?Fran=C3=A7ais?='), 'Courrier \xe8lectronique Fran\xe7ais')
        self.assertEqual(decode_mail_header('=?iso-8859-1?q?Courrier_=E8lectronique_?= =?utf-8?b?RnJhbsOnYWlz?='), 'Courrier \xe8lectronique Fran\xe7ais')
        self.assertEqual(decode_mail_header('h_subject_q_iso_8858_1 : =?ISO-8859-1?Q?Fran=E7ais=E20accentu=E9?= !'), 'h_subject_q_iso_8858_1 :Fran\xe7ais\xe20accentu\xe9!')
   
    def test_get_mail_addresses(self):
        """test get_mail_addresses()"""
        self.assertEqual([ ('foo@example.com', 'foo@example.com') ], get_mail_addresses(Msg('foo@example.com'), 'to'))
        self.assertEqual([ ('Foo', 'foo@example.com'), ], get_mail_addresses(Msg('Foo <foo@example.com>'), 'to'))
        # notice the space around the comma
        self.assertEqual([ ('foo@example.com', 'foo@example.com'), ('bar@example.com', 'bar@example.com')], get_mail_addresses(Msg('foo@example.com , bar@example.com'), 'to'))
        self.assertEqual([ ('Foo', 'foo@example.com'), ( 'Bar', 'bar@example.com')], get_mail_addresses(Msg('Foo <foo@example.com> , Bar <bar@example.com>'), 'to'))
        self.assertEqual([ ('Foo', 'foo@example.com'), ('bar@example.com', 'bar@example.com')], get_mail_addresses(Msg('Foo <foo@example.com> , bar@example.com'), 'to'))
        self.assertEqual([ ('Mr Foo', 'foo@example.com'), ('bar@example.com', 'bar@example.com')], get_mail_addresses(Msg('Mr\nFoo <foo@example.com> , bar@example.com'), 'to'))
        
        self.assertEqual([ ('Beno\xeet', 'benoit@example.com')], get_mail_addresses(Msg('=?utf-8?q?Beno=C3=AEt?= <benoit@example.com>'), 'to'))
        
        # address already encoded into utf8 (bad)
        address='Ant\xf3nio Foo <a.foo@example.com>'.encode('utf8')
        if sys.version_info<(3, 0):
            self.assertEqual([('Ant\ufffd\ufffdnio Foo', 'a.foo@example.com')], get_mail_addresses(Msg(address), 'to'))
        else:
            # Python 3.2 return header when surrogate characters are used in header
            self.assertEqual([('Ant??nio Foo', 'a.foo@example.com'), ], get_mail_addresses(Msg(email.header.Header(address, charset=email.charset.UNKNOWN8BIT, header_name='to')), 'to'))
        
    def test_get_filename(self):
        """test get_filename()"""
        import email.mime.image

        filename='Fran\xe7ais.png'
        if sys.version_info<(3, 0):
            encoded_filename=filename.encode('iso-8859-1')
        else:
            encoded_filename=filename
               
        payload=b'data'
        attach=email.mime.image.MIMEImage(payload, 'png')
        attach.add_header('Content-Disposition', 'attachment', filename='image.png')
        self.assertEqual('image.png', get_filename(attach))

        attach=email.mime.image.MIMEImage(payload, 'png')
        attach.add_header('Content-Disposition', 'attachment', filename=('iso-8859-1', 'fr', encoded_filename))
        self.assertEqual('Fran\xe7ais.png', get_filename(attach))
        
        attach=email.mime.image.MIMEImage(payload, 'png')
        attach.set_param('name', 'image.png')
        self.assertEqual('image.png', get_filename(attach))

        attach=email.mime.image.MIMEImage(payload, 'png')
        attach.set_param('name', ('iso-8859-1', 'fr', encoded_filename))
        self.assertEqual('Fran\xe7ais.png', get_filename(attach))

        attach=email.mime.image.MIMEImage(payload, 'png')
        attach.add_header('Content-Disposition', 'attachment', filename='image.png')
        attach.set_param('name', 'image_wrong.png')
        self.assertEqual('image.png', get_filename(attach))

    def test_get_mailparts(self):
        """test get_mailparts()"""
        import email.mime.multipart
        import email.mime.text
        import email.mime.image
        msg=email.mime.multipart.MIMEMultipart(boundary='===limit1==')
        txt=email.mime.text.MIMEText('The text.', 'plain', 'us-ascii')
        msg.attach(txt)
        image=email.mime.image.MIMEImage(b'data', 'png')
        image.add_header('Content-Disposition', 'attachment', filename='image.png')
        image.add_header('Content-Description', 'the description')
        image.add_header('Content-ID', '<this.is.the.normaly.unique.contentid>')
        msg.attach(image)
        
        raw=msg.as_string(unixfrom=False)
        expected_raw="""Content-Type: multipart/mixed; boundary="===limit1=="
MIME-Version: 1.0

--===limit1==
Content-Type: text/plain; charset="us-ascii"
MIME-Version: 1.0
Content-Transfer-Encoding: 7bit

The text.
--===limit1==
Content-Type: image/png
MIME-Version: 1.0
Content-Transfer-Encoding: base64
Content-Disposition: attachment; filename="image.png"
Content-Description: the description
Content-ID: <this.is.the.normaly.unique.contentid>

ZGF0YQ==<HERE1>
--===limit1==--"""
    
        if sys.version_info<(3, 0):
            expected_raw=expected_raw.replace('<HERE1>','')
        else:
            expected_raw=expected_raw.replace('<HERE1>','\n')

        self.assertEqual(raw, expected_raw)
        
        parts=get_mail_parts(msg)
        # [MailPart<*text/plain charset=us-ascii len=9>, MailPart<image/png filename=image.png len=4>]

        self.assertEqual(len(parts), 2)

        self.assertEqual(parts[0].type, 'text/plain')
        self.assertEqual(parts[0].is_body, 'text/plain') # not a error, is_body must be type 
        self.assertEqual(parts[0].charset, 'us-ascii')
        self.assertEqual(parts[0].get_payload().decode(parts[0].charset), 'The text.')

        self.assertEqual(parts[1].type, 'image/png')
        self.assertEqual(parts[1].is_body, False)
        self.assertEqual(parts[1].charset, None)
        self.assertEqual(parts[1].filename, 'image.png')
        self.assertEqual(parts[1].description, 'the description')
        self.assertEqual(parts[1].content_id, 'this.is.the.normaly.unique.contentid')
        self.assertEqual(parts[1].get_payload(), b'data')

    
    raw_1='''Content-Type: text/plain; charset="us-ascii"
MIME-Version: 1.0
Content-Transfer-Encoding: 7bit
Subject: simple test
From: Me <me@foo.com>
To: A <a@foo.com>, B <b@foo.com>
Cc: C <c@foo.com>, d@foo.com
User-Agent: pyzmail

The text.
'''

    def check_message_1(self, msg):
        self.assertEqual(msg.get_subject(), 'simple test')
        self.assertEqual(msg.get_decoded_header('subject'), 'simple test')
        self.assertEqual(msg.get_decoded_header('User-Agent'), 'pyzmail')
        self.assertEqual(msg.get('User-Agent'), 'pyzmail')
        self.assertEqual(msg.get_address('from'), ('Me', 'me@foo.com'))
        self.assertEqual(msg.get_addresses('to'), [('A', 'a@foo.com'), ('B', 'b@foo.com')])
        self.assertEqual(msg.get_addresses('cc'), [('C', 'c@foo.com'), ('d@foo.com', 'd@foo.com')])
        self.assertEqual(len(msg.mailparts), 1)
        self.assertEqual(msg.text_part, msg.mailparts[0])
        self.assertEqual(msg.html_part, None)

    # use 8bits encoding and 2 different charsets ! python 3.0 & 3.1 are not eable to parse this sample 
    raw_2=b"""From: sender@domain.com
To: recipient@domain.com
Date: Tue, 7 Jun 2011 16:32:17 +0200
Subject: contains 8bits attachments using different encoding
Content-Type: multipart/mixed; boundary=mixed

--mixed
Content-Type: text/plain; charset="us-ascii"
MIME-Version: 1.0
Content-Transfer-Encoding: 7bit

body
--mixed
Content-Type: text/plain; charset="windows-1252"
MIME-Version: 1.0
Content-Transfer-Encoding: 8bit
Content-Disposition: attachment; filename="file1.txt"

bo\xeete mail = mailbox
--mixed
Content-Type: text/plain; charset="utf-8"
MIME-Version: 1.0
Content-Transfer-Encoding: 8bit
Content-Disposition: attachment; filename="file2.txt"

bo\xc3\xaete mail = mailbox
--mixed--
"""
    
    def check_message_2(self, msg):
        self.assertEqual(msg.get_subject(), 'contains 8bits attachments using different encoding')
    
        body, file1, file2=msg.mailparts

        self.assertEqual('file1.txt', file1.filename)
        self.assertEqual('file2.txt', file2.filename)
        self.assertEqual('windows-1252', file1.charset)
        self.assertEqual('utf-8', file2.charset)
        content=b'bo\xeete mail = mailbox'.decode("windows-1252")
        content1=file1.get_payload().decode(file1.charset)
        content2=file2.get_payload().decode(file2.charset)
        self.assertEqual(content, content1)
        self.assertEqual(content, content2)

    # this one contain non us-ascii chars in the header 
    # py 2x and py3k return different value here  
    raw_3=b'Content-Type: text/plain; charset="us-ascii"\n' \
          b'MIME-Version: 1.0\n' \
          b'Content-Transfer-Encoding: 7bit\n' \
          + 'Subject: Beno\xeet & Ant\xf3nio\n'.encode('utf8') +\
          b'From: =?utf-8?q?Beno=C3=AEt?= <benoit@example.com>\n' \
          + 'To: Ant\xf3nio Foo <a.foo@example.com>\n'.encode('utf8') \
          + 'Cc: Beno\xeet <benoit@foo.com>, d@foo.com\n'.encode('utf8') +\
          b'User-Agent: pyzmail\n' \
          b'\n' \
          b'The text.\n'

    def check_message_3(self, msg):
        subject='Beno\ufffd\ufffdt & Ant\ufffd\ufffdnio' #  if sys.version_info<(3, 0) else u'Beno??t & Ant??nio'
        self.assertEqual(msg.get_subject(), subject)
        self.assertEqual(msg.get_decoded_header('subject'), subject)
        self.assertEqual(msg.get_decoded_header('User-Agent'), 'pyzmail')
        self.assertEqual(msg.get('User-Agent'), 'pyzmail')
        self.assertEqual(msg.get_address('from'), ('Beno\xeet', 'benoit@example.com'))

        to=msg.get_addresses('to')
        self.assertEqual(to[0][1], 'a.foo@example.com')
        self.assertEqual(to[0][0], 'Ant\ufffd\ufffdnio Foo' if sys.version_info<(3, 0) else 'Ant??nio Foo')
        
        cc=msg.get_addresses('cc')
        self.assertEqual(cc[0][1], 'benoit@foo.com')
        self.assertEqual(cc[0][0], 'Beno\ufffd\ufffdt' if sys.version_info<(3, 0) else 'Beno??t')
        self.assertEqual(cc[1], ('d@foo.com', 'd@foo.com'))
        
        self.assertEqual(len(msg.mailparts), 1)
        self.assertEqual(msg.text_part, msg.mailparts[0])
        self.assertEqual(msg.html_part, None)


    def check_pyzmessage_factories(self, input, check):
        """test PyzMessage from different sources"""
        if isinstance(input, bytes) and sys.version_info>=(3, 2):
            check(PyzMessage.factory(input))
            check(message_from_bytes(input))

            import io
            check(PyzMessage.factory(io.BytesIO(input)))
            check(message_from_binary_file(io.BytesIO(input)))

        if isinstance(input, str):

            check(PyzMessage.factory(input))
            check(message_from_string(input))

            import io
            check(PyzMessage.factory(io.StringIO(input)))
            check(message_from_file(io.StringIO(input)))
        
    def test_pyzmessage_factories(self):
        """test PyzMessage class different sources"""
        self.check_pyzmessage_factories(self.raw_1, self.check_message_1)
        self.check_pyzmessage_factories(self.raw_2, self.check_message_2)
        self.check_pyzmessage_factories(self.raw_3, self.check_message_3)


# Add doctest 
def load_tests(loader, tests, ignore):
    # this works with python 2.7 and 3.x
    if sys.version_info<(3, 0): 
        tests.addTests(doctest.DocTestSuite(pyzmail.parse))
    return tests

def additional_tests():
    # Add doctest for python 2.6 and below
    if sys.version_info<(2, 7):
        return doctest.DocTestSuite(pyzmail.parse)
    else:
        return unittest.TestSuite()

