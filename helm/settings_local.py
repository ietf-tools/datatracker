# Copyright The IETF Trust 2007-2024, All Rights Reserved
# -*- coding: utf-8 -*-

from ietf.settings import *                                          # pyflakes:ignore

ALLOWED_HOSTS = ['*']

DATABASES = {
    "default": {
        "HOST": os.environ.get("DBHOST", "db"),
        "PORT": os.environ.get("DBPORT", "5432"),
        "NAME": os.environ.get("DBNAME", "datatracker"),
        "ENGINE": "django.db.backends.postgresql",
        "USER": os.environ.get("DBUSER", "django"),
        "PASSWORD": os.environ.get("DBPASS", ""),
    },
}

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")

CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL")

IDSUBMIT_IDNITS_BINARY = "/usr/local/bin/idnits"
IDSUBMIT_REPOSITORY_PATH = "/test/id/"
IDSUBMIT_STAGING_PATH = "/test/staging/"

AGENDA_PATH = "/assets/www6s/proceedings/"
MEETINGHOST_LOGO_PATH = AGENDA_PATH

USING_DEBUG_EMAIL_SERVER=True
EMAIL_HOST= "localhost"
EMAIL_PORT=2025

MEDIA_BASE_DIR = "/assets"
MEDIA_ROOT = MEDIA_BASE_DIR + "/media/"
MEDIA_URL = "/media/"

PHOTOS_DIRNAME = "photo"
PHOTOS_DIR = MEDIA_ROOT + PHOTOS_DIRNAME

SUBMIT_YANG_CATALOG_MODEL_DIR = "/assets/ietf-ftp/yang/catalogmod/"
SUBMIT_YANG_DRAFT_MODEL_DIR = "/assets/ietf-ftp/yang/draftmod/"
SUBMIT_YANG_INVAL_MODEL_DIR = "/assets/ietf-ftp/yang/invalmod/"
SUBMIT_YANG_IANA_MODEL_DIR = "/assets/ietf-ftp/yang/ianamod/"
SUBMIT_YANG_RFC_MODEL_DIR = "/assets/ietf-ftp/yang/rfcmod/"

# Set INTERNAL_IPS for use within Docker. See https://knasmueller.net/fix-djangos-debug-toolbar-not-showing-inside-docker
import socket
hostname, _, ips = socket.gethostbyname_ex(socket.gethostname())
INTERNAL_IPS = [".".join(ip.split(".")[:-1] + ["1"]) for ip in ips]

# DEV_TEMPLATE_CONTEXT_PROCESSORS = [
#    'ietf.context_processors.sql_debug',
# ]

DOCUMENT_PATH_PATTERN = "/assets/ietfdata/doc/{doc.type_id}/"
INTERNET_DRAFT_PATH = "/assets/ietf-ftp/internet-drafts/"
RFC_PATH = "/assets/ietf-ftp/rfc/"
CHARTER_PATH = "/assets/ietf-ftp/charter/"
BOFREQ_PATH = "/assets/ietf-ftp/bofreq/"
CONFLICT_REVIEW_PATH = "/assets/ietf-ftp/conflict-reviews/"
STATUS_CHANGE_PATH = "/assets/ietf-ftp/status-changes/"
INTERNET_DRAFT_ARCHIVE_DIR = "/assets/archive/id"
INTERNET_ALL_DRAFTS_ARCHIVE_DIR = "/assets/archive/id"
BIBXML_BASE_PATH = "/assets/ietfdata/derived/bibxml"
IDSUBMIT_REPOSITORY_PATH = INTERNET_DRAFT_PATH

NOMCOM_PUBLIC_KEYS_DIR = "data/nomcom_keys/public_keys/"
SLIDE_STAGING_PATH = "/test/staging/"

# todo check that de-gfm is in place
DE_GFM_BINARY = "/usr/local/bin/de-gfm"

# OIDC configuration
SITE_URL = os.environ.get("OIDC_SITE_URL")

# todo: parameterize memcached url in settings.py
MEMCACHED_HOST = os.environ.get(f"MEMCACHED_SERVICE_HOST", "127.0.0.1")
MEMCACHED_PORT = os.environ.get("MEMCACHED_SERVICE_PORT", "11211")
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

# Normally only set for debug, but needed until we have a real FS
DJANGO_VITE_MANIFEST_PATH = os.path.join(BASE_DIR, 'static/dist-neue/manifest.json')
