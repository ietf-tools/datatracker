# Standard settings except we use SQLite, this is useful for speeding
# up tests that depend on the test database, try for instance:
#
#   ./manage.py test --settings=settings_sqlitetest idrfc.ChangeStateTestCase
#

from settings import *
DATABASE_ENGINE = "sqlite3"
DATABASE_NAME = "test.db" 
