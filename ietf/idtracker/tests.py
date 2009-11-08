# Copyright The IETF Trust 2007, All Rights Reserved
#
import doctest
from ietf.idtracker.templatetags import ietf_filters
import unittest
from ietf.utils.test_utils import SimpleUrlTestCase, canonicalize_feed, canonicalize_sitemap
import django.test

class TemplateTagTest(unittest.TestCase):
    def testTemplateTags(self):
        print "Testing ietf_filters"
        #doctest.testmod(ietf_filters,verbose=True)
        (failures, tests) = doctest.testmod(ietf_filters)
        self.assertEqual(failures, 0)
        print "OK (ietf_filters)"

class IdTrackerUrlTestCase(SimpleUrlTestCase):
    def testUrls(self):
        self.doTestUrls(__file__)
    def doCanonicalize(self, url, content):
        if url.startswith("/feed/"):
            return canonicalize_feed(content)
        elif url.startswith("/sitemap"):
            return canonicalize_sitemap(content)
        else:
            return content

class WGRoleTest(django.test.TestCase):
    fixtures = ['wgtest']

    def setUp(self):
        from ietf.idtracker.models import IETFWG
	self.xmas = IETFWG.objects.get(group_acronym__acronym='xmas')
	self.snow = IETFWG.objects.get(group_acronym__acronym='snow')

    def test_roles(self):
        print "Testing WG roles"
    	self.assertEquals(self.xmas.wgchair_set.all()[0].role(), 'xmas WG Chair')
	self.assertEquals(self.snow.wgchair_set.all()[0].role(), 'snow BOF Chair')
	self.assertEquals(self.xmas.wgsecretary_set.all()[0].role(), 'xmas WG Secretary')
	self.assertEquals(self.xmas.wgtechadvisor_set.all()[0].role(), 'xmas Technical Advisor')
        print "OK"
