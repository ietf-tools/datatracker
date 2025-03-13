# Copyright The IETF Trust 2010-2023, All Rights Reserved
# -*- coding: utf-8 -*-


# Standard settings except we use Postgres and skip migrations, this is
# useful for speeding up tests that depend on the test database, try
# for instance:
#
#   ./manage.py test --settings=settings_test doc.ChangeStateTestCase
#

import atexit
import os
import shutil
import tempfile
from ietf.settings import *                                          # pyflakes:ignore
from ietf.settings import STORAGES, TEST_CODE_COVERAGE_CHECKER, MORE_STORAGE_NAMES, BLOBSTORAGE_CONNECT_TIMEOUT, BLOBSTORAGE_READ_TIMEOUT, BLOBSTORAGE_MAX_ATTEMPTS
import botocore.config
import debug                            # pyflakes:ignore
debug.debug = True

# Use a different hostname, to catch hardcoded values
IDTRACKER_BASE_URL = "https://postgrestest.ietf.org"

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
        'HOST': 'db',
        'PORT': '5432',
        'NAME': 'test.db',
        'ENGINE': 'django.db.backends.postgresql',
        'USER': 'django',
        'PASSWORD': 'RkTkDPFnKpko',
        },
    }

if TEST_CODE_COVERAGE_CHECKER and not TEST_CODE_COVERAGE_CHECKER._started: # pyflakes:ignore
    TEST_CODE_COVERAGE_CHECKER.start()                          # pyflakes:ignore


def tempdir_with_cleanup(**kwargs):
    """Utility to create a temporary dir and arrange cleanup"""
    _dir = tempfile.mkdtemp(**kwargs)
    atexit.register(shutil.rmtree, _dir)
    return _dir


NOMCOM_PUBLIC_KEYS_DIR = tempdir_with_cleanup(suffix="-nomcom-public-keys-dir")

MEDIA_ROOT = tempdir_with_cleanup(suffix="-media")
PHOTOS_DIRNAME = "photo"
PHOTOS_DIR = os.path.join(MEDIA_ROOT, PHOTOS_DIRNAME)
os.mkdir(PHOTOS_DIR)

# Undo any developer-dependent middleware when running the tests
MIDDLEWARE = [ c for c in MIDDLEWARE if not c in DEV_MIDDLEWARE ] # pyflakes:ignore

TEMPLATES[0]['OPTIONS']['context_processors'] = [ p for p in TEMPLATES[0]['OPTIONS']['context_processors'] if not p in DEV_TEMPLATE_CONTEXT_PROCESSORS ] # pyflakes:ignore

REQUEST_PROFILE_STORE_ANONYMOUS_SESSIONS = False

# Override loggers with a safer set in case things go to the log during testing. Specifically,
# make sure there are no syslog loggers that might send things to a real syslog.
LOGGING["loggers"] = {  # pyflakes:ignore
    'django': {
        'handlers': ['debug_console'],
        'level': 'INFO',
    },
    'django.request': {
        'handlers': ['debug_console'],
        'level': 'ERROR',
    },
    'django.server': {
        'handlers': ['django.server'],
        'level': 'INFO',
    },
    'django.security': {
        'handlers': ['debug_console', ],
        'level': 'INFO',
    },
    'oidc_provider': {
        'handlers': ['debug_console', ],
        'level': 'DEBUG',
    },
    'datatracker': {
        'handlers': ['debug_console'],
        'level': 'INFO',
    },
    'celery': {
        'handlers': ['debug_console'],
        'level': 'INFO',
    },
}

# Configure storages for the blob store - use env settings if present. See the --no-manage-blobstore test option.
_blob_store_endpoint_url = os.environ.get("DATATRACKER_BLOB_STORE_ENDPOINT_URL", "http://blobstore:9000")
_blob_store_access_key = os.environ.get("DATATRACKER_BLOB_STORE_ACCESS_KEY", "minio_root")
_blob_store_secret_key = os.environ.get("DATATRACKER_BLOB_STORE_SECRET_KEY", "minio_pass")
_blob_store_bucket_prefix = os.environ.get("DATATRACKER_BLOB_STORE_BUCKET_PREFIX", "test-")
_blob_store_enable_profiling = (
    os.environ.get("DATATRACKER_BLOB_STORE_ENABLE_PROFILING", "false").lower() == "true"
)
for storagename in MORE_STORAGE_NAMES:
    STORAGES[storagename] = {
        "BACKEND": "ietf.doc.storage_backends.CustomS3Storage",
        "OPTIONS": dict(
            endpoint_url=_blob_store_endpoint_url,
            access_key=_blob_store_access_key,
            secret_key=_blob_store_secret_key,
            security_token=None,
            client_config=botocore.config.Config(
                signature_version="s3v4",
                connect_timeout=BLOBSTORAGE_CONNECT_TIMEOUT,
                read_timeout=BLOBSTORAGE_READ_TIMEOUT,
                retries={"total_max_attempts": BLOBSTORAGE_MAX_ATTEMPTS},
            ),
            bucket_name=f"{_blob_store_bucket_prefix}{storagename}",
            ietf_log_blob_timing=_blob_store_enable_profiling,
        ),
    }
