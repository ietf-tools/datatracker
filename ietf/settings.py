# Copyright The IETF Trust 2007, All Rights Reserved

# Django settings for ietf project.
# BASE_DIR and "settings_local" are from
# http://code.djangoproject.com/wiki/SplitSettings

import os
import syslog
syslog.openlog("django", syslog.LOG_PID, syslog.LOG_LOCAL0)


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DEBUG = True
TEMPLATE_DEBUG = DEBUG

# Domain name of the IETF
IETF_DOMAIN = 'ietf.org'

ADMINS = (
    ('IETF Django Developers', 'django-project@' + IETF_DOMAIN),
    ('GMail Tracker Archive', 'ietf.tracker.archive+errors@gmail.com'),
    ('Henrik Levkowetz', 'henrik@levkowetz.com'),
)

# Server name of the tools server
TOOLS_SERVER = 'tools.' + IETF_DOMAIN

# Override this in the settings_local.py file:
SERVER_EMAIL = 'Django Server <django-project@' + TOOLS_SERVER + '>'

DEFAULT_FROM_EMAIL = 'IETF Secretariat <ietf-secretariat-reply@' + IETF_DOMAIN + '>'

MANAGERS = ADMINS

DATABASE_ENGINE = 'mysql'      # 'postgresql_psycopg2', 'postgresql', 'mysql', 'sqlite3' or 'ado_mssql'.
DATABASE_NAME = 'ietf'         # Or path to database file if using sqlite3.
DATABASE_USER = 'ietf'       # Not used with sqlite3.
#DATABASE_PASSWORD = 'ietf' # Not used with sqlite3.
DATABASE_PORT = ''             # Set to empty string for default. Not used with sqlite3.
DATABASE_HOST = ''             # Set to empty string for localhost. Not used with sqlite3.

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

# Absolute path to the directory that holds media.
# Example: "/home/media/media.lawrence.com/"
MEDIA_ROOT = BASE_DIR + "/../static/"

# URL that handles the media served from MEDIA_ROOT.
# Example: "http://media.lawrence.com"
MEDIA_URL = ''

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
ADMIN_MEDIA_PREFIX = '/media/'

AUTH_PROFILE_MODULE = 'ietfauth.IetfUserProfile'
AUTHENTICATION_BACKENDS = ( "ietf.ietfauth.auth.IetfUserBackend", )
SESSION_COOKIE_AGE = 43200 # 12 hours
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.load_template_source',
    'django.template.loaders.app_directories.load_template_source',
#     'django.template.loaders.eggs.load_template_source',
)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.auth.middleware.RemoteUserMiddleware',
    'django.middleware.doc.XViewMiddleware',
#    'ietf.middleware.PrettifyMiddleware',
    'ietf.middleware.SQLLogMiddleware',
    'ietf.middleware.SMTPExceptionMiddleware',
    'ietf.middleware.RedirectTrailingPeriod',
    'django.middleware.transaction.TransactionMiddleware',
#    'django.middleware.cache.CacheMiddleware',
)

ROOT_URLCONF = 'ietf.urls'

TEMPLATE_DIRS = (
    # Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
    BASE_DIR + "/templates"
)

TEMPLATE_CONTEXT_PROCESSORS = (
    'django.core.context_processors.auth',
    'django.core.context_processors.debug',
    'django.core.context_processors.i18n',
    'django.core.context_processors.request',
    'ietf.context_processors.server_mode',
    'ietf.context_processors.revision_info'
)

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.sitemaps',
    'django.contrib.admin',
    'django.contrib.humanize',
    'ietf.announcements',
    'ietf.idindex',
    'ietf.idtracker',
    'ietf.ietfauth',
    'ietf.iesg',
    'ietf.ipr',
    'ietf.liaisons',
    'ietf.mailinglists',
    'ietf.meeting',
    'ietf.proceedings',
    'ietf.redirects',
    'ietf.idrfc',
    'ietf.wginfo',
)

INTERNAL_IPS = (
# AMS servers
	'64.170.98.32',
	'64.170.98.86',

# local
        '127.0.0.1',
        '::1',
)

# Valid values:
# 'production', 'test', 'development'
# Override this in settings_local.py if it's not true
SERVER_MODE = 'development'

# The name of the method to use to invoke the test suite
TEST_RUNNER = 'ietf.utils.test_runner.run_tests'

# Override this in settings_local.py if needed
# *_PATH variables ends with a slash/ .
INTERNET_DRAFT_PATH = '/a/www/ietf-ftp/internet-drafts/'
RFC_PATH = '/a/www/ietf-ftp/rfc/'
AGENDA_PATH = '/a/www/www6s/proceedings/'
IPR_DOCUMENT_PATH = '/a/www/ietf-ftp/ietf/IPR/'
# Path to Work Group Description Text Files
IETFWG_DESCRIPTIONS_PATH = '/a/www/www6s/wg-descriptions/'
IESG_TASK_FILE = '/a/www/www6/iesg/internal/task.txt'
IESG_ROLL_CALL_FILE = '/a/www/www6/iesg/internal/rollcall.txt'
IESG_MINUTES_FILE = '/a/www/www6/iesg/internal/minutes.txt'

# External page top and bottom, which gives a html page the current menubar
# and footer used in the current web-page design
EXTERNAL_PAGE_TOP = '/a/www/www6s/scripts/templates/top-page'
EXTERNAL_PAGE_BOT = '/a/www/www6s/scripts/templates/bottom-page'

# Override this in settings_local.py if needed
CACHE_MIDDLEWARE_SECONDS = 300
CACHE_MIDDLEWARE_KEY_PREFIX = ''
if SERVER_MODE == 'production':
    CACHE_BACKEND= 'file://'+'/a/www/ietf-datatracker/cache/'
else:
    # Default to no caching in development/test, so that every developer
    # doesn't have to set CACHE_BACKEND in settings_local
    CACHE_BACKEND = 'dummy:///'

IPR_EMAIL_TO = ['ietf-ipr@ietf.org', ]

# Put SECRET_KEY in here, or any other sensitive or site-specific
# changes.  DO NOT commit settings_local.py to svn.
from settings_local import *

