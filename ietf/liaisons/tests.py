
from ietf.utils.test_utils import SimpleUrlTestCase, canonicalize_feed, canonicalize_sitemap

class LiaisonsUrlTestCase(SimpleUrlTestCase):
    def testUrls(self):
        self.doTestUrls(__file__)
    def doCanonicalize(self, url, content):
        if url.startswith("/feed/"):
            return canonicalize_feed(content)
        elif url == "/sitemap-liaison.xml":
            return canonicalize_sitemap(content)
        else:
            return content
