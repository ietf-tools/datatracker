# Copyright The IETF Trust 2007, All Rights Reserved
#
import doctest, unittest

from ietf.idtracker.templatetags import ietf_filters

class TemplateTagTest(unittest.TestCase):
    def test_template_tags(self):
        failures, tests = doctest.testmod(ietf_filters)
        self.assertEqual(failures, 0)
