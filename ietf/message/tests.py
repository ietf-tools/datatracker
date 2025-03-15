# Copyright The IETF Trust 2013-2020, All Rights Reserved
# -*- coding: utf-8 -*-
import datetime
import mock

from smtplib import SMTPException

from django.urls import reverse as urlreverse
from django.utils import timezone

import debug                            # pyflakes:ignore

from ietf.group.factories import GroupFactory
from ietf.message.factories import MessageFactory, SendQueueFactory
from ietf.message.models import Message, SendQueue
from ietf.message.tasks import send_scheduled_mail_task, retry_send_messages_by_pk_task
from ietf.message.utils import send_scheduled_message_from_send_queue, retry_send_messages
from ietf.person.models import Person
from ietf.utils.mail import outbox, send_mail_text, send_mail_message, get_payload_text
from ietf.utils.test_utils import TestCase
from ietf.utils.timezone import date_today



class MessageTests(TestCase):
    def test_message_view(self):
        nomcom = GroupFactory(name="nomcom%s" % date_today().year, type_id="nomcom")
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
            send_at=timezone.now() + datetime.timedelta(hours=12)
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
            send_at=timezone.now() + datetime.timedelta(hours=12)
            )
        
        mailbox_before = len(outbox)
        
        send_scheduled_message_from_send_queue(q)

        self.assertEqual(len(outbox), mailbox_before + 1)
        self.assertTrue("This is a test" in outbox[-1]["Subject"])
        self.assertTrue("--NextPart" in outbox[-1].as_string())
        self.assertTrue(SendQueue.objects.get(id=q.id).sent_at)


class UtilsTests(TestCase):
    @mock.patch("ietf.message.utils.send_mail_message")
    def test_retry_send_messages(self, mock_send_mail_message):
        sent_message = MessageFactory(sent=timezone.now())
        unsent_messages = MessageFactory.create_batch(2, sent=None)
        
        # Send the sent message and one of the unsent messages
        retry_send_messages(
            Message.objects.filter(pk__in=[
                sent_message.pk,
                unsent_messages[0].pk,
            ]),
            resend=False,
        )
        self.assertEqual(mock_send_mail_message.call_count, 1)
        self.assertEqual(
            mock_send_mail_message.call_args.args[1],
            unsent_messages[0],
        )
        
        mock_send_mail_message.reset_mock()
        # Once again, send the sent message and one of the unsent messages 
        # (we can use the same one because our mock prevented it from having
        # its status updated to sent)
        retry_send_messages(
            Message.objects.filter(pk__in=[
                sent_message.pk,
                unsent_messages[0].pk,
            ]),
            resend=True,
        )
        self.assertEqual(mock_send_mail_message.call_count, 2)
        self.assertCountEqual(
            [call_args.args[1] for call_args in mock_send_mail_message.call_args_list],
            [sent_message, unsent_messages[0]],
        )


class TaskTests(TestCase):
    @mock.patch("ietf.message.tasks.log_smtp_exception")
    @mock.patch("ietf.message.tasks.send_scheduled_message_from_send_queue")
    def test_send_scheduled_mail_task(self, mock_send_message, mock_log_smtp_exception):
        not_yet_sent = SendQueueFactory()
        SendQueueFactory(sent_at=timezone.now())  # already sent
        send_scheduled_mail_task()
        self.assertEqual(mock_send_message.call_count, 1)
        self.assertEqual(mock_send_message.call_args[0], (not_yet_sent,))
        self.assertFalse(mock_log_smtp_exception.called)

        mock_send_message.reset_mock()
        mock_send_message.side_effect = SMTPException
        send_scheduled_mail_task()
        self.assertEqual(mock_send_message.call_count, 1)
        self.assertEqual(mock_send_message.call_args[0], (not_yet_sent,))
        self.assertTrue(mock_log_smtp_exception.called)

    @mock.patch("ietf.message.tasks.retry_send_messages")
    def test_retry_send_messages_by_pk_task(self, mock_retry_send):
        msgs = MessageFactory.create_batch(3)
        MessageFactory()  # an extra message that won't be resent

        retry_send_messages_by_pk_task([msg.pk for msg in msgs], resend=False)
        called_with_messages = mock_retry_send.call_args.kwargs["messages"]
        self.assertCountEqual(msgs, called_with_messages)
        self.assertFalse(mock_retry_send.call_args.kwargs["resend"])

        retry_send_messages_by_pk_task([msg.pk for msg in msgs], resend=True)
        called_with_messages = mock_retry_send.call_args.kwargs["messages"]
        self.assertCountEqual(msgs, called_with_messages)
        self.assertTrue(mock_retry_send.call_args.kwargs["resend"])
