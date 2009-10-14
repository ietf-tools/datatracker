
from ietf.utils.test_utils import SimpleUrlTestCase

class IesgUrlTestCase(SimpleUrlTestCase):
    def testUrls(self):
        self.doTestUrls(__file__)
