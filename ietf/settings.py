# Copyright The IETF Trust 2007-2020, All Rights Reserved
# -*- coding: utf-8 -*-


# Django settings for ietf project.
# BASE_DIR and "settings_local" are from
# http://code.djangoproject.com/wiki/SplitSettings

import os
import sys
import datetime
import warnings
from typing import Any, Dict, List, Tuple # pyflakes:ignore

warnings.simplefilter("always", DeprecationWarning)
warnings.filterwarnings("ignore", message="Add the `renderer` argument to the render\(\) method of", module="bootstrap3")
warnings.filterwarnings("ignore", message="The logout\(\) view is superseded by")
warnings.filterwarnings("ignore", message="Report.file_reporters will no longer be available in Coverage.py 4.2", module="coverage.report")
warnings.filterwarnings("ignore", message="{% load staticfiles %} is deprecated")
warnings.filterwarnings("ignore", message="Using or importing the ABCs from 'collections' instead of from 'collections.abc' is deprecated", module="bleach")

try:
    import syslog
    syslog.openlog(str("datatracker"), syslog.LOG_PID, syslog.LOG_USER)
except ImportError:
    pass

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

ADMINS = [
#    ('Henrik Levkowetz', 'henrik@levkowetz.com'),
    ('Robert Sparks', 'rjsparks@nostrum.com'),
#    ('Ole Laursen', 'olau@iola.dk'),
    ('Ryan Cross', 'rcross@amsl.com'),
    ('Glen Barney', 'glen@amsl.com'),
    ('Maddy Conner', 'maddy@amsl.com'),
]                                       # type: List[Tuple[str, str]]

BUG_REPORT_EMAIL = "datatracker-project@ietf.org"

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.SHA1PasswordHasher',
    'django.contrib.auth.hashers.CryptPasswordHasher',
]

ALLOWED_HOSTS = [".ietf.org", ".ietf.org.", "209.208.19.216", "4.31.198.44", "127.0.0.1", "localhost:8000", ]

# Server name of the tools server
TOOLS_SERVER = 'tools.' + IETF_DOMAIN
TOOLS_SERVER_URL = 'https://' + TOOLS_SERVER
TOOLS_ID_PDF_URL = TOOLS_SERVER_URL + '/pdf/'
TOOLS_ID_HTML_URL = TOOLS_SERVER_URL + '/html/'

# Override this in the settings_local.py file:
SERVER_EMAIL = 'Django Server <django-project@' + IETF_DOMAIN + '>'

DEFAULT_FROM_EMAIL = 'IETF Secretariat <ietf-secretariat-reply@' + IETF_DOMAIN + '>'
UTILS_ON_BEHALF_EMAIL = 'noreply@' + IETF_DOMAIN
UTILS_FROM_EMAIL_DOMAINS = [ 'ietf.org', 'iab.org', 'tools.ietf.org', ]

MANAGERS = ADMINS

DATABASES = {
    'default': {
        'NAME': 'ietf_utf8',
        'ENGINE': 'django.db.backends.mysql',
        'USER': 'ietf',
        #'PASSWORD': 'ietf',
        'OPTIONS': {
            'sql_mode': 'STRICT_TRANS_TABLES',
            'init_command': 'SET storage_engine=MyISAM; SET names "utf8"'
        },
    },
}

DATABASE_TEST_OPTIONS = {
    # Comment this out if your database doesn't support InnoDB
    'init_command': 'SET storage_engine=InnoDB',
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

USE_TZ = False

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


# Absolute path to the directory static files should be collected to.
# Example: "/var/www/example.com/static/"



SERVE_CDN_FILES_LOCALLY_IN_DEV_MODE = True

# URL to use when referring to static files located in STATIC_ROOT.
if SERVER_MODE != 'production' and SERVE_CDN_FILES_LOCALLY_IN_DEV_MODE:
    STATIC_URL = "/static/"
    STATIC_ROOT = os.path.abspath(BASE_DIR + "/../static/")
else:
    STATIC_URL = "https://www.ietf.org/lib/dt/%s/"%__version__
    STATIC_ROOT = "/a/www/www6s/lib/dt/%s/"%__version__

# Destination for components handled by djangobower
COMPONENT_ROOT = BASE_DIR + "/externals/static/"
COMPONENT_URL  = STATIC_URL

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'ietf.utils.bower_storage.BowerStorageFinder',
)

WSGI_APPLICATION = "ietf.wsgi.application"

AUTHENTICATION_BACKENDS = ( 'django.contrib.auth.backends.ModelBackend', )

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
            'handlers': ['debug_console', 'mail_admins'],
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
        'syslog': {
            'level': 'DEBUG',
            'class': 'logging.handlers.SysLogHandler',
            'facility': 'user',
            'formatter': 'plain',
            'address': '/dev/log',
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
    },
}

# This should be overridden by settings_local for any logger where debug (or
# other) custom log settings are wanted.  Use "ietf/manage.py showloggers -l"
# to show registered loggers.  The content here should match the levels above
# and is shown as an example:
UTILS_LOGGER_LEVELS: Dict[str, str] = {
#    'django':           'INFO',
#    'django.server':    'INFO',
}

# End logging
# ------------------------------------------------------------------------


X_FRAME_OPTIONS = 'ALLOW-FROM ietf.org *.ietf.org meetecho.com *.meetecho.com gather.town *.gather.town'
CSRF_TRUSTED_ORIGINS = ['ietf.org', '*.ietf.org', 'meetecho.com', '*.meetecho.com', 'gather.town', '*.gather.town', ]
CSRF_COOKIE_SAMESITE = 'None'
CSRF_COOKIE_SECURE = True

# SESSION_COOKIE_AGE = 60 * 60 * 24 * 7 * 2 # Age of cookie, in seconds: 2 weeks (django default)
SESSION_COOKIE_AGE = 60 * 60 * 24 * 7 * 4 # Age of cookie, in seconds: 4 weeks
SESSION_COOKIE_SAMESITE = 'None'
SESSION_COOKIE_SECURE = True

SESSION_EXPIRE_AT_BROWSER_CLOSE = False
# We want to use the JSON serialisation, as it's safer -- but there is /secr/
# code which stashes objects in the session that can't be JSON serialized.
# Switch when that code is rewritten.
#SESSION_SERIALIZER = "django.contrib.sessions.serializers.JSONSerializer"
SESSION_SERIALIZER = 'django.contrib.sessions.serializers.PickleSerializer'
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
    'django.middleware.csrf.CsrfViewMiddleware',
    'corsheaders.middleware.CorsMiddleware', # see docs on CORS_REPLACE_HTTPS_REFERER before using it
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.http.ConditionalGetMiddleware',
    'simple_history.middleware.HistoryRequestMiddleware',
    # comment in this to get logging of SQL insert and update statements:
    #'ietf.middleware.sql_log_middleware',
    'ietf.middleware.SMTPExceptionMiddleware',
    'ietf.middleware.Utf8ExceptionMiddleware',
    'ietf.middleware.redirect_trailing_period_middleware',
    'django_referrer_policy.middleware.ReferrerPolicyMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.middleware.security.SecurityMiddleware',
 #   'csp.middleware.CSPMiddleware',
    'ietf.middleware.unicode_nfkc_normalization_middleware',
]

ROOT_URLCONF = 'ietf.urls'

# Additional locations of static files (in addition to each app's static/ dir)
STATICFILES_DIRS = (
    os.path.join(BASE_DIR, 'static'),
    os.path.join(BASE_DIR, 'secr/static'),
    os.path.join(BASE_DIR, 'externals/static'),
)

INSTALLED_APPS = [
    # Django apps
    'django.contrib.admin',
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
    'bootstrap3',
    'corsheaders',
    'django_markup',
    'django_password_strength',
    'djangobwr',
    'form_utils',
    'oidc_provider',
    'simple_history',
    'tastypie',
    'widget_tweaks',
    # IETF apps
    'ietf.api',
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
    'ietf.submit',
    'ietf.sync',
    'ietf.utils',
    # IETF Secretariat apps
    'ietf.secr.announcement',
    'ietf.secr.areas',
    'ietf.secr.groups',
    'ietf.secr.meetings',
    'ietf.secr.proceedings',
    'ietf.secr.roles',
    'ietf.secr.rolodex',
    'ietf.secr.sreq',
    'ietf.secr.telechat',
]

try:
    import django_extensions            # pyflakes:ignore
    INSTALLED_APPS.append('django_extensions')
except ImportError:
    pass

# Settings for django-bootstrap3
# See http://django-bootstrap3.readthedocs.org/en/latest/settings.html
BOOTSTRAP3 = {
    # Label class to use in horizontal forms
    'horizontal_label_class': 'col-md-2',

    # Field class to use in horiozntal forms
    'horizontal_field_class': 'col-md-10',

    # Set HTML required attribute on required fields
    'set_required': True,

    # Set placeholder attributes to label if no placeholder is provided
    'set_placeholder': False,

    # Class to indicate required
    'form_required_class': 'bootstrap3-required',

    # Class to indicate error
    'form_error_class': 'bootstrap3-error',

    'field_renderers': {
        'default': 'ietf.utils.bootstrap.SeparateErrorsFromHelpTextFieldRenderer',
        'inline': 'bootstrap3.renderers.InlineFieldRenderer',
    },
    
}

# CORS settings
# See https://github.com/ottoyiu/django-cors-headers/
CORS_ORIGIN_ALLOW_ALL = True
CORS_ALLOW_METHODS = ( 'GET', 'OPTIONS', )
CORS_URLS_REGEX = r'^(/api/.*|.*\.json|.*/json/?)$'

# Setting for django_referrer_policy.middleware.ReferrerPolicyMiddleware
REFERRER_POLICY = 'strict-origin-when-cross-origin'

# Content security policy configuration (django-csp)
CSP_DEFAULT_SRC = ("'self'", "'unsafe-inline'", "data: https://datatracker.ietf.org/ https://www.ietf.org/")

# django.middleware.security.SecurityMiddleware 
SECURE_BROWSER_XSS_FILTER       = True
SECURE_CONTENT_TYPE_NOSNIFF     = True
SECURE_HSTS_INCLUDE_SUBDOMAINS  = True
#SECURE_HSTS_PRELOAD             = True             # Enable after testing
SECURE_HSTS_SECONDS             = 3600
#SECURE_REDIRECT_EXEMPT
#SECURE_SSL_HOST 
#SECURE_SSL_REDIRECT             = True

# Override this in your settings_local with the IP addresses relevant for you:
INTERNAL_IPS = (
# local
        '127.0.0.1',
        '::1',
)

# no slash at end
IDTRACKER_BASE_URL = "https://datatracker.ietf.org"
RFCDIFF_BASE_URL = "https://www.ietf.org/rfcdiff"
IDNITS_BASE_URL = "https://www.ietf.org/tools/idnits"
XML2RFC_BASE_URL = "https://xml2rfc.tools.ietf.org/experimental.html"

# The name of the method to use to invoke the test suite
TEST_RUNNER = 'ietf.utils.test_runner.IetfTestRunner'

# Fixtures which will be loaded before testing starts
GLOBAL_TEST_FIXTURES = [ 'names','ietf.utils.test_data.make_immutable_base_data',
    'nomcom_templates','proceedings_templates' ]

TEST_DIFF_FAILURE_DIR = "/tmp/test/failure/"

TEST_GHOSTDRIVER_LOG_PATH = "ghostdriver.log"

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
    "ietf/stats/backfill_data.py",
    "ietf/utils/patch.py",
    "ietf/utils/test_data.py",
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

TEST_COVERAGE_MASTER_FILE = os.path.join(BASE_DIR, "../release-coverage.json.gz")
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

# Review team releated settings
GROUP_REVIEW_MAX_ITEMS_TO_SHOW_IN_REVIEWER_LIST = 10
GROUP_REVIEW_DAYS_TO_SHOW_IN_REVIEWER_LIST = 365

DATE_FORMAT = "Y-m-d"
DATETIME_FORMAT = "Y-m-d H:i T"

# Add reusable URL regexps here, for consistency.  No need to do so if the
# regex can reasonably be expected to be a unique one-off.
URL_REGEXPS = {
    "acronym": r"(?P<acronym>[-a-z0-9]+)",
    "charter": r"(?P<name>charter-[-a-z0-9]+)",
    "date": r"(?P<date>\d{4}-\d{2}-\d{2})",
    "name": r"(?P<name>[A-Za-z0-9._+-]+?)",
    "document": r"(?P<document>[a-z][-a-z0-9]+)", # regular document names
    "rev": r"(?P<rev>[0-9]{1,2}(-[0-9]{2})?)",
    "owner": r"(?P<owner>[-A-Za-z0-9\'+._]+@[A-Za-z0-9-._]+)",
    "schedule_name": r"(?P<name>[A-Za-z0-9-:_]+)",
}

# Override this in settings_local.py if needed
# *_PATH variables ends with a slash/ .

#DOCUMENT_PATH_PATTERN = '/a/www/ietf-ftp/{doc.type_id}/'
DOCUMENT_PATH_PATTERN = '/a/ietfdata/doc/{doc.type_id}/'
INTERNET_DRAFT_PATH = '/a/ietfdata/doc/draft/repository'
INTERNET_DRAFT_PDF_PATH = '/a/www/ietf-datatracker/pdf/'
RFC_PATH = '/a/www/ietf-ftp/rfc/'
CHARTER_PATH = '/a/ietfdata/doc/charter/'
CONFLICT_REVIEW_PATH = '/a/ietfdata/doc/conflict-review'
STATUS_CHANGE_PATH = '/a/ietfdata/doc/status-change'
AGENDA_PATH = '/a/www/www6s/proceedings/'
IPR_DOCUMENT_PATH = '/a/www/ietf-ftp/ietf/IPR/'
IESG_TASK_FILE = '/a/www/www6/iesg/internal/task.txt'
IESG_ROLL_CALL_FILE = '/a/www/www6/iesg/internal/rollcall.txt'
IESG_ROLL_CALL_URL = 'https://www6.ietf.org/iesg/internal/rollcall.txt'
IESG_MINUTES_FILE = '/a/www/www6/iesg/internal/minutes.txt'
IESG_MINUTES_URL = 'https://www6.ietf.org/iesg/internal/minutes.txt'
IESG_WG_EVALUATION_DIR = "/a/www/www6/iesg/evaluation"
# Move drafts to this directory when they expire
INTERNET_DRAFT_ARCHIVE_DIR = '/a/ietfdata/doc/draft/collection/draft-archive/'
# The following directory contains linked copies of all drafts, but don't
# write anything to this directory -- its content is maintained by ghostlinkd:
INTERNET_ALL_DRAFTS_ARCHIVE_DIR = '/a/ietfdata/doc/draft/archive'
MEETING_RECORDINGS_DIR = '/a/www/audio'

DOCUMENT_FORMAT_WHITELIST = ["txt", "ps", "pdf", "xml", "html", ]

# Mailing list info URL for lists hosted on the IETF servers
MAILING_LIST_INFO_URL = "https://www.ietf.org/mailman/listinfo/%(list_addr)s"
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
    "rfc":      "https://www.rfc-editor.org/rfc/rfc{doc.rfcnum}.txt",
    "slides": "https://www.ietf.org/slides/{doc.name}-{doc.rev}",
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

# The default with no CACHES setting is 'django.core.cache.backends.locmem.LocMemCache'
# This setting is possibly overridden further down, after the import of settings_local
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.memcached.MemcachedCache',
        'LOCATION': '127.0.0.1:11211',
        'VERSION': __version__,
        'KEY_PREFIX': 'ietf:dt',
    },
    'sessions': {
        'BACKEND': 'django.core.cache.backends.memcached.MemcachedCache',
        'LOCATION': '127.0.0.1:11211',
        # No release-specific VERSION setting.
        'KEY_PREFIX': 'ietf:dt',
    },
    'htmlized': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': '/a/cache/datatracker/htmlized',
        'OPTIONS': {
            'MAX_ENTRIES': 100000,      # 100,000
        },
    },
    'slowpages': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': '/a/cache/datatracker/slowpages',
        'OPTIONS': {
            'MAX_ENTRIES': 5000,
        },
    },
}

HTMLIZER_VERSION = 1
HTMLIZER_URL_PREFIX = "/doc/html"
HTMLIZER_CACHE_TIME = 60*60*24*14       # 14 days

# Email settings
IPR_EMAIL_FROM = 'ietf-ipr@ietf.org'
AUDIO_IMPORT_EMAIL = ['ietf@meetecho.com']
IANA_EVAL_EMAIL = "drafts-eval@icann.org"
SESSION_REQUEST_FROM_EMAIL = 'IETF Meeting Session Request Tool <session-request@ietf.org>' 

SECRETARIAT_SUPPORT_EMAIL = "support@ietf.org"
SECRETARIAT_ACTION_EMAIL = "ietf-action@ietf.org"
SECRETARIAT_INFO_EMAIL = "ietf-info@ietf.org"

# Put real password in settings_local.py
IANA_SYNC_PASSWORD = "secret"
IANA_SYNC_CHANGES_URL = "https://datatracker.iana.org:4443/data-tracker/changes"
IANA_SYNC_PROTOCOLS_URL = "https://www.iana.org/protocols/"

RFC_TEXT_RSYNC_SOURCE="ftp.rfc-editor.org::rfcs-text-only"

RFC_EDITOR_SYNC_PASSWORD="secret"
RFC_EDITOR_SYNC_NOTIFICATION_URL = "https://www.rfc-editor.org/parser/parser.php"
RFC_EDITOR_GROUP_NOTIFICATION_EMAIL = "webmaster@rfc-editor.org"
#RFC_EDITOR_GROUP_NOTIFICATION_URL = "https://www.rfc-editor.org/notification/group.php"
RFC_EDITOR_QUEUE_URL = "https://www.rfc-editor.org/queue2.xml"
RFC_EDITOR_INDEX_URL = "https://www.rfc-editor.org/rfc/rfc-index.xml"
RFC_EDITOR_ERRATA_JSON_URL = "https://www.rfc-editor.org/errata.json"
RFC_EDITOR_ERRATA_URL = "https://www.rfc-editor.org/errata_search.php?rfc={rfc_number}&amp;rec_status=0"
RFC_EDITOR_INLINE_ERRATA_URL = "https://www.rfc-editor.org/rfc/inline-errata/rfc{rfc_number}.html"
RFC_EDITOR_INFO_BASE_URL = "https://www.rfc-editor.org/info/"

# NomCom Tool settings
ROLODEX_URL = ""
NOMCOM_PUBLIC_KEYS_DIR = '/a/www/nomcom/public_keys/'
NOMCOM_FROM_EMAIL = 'nomcom-chair-{year}@ietf.org'
OPENSSL_COMMAND = '/usr/bin/openssl'
DAYS_TO_EXPIRE_NOMINATION_LINK = ''
NOMINEE_FEEDBACK_TYPES = ['comment', 'questio', 'nomina']

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


IDSUBMIT_MANUAL_STAGING_DIR = '/tmp/'

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

XML_LIBRARY = "/www/tools.ietf.org/tools/xml2rfc/web/public/rfc/"

# === Meeting Related Settings =================================================

MEETING_MATERIALS_SERVE_LOCALLY = True

# If you override MEETING_MATERIALS_SERVE_LOCALLY in your settings_local.conf, you will need to
# set the right value for MEETING_DOC_HREFS there as well. MEETING_DOC_LOCAL_HREFS and 
# CDN_MEETING_DOC_HREFS are defined here to make that simpler.

MEETING_DOC_LOCAL_HREFS = {
    "agenda": "/meeting/{meeting.number}/materials/{doc.name}-{doc.rev}",
    "minutes": "/meeting/{meeting.number}/materials/{doc.name}-{doc.rev}",
    "slides": "/meeting/{meeting.number}/materials/{doc.name}-{doc.rev}",
    "recording": "{doc.external_url}",
    "bluesheets": "https://www.ietf.org/proceedings/{meeting.number}/bluesheets/{doc.uploaded_filename}",
}

MEETING_DOC_CDN_HREFS = {
    "agenda": "https://www.ietf.org/proceedings/{meeting.number}/agenda/{doc.name}-{doc.rev}",
    "minutes": "https://www.ietf.org/proceedings/{meeting.number}/minutes/{doc.name}-{doc.rev}",
    "slides": "https://www.ietf.org/proceedings/{meeting.number}/slides/{doc.name}-{doc.rev}",
    "recording": "{doc.external_url}",
    "bluesheets": "https://www.ietf.org/proceedings/{meeting.number}/bluesheets/{doc.uploaded_filename}",
}

MEETING_DOC_HREFS = MEETING_DOC_LOCAL_HREFS if MEETING_MATERIALS_SERVE_LOCALLY else MEETING_DOC_CDN_HREFS

MEETING_DOC_OLD_HREFS = {
    "agenda": "/meeting/{meeting.number}/materials/{doc.name}",
    "minutes": "/meeting/{meeting.number}/materials/{doc.name}",
    "slides": "/meeting/{meeting.number}/materials/{doc.name}",
    "recording": "{doc.external_url}",
    "bluesheets": "https://www.ietf.org/proceedings/{meeting.number}/bluesheets/{doc.uploaded_filename}",
}

# For http references to documents without a version number (that is, to the current version at the time of reference)
MEETING_DOC_GREFS = {
    "agenda": "/meeting/{meeting.number}/materials/{doc.name}",
    "minutes": "/meeting/{meeting.number}/materials/{doc.name}",
    "slides": "/meeting/{meeting.number}/materials/{doc.name}",
    "recording": "{doc.external_url}",
    "bluesheets": "https://www.ietf.org/proceedings/{meeting.number}/bluesheets/{doc.uploaded_filename}",
}

MEETING_MATERIALS_DEFAULT_SUBMISSION_START_DAYS = 90
MEETING_MATERIALS_DEFAULT_SUBMISSION_CUTOFF_DAYS = 26
MEETING_MATERIALS_DEFAULT_SUBMISSION_CORRECTION_DAYS = 50

MEETING_VALID_UPLOAD_EXTENSIONS = {
    'agenda':       ['.txt','.html','.htm', '.md', ],
    'minutes':      ['.txt','.html','.htm', '.md', '.pdf', ],
    'slides':       ['.doc','.docx','.pdf','.ppt','.pptx','.txt', ], # Note the removal of .zip
    'bluesheets':   ['.pdf', '.txt', ],
}
    
MEETING_VALID_UPLOAD_MIME_TYPES = {
    'agenda':       ['text/plain', 'text/html', 'text/markdown', 'text/x-markdown', ],
    'minutes':      ['text/plain', 'text/html', 'application/pdf', 'text/markdown', 'text/x-markdown', ],
    'slides':       [],
    'bluesheets':   ['application/pdf', 'text/plain', ],
}

MEETING_VALID_MIME_TYPE_EXTENSIONS = {
    'text/plain':   ['.txt', '.md', ],
    'text/markdown': ['.txt', '.md', ],
    'text/x-markdown': ['.txt', '.md', ],
    'text/html':    ['.html', '.htm'],
    'application/pdf': ['.pdf'],
}

MEETING_VALID_UPLOAD_MIME_FOR_OBSERVED_MIME = {
    'text/plain':   ['text/plain', 'text/markdown', 'text/x-markdown', ],
    'text/html':    ['text/html', ],
    'application/pdf': ['application/pdf', ],
}

INTERNET_DRAFT_DAYS_TO_EXPIRE = 185

FLOORPLAN_MEDIA_DIR = 'floor'
FLOORPLAN_DIR = os.path.join(MEDIA_ROOT, FLOORPLAN_MEDIA_DIR)

MEETING_USES_CODIMD_DATE = datetime.date(2020,7,6)

# === OpenID Connect Provide Related Settings ==================================

# Used by django-oidc-provider
LOGIN_URL = '/accounts/login/'
OIDC_USERINFO = 'ietf.ietfauth.utils.openid_userinfo'
OIDC_EXTRA_SCOPE_CLAIMS = 'ietf.ietfauth.utils.OidcExtraScopeClaims'

# ==============================================================================


DOT_BINARY = '/usr/bin/dot'
UNFLATTEN_BINARY= '/usr/bin/unflatten'
RSYNC_BINARY = '/usr/bin/rsync'
YANGLINT_BINARY = '/usr/bin/yanglint'

# Account settings
DAYS_TO_EXPIRE_REGISTRATION_LINK = 3
HTPASSWD_COMMAND = "/usr/bin/htpasswd"
HTPASSWD_FILE = "/www/htpasswd"

# Generation of pdf files
GHOSTSCRIPT_COMMAND = "/usr/bin/gs"

# Generation of bibxml files for xml2rfc
BIBXML_BASE_PATH = '/a/www/ietf-ftp/xml2rfc'

# Timezone files for iCalendar
TZDATA_ICS_PATH = BASE_DIR + '/../vzic/zoneinfo/'
CHANGELOG_PATH =  BASE_DIR + '/../changelog'

SECR_BLUE_SHEET_PATH = '/a/www/ietf-datatracker/documents/blue_sheet.rtf'
SECR_BLUE_SHEET_URL = '//datatracker.ietf.org/documents/blue_sheet.rtf'
SECR_INTERIM_LISTING_DIR = '/a/www/www6/meeting/interim'
SECR_MAX_UPLOAD_SIZE = 40960000
SECR_PROCEEDINGS_DIR = '/a/www/www6s/proceedings/'
SECR_PPT2PDF_COMMAND = ['/usr/bin/soffice','--headless','--convert-to','pdf:writer_globaldocument_pdf_Export','--outdir']
SECR_VIRTUAL_MEETINGS = ['108']
STATS_REGISTRATION_ATTENDEES_JSON_URL = 'https://registration.ietf.org/{number}/attendees/'
NEW_PROCEEDINGS_START = 95
YOUTUBE_API_KEY = ''
YOUTUBE_API_SERVICE_NAME = 'youtube'
YOUTUBE_API_VERSION = 'v3'
YOUTUBE_BASE_URL = 'https://www.youtube.com/watch'
YOUTUBE_IETF_CHANNEL_ID = 'UC8dtK9njBLdFnBahHFp0eZQ'

PRODUCTION_TIMEZONE = "America/Los_Angeles"

PYFLAKES_DEFAULT_ARGS= ["ietf", ]
VULTURE_DEFAULT_ARGS= ["ietf", ]

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
DEV_MIDDLEWARE = ()

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

# Path to the email alias lists.  Used by ietf.utils.aliases
DRAFT_ALIASES_PATH = os.path.join(TEST_DATA_DIR, "draft-aliases")
DRAFT_VIRTUAL_PATH = os.path.join(TEST_DATA_DIR, "draft-virtual")
DRAFT_VIRTUAL_DOMAIN = "virtual.ietf.org"

GROUP_ALIASES_PATH = os.path.join(TEST_DATA_DIR, "group-aliases")
GROUP_VIRTUAL_PATH = os.path.join(TEST_DATA_DIR, "group-virtual")
GROUP_VIRTUAL_DOMAIN = "virtual.ietf.org"

POSTCONFIRM_PATH   = "/a/postconfirm/wrapper"

USER_PREFERENCE_DEFAULTS = {
    "expires_soon"  : "14",
    "new_enough"    : "14",
    "full_draft"    : "on",
    "left_menu"     : "off",
}

TRAC_MASTER_DIR = "/a/www/trac-setup/"
TRAC_WIKI_DIR_PATTERN = "/a/www/www6s/trac/%s"
TRAC_WIKI_URL_PATTERN = "https://trac.ietf.org/trac/%s/wiki"
TRAC_ISSUE_URL_PATTERN = "https://trac.ietf.org/trac/%s/report/1"
TRAC_SVN_DIR_PATTERN = "/a/svn/group/%s"
#TRAC_SVN_URL_PATTERN = "https://svn.ietf.org/svn/group/%s/"

# The group types setting was replaced by a group feature entry 10 Jan 2019
#TRAC_CREATE_GROUP_TYPES = ['wg', 'rg', 'area', 'team', 'dir', 'review', 'ag', 'nomcom', ]
TRAC_CREATE_GROUP_STATES = ['bof', 'active', ]
TRAC_CREATE_GROUP_ACRONYMS = ['iesg', 'iaoc', 'ietf', ]

# This is overridden in production's settings-local.  Make sure to update it.
TRAC_CREATE_ADHOC_WIKIS = [
    # admin group acronym, name, sub-path
    # A trailing fileglob wildcard is supported on group acronyms
    ('iesg', 'Meeting', "ietf/meeting"),
    ('nomcom*', 'NomCom', 'nomcom'),
]

SVN_PACKAGES = [
    "/usr/lib/python/dist-packages/svn",
    "/usr/lib/python3.6/dist-packages/libsvn",
]

TRAC_ENV_OPTIONS = [
    ('project', 'name', "{name} Wiki"),
    ('trac', 'database', 'sqlite:db/trac.db' ),
    ('trac', 'repository_type', 'svn'),
    ('trac', 'repository_dir', "{svn_dir}"),
    ('inherit', 'file', "/a/www/trac-setup/conf/trac.ini"),
    ('components', 'tracopt.versioncontrol.svn.*', 'enabled'),
]

TRAC_WIKI_PAGES_TEMPLATES = [
    "utils/wiki/IetfSpecificFeatures",
    "utils/wiki/InterMapTxt",
    "utils/wiki/SvnTracHooks",
    "utils/wiki/ThisTracInstallation",
    "utils/wiki/TrainingMaterials",
    "utils/wiki/WikiStart",
]

TRAC_ISSUE_SEVERITY_ADD = [
    "-",
    "Candidate WG Document",
    "Active WG Document",
    "Waiting for Expert Review",
    "In WG Last Call",
    "Waiting for Shepherd Writeup",
    "Submitted WG Document",
    "Dead WG Document",
]

SVN_ADMIN_COMMAND = "/usr/bin/svnadmin"

# Email addresses people attempt to set for their account will be checked
# against the following list of regex expressions with re.search(pat, addr):
EXCLUDED_PERSONAL_EMAIL_REGEX_PATTERNS = [
    "@ietf.org$",
]

MARKUP_SETTINGS = {
    'restructuredtext': {
        'settings_overrides': {
            'initial_header_level': 3,
            'doctitle_xform': False,
            'footnote_references': 'superscript',
            'trim_footnote_reference_space': True,
            'default_reference_context': 'view',
            'link_base': ''
        }
    }
}

MAILMAN_LIB_DIR = '/usr/lib/mailman'

# This is the number of seconds required between subscribing to an ietf
# mailing list and datatracker account creation being accepted
LIST_ACCOUNT_DELAY = 60*60*25           # 25 hours
ACCOUNT_REQUEST_EMAIL = 'account-request@ietf.org'


SILENCED_SYSTEM_CHECKS = [
    "fields.W342",  # Setting unique=True on a ForeignKey has the same effect as using a OneToOneField.
]

CHECKS_LIBRARY_PATCHES_TO_APPLY = [
    'patch/fix-unidecode-argument-warning.patch',
    'patch/change-oidc-provider-field-sizes-228.patch',
    'patch/fix-oidc-access-token-post.patch',
    'patch/fix-jwkest-jwt-logging.patch',
    'patch/fix-oic-logging.patch',
    'patch/fix-django-password-strength-kwargs.patch',
    'patch/add-django-http-cookie-value-none.patch',
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

# Put the production SECRET_KEY in settings_local.py, and also any other
# sensitive or site-specific changes.  DO NOT commit settings_local.py to svn.
from ietf.settings_local import *            # pyflakes:ignore pylint: disable=wildcard-import

for app in INSTALLED_APPS:
    if app.startswith('ietf'):
        app_settings_file = os.path.join(BASE_DIR, '../', app.replace('.', os.sep), "settings.py")
        if os.path.exists(app_settings_file):
            exec("from %s import *" % (app+".settings"))

# Add DEV_APPS to INSTALLED_APPS
INSTALLED_APPS += DEV_APPS
MIDDLEWARE += DEV_MIDDLEWARE
TEMPLATES[0]['OPTIONS']['context_processors'] += DEV_TEMPLATE_CONTEXT_PROCESSORS


# We provide a secret key only for test and development modes.  It's
# absolutely vital that django fails to start in production mode unless a
# secret key has been provided elsewhere, not in this file which is
# publicly available, for instance from the source repository.
if SERVER_MODE != 'production':
    # stomp out the cached template loader, it's annoying
    loaders = TEMPLATES[0]['OPTIONS']['loaders']
    loaders = tuple(l for e in loaders for l in (e[1] if isinstance(e, tuple) and "cached.Loader" in e[0] else (e,)))
    TEMPLATES[0]['OPTIONS']['loaders'] = loaders

    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
            #'BACKEND': 'django.core.cache.backends.memcached.MemcachedCache',
            #'LOCATION': '127.0.0.1:11211',
            #'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
            'VERSION': __version__,
            'KEY_PREFIX': 'ietf:dt',
        },
        'sessions': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        },
        'htmlized': {
            'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
            #'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
            'LOCATION': '/var/cache/datatracker/htmlized',
            'OPTIONS': {
                'MAX_ENTRIES': 1000,
            },
        },
        'slowpages': {
            'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
            #'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
            'LOCATION': '/var/cache/datatracker/',
            'OPTIONS': {
                'MAX_ENTRIES': 5000,
            },
        },
    }
    SESSION_ENGINE = "django.contrib.sessions.backends.db"

    if 'SECRET_KEY' not in locals():
        SECRET_KEY = 'PDwXboUq!=hPjnrtG2=ge#N$Dwy+wn@uivrugwpic8mxyPfHka'

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
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_SAMESITE = 'Lax'
    