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
