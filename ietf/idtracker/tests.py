# Copyright The IETF Trust 2007, All Rights Reserved
#
#import doctest
#import templatetags.ietf_filters
from django.test import TestCase
from ietf.utils.test_utils import SimpleUrlTestCase

class IDTrackerTest(TestCase):
    def testDoctest(self):
        # doctests in models.py will be automatically tested when running
        # django's 'test' command, but for other modules we need to make a
        # bit of extra effort to have doctests run.

        #doctest.testmod(templatetags.ietf_filters)
        pass

class IdTrackerUrlTestCase(SimpleUrlTestCase):
    def testUrls(self):
        self.doTestUrls(__file__)
