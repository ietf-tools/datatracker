import unittest, doctest
import pyzmail
from pyzmail.generate import *

class TestGenerate(unittest.TestCase):

    def setUp(self):
        pass
    
    def test_format_addresses(self):
        """test format_addresse"""
        self.assertEqual('foo@example.com', str(format_addresses([ 'foo@example.com', ])))
        self.assertEqual('Foo <foo@example.com>', str(format_addresses([ ('Foo', 'foo@example.com'), ])))
        # notice the space around the comma
        self.assertEqual('foo@example.com , bar@example.com', str(format_addresses([ 'foo@example.com', 'bar@example.com'])))
        # notice the space around the comma
        self.assertEqual('Foo <foo@example.com> , Bar <bar@example.com>', str(format_addresses([ ('Foo', 'foo@example.com'), ( 'Bar', 'bar@example.com')])))

# Add doctest 
def load_tests(loader, tests, ignore):
    # this works with python 2.7 and 3.x
    tests.addTests(doctest.DocTestSuite(pyzmail.generate))
    return tests

def additional_tests():
    # Add doctest for python 2.6 and below
    if sys.version_info<(2, 7):
        return doctest.DocTestSuite(pyzmail.generate)
    else:
        return unittest.TestSuite()
