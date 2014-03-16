from __future__ import print_function

import os.path

from django.conf import settings

from ietf.utils.management.commands import pyflakes
from ietf.utils.test_utils import TestCase


class PyFlakesTestCase(TestCase):

    def test_pyflakes(self):
        path = os.path.join(settings.BASE_DIR)
        warnings = []
        warnings = pyflakes.checkPaths([path], verbosity=0)
        self.assertEqual([str(w) for w in warnings], [])
