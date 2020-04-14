import threading, smtpd, asyncore, socket, smtplib, time
import unittest
import pyzmail
from pyzmail.generate import *


smtpd_addr='127.0.0.1' 
smtpd_port=32525
smtp_bad_port=smtpd_port-1

smtp_mode='normal'
smtp_login=None
smtp_password=None
    

class SMTPServer(smtpd.SMTPServer):
    def __init__(self, localaddr, remoteaddr, received):
        smtpd.SMTPServer.__init__(self, localaddr, remoteaddr)
        self.set_reuse_addr()
        # put the received mail into received list 
        self.received=received
        
    def process_message(self, peer, mail_from, rcpt_to, data):
        ret=None
        if mail_from.startswith('data_error'):
            ret='552 Requested mail action aborted: exceeded storage allocation'
        self.received.append((ret, peer, mail_from, rcpt_to, data))
        return ret

class TestSend(unittest.TestCase):

    def setUp(self):
        self.received=[]
        self.smtp_server=SMTPServer((smtpd_addr, smtpd_port), None, self.received)

        def asyncloop():
            # check every sec if all channel are close
            asyncore.loop(1)

                    
        self.payload, self.mail_from, self.rcpt_to, self.msg_id=compose_mail(('Me', 'me@foo.com'), [('Him', 'him@bar.com')], 'the subject', 'iso-8859-1', ('Hello world', 'us-ascii'))

        # start the server after having built the payload, to handle failure in 
        # the code above
        self.smtpd_thread=threading.Thread(target=asyncloop)
        self.smtpd_thread.daemon=True
        self.smtpd_thread.start()


    def tearDown(self):
        self.smtp_server.close()
        self.smtpd_thread.join()
        
    def test_simple_send(self):
        """simple send"""
        ret=send_mail(self.payload, self.mail_from, self.rcpt_to, smtpd_addr, smtpd_port, smtp_mode=smtp_mode, smtp_login=smtp_login, smtp_password=smtp_password)
        self.assertEqual(ret, dict())
        (ret, peer, mail_from, rcpt_to, payload)=self.received[0]
        self.assertEqual(self.payload, payload)
        self.assertEqual(self.mail_from, mail_from)
        self.assertEqual(self.rcpt_to, rcpt_to)
        self.assertEqual('127.0.0.1', peer[0])

    def test_send_to_a_wrong_port(self):
        """send to a wrong port"""
        self.smtp_server.close()
        ret=send_mail(self.payload, self.mail_from, self.rcpt_to, smtpd_addr, smtpd_port, smtp_mode=smtp_mode, smtp_login=smtp_login, smtp_password=smtp_password)
        self.assertEqual(type(ret), str)

    def test_send_data_error(self):
        """smtp server return error code"""
        ret=send_mail(self.payload, 'data_error@foo.com', self.rcpt_to, smtpd_addr, smtp_bad_port, smtp_mode=smtp_mode, smtp_login=smtp_login, smtp_password=smtp_password)
        self.assertEqual(type(ret), str)

if __name__ == '__main__':
    unittest.main()

