# Copyright The IETF Trust 2012, All Rights Reserved

"""
The test cases are split into multiple files.
"""

import sys
from django.test import TestCase
from datetime import datetime

# actual tests are distributed among a set of files in subdir tests/
from ietf.group.tests.workinggroups   import WorkingGroupTestCase

