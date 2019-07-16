import unittest, doctest
import pyzmail
from pyzmail.utils import *

class TestUtils(unittest.TestCase):

    def setUp(self):
        pass
    
    def test_nothing(self):
        pass

# Add doctest 
def load_tests(loader, tests, ignore):
    # this works with python 2.7 and 3.x
    tests.addTests(doctest.DocTestSuite(pyzmail.utils))
    return tests

def additional_tests():
    # Add doctest for python 2.6 and below
    if sys.version_info<(2, 7):
        return doctest.DocTestSuite(pyzmail.utils)
    else:
        return unittest.TestSuite()
