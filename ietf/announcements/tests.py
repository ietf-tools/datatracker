import django.test

from ietf.utils.test_utils import SimpleUrlTestCase, canonicalize_sitemap
from ietf.utils.test_runner import mail_outbox

from ietf.announcements.models import ScheduledAnnouncement

class AnnouncementsUrlTestCase(SimpleUrlTestCase):
    def testUrls(self):
        self.doTestUrls(__file__)
    def doCanonicalize(self, url, content):
        if url.startswith("/sitemap"):
            return canonicalize_sitemap(content)
        else:
            return content

class SendScheduledAnnouncementsTestCase(django.test.TestCase):
    def test_send_plain_announcement(self):
        a = ScheduledAnnouncement.objects.create(
            mail_sent=False,
            subject="This is a test",
            to_val="test@example.com",
            from_val="testmonkey@example.com",
            cc_val="cc.a@example.com, cc.b@example.com",
            bcc_val="bcc@example.com",
            body="Hello World!",
            content_type="",
            )

        mailbox_before = len(mail_outbox)
        
        from ietf.announcements.send_scheduled import send_scheduled_announcement
        send_scheduled_announcement(a)

        self.assertEquals(len(mail_outbox), mailbox_before + 1)
        self.assertTrue("This is a test" in mail_outbox[-1]["Subject"])
        self.assertTrue(ScheduledAnnouncement.objects.get(id=a.id).mail_sent)

    def test_send_mime_announcement(self):
        a = ScheduledAnnouncement.objects.create(
            mail_sent=False,
            subject="This is a test",
            to_val="test@example.com",
            from_val="testmonkey@example.com",
            cc_val="cc.a@example.com, cc.b@example.com",
            bcc_val="bcc@example.com",
            body='--NextPart\r\n\r\nA New Internet-Draft is available from the on-line Internet-Drafts directories.\r\n--NextPart\r\nContent-Type: Message/External-body;\r\n\tname="draft-huang-behave-bih-01.txt";\r\n\tsite="ftp.ietf.org";\r\n\taccess-type="anon-ftp";\r\n\tdirectory="internet-drafts"\r\n\r\nContent-Type: text/plain\r\nContent-ID:     <2010-07-30001541.I-D@ietf.org>\r\n\r\n--NextPart--',
            content_type='Multipart/Mixed; Boundary="NextPart"',
            )

        mailbox_before = len(mail_outbox)
        
        from ietf.announcements.send_scheduled import send_scheduled_announcement
        send_scheduled_announcement(a)

        self.assertEquals(len(mail_outbox), mailbox_before + 1)
        self.assertTrue("This is a test" in mail_outbox[-1]["Subject"])
        self.assertTrue("--NextPart" in mail_outbox[-1].as_string())
        self.assertTrue(ScheduledAnnouncement.objects.get(id=a.id).mail_sent)
