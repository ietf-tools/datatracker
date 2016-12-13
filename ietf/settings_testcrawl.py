# Standard settings except we enable caching like in the production
# environment, this is useful for speeding up the test crawl, try for
# instance:
#
#   bin/test-crawl --settings=ietf.settings_testcrawl
#

from settings import *                  # pyflakes:ignore
from settings import TEMPLATES

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
    }
}

PASSWORD_HASHERS = ( 'django.contrib.auth.hashers.MD5PasswordHasher', )
SERVER_MODE = 'test'

SILENCED_SYSTEM_CHECKS = [
    "fields.W342",  # Setting unique=True on a ForeignKey has the same effect as using a OneToOneField.
]
