# Copyright The IETF Trust 2007-2024, All Rights Reserved
# -*- coding: utf-8 -*-


# Django settings for ietf project.
# BASE_DIR and "settings_local" are from
# http://code.djangoproject.com/wiki/SplitSettings

import os
import sys
import datetime
import warnings
from hashlib import sha384
from typing import Any, Dict, List, Tuple # pyflakes:ignore

warnings.simplefilter("always", DeprecationWarning)
warnings.filterwarnings("ignore", message="pkg_resources is deprecated as an API")
warnings.filterwarnings("ignore", "Log out via GET requests is deprecated")  # happens in oidc_provider
warnings.filterwarnings("ignore", module="tastypie", message="The django.utils.datetime_safe module is deprecated.")
warnings.filterwarnings("ignore", module="oidc_provider", message="The django.utils.timezone.utc alias is deprecated.")
warnings.filterwarnings("ignore", message="The USE_DEPRECATED_PYTZ setting,")  # https://github.com/ietf-tools/datatracker/issues/5635
warnings.filterwarnings("ignore", message="The USE_L10N setting is deprecated.")  # https://github.com/ietf-tools/datatracker/issues/5648
warnings.filterwarnings("ignore", message="django.contrib.auth.hashers.CryptPasswordHasher is deprecated.")  # https://github.com/ietf-tools/datatracker/issues/5663
warnings.filterwarnings("ignore", message="'urllib3\\[secure\\]' extra is deprecated")
warnings.filterwarnings("ignore", message="The logout\\(\\) view is superseded by")
warnings.filterwarnings("ignore", message="Report.file_reporters will no longer be available in Coverage.py 4.2", module="coverage.report")
warnings.filterwarnings("ignore", message="Using or importing the ABCs from 'collections' instead of from 'collections.abc' is deprecated", module="bleach")
warnings.filterwarnings("ignore", message="HTTPResponse.getheader\\(\\) is deprecated", module='selenium.webdriver')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.abspath(BASE_DIR + "/.."))

from ietf import __version__
import debug

DEBUG = True
debug.debug = DEBUG

DEBUG_AGENDA = False

# Valid values:
# 'production', 'test', 'development'
# Override this in settings_local.py if it's not the desired setting:
SERVER_MODE = 'development'

# Domain name of the IETF
IETF_DOMAIN = 'ietf.org'

# Overriden in settings_local
ADMINS = [
    ('Tools Help', 'tools-help@ietf.org'),
]                                       # type: List[Tuple[str, str]]

BUG_REPORT_EMAIL = "tools-help@ietf.org"

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.SHA1PasswordHasher',
    'django.contrib.auth.hashers.CryptPasswordHasher',
]

ALLOWED_HOSTS = [".ietf.org", ".ietf.org.", "209.208.19.216", "4.31.198.44", "127.0.0.1", "localhost", ]

# Server name of the tools server
TOOLS_SERVER = 'tools.' + IETF_DOMAIN

# Override this in the settings_local.py file:
SERVER_EMAIL = 'Django Server <django-project@' + IETF_DOMAIN + '>'

DEFAULT_FROM_EMAIL = 'IETF Secretariat <ietf-secretariat-reply@' + IETF_DOMAIN + '>'
UTILS_ON_BEHALF_EMAIL = 'noreply@' + IETF_DOMAIN
UTILS_FROM_EMAIL_DOMAINS = [ 'ietf.org', 'iab.org', ]

MANAGERS = ADMINS

DATABASES = {
    'default': {
        'NAME': 'datatracker',
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'USER': 'ietf',
        #'PASSWORD': 'somepassword',
    },
}


# Local time zone for this installation. Choices can be found here:
# http://www.postgresql.org/docs/8.1/static/datetime-keywords.html#DATETIME-TIMEZONE-SET-TABLE
# although not all variations may be possible on all operating systems.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'PST8PDT'

# Language code for this installation. All choices can be found here:
# http://www.w3.org/TR/REC-html40/struct/dirlang.html#langcodes
# http://blogs.law.harvard.edu/tech/stories/storyReader$15
LANGUAGE_CODE = 'en-us'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = False

# Django 4.0 changed the default setting of USE_L10N to True. The setting
# is deprecated and will be removed in Django 5.0.
USE_L10N = False

USE_TZ = True
USE_DEPRECATED_PYTZ = True  # supported until Django 5

# The DjangoDivFormRenderer is a transitional class that opts in to defaulting to the div.html
# template for formsets. This will become the default behavior in Django 5.0. This configuration
# can be removed at that point.
# See https://docs.djangoproject.com/en/4.2/releases/4.1/#forms
FORM_RENDERER = "django.forms.renderers.DjangoDivFormRenderer"

# Default primary key field type to use for models that don’t have a field with primary_key=True.
# In the future (relative to 4.2), the default will become 'django.db.models.BigAutoField.'
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

# OIDC configuration
_SITE_URL = os.environ.get("OIDC_SITE_URL", None)
if _SITE_URL is not None:
    SITE_URL = _SITE_URL

if SERVER_MODE == 'production':
    MEDIA_ROOT = '/a/www/www6s/lib/dt/media/'
    MEDIA_URL  = 'https://www.ietf.org/lib/dt/media/'
    PHOTOS_DIRNAME = 'photo'
    PHOTOS_DIR = os.path.join(MEDIA_ROOT, PHOTOS_DIRNAME)
else:
    MEDIA_ROOT = os.path.join(os.path.dirname(BASE_DIR), 'media')
    MEDIA_URL = '/media/'
    PHOTOS_DIRNAME = 'photo'
    PHOTOS_DIR = os.path.join(MEDIA_ROOT, PHOTOS_DIRNAME)

OLD_PHOTO_DIRS = [
    '/a/www/www6/wg/images',
    '/a/www/www6/iesg/bio/photo',
    '/a/www/iab/wp-content/IAB-uploads/2010/10/',
    '/a/www/iab/wp-content/IAB-uploads/2011/05/',
    '/a/www/iab/wp-content/IAB-uploads/2014/02/',
    '/a/www/iab/wp-content/IAB-uploads/2015/02/',
    '/a/www/iab/wp-content/IAB-uploads/2015/03/',
    '/a/www/iab/wp-content/IAB-uploads/2015/06/',
    '/a/www/iab/wp-content/IAB-uploads/2015/08/',
    '/a/www/iab/wp-content/IAB-uploads/2016/03/',
]

IETF_HOST_URL = 'https://www.ietf.org/'
IETF_ID_URL = IETF_HOST_URL + 'id/' # currently unused
IETF_ID_ARCHIVE_URL = IETF_HOST_URL + 'archive/id/'
IETF_AUDIO_URL = IETF_HOST_URL + 'audio/'

IETF_NOTES_URL = 'https://notes.ietf.org/'  # HedgeDoc base URL

# Absolute path to the directory static files should be collected to.
# Example: "/var/www/example.com/static/"

SERVE_CDN_PHOTOS = True

SERVE_CDN_FILES_LOCALLY_IN_DEV_MODE = True

# URL to use when referring to static files located in STATIC_ROOT.
if SERVER_MODE != 'production' and SERVE_CDN_FILES_LOCALLY_IN_DEV_MODE:
    STATIC_URL = "/static/"
    STATIC_ROOT = os.path.abspath(BASE_DIR + "/../static/")
else:
    STATIC_URL = "https://static.ietf.org/dt/%s/"%__version__
    STATIC_ROOT = "/a/www/www6s/lib/dt/%s/"%__version__

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
)

# Client-side static.ietf.org URL
STATIC_IETF_ORG = "https://static.ietf.org"
# Server-side static.ietf.org URL (used in pdfized)
STATIC_IETF_ORG_INTERNAL = STATIC_IETF_ORG

ENABLE_BLOBSTORAGE = True

# "standard" retry mode is used, which does exponential backoff with a base factor of 2
# and a cap of 20. 
BLOBSTORAGE_MAX_ATTEMPTS = 5  # boto3 default is 3 (for "standard" retry mode)
BLOBSTORAGE_CONNECT_TIMEOUT = 10  # seconds; boto3 default is 60
BLOBSTORAGE_READ_TIMEOUT = 10  # seconds; boto3 default is 60

WSGI_APPLICATION = "ietf.wsgi.application"

AUTHENTICATION_BACKENDS = ( 'ietf.ietfauth.backends.CaseInsensitiveModelBackend', )

FILE_UPLOAD_PERMISSIONS = 0o644          

# ------------------------------------------------------------------------
# Django/Python Logging Framework Modifications

# Filter out "Invalid HTTP_HOST" emails
# Based on http://www.tiwoc.de/blog/2013/03/django-prevent-email-notification-on-suspiciousoperation/
from django.core.exceptions import SuspiciousOperation
def skip_suspicious_operations(record):
    if record.exc_info:
        exc_value = record.exc_info[1]
        if isinstance(exc_value, SuspiciousOperation):
            return False
    return True

# Filter out UreadablePostError:
from django.http import UnreadablePostError
def skip_unreadable_post(record):
    if record.exc_info:
        exc_type, exc_value = record.exc_info[:2] # pylint: disable=unused-variable
        if isinstance(exc_value, UnreadablePostError):
            return False
    return True

# Copied from DEFAULT_LOGGING as of Django 1.10.5 on 22 Feb 2017, and modified
# to incorporate html logging, invalid http_host filtering, and more.
# Changes from the default has comments.

# The Python logging flow is as follows:
# (see https://docs.python.org/2.7/howto/logging.html#logging-flow)
#
#   Init: get a Logger: logger = logging.getLogger(name)
#
#   Logging call, e.g. logger.error(level, msg, *args, exc_info=(...), extra={...})
#   --> Logger (discard if level too low for this logger)
#       (create log record from level, msg, args, exc_info, extra)
#       --> Filters (discard if any filter attach to logger rejects record)
#           --> Handlers (discard if level too low for handler)
#               --> Filters (discard if any filter attached to handler rejects record)
#                   --> Formatter (format log record and emit)
#

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    #
    'loggers': {
        'django': {
            'handlers': ['console', 'mail_admins'],
            'level': 'INFO',
        },
        'django.request': {
            'handlers': ['console'],
            'level': 'ERROR',
        },
        'django.server': {
            'handlers': ['django.server'],
            'level': 'INFO',
        },
        'django.security': {
            'handlers': ['console', ],
            'level': 'INFO',
        },
        'oidc_provider': {
            'handlers': ['console', ],
            'level': 'DEBUG',
        },
        'datatracker': {
            'handlers': ['console'],
            'level': 'INFO',
        },
        'celery': {
            'handlers': ['console'],
            'level': 'INFO',
        },
    },
    #
    # No logger filters
    #
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'plain',
        },
        'debug_console': {
            # Active only when DEBUG=True
            'level': 'DEBUG',
            'filters': ['require_debug_true'],
            'class': 'logging.StreamHandler',
            'formatter': 'plain',
        },
        'django.server': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'django.server',
        },
        'mail_admins': {
            'level': 'ERROR',
            'filters': [
                'require_debug_false',
                'skip_suspicious_operations', # custom
                'skip_unreadable_posts', # custom
            ],
            'class': 'django.utils.log.AdminEmailHandler',
            'include_html': True,       # non-default
        }
    },
    #
    # All these are used by handlers
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
        # custom filter, function defined above:
        'skip_suspicious_operations': {
            '()': 'django.utils.log.CallbackFilter',
            'callback': skip_suspicious_operations,
        },
        # custom filter, function defined above:
        'skip_unreadable_posts': {
            '()': 'django.utils.log.CallbackFilter',
            'callback': skip_unreadable_post,
        },
    },
    # And finally the formatters
    'formatters': {
        'django.server': {
            '()': 'django.utils.log.ServerFormatter',
            'format': '[%(server_time)s] %(message)s',
        },
        'plain': {
            'style': '{',
            'format': '{levelname}: {name}:{lineno}: {message}',
        },
        'json' : {
            "class": "ietf.utils.jsonlogger.DatatrackerJsonFormatter",
            "style": "{",
            "format": "{asctime}{levelname}{message}{name}{pathname}{lineno}{funcName}{process}",
        }
    },
}

# End logging
# ------------------------------------------------------------------------


X_FRAME_OPTIONS = 'SAMEORIGIN'
CSRF_TRUSTED_ORIGINS = [
    "https://ietf.org",
    "https://*.ietf.org",
    'https://meetecho.com',
    'https://*.meetecho.com',
]
CSRF_COOKIE_SAMESITE = 'None'
CSRF_COOKIE_SECURE = True

# SESSION_COOKIE_AGE = 60 * 60 * 24 * 7 * 2 # Age of cookie, in seconds: 2 weeks (django default)
SESSION_COOKIE_AGE = 60 * 60 * 24 * 7 * 4 # Age of cookie, in seconds: 4 weeks
SESSION_COOKIE_SAMESITE = 'None'
SESSION_COOKIE_SECURE = True

SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_SERIALIZER = "django.contrib.sessions.serializers.JSONSerializer"
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_SAVE_EVERY_REQUEST = True
SESSION_CACHE_ALIAS = 'sessions'

PREFERENCES_COOKIE_AGE = 60 * 60 * 24 * 365 * 50 # Age of cookie, in seconds: 50 years

TEMPLATES = [                           
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR + "/templates",
            BASE_DIR + "/secr/templates",
        ],
        'OPTIONS': {
            'context_processors': [
                'django.contrib.auth.context_processors.auth',
                'django.template.context_processors.debug',     # makes 'sql_queries' available in templates
                'django.template.context_processors.i18n',
                'django.template.context_processors.request',
                'django.template.context_processors.media',
                #'django.template.context_processors.tz',
                'django.contrib.messages.context_processors.messages',
                'ietf.context_processors.server_mode',
#                'ietf.context_processors.debug_mark_queries_from_view',
#                'ietf.context_processors.sql_debug',
                'ietf.context_processors.revision_info',
                'ietf.context_processors.settings_info',
                'ietf.secr.context_processors.secr_revision_info',
                'ietf.context_processors.rfcdiff_base_url',
                'ietf.context_processors.timezone_now',
            ],
            'loaders': [
                ('django.template.loaders.cached.Loader', (
                    'django.template.loaders.filesystem.Loader',
                    'django.template.loaders.app_directories.Loader',
                )),
                'ietf.dbtemplate.template.Loader',
            ]
        },
    },
]                                       # type: List[Dict[str,Any]]

if DEBUG:
    TEMPLATES[0]['OPTIONS']['string_if_invalid'] = "** No value found for '%s' **"


MIDDLEWARE = [
    "django.middleware.csrf.CsrfViewMiddleware",
    "corsheaders.middleware.CorsMiddleware", # see docs on CORS_REPLACE_HTTPS_REFERER before using it
    "django.middleware.common.CommonMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.http.ConditionalGetMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",
    # comment in this to get logging of SQL insert and update statements:
    #"ietf.middleware.sql_log_middleware",
    "ietf.middleware.SMTPExceptionMiddleware",
    "ietf.middleware.Utf8ExceptionMiddleware",
    "ietf.middleware.redirect_trailing_period_middleware",
    "django_referrer_policy.middleware.ReferrerPolicyMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    #"csp.middleware.CSPMiddleware",
    "ietf.middleware.unicode_nfkc_normalization_middleware",
    "ietf.middleware.is_authenticated_header_middleware",
]

ROOT_URLCONF = 'ietf.urls'

DJANGO_VITE_ASSETS_PATH = os.path.join(BASE_DIR, 'static/dist-neue')
if DEBUG:
    DJANGO_VITE_MANIFEST_PATH = os.path.join(BASE_DIR, 'static/dist-neue/manifest.json')

# Additional locations of static files (in addition to each app's static/ dir)
STATICFILES_DIRS = (
    DJANGO_VITE_ASSETS_PATH,
    os.path.join(BASE_DIR, 'static/dist'),
    os.path.join(BASE_DIR, 'secr/static/dist'),
)

INSTALLED_APPS = [
    # Django apps
    'ietf.admin',  # replaces django.contrib.admin
    'django.contrib.admindocs',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.humanize',
    'django.contrib.messages',
    'django.contrib.sessions',
    'django.contrib.sitemaps',
    'django.contrib.sites',
    'django.contrib.staticfiles',
    # External apps 
    'analytical',
    'django_vite',
    'django_bootstrap5',
    'django_celery_beat',
    'django_celery_results',
    'corsheaders',
    'django_markup',
    'oidc_provider',
    'drf_spectacular',
    'drf_standardized_errors',
    'rest_framework',
    'rangefilter',
    'simple_history',
    'tastypie',
    'widget_tweaks',
    # IETF apps
    'ietf.api',
    'ietf.blobdb',
    'ietf.community',
    'ietf.dbtemplate',
    'ietf.doc',
    'ietf.group',
    'ietf.idindex',
    'ietf.iesg',
    'ietf.ietfauth',
    'ietf.ipr',
    'ietf.liaisons',
    'ietf.mailinglists',
    'ietf.mailtrigger',
    'ietf.meeting',
    'ietf.message',
    'ietf.name',
    'ietf.nomcom',
    'ietf.person',
    'ietf.redirects',
    'ietf.release',
    'ietf.review',
    'ietf.stats',
    'ietf.status',
    'ietf.submit',
    'ietf.sync',
    'ietf.utils',
    # IETF Secretariat apps
    'ietf.secr.announcement',
    'ietf.secr.meetings',
    'ietf.secr.rolodex',
    'ietf.secr.sreq',
    'ietf.secr.telechat',
]

try:
    import django_extensions            # pyflakes:ignore
    INSTALLED_APPS.append('django_extensions')
except ImportError:
    pass

# Settings for django-bootstrap5
# See https://django-bootstrap5.readthedocs.io/en/latest/settings.html
BOOTSTRAP5 = {
    # Label class to use in horizontal forms
    'horizontal_label_class': 'col-md-2 fw-bold',

    # Field class to use in horiozntal forms
    'horizontal_field_class': 'col-md-10',

    # Field class used for horizontal fields withut a label.
    'horizontal_field_offset_class': 'offset-md-2',

    # Set placeholder attributes to label if no placeholder is provided
    'set_placeholder': False,

    'required_css_class': 'required',
    'error_css_class': 'is-invalid',
    'success_css_class': 'is-valid',

    'field_renderers': {
        'default': 'ietf.utils.bootstrap.SeparateErrorsFromHelpTextFieldRenderer',
    },
}

# CORS settings
# See https://github.com/ottoyiu/django-cors-headers/
CORS_ORIGIN_ALLOW_ALL = True
CORS_ALLOW_METHODS = ( 'GET', 'OPTIONS', )
CORS_URLS_REGEX = r'^(/api/.*|.*\.json|.*/json/?)$'

# Setting for django_referrer_policy.middleware.ReferrerPolicyMiddleware
REFERRER_POLICY = 'strict-origin-when-cross-origin'

# django.middleware.security.SecurityMiddleware 
SECURE_BROWSER_XSS_FILTER       = True
SECURE_CONTENT_TYPE_NOSNIFF     = True
SECURE_HSTS_INCLUDE_SUBDOMAINS  = True
#SECURE_HSTS_PRELOAD             = True             # Enable after testing
SECURE_HSTS_SECONDS             = 3600
#SECURE_REDIRECT_EXEMPT
#SECURE_SSL_HOST 
#SECURE_SSL_REDIRECT             = True
# Relax the COOP policy to allow Meetecho authentication pop-up
SECURE_CROSS_ORIGIN_OPENER_POLICY = "unsafe-none"

# Override this in your settings_local with the IP addresses relevant for you:
INTERNAL_IPS = (
# local
        '127.0.0.1',
        '::1',
)

# django-rest-framework configuration
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "ietf.api.authentication.ApiKeyAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "ietf.api.permissions.HasApiKey",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_standardized_errors.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "drf_standardized_errors.handler.exception_handler",
}

# DRF OpenApi schema settings
SPECTACULAR_SETTINGS = {
    "TITLE": "Datatracker API",
    "DESCRIPTION": "Datatracker API",
    "VERSION": "1.0.0",
    "SCHEMA_PATH_PREFIX": "/api/",
    "COMPONENT_SPLIT_REQUEST": True,
    "COMPONENT_NO_READ_ONLY_REQUIRED": True,
    "SERVERS": [
        {"url": "http://localhost:8000", "description": "local dev server"},
        {"url": "https://datatracker.ietf.org", "description": "production server"},
    ],
    # The following settings are needed for drf-standardized-errors
    "ENUM_NAME_OVERRIDES": {
        "ValidationErrorEnum": "drf_standardized_errors.openapi_serializers.ValidationErrorEnum.choices",
        "ClientErrorEnum": "drf_standardized_errors.openapi_serializers.ClientErrorEnum.choices",
        "ServerErrorEnum": "drf_standardized_errors.openapi_serializers.ServerErrorEnum.choices",
        "ErrorCode401Enum": "drf_standardized_errors.openapi_serializers.ErrorCode401Enum.choices",
        "ErrorCode403Enum": "drf_standardized_errors.openapi_serializers.ErrorCode403Enum.choices",
        "ErrorCode404Enum": "drf_standardized_errors.openapi_serializers.ErrorCode404Enum.choices",
        "ErrorCode405Enum": "drf_standardized_errors.openapi_serializers.ErrorCode405Enum.choices",
        "ErrorCode406Enum": "drf_standardized_errors.openapi_serializers.ErrorCode406Enum.choices",
        "ErrorCode415Enum": "drf_standardized_errors.openapi_serializers.ErrorCode415Enum.choices",
        "ErrorCode429Enum": "drf_standardized_errors.openapi_serializers.ErrorCode429Enum.choices",
        "ErrorCode500Enum": "drf_standardized_errors.openapi_serializers.ErrorCode500Enum.choices",
    },
    "POSTPROCESSING_HOOKS": ["drf_standardized_errors.openapi_hooks.postprocess_schema_enums"],
}

# DRF Standardized Errors settings
DRF_STANDARDIZED_ERRORS = {
    # enable the standardized errors when DEBUG=True for unhandled exceptions.
    # By default, this is set to False so you're able to view the traceback in
    # the terminal and get more information about the exception.
    "ENABLE_IN_DEBUG_FOR_UNHANDLED_EXCEPTIONS": False,
    # ONLY the responses that correspond to these status codes will appear
    # in the API schema.
    "ALLOWED_ERROR_STATUS_CODES": [
        "400",
        # "401",
        # "403",
        "404",
        # "405",
        # "406",
        # "415",
        # "429",
        # "500",
    ],

}

# no slash at end
IDTRACKER_BASE_URL = "https://datatracker.ietf.org"
RFCDIFF_BASE_URL = "https://author-tools.ietf.org/iddiff"
IDNITS_BASE_URL = "https://author-tools.ietf.org/api/idnits"
IDNITS_SERVICE_URL = "https://author-tools.ietf.org/idnits"

# Content security policy configuration (django-csp)
# (In current production, the Content-Security-Policy header is completely set by nginx configuration, but
#  we try to keep this in sync to avoid confusion)
CSP_DEFAULT_SRC = ("'self'", "'unsafe-inline'", f"data: {IDTRACKER_BASE_URL} http://ietf.org/ https://www.ietf.org/ https://analytics.ietf.org/ https://static.ietf.org")

# The name of the method to use to invoke the test suite
TEST_RUNNER = 'ietf.utils.test_runner.IetfTestRunner'

# Fixtures which will be loaded before testing starts
GLOBAL_TEST_FIXTURES = [ 'names','ietf.utils.test_data.make_immutable_base_data',
    'nomcom_templates','proceedings_templates' ]

TEST_DIFF_FAILURE_DIR = "/tmp/test/failure/"

# These are regexes
TEST_URL_COVERAGE_EXCLUDE = [
    r"^\^admin/",
]

# These are filename globs.  They are fed directly to the coverage code checker.
TEST_CODE_COVERAGE_EXCLUDE_FILES = [
    "*/tests*",
    "*/admin.py",
    "*/factories.py",
    "*/migrations/*",
    "*/management/commands/*",
    "docker/*",
    "idindex/generate_all_id2_txt.py",
    "idindex/generate_all_id_txt.py",
    "idindex/generate_id_abstracts_txt.py",
    "idindex/generate_id_index_txt.py",
    "ietf/checks.py",
    "ietf/manage.py",
    "ietf/virtualenv-manage.py",
    "ietf/meeting/timedeltafield.py",   # Dead code, kept for a migration include
    "ietf/settings*",
    "ietf/utils/templatetags/debug_filters.py",
    "ietf/utils/test_runner.py",
    "ietf/name/generate_fixtures.py",
    "ietf/review/import_from_review_tool.py",
    "ietf/utils/patch.py",
    "ietf/utils/test_data.py",
    "ietf/utils/jstest.py",
]

# These are code line regex patterns
TEST_CODE_COVERAGE_EXCLUDE_LINES = [
    "coverage: *ignore",
    "debug",
    r"unreachable\([^)]*\)",
    "if settings.DEBUG",
    "if settings.TEST_CODE_COVERAGE_CHECKER",
    "if __name__ == .__main__.:",
]

# These are filename globs.  They are used by test_parse_templates() and
# get_template_paths()
TEST_TEMPLATE_IGNORE = [
    ".*",                             # dot-files
    "*~",                             # tilde temp-files
    "#*",                             # files beginning with a hashmark
    "500.html"                        # isn't loaded by regular loader, but checked by test_500_page()
]

TEST_COVERAGE_MAIN_FILE = os.path.join(BASE_DIR, "../release-coverage.json")
TEST_COVERAGE_LATEST_FILE = os.path.join(BASE_DIR, "../latest-coverage.json")

TEST_CODE_COVERAGE_CHECKER = None
if SERVER_MODE != 'production':
    import coverage
    TEST_CODE_COVERAGE_CHECKER = coverage.Coverage(source=[ BASE_DIR ], cover_pylib=False, omit=TEST_CODE_COVERAGE_EXCLUDE_FILES)

TEST_CODE_COVERAGE_REPORT_PATH = "coverage/"
TEST_CODE_COVERAGE_REPORT_URL = os.path.join(STATIC_URL, TEST_CODE_COVERAGE_REPORT_PATH, "index.html")
TEST_CODE_COVERAGE_REPORT_DIR = os.path.join(BASE_DIR, "static", TEST_CODE_COVERAGE_REPORT_PATH)
TEST_CODE_COVERAGE_REPORT_FILE = os.path.join(TEST_CODE_COVERAGE_REPORT_DIR, "index.html")

# WG Chair configuration
MAX_WG_DELEGATES = 3

# These states aren't available in forms with drop-down choices for new
# document state:
GROUP_STATES_WITH_EXTRA_PROCESSING = ["sub-pub", "rfc-edit", ]

# Review team related settings
GROUP_REVIEW_MAX_ITEMS_TO_SHOW_IN_REVIEWER_LIST = 10
GROUP_REVIEW_DAYS_TO_SHOW_IN_REVIEWER_LIST = 365

DATE_FORMAT = "Y-m-d"
DATETIME_FORMAT = "Y-m-d H:i T"

# Add reusable URL regexps here, for consistency.  No need to do so if the
# regex can reasonably be expected to be a unique one-off.
URL_REGEXPS = {
    "acronym": r"(?P<acronym>[-a-z0-9]+)",
    "bofreq": r"(?P<name>bofreq-[-a-z0-9]+)",
    "charter": r"(?P<name>charter-[-a-z0-9]+)",
    "statement": r"(?P<name>statement-[-a-z0-9]+)",
    "date": r"(?P<date>\d{4}-\d{2}-\d{2})",
    "name": r"(?P<name>[A-Za-z0-9._+-]+?)",
    "document": r"(?P<document>[a-z][-a-z0-9]+)", # regular document names
    "rev": r"(?P<rev>[0-9]{1,2}(-[0-9]{2})?)",
    "owner": r"(?P<owner>[-A-Za-z0-9\'+._]+@[A-Za-z0-9-._]+)",
    "schedule_name": r"(?P<name>[A-Za-z0-9-:_]+)",
}

STORAGES: dict[str, Any] = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# Storages for artifacts stored as blobs
ARTIFACT_STORAGE_NAMES: list[str] = [
    "bofreq",
    "charter",
    "conflrev",
    "active-draft",
    "draft",
    "slides",
    "minutes",
    "agenda",
    "bluesheets",
    "procmaterials",
    "narrativeminutes",
    "statement",
    "statchg",
    "liai-att",
    "chatlog",
    "polls",
    "staging",
    "bibxml-ids",
    "indexes",
    "floorplan",
    "meetinghostlogo",
    "photo",
    "review",
]
for storagename in ARTIFACT_STORAGE_NAMES:
    assert storagename not in STORAGES
    STORAGES[storagename] = {
        "BACKEND": "ietf.doc.storage.StoredObjectBlobdbStorage",
        "OPTIONS": {"bucket_name": storagename},
    }

# Override this in settings_local.py if needed
# *_PATH variables ends with a slash/ .

DOCUMENT_PATH_PATTERN = '/a/ietfdata/doc/{doc.type_id}/'
INTERNET_DRAFT_PATH = '/a/ietfdata/doc/draft/repository'
INTERNET_DRAFT_PDF_PATH = '/a/www/ietf-datatracker/pdf/'
RFC_PATH = '/a/www/ietf-ftp/rfc/'
CHARTER_PATH = '/a/ietfdata/doc/charter/'
CHARTER_COPY_PATH = '/a/www/ietf-ftp/ietf'  # copy 1wg-charters files here if set
CHARTER_COPY_OTHER_PATH = '/a/ftp/ietf'
CHARTER_COPY_THIRD_PATH = '/a/ftp/charter'
GROUP_SUMMARY_PATH = '/a/www/ietf-ftp/ietf'
BOFREQ_PATH = '/a/ietfdata/doc/bofreq/'
CONFLICT_REVIEW_PATH = '/a/ietfdata/doc/conflict-review'
STATUS_CHANGE_PATH = '/a/ietfdata/doc/status-change'
AGENDA_PATH = '/a/www/www6s/proceedings/'
MEETINGHOST_LOGO_PATH = AGENDA_PATH  # put these in the same place as other proceedings files
# Move drafts to this directory when they expire
INTERNET_DRAFT_ARCHIVE_DIR = '/a/ietfdata/doc/draft/collection/draft-archive/'
# The following directory contains copies of all drafts - it used to be
# a set of hardlinks maintained by ghostlinkd, but is now explicitly written to
INTERNET_ALL_DRAFTS_ARCHIVE_DIR = '/a/ietfdata/doc/draft/archive'
MEETING_RECORDINGS_DIR = '/a/www/audio'
DERIVED_DIR = '/a/ietfdata/derived'
FTP_DIR = '/a/ftp'
ALL_ID_DOWNLOAD_DIR = '/a/www/www6s/download'
NFS_METRICS_TMP_DIR = '/a/tmp'

DOCUMENT_FORMAT_ALLOWLIST = ["txt", "ps", "pdf", "xml", "html", ]

# Mailing list info URL for lists hosted on the IETF servers
MAILING_LIST_INFO_URL = "https://mailman3.%(domain)s/mailman3/lists/%(list_addr)s.%(domain)s"
MAILING_LIST_ARCHIVE_URL = "https://mailarchive.ietf.org"

# Liaison Statement Tool settings (one is used in DOC_HREFS below)
LIAISON_UNIVERSAL_FROM = 'Liaison Statement Management Tool <statements@' + IETF_DOMAIN + '>'
LIAISON_ATTACH_PATH = '/a/www/ietf-datatracker/documents/LIAISON/' # should end in a slash
LIAISON_ATTACH_URL = 'https://www.ietf.org/lib/dt/documents/LIAISON/' # should end in a slash, location should have a symlink to LIAISON_ATTACH_PATH

# Ideally, more of these would be local -- but since we don't support
# versions right now, we'll point to external websites
DOC_HREFS = {
    "charter":  "https://www.ietf.org/charter/{doc.name}-{doc.rev}.txt",
    "draft":    "https://www.ietf.org/archive/id/{doc.name}-{doc.rev}.txt",
    "rfc":      "https://www.rfc-editor.org/rfc/rfc{doc.rfc_number}.txt",
    "slides": "https://www.ietf.org/slides/{doc.name}-{doc.rev}",
    "procmaterials": "https://www.ietf.org/procmaterials/{doc.name}-{doc.rev}",
    "conflrev": "https://www.ietf.org/cr/{doc.name}-{doc.rev}.txt",
    "statchg": "https://www.ietf.org/sc/{doc.name}-{doc.rev}.txt",
    "liaison": "%s{doc.uploaded_filename}" % LIAISON_ATTACH_URL,
    "liai-att": "%s{doc.uploaded_filename}" % LIAISON_ATTACH_URL,
}

# Valid MIME types for cases where text is uploaded and immediately extracted,
# e.g. a charter or a review. Must be a tuple, not a list.
DOC_TEXT_FILE_VALID_UPLOAD_MIME_TYPES = ('text/plain', 'text/markdown', 'text/x-rst', 'text/x-markdown', )

# Age limit before action holders are flagged in the document display
DOC_ACTION_HOLDER_AGE_LIMIT_DAYS = 20

# Override this in settings_local.py if needed
CACHE_MIDDLEWARE_SECONDS = 300
CACHE_MIDDLEWARE_KEY_PREFIX = ''

HTMLIZER_VERSION = 1
HTMLIZER_URL_PREFIX = "/doc/html"
HTMLIZER_CACHE_TIME = 60*60*24*14       # 14 days
PDFIZER_CACHE_TIME = HTMLIZER_CACHE_TIME
PDFIZER_URL_PREFIX = IDTRACKER_BASE_URL+"/doc/pdf"

# Email settings
IPR_EMAIL_FROM = 'ietf-ipr@ietf.org'
AUDIO_IMPORT_EMAIL = ['ietf@meetecho.com']
SESSION_REQUEST_FROM_EMAIL = 'IETF Meeting Session Request Tool <session-request@ietf.org>' 

SECRETARIAT_SUPPORT_EMAIL = "support@ietf.org"
SECRETARIAT_ACTION_EMAIL = SECRETARIAT_SUPPORT_EMAIL
SECRETARIAT_INFO_EMAIL = SECRETARIAT_SUPPORT_EMAIL

# Put real password in settings_local.py
IANA_SYNC_PASSWORD = "secret"
IANA_SYNC_CHANGES_URL = "https://datatracker.iana.org:4443/data-tracker/changes"
IANA_SYNC_PROTOCOLS_URL = "https://www.iana.org/protocols/"

RFC_EDITOR_SYNC_PASSWORD="secret"
RFC_EDITOR_SYNC_NOTIFICATION_URL = "https://www.rfc-editor.org/parser/parser.php"
RFC_EDITOR_GROUP_NOTIFICATION_EMAIL = "webmaster@rfc-editor.org"
#RFC_EDITOR_GROUP_NOTIFICATION_URL = "https://www.rfc-editor.org/notification/group.php"
RFC_EDITOR_QUEUE_URL = "https://www.rfc-editor.org/queue2.xml"
RFC_EDITOR_INDEX_URL = "https://www.rfc-editor.org/rfc/rfc-index.xml"
RFC_EDITOR_ERRATA_JSON_URL = "https://www.rfc-editor.org/errata.json"
RFC_EDITOR_ERRATA_URL = "https://www.rfc-editor.org/errata_search.php?rfc={rfc_number}"
RFC_EDITOR_INLINE_ERRATA_URL = "https://www.rfc-editor.org/rfc/inline-errata/rfc{rfc_number}.html"
RFC_EDITOR_INFO_BASE_URL = "https://www.rfc-editor.org/info/"

# NomCom Tool settings
ROLODEX_URL = ""
NOMCOM_PUBLIC_KEYS_DIR = '/a/www/nomcom/public_keys/'
NOMCOM_FROM_EMAIL = 'nomcom-chair-{year}@ietf.org'
OPENSSL_COMMAND = '/usr/bin/openssl'
DAYS_TO_EXPIRE_NOMINATION_LINK = ''
NOMINEE_FEEDBACK_TYPES = ['comment', 'questio', 'nomina', 'obe']

# SlideSubmission settings
SLIDE_STAGING_PATH = '/a/www/www6s/staging/'
SLIDE_STAGING_URL = 'https://www.ietf.org/staging/'

# ID Submission Tool settings
IDSUBMIT_FROM_EMAIL = 'IETF I-D Submission Tool <idsubmission@ietf.org>'
IDSUBMIT_ANNOUNCE_FROM_EMAIL = 'internet-drafts@ietf.org'
IDSUBMIT_ANNOUNCE_LIST_EMAIL = 'i-d-announce@ietf.org'

# Interim Meeting Tool settings
INTERIM_ANNOUNCE_FROM_EMAIL_DEFAULT = 'IESG Secretary <iesg-secretary@ietf.org>'
INTERIM_ANNOUNCE_FROM_EMAIL_PROGRAM = 'IAB Executive Administrative Manager <execd@iab.org>'
VIRTUAL_INTERIMS_REQUIRE_APPROVAL = False
INTERIM_SESSION_MINIMUM_MINUTES = 30
INTERIM_SESSION_MAXIMUM_MINUTES = 300

# Days from meeting to day of cut off dates on submit -- cutoff_time_utc is added to this
IDSUBMIT_DEFAULT_CUTOFF_DAY_OFFSET_00 = 13
IDSUBMIT_DEFAULT_CUTOFF_DAY_OFFSET_01 = 13
IDSUBMIT_DEFAULT_CUTOFF_TIME_UTC = datetime.timedelta(hours=23, minutes=59, seconds=59)
IDSUBMIT_DEFAULT_CUTOFF_WARNING_DAYS = datetime.timedelta(days=21)

# 14 Jun 2017: New convention: prefix settings with the app name to which
# they (mainly) belong.  So here, SUBMIT_, rather than IDSUBMIT_
SUBMIT_YANG_RFC_MODEL_DIR = '/a/www/ietf-ftp/yang/rfcmod/'
SUBMIT_YANG_DRAFT_MODEL_DIR = '/a/www/ietf-ftp/yang/draftmod/'
SUBMIT_YANG_IANA_MODEL_DIR = '/a/www/ietf-ftp/yang/ianamod/'
SUBMIT_YANG_CATALOG_MODEL_DIR = '/a/www/ietf-ftp/yang/catalogmod/'

IDSUBMIT_REPOSITORY_PATH = INTERNET_DRAFT_PATH
IDSUBMIT_STAGING_PATH = '/a/www/www6s/staging/'
IDSUBMIT_STAGING_URL = '//www.ietf.org/staging/'
IDSUBMIT_IDNITS_BINARY = '/a/www/ietf-datatracker/scripts/idnits'
SUBMIT_PYANG_COMMAND = 'pyang --verbose --ietf -p {libs} {model}'
SUBMIT_YANGLINT_COMMAND = 'yanglint --verbose -p {tmplib} -p {rfclib} -p {draftlib} -p {ianalib} -p {cataloglib} {model} -i'

SUBMIT_YANG_CATALOG_MODULEARG = "modules[]={module}"
SUBMIT_YANG_CATALOG_IMPACT_URL = "https://www.yangcatalog.org/yang-search/impact_analysis.php?{moduleargs}&recurse=0&rfcs=1&show_subm=1&show_dir=both"
SUBMIT_YANG_CATALOG_IMPACT_DESC = "Yang impact analysis for {draft}"
SUBMIT_YANG_CATALOG_MODULE_URL = "https://www.yangcatalog.org/yang-search/module_details.php?module={module}"
SUBMIT_YANG_CATALOG_MODULE_DESC = "Yang catalog entry for {module}"

SUBMIT_YANG_CATALOG_CHECKER_URL = "https://yangcatalog.org/yangvalidator/api/v1/datatracker/{type}"

IDSUBMIT_CHECKER_CLASSES = (
    "ietf.submit.checkers.DraftIdnitsChecker",
    "ietf.submit.checkers.DraftYangChecker",
#    "ietf.submit.checkers.DraftYangvalidatorChecker",    
)

# Max time to allow for validation before a submission is subject to cancellation
IDSUBMIT_MAX_VALIDATION_TIME = datetime.timedelta(minutes=20)

# Age at which a submission expires if not posted
IDSUBMIT_EXPIRATION_AGE = datetime.timedelta(days=14)

IDSUBMIT_FILE_TYPES = (
    'txt',
    'html',
    'xml',
    'pdf',
    'ps',
)
RFC_FILE_TYPES = IDSUBMIT_FILE_TYPES

IDSUBMIT_MAX_DRAFT_SIZE =  {
    'txt':  2*1024*1024,  # Max size of txt draft file in bytes
    'xml':  3*1024*1024,  # Max size of xml draft file in bytes
    'html': 4*1024*1024,
    'pdf':  6*1024*1024,
    'ps' :  6*1024*1024,
}

IDSUBMIT_MAX_DAILY_SAME_DRAFT_NAME = 20
IDSUBMIT_MAX_DAILY_SAME_DRAFT_NAME_SIZE = 50 # in MB
IDSUBMIT_MAX_DAILY_SAME_SUBMITTER = 50
IDSUBMIT_MAX_DAILY_SAME_SUBMITTER_SIZE = 150 # in MB
IDSUBMIT_MAX_DAILY_SAME_GROUP = 150
IDSUBMIT_MAX_DAILY_SAME_GROUP_SIZE = 450 # in MB
IDSUBMIT_MAX_DAILY_SUBMISSIONS = 1000
IDSUBMIT_MAX_DAILY_SUBMISSIONS_SIZE = 2000 # in MB


# === Meeting Related Settings =================================================

MEETING_MATERIALS_SERVE_LOCALLY = True

# If you override MEETING_MATERIALS_SERVE_LOCALLY in your settings_local.conf, you will need to
# set the right value for MEETING_DOC_HREFS there as well. MEETING_DOC_LOCAL_HREFS and 
# CDN_MEETING_DOC_HREFS are defined here to make that simpler.

MEETING_DOC_LOCAL_HREFS = {
    "agenda": "/meeting/{meeting.number}/materials/{doc.name}-{doc.rev}",
    "minutes": "/meeting/{meeting.number}/materials/{doc.name}-{doc.rev}",
    "narrativeminutes": "/meeting/{meeting.number}/materials/{doc.name}-{doc.rev}",
    "slides": "/meeting/{meeting.number}/materials/{doc.name}-{doc.rev}",
    "chatlog": "/meeting/{meeting.number}/materials/{doc.name}-{doc.rev}",
    "polls": "/meeting/{meeting.number}/materials/{doc.name}-{doc.rev}",
    "recording": "{doc.external_url}",
    "bluesheets": "https://www.ietf.org/proceedings/{meeting.number}/bluesheets/{doc.uploaded_filename}",
    "procmaterials": "/meeting/{meeting.number}/materials/{doc.name}-{doc.rev}",
}

MEETING_DOC_CDN_HREFS = {
    "agenda": "https://www.ietf.org/proceedings/{meeting.number}/agenda/{doc.name}-{doc.rev}",
    "minutes": "https://www.ietf.org/proceedings/{meeting.number}/minutes/{doc.name}-{doc.rev}",
    "narrativeminutes": "https://www.ietf.org/proceedings/{meeting.number}/narrative-minutes/{doc.name}-{doc.rev}",
    "slides": "https://www.ietf.org/proceedings/{meeting.number}/slides/{doc.name}-{doc.rev}",
    "recording": "{doc.external_url}",
    "bluesheets": "https://www.ietf.org/proceedings/{meeting.number}/bluesheets/{doc.uploaded_filename}",
    "procmaterials": "https://www.ietf.org/proceedings/{meeting.number}/procmaterials/{doc.name}-{doc.rev}",
}

MEETING_DOC_HREFS = MEETING_DOC_LOCAL_HREFS if MEETING_MATERIALS_SERVE_LOCALLY else MEETING_DOC_CDN_HREFS

MEETING_DOC_OLD_HREFS = {
    "agenda": "/meeting/{meeting.number}/materials/{doc.name}",
    "minutes": "/meeting/{meeting.number}/materials/{doc.name}",
    "narrativeminutes" : "/meeting/{meeting.number}/materials/{doc.name}",
    "slides": "/meeting/{meeting.number}/materials/{doc.name}",
    "recording": "{doc.external_url}",
    "bluesheets": "https://www.ietf.org/proceedings/{meeting.number}/bluesheets/{doc.uploaded_filename}",
}

# For http references to documents without a version number (that is, to the current version at the time of reference)
MEETING_DOC_GREFS = {
    "agenda": "/meeting/{meeting.number}/materials/{doc.name}",
    "minutes": "/meeting/{meeting.number}/materials/{doc.name}",
    "narrativeminutes": "/meeting/{meeting.number}/materials/{doc.name}",
    "slides": "/meeting/{meeting.number}/materials/{doc.name}",
    "recording": "{doc.external_url}",
    "bluesheets": "https://www.ietf.org/proceedings/{meeting.number}/bluesheets/{doc.uploaded_filename}",
    "procmaterials": "/meeting/{meeting.number}/materials/{doc.name}",
}

MEETING_MATERIALS_DEFAULT_SUBMISSION_START_DAYS = 90
MEETING_MATERIALS_DEFAULT_SUBMISSION_CUTOFF_DAYS = 26
MEETING_MATERIALS_DEFAULT_SUBMISSION_CORRECTION_DAYS = 50

MEETING_VALID_UPLOAD_EXTENSIONS = {
    'agenda':       ['.txt','.html','.htm', '.md', ],
    'minutes':      ['.txt','.html','.htm', '.md', '.pdf', ],
    'narrativeminutes': ['.txt','.html','.htm', '.md', '.pdf', ],
    'slides':       ['.doc','.docx','.pdf','.ppt','.pptx','.txt', ], # Note the removal of .zip
    'bluesheets':   ['.pdf', '.txt', ],
    'procmaterials':['.pdf', ],
    'meetinghostlogo':  ['.png', '.jpg', '.jpeg'],
}
    
MEETING_VALID_UPLOAD_MIME_TYPES = {
    'agenda':       ['text/plain', 'text/html', 'text/markdown', 'text/x-markdown', ],
    'minutes':      ['text/plain', 'text/html', 'application/pdf', 'text/markdown', 'text/x-markdown', ],
    'narrativeminutes': ['text/plain', 'text/html', 'application/pdf', 'text/markdown', 'text/x-markdown', ],
    'slides':       [],
    'bluesheets':   ['application/pdf', 'text/plain', ],
    'procmaterials':['application/pdf', ],
    'meetinghostlogo':  ['image/jpeg', 'image/png', ],
}

MEETING_VALID_MIME_TYPE_EXTENSIONS = {
    'text/plain':   ['.txt', '.md', ],
    'text/markdown': ['.txt', '.md', ],
    'text/x-markdown': ['.txt', '.md', ],
    'text/html':    ['.html', '.htm'],
    'application/pdf': ['.pdf'],
}

# Files uploaded with Content-Type application/octet-stream and an extension in this map will
# be treated as if they had been uploaded with the mapped Content-Type value.
MEETING_APPLICATION_OCTET_STREAM_OVERRIDES = {
    '.md': 'text/markdown',
}

MEETING_VALID_UPLOAD_MIME_FOR_OBSERVED_MIME = {
    'text/plain':   ['text/plain', 'text/markdown', 'text/x-markdown', ],
    'text/html':    ['text/html', ],
    'application/pdf': ['application/pdf', ],
}

INTERNET_DRAFT_DAYS_TO_EXPIRE = 185

FLOORPLAN_MEDIA_DIR = 'floor'
FLOORPLAN_DIR = os.path.join(MEDIA_ROOT, FLOORPLAN_MEDIA_DIR)

MEETING_LEGACY_OFFICE_HOURS_END = 112  # last meeting to use legacy office hours representation

# Maximum dimensions to accept at all
MEETINGHOST_LOGO_MAX_UPLOAD_WIDTH = 400
MEETINGHOST_LOGO_MAX_UPLOAD_HEIGHT = 400

# Maximum dimensions to display
MEETINGHOST_LOGO_MAX_DISPLAY_WIDTH = 120
MEETINGHOST_LOGO_MAX_DISPLAY_HEIGHT = 120

# Session assignments on the official schedule lock this long before the timeslot starts
MEETING_SESSION_LOCK_TIME = datetime.timedelta(minutes=10)

# === OpenID Connect Provide Related Settings ==================================

# Used by django-oidc-provider
LOGIN_URL = '/accounts/login/'
OIDC_USERINFO = 'ietf.ietfauth.utils.openid_userinfo'
OIDC_EXTRA_SCOPE_CLAIMS = 'ietf.ietfauth.utils.OidcExtraScopeClaims'

# ==============================================================================


YANGLINT_BINARY = '/usr/bin/yanglint'
DE_GFM_BINARY = '/usr/bin/de-gfm.ruby2.5'

# Account settings
DAYS_TO_EXPIRE_REGISTRATION_LINK = 3
MINUTES_TO_EXPIRE_RESET_PASSWORD_LINK = 60

# Generation of pdf files
GHOSTSCRIPT_COMMAND = "/usr/bin/gs"

# Generation of bibxml files (currently only for Internet-Drafts)
BIBXML_BASE_PATH = '/a/ietfdata/derived/bibxml'

# Timezone files for iCalendar
TZDATA_ICS_PATH = BASE_DIR + '/../vzic/zoneinfo/'

DATATRACKER_MAX_UPLOAD_SIZE = 40960000
PPT2PDF_COMMAND = [
    "/usr/bin/soffice",
    "--headless", # no GUI
    "--safe-mode", # use a new libreoffice profile every time (ensures no reliance on accumulated profile config)
    "--norestore", # don't attempt to restore files after a previous crash (ensures that one crash won't block future conversions until UI intervention)
    "--convert-to", "pdf:writer_globaldocument_pdf_Export",
    "--outdir"
]

STATS_REGISTRATION_ATTENDEES_JSON_URL = 'https://registration.ietf.org/{number}/attendees/'
PROCEEDINGS_VERSION_CHANGES = [
    0,   # version 1
    97,  # version 2: meeting 97 and later (was number was NEW_PROCEEDINGS_START)
    111, # version 3: meeting 111 and later
]
PROCEEDINGS_V1_BASE_URL = 'https://www.ietf.org/proceedings/{meeting.number}'
YOUTUBE_API_KEY = ''
YOUTUBE_API_SERVICE_NAME = 'youtube'
YOUTUBE_API_VERSION = 'v3'
YOUTUBE_BASE_URL = 'https://www.youtube.com/watch'
YOUTUBE_IETF_CHANNEL_ID = 'UC8dtK9njBLdFnBahHFp0eZQ'

# If we need to revert to xmpp, change this to 'xmpp:{chat_room_name}@jabber.ietf.org?join'
CHAT_URL_PATTERN = 'https://zulip.ietf.org/#narrow/stream/{chat_room_name}'

# If we need to revert to xmpp
# CHAT_ARCHIVE_URL_PATTERN = 'https://www.ietf.org/jabber/logs/{chat_room_name}?C=M;O=D'

PYFLAKES_DEFAULT_ARGS= ["ietf", ]

# Automatic Scheduling
#
# how much to login while running, bigger numbers make it more verbose.
BADNESS_CALC_LOG   = 0
#
# these penalties affect the calculation of how bad the assignments are.
BADNESS_UNPLACED   = 1000000

# following four are used only during migrations to setup up ConstraintName
# and penalties are taken from the database afterwards.
BADNESS_BETHERE    = 200000
BADNESS_CONFLICT_1 = 100000
BADNESS_CONFLICT_2 = 10000
BADNESS_CONFLICT_3 = 1000

BADNESS_TOOSMALL_50  = 5000
BADNESS_TOOSMALL_100 = 50000
BADNESS_TOOBIG     = 100
BADNESS_MUCHTOOBIG = 500

# Set debug apps in settings_local.DEV_APPS

DEV_APPS = []                           # type: List[str]
DEV_PRE_APPS = []                       # type: List[str]
DEV_MIDDLEWARE = ()

PROD_PRE_APPS = []                      # type: List[str]

# django-debug-toolbar and the debug listing of sql queries at the bottom of
# each page when in dev mode can overlap in functionality, and can slow down
# page loading.  If you wish to use the sql_queries debug listing, put this in
# your settings_local and make sure your client IP address is in INTERNAL_IPS:
#
#    DEV_TEMPLATE_CONTEXT_PROCESSORS = [
#        'ietf.context_processors.sql_debug',
#    ]
#
DEV_TEMPLATE_CONTEXT_PROCESSORS = []    # type: List[str]

# Domain which hosts draft and wg alias lists
DRAFT_ALIAS_DOMAIN = IETF_DOMAIN
GROUP_ALIAS_DOMAIN = IETF_DOMAIN

TEST_DATA_DIR = os.path.abspath(BASE_DIR + "/../test/data")


USER_PREFERENCE_DEFAULTS = {
    "expires_soon"  : "14",
    "new_enough"    : "14",
    "full_draft"    : "on",
    "left_menu"     : "off",
}


# Email addresses people attempt to set for their account will be checked
# against the following list of regex expressions with re.search(pat, addr):
EXCLUDED_PERSONAL_EMAIL_REGEX_PATTERNS = [
    "@ietf.org$",
]

# Configuration for django-markup
MARKUP_SETTINGS = {
    'restructuredtext': {
        'settings_overrides': {
            'report_level': 3,  # error (3) or severe (4) only
            'initial_header_level': 3,
            'doctitle_xform': False,
            'footnote_references': 'superscript',
            'trim_footnote_reference_space': True,
            'default_reference_context': 'view',
            'raw_enabled': False,  # critical for security
            'file_insertion_enabled': False,  # critical for security
            'link_base': ''
        }
    }
}

# This is the number of seconds required between subscribing to an ietf
# mailing list and datatracker account creation being accepted
LIST_ACCOUNT_DELAY = 60*60*25           # 25 hours
ACCOUNT_REQUEST_EMAIL = 'account-request@ietf.org'


SILENCED_SYSTEM_CHECKS = [
    "fields.W342",  # Setting unique=True on a ForeignKey has the same effect as using a OneToOneField.
    "fields.W905",  # django.contrib.postgres.fields.CICharField is deprecated. (see https://github.com/ietf-tools/datatracker/issues/5660)
]

CHECKS_LIBRARY_PATCHES_TO_APPLY = [
    'patch/change-oidc-provider-field-sizes-228.patch',
    'patch/fix-oidc-access-token-post.patch',
    'patch/fix-jwkest-jwt-logging.patch',
    'patch/django-cookie-delete-with-all-settings.patch',
    'patch/tastypie-django22-fielderror-response.patch',
]
if DEBUG:
    try:
        import django_cprofile_middleware # pyflakes:ignore
        CHECKS_LIBRARY_PATCHES_TO_APPLY += [ 'patch/add-django-cprofile-filter.patch', ]
    except ImportError:
        pass

STATS_NAMES_LIMIT = 25

UTILS_MEETING_CONFERENCE_DOMAINS = ['webex.com', 'zoom.us', 'jitsi.org', 'meetecho.com', 'gather.town', ]
UTILS_TEST_RANDOM_STATE_FILE = '.factoryboy_random_state'
UTILS_APIKEY_GUI_LOGIN_LIMIT_DAYS = 30


API_KEY_TYPE="ES256"                    # EC / P=256
API_PUBLIC_KEY_PEM = b"""
-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEqVojsaofDJScuMJN+tshumyNM5ME
garzVPqkVovmF6yE7IJ/dv4FcV+QKCtJ/rOS8e36Y8ZAEVYuukhes0yZ1w==
-----END PUBLIC KEY-----
"""
API_PRIVATE_KEY_PEM = b"""
-----BEGIN PRIVATE KEY-----
MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgoI6LJkopKq8XrHi9
QqGQvE4A83TFYjqLz+8gULYecsqhRANCAASpWiOxqh8MlJy4wk362yG6bI0zkwSB
qvNU+qRWi+YXrITsgn92/gVxX5AoK0n+s5Lx7fpjxkARVi66SF6zTJnX
-----END PRIVATE KEY-----
"""


# Default timeout for HTTP requests via the requests library
DEFAULT_REQUESTS_TIMEOUT = 20  # seconds


# Celery configuration
CELERY_TIMEZONE = 'UTC'
CELERY_BROKER_URL = 'amqp://mq/'
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
CELERY_BEAT_SYNC_EVERY = 1  # update DB after every event
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True  # the default, but setting it squelches a warning
# Use a result backend so we can chain tasks. This uses the rpc backend, see
# https://docs.celeryq.dev/en/stable/userguide/tasks.html#rpc-result-backend-rabbitmq-qpid
# Results can be retrieved only once and only by the caller of the task. Results will be
# lost if the message broker restarts.
CELERY_RESULT_BACKEND = 'django-cache'  # use a Django cache for results
CELERY_CACHE_BACKEND = 'celery-results'  # which Django cache to use
CELERY_RESULT_EXPIRES = datetime.timedelta(minutes=5)  # how long are results valid? (Default is 1 day)
CELERY_TASK_IGNORE_RESULT = True  # ignore results unless specifically enabled for a task

# Meetecho API setup: Uncomment this and provide real credentials to enable
# Meetecho conference creation for interim session requests
#
# MEETECHO_API_CONFIG = {
#     'api_base': 'https://meetings.conf.meetecho.com/api/v1/',
#     'client_id': 'datatracker',
#     'client_secret': 'some secret',
#     'request_timeout': 3.01,  # python-requests doc recommend slightly > a multiple of 3 seconds
#     # How many minutes before/after session to enable slide update API. Defaults to 15. Set to None to disable,
#     # or < 0 to _always_ send updates (useful for debugging)
#     'slides_notify_time': 15, 
#     'debug': False,  # if True, API calls will be echoed as debug instead of sent (only works for slides for now)
# }

# Meetecho URLs - instantiate with url.format(session=some_session)
MEETECHO_ONSITE_TOOL_URL = "https://meetings.conf.meetecho.com/onsite{session.meeting.number}/?session={session.pk}"
MEETECHO_VIDEO_STREAM_URL = "https://meetings.conf.meetecho.com/ietf{session.meeting.number}/?session={session.pk}"
MEETECHO_AUDIO_STREAM_URL = "https://mp3.conf.meetecho.com/ietf{session.meeting.number}/{session.pk}.m3u"
MEETECHO_SESSION_RECORDING_URL = "https://meetecho-player.ietf.org/playout/?session={session_label}"

# Put the production SECRET_KEY in settings_local.py, and also any other
# sensitive or site-specific changes.  DO NOT commit settings_local.py to svn.
from ietf.settings_local import *            # pyflakes:ignore pylint: disable=wildcard-import

for app in INSTALLED_APPS:
    if app.startswith('ietf'):
        app_settings_file = os.path.join(BASE_DIR, '../', app.replace('.', os.sep), "settings.py")
        if os.path.exists(app_settings_file):
            exec("from %s import *" % (app+".settings"))

# Add APPS from settings_local to INSTALLED_APPS
if SERVER_MODE == 'production':
    INSTALLED_APPS = PROD_PRE_APPS + INSTALLED_APPS
else:
    INSTALLED_APPS += DEV_APPS
    INSTALLED_APPS = DEV_PRE_APPS + INSTALLED_APPS
    MIDDLEWARE += DEV_MIDDLEWARE
    TEMPLATES[0]['OPTIONS']['context_processors'] += DEV_TEMPLATE_CONTEXT_PROCESSORS

if "CACHES" not in locals():
    if SERVER_MODE == "production":
        MEMCACHED_HOST = os.environ.get("MEMCACHED_SERVICE_HOST", "127.0.0.1")
        MEMCACHED_PORT = os.environ.get("MEMCACHED_SERVICE_PORT", "11211")
        CACHES = {
            "default": {
                "BACKEND": "ietf.utils.cache.LenientMemcacheCache",
                "LOCATION": f"{MEMCACHED_HOST}:{MEMCACHED_PORT}",
                "VERSION": __version__,
                "KEY_PREFIX": "ietf:dt",
                "KEY_FUNCTION": lambda key, key_prefix, version: (
                    f"{key_prefix}:{version}:{sha384(str(key).encode('utf8')).hexdigest()}"
                ),
            },
            "sessions": {
                "BACKEND": "ietf.utils.cache.LenientMemcacheCache",
                "LOCATION": f"{MEMCACHED_HOST}:{MEMCACHED_PORT}",
                # No release-specific VERSION setting.
                "KEY_PREFIX": "ietf:dt",
            },
            "htmlized": {
                "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
                "LOCATION": "/a/cache/datatracker/htmlized",
                "OPTIONS": {
                    "MAX_ENTRIES": 100000,  # 100,000
                },
            },
            "pdfized": {
                "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
                "LOCATION": "/a/cache/datatracker/pdfized",
                "OPTIONS": {
                    "MAX_ENTRIES": 100000,  # 100,000
                },
            },
            "slowpages": {
                "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
                "LOCATION": "/a/cache/datatracker/slowpages",
                "OPTIONS": {
                    "MAX_ENTRIES": 5000,
                },
            },
            "celery-results": {
                "BACKEND": "django.core.cache.backends.memcached.PyMemcacheCache",
                "LOCATION": f"{MEMCACHED_HOST}:{MEMCACHED_PORT}",
                "KEY_PREFIX": "ietf:celery",
            },
        }
    else:
        CACHES = {
            "default": {
                "BACKEND": "django.core.cache.backends.dummy.DummyCache",
                #'BACKEND': 'ietf.utils.cache.LenientMemcacheCache',
                #'LOCATION': '127.0.0.1:11211',
                #'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
                "VERSION": __version__,
                "KEY_PREFIX": "ietf:dt",
            },
            "sessions": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            },
            "htmlized": {
                "BACKEND": "django.core.cache.backends.dummy.DummyCache",
                #'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
                "LOCATION": "/var/cache/datatracker/htmlized",
                "OPTIONS": {
                    "MAX_ENTRIES": 1000,
                },
            },
            "pdfized": {
                "BACKEND": "django.core.cache.backends.dummy.DummyCache",
                #'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
                "LOCATION": "/var/cache/datatracker/pdfized",
                "OPTIONS": {
                    "MAX_ENTRIES": 1000,
                },
            },
            "slowpages": {
                "BACKEND": "django.core.cache.backends.dummy.DummyCache",
                #'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
                "LOCATION": "/var/cache/datatracker/",
                "OPTIONS": {
                    "MAX_ENTRIES": 5000,
                },
            },
            "celery-results": {
                "BACKEND": "django.core.cache.backends.memcached.PyMemcacheCache",
                "LOCATION": "app:11211",
                "KEY_PREFIX": "ietf:celery",
            },
        }

PUBLISH_IPR_STATES = ['posted', 'removed', 'removed_objfalse']

ADVERTISE_VERSIONS = ["markdown", "pyang", "rfc2html", "xml2rfc"]

# We provide a secret key only for test and development modes.  It's
# absolutely vital that django fails to start in production mode unless a
# secret key has been provided elsewhere, not in this file which is
# publicly available, for instance from the source repository.
if SERVER_MODE != 'production':
    # stomp out the cached template loader, it's annoying
    loaders = TEMPLATES[0]['OPTIONS']['loaders']
    loaders = tuple(l for e in loaders for l in (e[1] if isinstance(e, tuple) and "cached.Loader" in e[0] else (e,)))
    TEMPLATES[0]['OPTIONS']['loaders'] = loaders
    SESSION_ENGINE = "django.contrib.sessions.backends.db"

    if 'SECRET_KEY' not in locals():
        SECRET_KEY = 'PDwXboUq!=hPjnrtG2=ge#N$Dwy+wn@uivrugwpic8mxyPfHka'
    if 'NOMCOM_APP_SECRET' not in locals():
        NOMCOM_APP_SECRET = b'\x9b\xdas1\xec\xd5\xa0SI~\xcb\xd4\xf5t\x99\xc4i\xd7\x9f\x0b\xa9\xe8\xfeY\x80$\x1e\x12tN:\x84'

    ALLOWED_HOSTS = ['*',]
    
    try:
        # see https://github.com/omarish/django-cprofile-middleware
        import django_cprofile_middleware # pyflakes:ignore
        MIDDLEWARE = MIDDLEWARE + ['django_cprofile_middleware.middleware.ProfilerMiddleware', ]
    except ImportError:
        pass

    # Cannot have this set to True if we're using http: from the dev-server:
    CSRF_COOKIE_SECURE = False
    CSRF_COOKIE_SAMESITE = 'Lax'
    CSRF_TRUSTED_ORIGINS += ['http://localhost:8000', 'http://127.0.0.1:8000', 'http://[::1]:8000']
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_SAMESITE = 'Lax'


YOUTUBE_DOMAINS = ['www.youtube.com', 'youtube.com', 'youtu.be', 'm.youtube.com', 'youtube-nocookie.com', 'www.youtube-nocookie.com']
