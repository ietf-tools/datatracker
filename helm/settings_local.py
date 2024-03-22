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

CELERY_BROKER_URL = "amqp://datatracker:{password}@{host}/{queue}".format(
    host=os.environ.get("RABBITMQ_HOSTNAME", "rabbitmq"),
    password=os.environ.get("CELERY_PASSWORD", ""),
    queue=os.environ.get("RABBITMQ_QUEUE", "dt")
)

IDSUBMIT_IDNITS_BINARY = "/usr/local/bin/idnits"

USING_DEBUG_EMAIL_SERVER=os.environ.get("USING_DEBUG_EMAIL_SERVER",True)
EMAIL_HOST= os.environ.get("EMAIL_HOST","localhost")
EMAIL_PORT=os.environ.get("EMAIL_PORT", 2025)

# Set INTERNAL_IPS for use within Docker. See https://knasmueller.net/fix-djangos-debug-toolbar-not-showing-inside-docker
import socket
hostname, _, ips = socket.gethostbyname_ex(socket.gethostname())
INTERNAL_IPS = [".".join(ip.split(".")[:-1] + ["1"]) for ip in ips]

DE_GFM_BINARY = "/usr/local/bin/de-gfm"

# Duplicating production cache from settings.py and
# using it whether we're in production mode or not
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
