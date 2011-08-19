# Copyright The IETF Trust 2011, All Rights Reserved

import os
import unittest
from django.conf import settings
from ietf.utils.test_utils import SimpleUrlTestCase

class WgRecUrlTestCase(SimpleUrlTestCase):
    def testUrls(self):
        self.doTestUrls(__file__)

class WgRecFileTestCase(unittest.TestCase):
    def testFileExistence(self):
        print "     Testing if WG charter texts exist locally"
        fpath = os.path.join(settings.CHARTER_PATH, "charter-ietf-example-01.txt")
        if not os.path.exists(fpath):
            print "\nERROR: exampe charter text not found in "+settings.CHARTER_PATH
            print "Needed for testing WG record pages."
            print "Remember to set CHARTER_PATH in settings_local.py\n"
        else:
            print "OK   (seem to exist)"
    
