# Copyright The IETF Trust 2013-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime

from django.urls import reverse as urlreverse

import debug                            # pyflakes:ignore

from ietf.group.factories import GroupFactory
from ietf.message.models import Message, SendQueue
from ietf.message.utils import send_scheduled_message_from_send_queue
from ietf.person.models import Person
from ietf.utils.mail import outbox, send_mail_text, send_mail_message, get_payload_text
from ietf.utils.test_utils import TestCase

class MessageTests(TestCase):
    def test_message_view(self):
        nomcom = GroupFactory(name="nomcom%s" % datetime.date.today().year, type_id="nomcom")
        msg = Message.objects.create(
            by=Person.objects.get(name="(System)"),
            subject="This is a test",
            to="test@example.com",
            frm="nomcomchair@example.com",
            body="Hello World!",
            content_type="text/plain",
            )
        msg.related_groups.add(nomcom)

        r = self.client.get(urlreverse("ietf.message.views.message", kwargs=dict(message_id=msg.id)))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, msg.subject)
        self.assertContains(r, msg.to)
        self.assertContains(r, msg.frm)
        self.assertContains(r, "Hello World!")

    def test_capture_send_mail_text(self):
        def cmp(e1, e2):
            e1keys = set(e1.keys())
            e2keys = set(e2.keys())
            self.assertEqual(e1keys, e2keys)
            self.longMessage = True
            for k in e1keys:
                if k in ['Date', ]:
                    continue
                self.assertEqual(e1.get_all(k), e2.get_all(k), "Header field: %s" % k)
            self.longMessage = False
            self.assertEqual(get_payload_text(e1), get_payload_text(e2))

        #
        self.assertEqual(Message.objects.count(), 0)
        to = "<iesg-secretary@ietf.org>"
        subj = "Dummy subject"
        cc="cc.a@example.com, cc.b@example.com"
        body = "Dummy message text"
        bcc="bcc@example.com"
        msg1 = send_mail_text(None, to, None, subj, body, cc=cc, bcc=bcc)
        self.assertEqual(Message.objects.count(), 1)
        message = Message.objects.last()
        self.assertEqual(message.by.name, '(System)')
        self.assertEqual(message.to, to)
        self.assertEqual(message.subject, subj)
        self.assertEqual(message.body, body)
        self.assertEqual(message.cc, cc)
        self.assertEqual(message.bcc, bcc)
        self.assertEqual(message.content_type, 'text/plain')
        # Check round-trip msg --> message --> msg
        msg2 = send_mail_message(None, message)
        cmp(msg1, msg2)
        cmp(msg1, outbox[-1])


class SendScheduledAnnouncementsTests(TestCase):
    def test_send_plain_announcement(self):
        msg = Message.objects.create(
            by=Person.objects.get(name="(System)"),
            subject="This is a test",
            to="test@example.com",
            frm="testmonkey@example.com",
            cc="cc.a@example.com, cc.b@example.com",
            bcc="bcc@example.com",
            body="Hello World!",
            content_type="text/plain",
            )

        q = SendQueue.objects.create(
            by=Person.objects.get(name="(System)"),
            message=msg,
            send_at=datetime.datetime.now() + datetime.timedelta(hours=12)
            )

        mailbox_before = len(outbox)
        
        send_scheduled_message_from_send_queue(q)

        self.assertEqual(len(outbox), mailbox_before + 1)
        self.assertTrue("This is a test" in outbox[-1]["Subject"])
        self.assertTrue(SendQueue.objects.get(id=q.id).sent_at)

    def test_send_mime_announcement(self):
        msg = Message.objects.create(
            by=Person.objects.get(name="(System)"),
            subject="This is a test",
            to="test@example.com",
            frm="testmonkey@example.com",
            cc="cc.a@example.com, cc.b@example.com",
            bcc="bcc@example.com",
            body='--NextPart\r\n\r\nA New Internet-Draft is available from the on-line Internet-Drafts directories.\r\n--NextPart\r\nContent-Type: Message/External-body;\r\n\tname="draft-huang-behave-bih-01.txt";\r\n\tsite="ftp.ietf.org";\r\n\taccess-type="anon-ftp";\r\n\tdirectory="internet-drafts"\r\n\r\nContent-Type: text/plain\r\nContent-ID:     <2010-07-30001541.I-D@ietf.org>\r\n\r\n--NextPart--',
            content_type='Multipart/Mixed; Boundary="NextPart"',
            )

        q = SendQueue.objects.create(
            by=Person.objects.get(name="(System)"),
            message=msg,
            send_at=datetime.datetime.now() + datetime.timedelta(hours=12)
            )
        
        mailbox_before = len(outbox)
        
        send_scheduled_message_from_send_queue(q)

        self.assertEqual(len(outbox), mailbox_before + 1)
        self.assertTrue("This is a test" in outbox[-1]["Subject"])
        self.assertTrue("--NextPart" in outbox[-1].as_string())
        self.assertTrue(SendQueue.objects.get(id=q.id).sent_at)
