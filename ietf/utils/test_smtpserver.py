# Copyright The IETF Trust 2014-2025, All Rights Reserved
# -*- coding: utf-8 -*-

from aiosmtpd.controller import Controller
from email.utils import parseaddr
from typing import Optional


class SMTPTestHandler:

    def __init__(self, inbox: list):
        self.inbox = inbox

    async def handle_DATA(self, server, session, envelope):
        """Handle the DATA command and 'deliver' the message"""

        self.inbox.append(envelope.content)
        # Per RFC2033: https://datatracker.ietf.org/doc/html/rfc2033.html#section-4.2
        #     ...after the final ".", the server returns one reply
        #     for each previously successful RCPT command in the mail transaction,
        #     in the order that the RCPT commands were issued.  Even if there were
        #     multiple successful RCPT commands giving the same forward-path, there
        #     must be one reply for each successful RCPT command.
        return "\n".join("250 OK" for _ in envelope.rcpt_tos)

    async def handle_RCPT(self, server, session, envelope, address, rcpt_options):
        """Handle an RCPT command and add the address to the envelope if it is acceptable"""
        _, address = parseaddr(address)
        if address == "":
            return "501 Syntax: RCPT TO: <address>"
        if "poison" in address:
            return "550 Error: Not touching that"
        # At this point the address is acceptable
        envelope.rcpt_tos.append(address)
        return "250 OK"


class SMTPTestServerDriver:

    def __init__(self, address: str, port: int, inbox: Optional[list] = None):
        self.controller = Controller(
            hostname=address,
            port=port,
            handler=SMTPTestHandler(inbox=[] if inbox is None else inbox),
        )

    def start(self):
        self.controller.start()

    def stop(self):
        self.controller.stop()
