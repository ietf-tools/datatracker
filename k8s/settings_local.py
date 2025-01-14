# Copyright The IETF Trust 2007-2024, All Rights Reserved
# -*- coding: utf-8 -*-

from base64 import b64decode
from email.utils import parseaddr
import json

from ietf import __release_hash__
from ietf.settings import *                                          # pyflakes:ignore


def _multiline_to_list(s):
    """Helper to split at newlines and conver to list"""
    return [item.strip() for item in s.split("\n")]


# Default to "development". Production _must_ set DATATRACKER_SERVER_MODE="production" in the env!
SERVER_MODE = os.environ.get("DATATRACKER_SERVER_MODE", "development")

# Use X-Forwarded-Proto to determine request.is_secure(). This relies on CloudFlare overwriting the
# value of the header if an incoming request sets it, which it does:
# https://developers.cloudflare.com/fundamentals/reference/http-request-headers/#x-forwarded-proto
# See also, especially the warnings:
# https://docs.djangoproject.com/en/dev/ref/settings/#secure-proxy-ssl-header
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Secrets
_SECRET_KEY = os.environ.get("DATATRACKER_DJANGO_SECRET_KEY", None)
if _SECRET_KEY is not None:
    SECRET_KEY = _SECRET_KEY
else:
    raise RuntimeError("DATATRACKER_DJANGO_SECRET_KEY must be set")    

_NOMCOM_APP_SECRET_B64 = os.environ.get("DATATRACKER_NOMCOM_APP_SECRET_B64", None)
if _NOMCOM_APP_SECRET_B64 is not None:
    NOMCOM_APP_SECRET = b64decode(_NOMCOM_APP_SECRET_B64)
else:
    raise RuntimeError("DATATRACKER_NOMCOM_APP_SECRET_B64 must be set")

_IANA_SYNC_PASSWORD = os.environ.get("DATATRACKER_IANA_SYNC_PASSWORD", None)
if _IANA_SYNC_PASSWORD is not None:
    IANA_SYNC_PASSWORD = _IANA_SYNC_PASSWORD
else:
    raise RuntimeError("DATATRACKER_IANA_SYNC_PASSWORD must be set")    

_RFC_EDITOR_SYNC_PASSWORD = os.environ.get("DATATRACKER_RFC_EDITOR_SYNC_PASSWORD", None)
if _RFC_EDITOR_SYNC_PASSWORD is not None:
    RFC_EDITOR_SYNC_PASSWORD = os.environ.get("DATATRACKER_RFC_EDITOR_SYNC_PASSWORD")
else:
    raise RuntimeError("DATATRACKER_RFC_EDITOR_SYNC_PASSWORD must be set")

_YOUTUBE_API_KEY = os.environ.get("DATATRACKER_YOUTUBE_API_KEY", None)
if _YOUTUBE_API_KEY is not None:
    YOUTUBE_API_KEY = _YOUTUBE_API_KEY
else:
    raise RuntimeError("DATATRACKER_YOUTUBE_API_KEY must be set")

_GITHUB_BACKUP_API_KEY = os.environ.get("DATATRACKER_GITHUB_BACKUP_API_KEY", None)
if _GITHUB_BACKUP_API_KEY is not None:
    GITHUB_BACKUP_API_KEY = _GITHUB_BACKUP_API_KEY
else:
    raise RuntimeError("DATATRACKER_GITHUB_BACKUP_API_KEY must be set")    

_API_KEY_TYPE = os.environ.get("DATATRACKER_API_KEY_TYPE", None)
if _API_KEY_TYPE is not None:
    API_KEY_TYPE = _API_KEY_TYPE
else:
    raise RuntimeError("DATATRACKER_API_KEY_TYPE must be set")    

_API_PUBLIC_KEY_PEM_B64 = os.environ.get("DATATRACKER_API_PUBLIC_KEY_PEM_B64", None)
if _API_PUBLIC_KEY_PEM_B64 is not None:
    API_PUBLIC_KEY_PEM = b64decode(_API_PUBLIC_KEY_PEM_B64)
else:
    raise RuntimeError("DATATRACKER_API_PUBLIC_KEY_PEM_B64 must be set")    

_API_PRIVATE_KEY_PEM_B64 = os.environ.get("DATATRACKER_API_PRIVATE_KEY_PEM_B64", None)
if _API_PRIVATE_KEY_PEM_B64 is not None:
    API_PRIVATE_KEY_PEM = b64decode(_API_PRIVATE_KEY_PEM_B64)
else:
    raise RuntimeError("DATATRACKER_API_PRIVATE_KEY_PEM_B64 must be set")    

# Set DEBUG if DATATRACKER_DEBUG env var is the word "true"
DEBUG = os.environ.get("DATATRACKER_DEBUG", "false").lower() == "true"

# DATATRACKER_ALLOWED_HOSTS env var is a newline-separated list of allowed hosts
_allowed_hosts_str = os.environ.get("DATATRACKER_ALLOWED_HOSTS", None)
if _allowed_hosts_str is not None:
    ALLOWED_HOSTS = _multiline_to_list(_allowed_hosts_str)

DATABASES = {
    "default": {
        "HOST": os.environ.get("DATATRACKER_DB_HOST", "db"),
        "PORT": os.environ.get("DATATRACKER_DB_PORT", "5432"),
        "NAME": os.environ.get("DATATRACKER_DB_NAME", "datatracker"),
        "ENGINE": "django.db.backends.postgresql",
        "USER": os.environ.get("DATATRACKER_DB_USER", "django"),
        "PASSWORD": os.environ.get("DATATRACKER_DB_PASS", ""),
        "OPTIONS": json.loads(os.environ.get("DATATRACKER_DB_OPTS_JSON", "{}")),
    },
}

# Configure persistent connections. A setting of 0 is Django's default.
_conn_max_age = os.environ.get("DATATRACKER_DB_CONN_MAX_AGE", "0")
# A string "none" means unlimited age.
DATABASES["default"]["CONN_MAX_AGE"] = None if _conn_max_age.lower() == "none" else int(_conn_max_age)
# Enable connection health checks if DATATRACKER_DB_CONN_HEALTH_CHECK is the string "true"
_conn_health_checks = bool(
    os.environ.get("DATATRACKER_DB_CONN_HEALTH_CHECKS", "false").lower() == "true"
)
DATABASES["default"]["CONN_HEALTH_CHECKS"] = _conn_health_checks

# DATATRACKER_ADMINS is a newline-delimited list of addresses parseable by email.utils.parseaddr
_admins_str = os.environ.get("DATATRACKER_ADMINS", None)
if _admins_str is not None:
    ADMINS = [parseaddr(admin) for admin in _multiline_to_list(_admins_str)]
else:
    raise RuntimeError("DATATRACKER_ADMINS must be set")    

USING_DEBUG_EMAIL_SERVER = os.environ.get("DATATRACKER_EMAIL_DEBUG", "false").lower() == "true"
EMAIL_HOST = os.environ.get("DATATRACKER_EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("DATATRACKER_EMAIL_PORT", "2025"))

_celery_password = os.environ.get("CELERY_PASSWORD", None)
if _celery_password is None:
    raise RuntimeError("CELERY_PASSWORD must be set")
CELERY_BROKER_URL = "amqp://datatracker:{password}@{host}/{queue}".format(
    host=os.environ.get("RABBITMQ_HOSTNAME", "dt-rabbitmq"),
    password=_celery_password,
    queue=os.environ.get("RABBITMQ_QUEUE", "dt")
)

IANA_SYNC_USERNAME = "ietfsync"
IANA_SYNC_CHANGES_URL = "https://datatracker.iana.org:4443/data-tracker/changes"
IANA_SYNC_PROTOCOLS_URL = "http://www.iana.org/protocols/"

RFC_EDITOR_NOTIFICATION_URL = "http://www.rfc-editor.org/parser/parser.php"

_registration_api_key = os.environ.get("DATATRACKER_REGISTRATION_API_KEY", None)
if _registration_api_key is None:
    raise RuntimeError("DATATRACKER_REGISTRATION_API_KEY must be set")
STATS_REGISTRATION_ATTENDEES_JSON_URL = f"https://registration.ietf.org/{{number}}/attendees/?apikey={_registration_api_key}"

#FIRST_CUTOFF_DAYS = 12
#SECOND_CUTOFF_DAYS = 12
#SUBMISSION_CUTOFF_DAYS = 26
#SUBMISSION_CORRECTION_DAYS = 57
MEETING_MATERIALS_SUBMISSION_CUTOFF_DAYS = 26
MEETING_MATERIALS_SUBMISSION_CORRECTION_DAYS = 54

# disable htpasswd by setting to a do-nothing command
HTPASSWD_COMMAND = "/bin/true"

_MEETECHO_CLIENT_ID = os.environ.get("DATATRACKER_MEETECHO_CLIENT_ID", None)
_MEETECHO_CLIENT_SECRET = os.environ.get("DATATRACKER_MEETECHO_CLIENT_SECRET", None)
if _MEETECHO_CLIENT_ID is not None and _MEETECHO_CLIENT_SECRET is not None:
    MEETECHO_API_CONFIG = {
        "api_base": os.environ.get(
            "DATATRACKER_MEETECHO_API_BASE", 
            "https://meetings.conf.meetecho.com/api/v1/",
        ),
        "client_id": _MEETECHO_CLIENT_ID,
        "client_secret": _MEETECHO_CLIENT_SECRET,
        "request_timeout": 3.01,  # python-requests doc recommend slightly > a multiple of 3 seconds
    }
else:
    raise RuntimeError(
        "DATATRACKER_MEETECHO_CLIENT_ID and DATATRACKER_MEETECHO_CLIENT_SECRET must be set"
    )

# For APP_API_TOKENS, ccept either base64-encoded JSON or raw JSON, but not both
if "DATATRACKER_APP_API_TOKENS_JSON_B64" in os.environ:
    if "DATATRACKER_APP_API_TOKENS_JSON" in os.environ:
        raise RuntimeError(
            "Only one of DATATRACKER_APP_API_TOKENS_JSON and DATATRACKER_APP_API_TOKENS_JSON_B64 may be set"
        )
    _APP_API_TOKENS_JSON = b64decode(os.environ.get("DATATRACKER_APP_API_TOKENS_JSON_B64"))
else:
    _APP_API_TOKENS_JSON = os.environ.get("DATATRACKER_APP_API_TOKENS_JSON", None)

if _APP_API_TOKENS_JSON is not None:
    APP_API_TOKENS = json.loads(_APP_API_TOKENS_JSON)
else:
    APP_API_TOKENS = {}

EMAIL_COPY_TO = ""

# Until we teach the datatracker to look beyond cloudflare for this check
IDSUBMIT_MAX_DAILY_SAME_SUBMITTER = 5000

# Leave DATATRACKER_MATOMO_SITE_ID unset to disable Matomo reporting
if "DATATRACKER_MATOMO_SITE_ID" in os.environ:
    MATOMO_DOMAIN_PATH = os.environ.get("DATATRACKER_MATOMO_DOMAIN_PATH", "analytics.ietf.org")
    MATOMO_SITE_ID = os.environ.get("DATATRACKER_MATOMO_SITE_ID")
    MATOMO_DISABLE_COOKIES = True

# Leave DATATRACKER_SCOUT_KEY unset to disable Scout APM agent
_SCOUT_KEY = os.environ.get("DATATRACKER_SCOUT_KEY", None)
if _SCOUT_KEY is not None:
    if SERVER_MODE == "production":
        PROD_PRE_APPS = ["scout_apm.django", ]
    else:
        DEV_PRE_APPS = ["scout_apm.django", ]
    SCOUT_MONITOR = True
    SCOUT_KEY = _SCOUT_KEY
    SCOUT_NAME = os.environ.get("DATATRACKER_SCOUT_NAME", "Datatracker")
    SCOUT_ERRORS_ENABLED = True
    SCOUT_SHUTDOWN_MESSAGE_ENABLED = False
    SCOUT_CORE_AGENT_SOCKET_PATH = "tcp://{host}:{port}".format(
        host=os.environ.get("DATATRACKER_SCOUT_CORE_AGENT_HOST", "localhost"),
        port=os.environ.get("DATATRACKER_SCOUT_CORE_AGENT_PORT", "6590"),
    )
    SCOUT_CORE_AGENT_DOWNLOAD = False
    SCOUT_CORE_AGENT_LAUNCH = False
    SCOUT_REVISION_SHA = __release_hash__[:7]

STATIC_URL = os.environ.get("DATATRACKER_STATIC_URL", None)
if STATIC_URL is None:
    from ietf import __version__
    STATIC_URL = f"https://static.ietf.org/dt/{__version__}/"

# Set these to the same as "production" in settings.py, whether production mode or not
MEDIA_ROOT = "/a/www/www6s/lib/dt/media/"
MEDIA_URL  = "https://www.ietf.org/lib/dt/media/"
PHOTOS_DIRNAME = "photo"
PHOTOS_DIR = MEDIA_ROOT + PHOTOS_DIRNAME

# Normally only set for debug, but needed until we have a real FS
DJANGO_VITE_MANIFEST_PATH = os.path.join(BASE_DIR, 'static/dist-neue/manifest.json')

# Binaries that are different in the docker image
DE_GFM_BINARY = "/usr/local/bin/de-gfm"
IDSUBMIT_IDNITS_BINARY = "/usr/local/bin/idnits"

# Duplicating production cache from settings.py and using it whether we're in production mode or not
MEMCACHED_HOST = os.environ.get("DT_MEMCACHED_SERVICE_HOST", "127.0.0.1")
MEMCACHED_PORT = os.environ.get("DT_MEMCACHED_SERVICE_PORT", "11211")
from ietf import __version__
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
}

_csrf_trusted_origins_str = os.environ.get("DATATRACKER_CSRF_TRUSTED_ORIGINS")
if _csrf_trusted_origins_str is not None:
    CSRF_TRUSTED_ORIGINS = _multiline_to_list(_csrf_trusted_origins_str)

# Console logs as JSON instead of plain when running in k8s
LOGGING["handlers"]["console"]["formatter"] = "json"
