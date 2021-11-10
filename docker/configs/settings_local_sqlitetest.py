# Copyright The IETF Trust 2010-2020, All Rights Reserved
# -*- coding: utf-8 -*-


# Standard settings except we use SQLite and skip migrations, this is
# useful for speeding up tests that depend on the test database, try
# for instance:
#
#   ./manage.py test --settings=settings_sqlitetest doc.ChangeStateTestCase
#

import os 
from ietf.settings import *                                          # pyflakes:ignore
from ietf.settings import TEST_CODE_COVERAGE_CHECKER, BASE_DIR, PHOTOS_DIRNAME
import debug                            # pyflakes:ignore
debug.debug = True

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

NOMCOM_PUBLIC_KEYS_DIR=os.path.abspath("tmp-nomcom-public-keys-dir")

# Undo any developer-dependent middleware when running the tests
MIDDLEWARE = [ c for c in MIDDLEWARE if not c in DEV_MIDDLEWARE ] # pyflakes:ignore

TEMPLATES[0]['OPTIONS']['context_processors'] = [ p for p in TEMPLATES[0]['OPTIONS']['context_processors'] if not p in DEV_TEMPLATE_CONTEXT_PROCESSORS ] # pyflakes:ignore

REQUEST_PROFILE_STORE_ANONYMOUS_SESSIONS = False

IDSUBMIT_IDNITS_BINARY = "/usr/local/bin/idnits"
IDSUBMIT_REPOSITORY_PATH = "test/id/"
IDSUBMIT_STAGING_PATH = "test/staging/"
INTERNET_DRAFT_ARCHIVE_DIR = "test/archive/"
INTERNET_ALL_DRAFTS_ARCHIVE_DIR = "test/archive/"
RFC_PATH = "test/rfc/"

AGENDA_PATH = 'data/developers/www6s/proceedings/'
MEETINGHOST_LOGO_PATH = AGENDA_PATH

USING_DEBUG_EMAIL_SERVER=True
EMAIL_HOST='localhost'
EMAIL_PORT=2025

TRAC_WIKI_DIR_PATTERN = "test/wiki/%s"
TRAC_SVN_DIR_PATTERN = "test/svn/%s"
TRAC_CREATE_ADHOC_WIKIS = [
]                                       # type: List[Tuple[str, str, str]]

MEDIA_BASE_DIR = 'test'
MEDIA_ROOT = MEDIA_BASE_DIR + '/media/'
MEDIA_URL = '/media/'

PHOTOS_DIRNAME = 'photo'
PHOTOS_DIR = MEDIA_ROOT + PHOTOS_DIRNAME

DOCUMENT_PATH_PATTERN = 'data/developers/ietf-ftp/{doc.type_id}/'

SUBMIT_YANG_CATALOG_MODEL_DIR = 'data/developers/ietf-ftp/yang/catalogmod/'
SUBMIT_YANG_DRAFT_MODEL_DIR = 'data/developers/ietf-ftp/yang/draftmod/'
SUBMIT_YANG_INVAL_MODEL_DIR = 'data/developers/ietf-ftp/yang/invalmod/'
SUBMIT_YANG_IANA_MODEL_DIR = 'data/developers/ietf-ftp/yang/ianamod/'
SUBMIT_YANG_RFC_MODEL_DIR   = 'data/developers/ietf-ftp/yang/rfcmod/'
