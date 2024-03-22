# Copyright The IETF Trust 2007-2024, All Rights Reserved
# -*- coding: utf-8 -*-

from base64 import b64decode
from email.utils import parseaddr

from ietf import __release_hash__
from ietf.settings import *                                          # pyflakes:ignore

USE_TZ = True

# Secrets

SECRET_KEY = os.environ.get("DATATRACKER_DJANGO_SECRET_KEY")
NOMCOM_APP_SECRET = b64decode(os.environ.get("DATATRACKER_NOMCOM_APP_SECRET_B64")) 
IANA_SYNC_PASSWORD = os.environ.get("DATATRACKER_IANA_SYNC_PASSWORD")
RFC_EDITOR_SYNC_PASSWORD = os.environ.get("DATATRACKER_RFC_EDITOR_SYNC_PASSWORD")
YOUTUBE_API_KEY = os.environ.get("DATATRACKER_YOUTUBE_API_KEY")
GITHUB_BACKUP_API_KEY = os.environ.get("DATATRACKER_GITHUB_BACKUP_API_KEY")

API_KEY_TYPE = os.environ.get("DATATRACKER_API_KEY_TYPE", "ES265")
API_PUBLIC_KEY_PEM = b64decode(os.environ.get("DATATRACKER_API_PUBLIC_KEY_PEM_B64"))
API_PRIVATEC_KEY_PEM = b64decode(os.environ.get("DATATRACKER_API_PRIVATE_KEY_PEM_B64"))

SERVER_MODE = os.environ.get("DATATRACKER_SERVER_MODE", "development")  # todo decide if we need a "staging" mode

DEBUG = os.environ.get("DATATRACKER_DEBUG", "false").lower() == "true"

allowed_hosts_env = os.environ.get("DATATRACKER_ALLOWED_HOSTS", None)
if allowed_hosts_env is not None:
    ALLOWED_HOSTS = [h.strip() for h in allowed_hosts_env.split(",")]

DATABASES = {
    "default": {
        "HOST": os.environ.get("DATATRACKER_DBHOST", "db"),
        "PORT": os.environ.get("DATATRACKER_DBPORT", "5432"),
        "NAME": os.environ.get("DATATRACKER_DBNAME", "datatracker"),
        "ENGINE": "django.db.backends.postgresql",
        "USER": os.environ.get("DATATRACKER_DBUSER", "django"),
        "PASSWORD": os.environ.get("DATATRACKER_DBPASS", ""),
    },
}

ADMINS = [parseaddr(admin) for admin in os.environ.get("DATATRACKER_ADMINS").split("\n")]

USING_DEBUG_EMAIL_SERVER = os.environ.get("DATATRACKER_EMAIL_DEBUG", "false").lower() == "true"
EMAIL_HOST = os.environ.get("DATATRACKER_EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("DATATRACKER_EMAIL_PORT", "2025"))

CELERY_BROKER_URL = "amqp://datatracker:{password}@{host}/{queue}".format(
    host=os.environ.get("RABBITMQ_HOSTNAME", "rabbitmq"),
    password=os.environ.get("CELERY_PASSWORD", ""),
    queue=os.environ.get("RABBITMQ_QUEUE", "dt")
)

IANA_SYNC_USERNAME = "ietfsync"
IANA_SYNC_CHANGES_URL = "https://datatracker.iana.org:4443/data-tracker/changes"
IANA_SYNC_PROTOCOLS_URL = "http://www.iana.org/protocols/"

RFC_EDITOR_NOTIFICATION_URL = "http://www.rfc-editor.org/parser/parser.php"

STATS_REGISTRATION_ATTENDEES_JSON_URL = 'https://registration.ietf.org/{number}/attendees/?apikey=redacted'

#FIRST_CUTOFF_DAYS = 12
#SECOND_CUTOFF_DAYS = 12
#SUBMISSION_CUTOFF_DAYS = 26
#SUBMISSION_CORRECTION_DAYS = 57
MEETING_MATERIALS_SUBMISSION_CUTOFF_DAYS = 26
MEETING_MATERIALS_SUBMISSION_CORRECTION_DAYS = 54

HTPASSWD_COMMAND = "/usr/bin/htpasswd2"

MEETECHO_API_CONFIG = {
    "api_base": os.environ.get(
        "DATATRACKER_MEETECHO_API_BASE", 
        "https://meetings.conf.meetecho.com/api/v1/",
    ),
    "client_id": os.environ.get("DATATRACKER_MEETECHO_CLIENT_ID"),
    "client_secret": os.environ.get("DATATRACKER_MEETECHO_CLIENT_SECRET"),
    "request_timeout": 3.01,  # python-requests doc recommend slightly > a multiple of 3 seconds
}

APP_API_TOKENS = {
    "ietf.api.views.directauth": ["redacted",],
    "ietf.api.views.email_aliases": ["redacted"],
    "ietf.api.views.active_email_list": ["redacted"],
}

EMAIL_COPY_TO = ''

# Until we teach the datatracker to look beyond cloudflare for this check
IDSUBMIT_MAX_DAILY_SAME_SUBMITTER = 5000

if "DATATRACKER_MATOMO_SITE_ID" in os.environ:
    MATOMO_DOMAIN_PATH = os.environ.get("DATATRACKER_MATOMO_DOMAIN_PATH", "analytics.ietf.org")
    MATOMO_SITE_ID = os.environ.get("DATATRACKER_MATOMO_SITE_ID")
    MATOMO_DISABLE_COOKIES = True

if "DATATRACKER_SCOUT_KEY" in os.environ:
    if SERVER_MODE == "production":
        PROD_PRE_APPS = ["scout_apm.django", ]
    else:
        DEV_PRE_APPS = ["scout_apm.django", ]
    SCOUT_MONITOR = True
    SCOUT_KEY = os.environ.get("DATATRACKER_SCOUT_KEY")
    SCOUT_NAME = "Datatracker"
    SCOUT_ERRORS_ENABLED = True
    SCOUT_SHUTDOWN_MESSAGE_ENABLED = False
    SCOUT_CORE_AGENT_DIR = "/a/core-agent/1.4.0"
    SCOUT_CORE_AGENT_FULL_NAME = "scout_apm_core-v1.4.0-x86_64-unknown-linux-musl"
    SCOUT_CORE_AGENT_SOCKET_PATH = "tcp://{host}:{port}".format(
        host=os.environ.get("DATATRACKER_SCOUT_CORE_AGENT_HOST", "scout"),
        port=os.environ.get("DATATRACKER_SCOUT_CORE_AGENT_PORT", "16590"),
    ),
    SCOUT_CORE_AGENT_DOWNLOAD = False
    SCOUT_CORE_AGENT_LAUNCH = False
    SCOUT_REVISION_SHA = __release_hash__[:7]

## Paths from production settings_local --jlr

AGENDA_PATH = "/a/www/www6s/proceedings/"

# Path to the email alias lists.  Used by ietf.utils.aliases
DRAFT_ALIASES_PATH = "/a/postfix/draft-aliases"
DRAFT_VIRTUAL_PATH = "/a/postfix/draft-virtual"
GROUP_ALIASES_PATH = "/a/postfix/group-aliases"
GROUP_VIRTUAL_PATH = "/a/postfix/group-virtual"

NOMCOM_PUBLIC_KEYS_DIR = "/a/www/nomcom/public_keys/"

MEDIA_ROOT = "/a/www/www6s/lib/dt/media/"
MEDIA_URL  = "https://www.ietf.org/lib/dt/media/"
PHOTOS_DIRNAME = "photo"
PHOTOS_DIR = MEDIA_ROOT + PHOTOS_DIRNAME

# Normally only set for debug, but needed until we have a real FS
DJANGO_VITE_MANIFEST_PATH = os.path.join(BASE_DIR, 'static/dist-neue/manifest.json')


## below here is from dev settings_local --jlr
# IDSUBMIT_IDNITS_BINARY = "/usr/local/bin/idnits"
# IDSUBMIT_REPOSITORY_PATH = "/test/id/"
# IDSUBMIT_STAGING_PATH = "/test/staging/"
# 
# AGENDA_PATH = "/assets/www6s/proceedings/"
# MEETINGHOST_LOGO_PATH = AGENDA_PATH
# 
# MEDIA_BASE_DIR = "/assets"
# MEDIA_ROOT = MEDIA_BASE_DIR + "/media/"
# MEDIA_URL = "/media/"
# 
# PHOTOS_DIRNAME = "photo"
# PHOTOS_DIR = MEDIA_ROOT + PHOTOS_DIRNAME
# 
# SUBMIT_YANG_CATALOG_MODEL_DIR = "/assets/ietf-ftp/yang/catalogmod/"
# SUBMIT_YANG_DRAFT_MODEL_DIR = "/assets/ietf-ftp/yang/draftmod/"
# SUBMIT_YANG_INVAL_MODEL_DIR = "/assets/ietf-ftp/yang/invalmod/"
# SUBMIT_YANG_IANA_MODEL_DIR = "/assets/ietf-ftp/yang/ianamod/"
# SUBMIT_YANG_RFC_MODEL_DIR = "/assets/ietf-ftp/yang/rfcmod/"
# 
# # Set INTERNAL_IPS for use within Docker. See https://knasmueller.net/fix-djangos-debug-toolbar-not-showing-inside-docker
# import socket
# hostname, _, ips = socket.gethostbyname_ex(socket.gethostname())
# INTERNAL_IPS = [".".join(ip.split(".")[:-1] + ["1"]) for ip in ips]
# 
# # DEV_TEMPLATE_CONTEXT_PROCESSORS = [
# #    'ietf.context_processors.sql_debug',
# # ]
# 
# DOCUMENT_PATH_PATTERN = "/assets/ietfdata/doc/{doc.type_id}/"
# INTERNET_DRAFT_PATH = "/assets/ietf-ftp/internet-drafts/"
# RFC_PATH = "/assets/ietf-ftp/rfc/"
# CHARTER_PATH = "/assets/ietf-ftp/charter/"
# BOFREQ_PATH = "/assets/ietf-ftp/bofreq/"
# CONFLICT_REVIEW_PATH = "/assets/ietf-ftp/conflict-reviews/"
# STATUS_CHANGE_PATH = "/assets/ietf-ftp/status-changes/"
# INTERNET_DRAFT_ARCHIVE_DIR = "/assets/archive/id"
# INTERNET_ALL_DRAFTS_ARCHIVE_DIR = "/assets/archive/id"
# BIBXML_BASE_PATH = "/assets/ietfdata/derived/bibxml"
# IDSUBMIT_REPOSITORY_PATH = INTERNET_DRAFT_PATH
# 
# NOMCOM_PUBLIC_KEYS_DIR = "data/nomcom_keys/public_keys/"
# SLIDE_STAGING_PATH = "/test/staging/"
# 
# DE_GFM_BINARY = "/usr/local/bin/de-gfm"
# 
# # OIDC configuration
# SITE_URL = os.environ.get("OIDC_SITE_URL")
# 
# # todo: parameterize memcached url in settings.py
# MEMCACHED_HOST = os.environ.get("MEMCACHED_SERVICE_HOST", "127.0.0.1")
# MEMCACHED_PORT = os.environ.get("MEMCACHED_SERVICE_PORT", "11211")
# from ietf import __version__
# CACHES = {
#     "default": {
#         "BACKEND": "ietf.utils.cache.LenientMemcacheCache",
#         "LOCATION": f"{MEMCACHED_HOST}:{MEMCACHED_PORT}",
#         "VERSION": __version__,
#         "KEY_PREFIX": "ietf:dt",
#         "KEY_FUNCTION": lambda key, key_prefix, version: (
#             f"{key_prefix}:{version}:{sha384(str(key).encode('utf8')).hexdigest()}"
#         ),
#     },
#     "sessions": {
#         "BACKEND": "ietf.utils.cache.LenientMemcacheCache",
#         "LOCATION": f"{MEMCACHED_HOST}:{MEMCACHED_PORT}",
#         # No release-specific VERSION setting.
#         "KEY_PREFIX": "ietf:dt",
#     },
#     "htmlized": {
#         "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
#         "LOCATION": "/a/cache/datatracker/htmlized",
#         "OPTIONS": {
#             "MAX_ENTRIES": 100000,  # 100,000
#         },
#     },
#     "pdfized": {
#         "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
#         "LOCATION": "/a/cache/datatracker/pdfized",
#         "OPTIONS": {
#             "MAX_ENTRIES": 100000,  # 100,000
#         },
#     },
#     "slowpages": {
#         "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
#         "LOCATION": "/a/cache/datatracker/slowpages",
#         "OPTIONS": {
#             "MAX_ENTRIES": 5000,
#         },
#     },
# }
