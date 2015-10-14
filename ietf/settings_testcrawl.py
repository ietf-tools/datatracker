# Standard settings except we enable caching like in the production
# environment, this is useful for speeding up the test crawl, try for
# instance:
#
#   bin/test-crawl --settings=ietf.settings_testcrawl
#

from settings import *                  # pyflakes:ignore

TEMPLATE_LOADERS = (
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

DRAFT_ALIASES_PATH = "/tmp/draft-aliases"
DRAFT_VIRTUAL_PATH = "/tmp/draft-virtual"
GROUP_ALIASES_PATH = "/tmp/group-aliases"
GROUP_VIRTUAL_PATH = "/tmp/group-virtual"
