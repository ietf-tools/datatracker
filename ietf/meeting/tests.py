
from ietf.utils.test_utils import SimpleUrlTestCase

class MeetingUrlTestCase(SimpleUrlTestCase):
    def testUrls(self):
        self.doTestUrls(__file__)
