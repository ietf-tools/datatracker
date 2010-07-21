
from ietf.utils.test_utils import SimpleUrlTestCase, canonicalize_sitemap

class AnnouncementsUrlTestCase(SimpleUrlTestCase):
    def testUrls(self):
        self.doTestUrls(__file__)
    def doCanonicalize(self, url, content):
        if url.startswith("/sitemap"):
            return canonicalize_sitemap(content)
        else:
            return content

