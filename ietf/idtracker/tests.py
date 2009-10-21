# Copyright The IETF Trust 2007, All Rights Reserved
#
import doctest
from ietf.idtracker.templatetags import ietf_filters
import unittest
from ietf.utils.test_utils import SimpleUrlTestCase

class TemplateTagTest(unittest.TestCase):
    def testTemplateTags(self):
        print "Testing ietf_filters"
        #doctest.testmod(ietf_filters,verbose=True)
        doctest.testmod(ietf_filters)
        print "OK (ietf_filters)"

class IdTrackerUrlTestCase(SimpleUrlTestCase):
    def testUrls(self):
        self.doTestUrls(__file__)
