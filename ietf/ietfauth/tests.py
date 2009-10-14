
from ietf.utils.test_utils import SimpleUrlTestCase

class IetfAuthUrlTestCase(SimpleUrlTestCase):
    def testUrls(self):
        self.doTestUrls(__file__)
