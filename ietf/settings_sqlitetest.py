# Standard settings except we use SQLite and skip migrations, this is
# useful for speeding up tests that depend on the test database, try
# for instance:
#
#   ./manage.py test --settings=settings_sqlitetest doc.ChangeStateTestCase
#

from settings import *                  # pyflakes:ignore

DATABASES = {
    'default': {
        'NAME': 'test.db',
        'ENGINE': 'django.db.backends.sqlite3',
        },
    }

class DisableMigrations(object):
    def __contains__(self, item):
        return True
 
    def __getitem__(self, item):
        return "notmigrations"
 
MIGRATION_MODULES = DisableMigrations() 
