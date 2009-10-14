
from ietf.utils.test_utils import SimpleUrlTestCase

class IdRfcUrlTestCase(SimpleUrlTestCase):
    def testUrls(self):
        self.doTestUrls(__file__)
