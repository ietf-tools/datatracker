
from ietf.utils.test_utils import SimpleUrlTestCase

class WgInfoUrlTestCase(SimpleUrlTestCase):
    def testUrls(self):
        self.doTestUrls(__file__)
