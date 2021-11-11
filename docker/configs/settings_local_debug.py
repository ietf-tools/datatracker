# Copyright The IETF Trust 2007-2019, All Rights Reserved
# -*- coding: utf-8 -*-

from ietf.settings import INSTALLED_APPS, MIDDLEWARE
from ietf.settings_local import *                  # pyflakes:ignore

USE_DEBUG_TOOLBAR = True

INSTALLED_APPS = INSTALLED_APPS + ['debug_toolbar', ]

MIDDLEWARE = ['debug_toolbar.middleware.DebugToolbarMiddleware', ] + MIDDLEWARE

LOGGING = {
    'version': 1,
    'filters': {
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        }
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'filters': ['require_debug_true'],
            'class': 'logging.StreamHandler',
        }
    },
    'loggers': {
        'django.db.backends': {
            'level': 'DEBUG',
            'handlers': ['console'],
        }
    }
}
