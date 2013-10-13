import re

from ietf.utils.test_utils import SimpleUrlTestCase, canonicalize_feed

class MeetingUrlTestCase(SimpleUrlTestCase):
    def testUrls(self):
        self.doTestUrls(__file__)
    def doCanonicalize(self, url, content):
        if url.startswith("/feed/"):
            return canonicalize_feed(content)
        if "agenda" in url:
            content = re.sub("<!-- v.*-->","", content)
            content = re.sub('<a href="/release/.*?</a>','', content)
        return content

