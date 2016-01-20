import smtpd
import threading
import asyncore

class AsyncCoreLoopThread(object):

    def wrap_loop(self, exit_condition, timeout=1.0, use_poll=False, map=None):
        if map is None:
            map = asyncore.socket_map
            while map and not exit_condition:
                asyncore.loop(timeout=1.0, use_poll=False, map=map, count=1)

    def start(self):
        """Start the listening service"""
        self.exit_condition = []
        kwargs={'exit_condition':self.exit_condition,'timeout':1.0} 
        self.thread = threading.Thread(target=self.wrap_loop, kwargs=kwargs)
        self.thread.daemon = True
        self.thread.start()     

    def stop(self):
        """Stop the listening service"""
        self.exit_condition.append(True)
        self.thread.join()


class SMTPTestChannel(smtpd.SMTPChannel):

    def smtp_RCPT(self, arg):
        if not self._SMTPChannel__mailfrom:
            self.push('503 Error: need MAIL command')
            return
        address = self._SMTPChannel__getaddr('TO:', arg) if arg else None
        if not address:
            self.push('501 Syntax: RCPT TO: <address>')
            return
        if "poison" in address:
           self.push('550 Error: Not touching that')
           return
        self._SMTPChannel__rcpttos.append(address)
        self.push('250 Ok')

class SMTPTestServer(smtpd.SMTPServer):

    def __init__(self,localaddr,remoteaddr,inbox):
        if inbox is not None:
            self.inbox=inbox
        else:
            self.inbox = []
        smtpd.SMTPServer.__init__(self,localaddr,remoteaddr)

    def handle_accept(self):
        pair = self.accept()
        if pair is not None:
            conn, addr = pair
            #channel = SMTPTestChannel(self, conn, addr)
            SMTPTestChannel(self, conn, addr)

    def process_message(self, peer, mailfrom, rcpttos, data):
        self.inbox.append(data)


class SMTPTestServerDriver(object):
    def __init__(self, localaddr, remoteaddr, inbox=None):
        self.localaddr=localaddr
        self.remoteaddr=remoteaddr
        if inbox is not None:
            self.inbox = inbox
        else:
            self.inbox = []
        self.thread_driver = None

    def start(self):
        self.smtpserver = SMTPTestServer(self.localaddr,self.remoteaddr,self.inbox)
        self.thread_driver = AsyncCoreLoopThread()
        self.thread_driver.start()

    def stop(self):
        if self.thread_driver:
            self.thread_driver.stop()

