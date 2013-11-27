import datetime

from django.conf import settings

from ietf.utils.test_utils import SimpleUrlTestCase, canonicalize_sitemap
from ietf.utils.test_data import make_test_data
from ietf.utils.mail import outbox
from ietf.utils import TestCase

from ietf.message.models import Message, SendQueue
from ietf.person.models import Person

class AnnouncementsUrlTestCase(SimpleUrlTestCase):
    def testUrls(self):
        self.doTestUrls(__file__)
    def doCanonicalize(self, url, content):
        if url.startswith("/sitemap"):
            return canonicalize_sitemap(content)
        else:
            return content

class SendScheduledAnnouncementsTestCase(TestCase):
    def test_send_plain_announcement(self):
        make_test_data()

        msg = Message.objects.create(
            by=Person.objects.get(name="(System)"),
            subject="This is a test",
            to="test@example.com",
            frm="testmonkey@example.com",
            cc="cc.a@example.com, cc.b@example.com",
            bcc="bcc@example.com",
            body="Hello World!",
            content_type="",
            )

        q = SendQueue.objects.create(
            by=Person.objects.get(name="(System)"),
            message=msg,
            send_at=datetime.datetime.now() + datetime.timedelta(hours=12)
            )

        mailbox_before = len(outbox)
        
        from ietf.announcements.send_scheduled import send_scheduled_announcement
        send_scheduled_announcement(q)

        self.assertEquals(len(outbox), mailbox_before + 1)
        self.assertTrue("This is a test" in outbox[-1]["Subject"])
        self.assertTrue(SendQueue.objects.get(id=q.id).sent_at)

    def test_send_mime_announcement(self):
        make_test_data()

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
        
        from ietf.announcements.send_scheduled import send_scheduled_announcement
        send_scheduled_announcement(q)

        self.assertEquals(len(outbox), mailbox_before + 1)
        self.assertTrue("This is a test" in outbox[-1]["Subject"])
        self.assertTrue("--NextPart" in outbox[-1].as_string())
        self.assertTrue(SendQueue.objects.get(id=q.id).sent_at)
