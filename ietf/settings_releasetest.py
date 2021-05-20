# Copyright The IETF Trust 2015-2020, All Rights Reserved
# -*- coding: utf-8 -*-


# Standard settings except we use SQLite, this is useful for speeding
# up tests that depend on the test database, try for instance:
#
#   ./manage.py test --settings=settings_sqlitetest doc.ChangeStateTestCase
#

from .settings import *                  # pyflakes:ignore

# Workaround to avoid spending minutes stepping through the migrations in
# every test run.  The result of this is to use the 'syncdb' way of creating
# the test database instead of doing it through the migrations.  Taken from
# https://gist.github.com/NotSqrt/5f3c76cd15e40ef62d09

class DisableMigrations(object):
 
    def __contains__(self, item):
        return True
 
    def __getitem__(self, item):
        return None

MIGRATION_MODULES = DisableMigrations()

DATABASES = {
    'default': {
        'NAME': 'test.db',
        'ENGINE': 'django.db.backends.sqlite3',
        },
    }

if TEST_CODE_COVERAGE_CHECKER and not TEST_CODE_COVERAGE_CHECKER._started: # pyflakes:ignore
    TEST_CODE_COVERAGE_CHECKER.start()                          # pyflakes:ignore

MEDIA_ROOT = os.path.join(os.path.dirname(BASE_DIR), 'test/media/') # pyflakes:ignore
MEDIA_URL = '/test/media/'
PHOTOS_DIR = MEDIA_ROOT + PHOTOS_DIRNAME                            # pyflakes:ignore

REQUEST_PROFILE_STORE_ANONYMOUS_SESSIONS = False
    
