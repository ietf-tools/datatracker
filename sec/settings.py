# Feb 24 2012 

# Django settings for sec project.

import os
import syslog
syslog.openlog("django", syslog.LOG_PID, syslog.LOG_LOCAL0)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

#import sys
#sys.path.append(os.path.abspath(BASE_DIR + "/.."))
#sys.path.append(os.path.abspath(BASE_DIR + "/../redesign"))

DEBUG = False

# Domain name of the IETF
IETF_DOMAIN = 'ietf.org'

ADMINS = (
    ('Ryan Cross', 'rcross@amsl.com'),
)

# Server name of the tools server
TOOLS_SERVER = 'tools.' + IETF_DOMAIN

# Override this in the settings_local.py file:
#SERVER_EMAIL = 'Django Server <django-project@' + TOOLS_SERVER + '>'

DEFAULT_FROM_EMAIL = 'IETF Secretariat <ietf-secretariat-reply@' + IETF_DOMAIN + '>'

MANAGERS = ADMINS

# DATABASES defined in settings_local.py
 
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
MEDIA_ROOT = '/a/www/www6s'

# URL that handles the media served from MEDIA_ROOT.
# Example: "http://media.lawrence.com"
MEDIA_URL = 'http://www.ietf.org'

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
ADMIN_MEDIA_PREFIX = '/media/'

#AUTH_PROFILE_MODULE = 'ietfauth.IetfUserProfile'
#AUTHENTICATION_BACKENDS = ( "ietf.ietfauth.auth.IetfUserBackend", )
AUTH_PROFILE_MODULE = 'person.Person'
AUTHENTICATION_BACKENDS = ( 'django.contrib.auth.backends.RemoteUserBackend', )

#DATABASE_ROUTERS = ["ietf.legacy_router.LegacyRouter"]

SESSION_COOKIE_AGE = 43200 # 12 hours
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.load_template_source',
    'django.template.loaders.app_directories.load_template_source',
)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.auth.middleware.RemoteUserMiddleware',
    'django.middleware.doc.XViewMiddleware',
    'ietf.middleware.SQLLogMiddleware',
    'ietf.middleware.SMTPExceptionMiddleware',
    'ietf.middleware.RedirectTrailingPeriod',
    'django.middleware.transaction.TransactionMiddleware',
    'ietf.middleware.UnicodeNfkcNormalization',
    'sec.middleware.secauth.SecAuthMiddleware',
)

ROOT_URLCONF = 'sec.urls'

TEMPLATE_DIRS = (
    BASE_DIR + "/templates",
    "/a/www/ietf-datatracker/web/ietf/templates",
)

TEMPLATE_CONTEXT_PROCESSORS = (
    'django.core.context_processors.auth',
    'django.core.context_processors.debug',
    'django.core.context_processors.i18n',
    'django.core.context_processors.media',
    'django.core.context_processors.request',
    'django.contrib.messages.context_processors.messages',
    'sec.context_processors.server_mode',
    'sec.context_processors.revision_info',
)

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.sitemaps',
    'django.contrib.admin',
    'django.contrib.admindocs',
    'django.contrib.humanize',
    'django.contrib.messages',
    'django.contrib.formtools',
    'south',
    'workflows',
    'permissions',
    #'ietf.issue', #this is bogus leave it out
    'ietf.announcements',
    'ietf.doc',
    'ietf.group',
    'ietf.idindex',
    'ietf.idrfc',
    'ietf.idtracker',
    'ietf.iesg',
    'ietf.ietfauth',
    'ietf.ietfworkflows',
    'ietf.ipr',
    'ietf.liaisons',
    'ietf.mailinglists',
    'ietf.meeting',
    'ietf.message',
    'ietf.name',
    'ietf.person',
    #'ietf.proceedings', # deprecated
    'ietf.redirects',
    'ietf.submit',
    'ietf.wgchairs',
    'ietf.wgcharter',
    'ietf.wginfo',
    # new apps
    'sec.announcement',
    'sec.areas',
    'sec.drafts',
    'sec.groups',
    'sec.ipr',
    'sec.meetings',
    'sec.proceedings',
    'sec.roles',
    'sec.rolodex',
    'sec.sreq',
    'sec.telechat',
    'form_utils',
    'django_extensions',
)

# INTERNAL_IPS undefined in production

# this is a tuple of regular expressions.  if the incoming URL matches one of
# these, than non secretariat access is allowed.
SEC_AUTH_UNRESTRICTED_URLS = (
    (r'^/$'),
    (r'^/announcement/'),
    (r'^/proceedings/'),
    (r'^/sreq/'),
)

# no slash at end
IDTRACKER_BASE_URL = "http://datatracker.ietf.org"

# Valid values:
# 'production', 'test', 'development'
# Override this in settings_local.py if it's not true
SERVER_MODE = 'production'

# WG Chair configuration
MAX_WG_DELEGATES = 3

# Override this in settings_local.py if needed
# *_PATH variables ends with a slash/ .
INTERNET_DRAFT_PATH = '/a/www/ietf-ftp/internet-drafts/'
INTERNET_DRAFT_PDF_PATH = '/a/www/ietf-datatracker/pdf/'
RFC_PATH = '/a/www/ietf-ftp/rfc/'
AGENDA_PATH = '/a/www/www6s/proceedings/'
AGENDA_PATH_PATTERN = '/a/www/www6s/proceedings/%(meeting)s/agenda/%(wg)s.%(ext)s'
MINUTES_PATH_PATTERN = '/a/www/www6s/proceedings/%(meeting)s/minutes/%(wg)s.%(ext)s'
SLIDES_PATH_PATTERN = '/a/www/www6s/proceedings/%(meeting)s/slides/%(wg)s-*'
IPR_DOCUMENT_PATH = '/a/www/ietf-ftp/ietf/IPR/'
IETFWG_DESCRIPTIONS_PATH = '/a/www/www6s/wg-descriptions/'
IESG_TASK_FILE = '/a/www/www6/iesg/internal/task.txt'
IESG_ROLL_CALL_FILE = '/a/www/www6/iesg/internal/rollcall.txt'
IESG_MINUTES_FILE = '/a/www/www6/iesg/internal/minutes.txt'
IESG_WG_EVALUATION_DIR = "/a/www/www6/iesg/evaluation"
INTERNET_DRAFT_ARCHIVE_DIR = '/a/www/www6s/draft-archive'
INTERNET_DRAFT_DAYS_TO_EXPIRE = 185

# Override this in settings_local.py if needed
#CACHE_MIDDLEWARE_SECONDS = 300
#CACHE_MIDDLEWARE_KEY_PREFIX = ''
#if SERVER_MODE == 'production':
#    CACHE_BACKEND= 'file://'+'/a/www/ietf-datatracker/cache/'
#else:
    # Default to no caching in development/test, so that every developer
    # doesn't have to set CACHE_BACKEND in settings_local
#    CACHE_BACKEND = 'dummy:///'

IPR_EMAIL_TO = ['ietf-ipr@ietf.org', ]
DOC_APPROVAL_EMAIL_CC = ["RFC Editor <rfc-editor@rfc-editor.org>", ]

# Liaison Statement Tool settings
LIAISON_UNIVERSAL_FROM = 'Liaison Statement Management Tool <lsmt@' + IETF_DOMAIN + '>'
LIAISON_ATTACH_PATH = '/a/www/ietf-datatracker/documents/LIAISON/'
LIAISON_ATTACH_URL = '/documents/LIAISON/'

# ID Submission Tool settings
IDSUBMIT_FROM_EMAIL = 'IETF I-D Submission Tool <idsubmission@ietf.org>'
IDSUBMIT_TO_EMAIL = 'internet-drafts@ietf.org'
IDSUBMIT_ANNOUNCE_FROM_EMAIL = 'internet-drafts@ietf.org'
IDSUBMIT_ANNOUNCE_LIST_EMAIL = 'i-d-announce@ietf.org'

# Days from meeting to cut off dates on submit
FIRST_CUTOFF_DAYS = 20
SECOND_CUTOFF_DAYS = 13
CUTOFF_HOUR = 17
SUBMISSION_START_DAYS = -90
SUBMISSION_CUTOFF_DAYS = 33
SUBMISSION_CORRECTION_DAYS = 59

IDSUBMIT_REPOSITORY_PATH = INTERNET_DRAFT_PATH
IDSUBMIT_STAGING_PATH = '/a/www/www6s/staging/'
IDSUBMIT_STAGING_URL = 'http://www.ietf.org/staging/'
IDSUBMIT_IDNITS_BINARY = '/a/www/ietf-datatracker/scripts/idnits'

MAX_PLAIN_DRAFT_SIZE = 6291456  # Max size of the txt draft in bytes

# DOS THRESHOLDS PER DAY (Sizes are in MB)
MAX_SAME_DRAFT_NAME = 20
MAX_SAME_DRAFT_NAME_SIZE = 50
MAX_SAME_SUBMITTER = 50
MAX_SAME_SUBMITTER_SIZE = 150
MAX_SAME_WG_DRAFT = 150
MAX_SAME_WG_DRAFT_SIZE = 450
MAX_DAILY_SUBMISSION = 1000
MAX_DAILY_SUBMISSION_SIZE = 2000
# End of ID Submission Tool settings

# DB redesign
USE_DB_REDESIGN_PROXY_CLASSES = True

# no migrations
SOUTH_TESTS_MIGRATE = False

if USE_DB_REDESIGN_PROXY_CLASSES:
    AUTH_PROFILE_MODULE = 'person.Person'
    AUTHENTICATION_BACKENDS = ( 'django.contrib.auth.backends.RemoteUserBackend', )

CHARTER_PATH = '/a/www/ietf-ftp/charters/'
CHARTER_TXT_URL = 'http://www.ietf.org/charters/'

# AMS additions
# for meetings materials upload
MAX_UPLOAD_SIZE = 40960000
PROCEEDINGS_DIR = '/a/www/www6s/proceedings/'
INTERIM_LISTING_DIR = '/a/www/www6/meeting/interim'
GROUP_DESCRIPTION_DIR = '/a/www/www6s/wg-descriptions'
DEVELOPMENT = False
BLUE_SHEET_PATH = '/a/www/ietf-datatracker/documents/blue_sheet.rtf'
BLUE_SHEET_URL = 'https://datatracker.ietf.org/documents/blue_sheet.rtf'

# Put SECRET_KEY in here, or any other sensitive or site-specific
# changes.  DO NOT commit settings_local.py to svn.
from settings_local import *
