
from ietf.utils.test_utils import SimpleUrlTestCase

class IprUrlTestCase(SimpleUrlTestCase):
    def testUrls(self):
        self.doTestUrls(__file__)
