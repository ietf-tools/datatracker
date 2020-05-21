# Copyright The IETF Trust 2015-2020, All Rights Reserved
# -*- coding: utf-8 -*-


# Standard settings except we enable caching like in the production
# environment, this is useful for speeding up the test crawl, try for
# instance:
#
#   bin/test-crawl --settings=ietf.settings_testcrawl
#

from .settings import *                  # pyflakes:ignore
from .settings import TEMPLATES

TEMPLATES[0]['OPTIONS']['loaders'] = (
    ('django.template.loaders.cached.Loader', (
        'django.template.loaders.filesystem.Loader',
        'django.template.loaders.app_directories.Loader',
    )),
    'ietf.dbtemplate.template.Loader',
)

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'OPTIONS': {
            'MAX_ENTRIES': 10000,
        },
    },
    'htmlized': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
        #'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': '/var/cache/datatracker/htmlized',
        'OPTIONS': {
            'MAX_ENTRIES': 100000,
        },
    },
    'slowpages': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
        #'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': '/var/cache/datatracker/slowpages',
        'OPTIONS': {
            'MAX_ENTRIES': 5000,
        },
    },
}

PASSWORD_HASHERS = [ 'django.contrib.auth.hashers.MD5PasswordHasher', ]
SERVER_MODE = 'test'
ALLOWED_HOSTS = ["127.0.0.1", "localhost:8000", "testserver", ]

SILENCED_SYSTEM_CHECKS = [
    "fields.W342",  # Setting unique=True on a ForeignKey has the same effect as using a OneToOneField.
]
