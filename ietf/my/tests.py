
from ietf.utils.test_utils import SimpleUrlTestCase

class MyUrlTestCase(SimpleUrlTestCase):
    def testUrls(self):
        self.doTestUrls(__file__)
