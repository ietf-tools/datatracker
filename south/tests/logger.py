import os
import unittest
from django.conf import settings
from django.db import connection, models

from south.db import db

# 
# # Create a list of error classes from the various database libraries
# errors = []
# try:
#     from psycopg2 import ProgrammingError
#     errors.append(ProgrammingError)
# except ImportError:
#     pass
# errors = tuple(errors)

class TestLogger(unittest.TestCase):

    """
    Tests if the various logging functions.
    """
    def setUp(self):
        db.debug = False
        self.test_path = os.path.join(os.path.dirname(__file__),"test.log")
        
    def test_db_execute_logging_nofile(self):
        """ Does logging degrade nicely if SOUTH_DEBUG_ON not set?
        """
        settings.SOUTH_LOGGING_ON = False     # this needs to be set to False
                                              # to avoid issues where other tests
                                              # set this to True. settings is shared
                                              # between these tests.
        db.create_table("test9", [('email_confirmed', models.BooleanField(default=False))])
        
    def test_db_execute_logging_validfile(self):
        """ Does logging work when passing in a valid file?
        """
        settings.SOUTH_LOGGING_ON = True
        settings.SOUTH_LOGGING_FILE = self.test_path
        db.create_table("test10", [('email_confirmed', models.BooleanField(default=False))])
        
        # remove the test log file
        os.remove(self.test_path) 

    def test_db_execute_logging_missingfilename(self):
        """ Does logging raise an error if there is a missing filename?
        """
        settings.SOUTH_LOGGING_ON = True
        settings.SOUTH_LOGGING_FILE = None
        self.assertRaises(IOError,
            db.create_table, "test11", [('email_confirmed', models.BooleanField(default=False))])
        
        