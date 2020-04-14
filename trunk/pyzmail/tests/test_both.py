import unittest
import pyzmail
from pyzmail.generate import *
from pyzmail.parse import *

class TestBoth(unittest.TestCase):

    def setUp(self):
        pass
    
    def test_compose_and_parse(self):
        """test generate and parse"""
        
        sender=('Me', 'me@foo.com')
        recipients=[('Him', 'him@bar.com'), 'just@me.com']
        subject='Le sujet en Fran\xe7ais'
        text_content='Bonjour aux Fran\xe7ais'
        prefered_encoding='iso-8859-1'
        text_encoding='iso-8859-1'
        attachments=[('attached content', 'text', 'plain', 'textfile1.txt', 'us-ascii'),
                     ('Fran\xe7ais', 'text', 'plain', 'textfile2.txt', 'iso-8859-1'),
                     ('Fran\xe7ais', 'text', 'plain', 'textfile3.txt', 'iso-8859-1'),
                     (b'image', 'image', 'jpg', 'imagefile.jpg', None),
                     ]
        embeddeds=[('embedded content', 'text', 'plain', 'embedded', 'us-ascii'),
                   (b'picture', 'image', 'png', 'picture', None),
                   ]
        headers=[ ('X-extra', 'extra value'), ('X-extra2', "Seconde ent\xe8te"), ('X-extra3', 'last extra'),]
        
        message_id_string='pyzmail'
        date=1313558269
        
        payload, mail_from, rcpt_to, msg_id=pyzmail.compose_mail(\
            sender, \
            recipients, \
            subject, \
            prefered_encoding, \
            (text_content, text_encoding), \
            html=None, \
            attachments=attachments, \
            embeddeds=embeddeds, \
            headers=headers, \
            message_id_string=message_id_string, \
            date=date\
            )
        
        msg=PyzMessage.factory(payload)
        
        self.assertEqual(sender, msg.get_address('from'))
        self.assertEqual(recipients[0], msg.get_addresses('to')[0])
        self.assertEqual(recipients[1], msg.get_addresses('to')[1][1])
        self.assertEqual(subject, msg.get_subject())
        self.assertEqual(subject, msg.get_decoded_header('subject'))
        
        # try to handle different timezone carefully
        mail_date=list(email.utils.parsedate(msg.get_decoded_header('date')))
        self.assertEqual(mail_date[:6], list(time.localtime(date))[:6])
        
        self.assertNotEqual(msg.get('message-id').find(message_id_string), -1)
        for name, value in headers:
            self.assertEqual(value, msg.get_decoded_header(name))
        
        for mailpart in msg.mailparts:
            if mailpart.is_body:
                self.assertEqual(mailpart.content_id, None)
                self.assertEqual(mailpart.filename, None)
                self.assertEqual(type(mailpart.sanitized_filename), str)
                if mailpart.type=='text/plain':
                    self.assertEqual(mailpart.get_payload(), text_content.encode(text_encoding))
                else:
                    self.fail('found unknown body part')
            else:
                if mailpart.filename:
                    lst=attachments
                    self.assertEqual(mailpart.filename, mailpart.sanitized_filename)
                    self.assertEqual(mailpart.content_id, None)
                elif mailpart.content_id:
                    lst=embeddeds
                    self.assertEqual(mailpart.filename, None)
                else:
                    self.fail('found unknown part')
                    
                found=False
                for attach in lst:
                    found=(mailpart.filename and attach[3]==mailpart.filename) \
                        or (mailpart.content_id and attach[3]==mailpart.content_id)
                    if found:
                        break
                        
                if found:
                    self.assertEqual(mailpart.type, attach[1]+'/'+attach[2])
                    payload=mailpart.get_payload()
                    if attach[1]=='text' and attach[4] and isinstance(attach[0], str):
                        payload=payload.decode(attach[4])
                    self.assertEqual(payload, attach[0])
                else:
                    self.fail('found unknown attachment')


