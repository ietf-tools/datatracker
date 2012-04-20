# Standard settings except we use SQLite, this is useful for speeding
# up tests that depend on the test database, try for instance:
#
#   ./manage.py test --settings=settings_sqlitetest idrfc.ChangeStateTestCase
#

from settings import *
DATABASES = {
    'default': {
        'NAME': os.path.join(BASE_DIR,'test.db'),
        'ENGINE': 'django.db.backends.sqlite3',
        },
    }
