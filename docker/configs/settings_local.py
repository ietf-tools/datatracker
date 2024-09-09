# Copyright The IETF Trust 2007-2019, All Rights Reserved
# -*- coding: utf-8 -*-

from ietf.settings import *                                          # pyflakes:ignore

ALLOWED_HOSTS = ['*']

from ietf.settings_postgresqldb import DATABASES   # pyflakes:ignore

IDSUBMIT_IDNITS_BINARY = "/usr/local/bin/idnits"
IDSUBMIT_STAGING_PATH = "/assets/www6s/staging/"

AGENDA_PATH = '/assets/www6s/proceedings/'
MEETINGHOST_LOGO_PATH = AGENDA_PATH

USING_DEBUG_EMAIL_SERVER=True
EMAIL_HOST='localhost'
EMAIL_PORT=2025

MEDIA_BASE_DIR = '/assets'
MEDIA_ROOT = MEDIA_BASE_DIR + '/media/'
MEDIA_URL = '/media/'

PHOTOS_DIRNAME = 'photo'
PHOTOS_DIR = MEDIA_ROOT + PHOTOS_DIRNAME

SUBMIT_YANG_CATALOG_MODEL_DIR = '/assets/ietf-ftp/yang/catalogmod/'
SUBMIT_YANG_DRAFT_MODEL_DIR = '/assets/ietf-ftp/yang/draftmod/'
SUBMIT_YANG_INVAL_MODEL_DIR = '/assets/ietf-ftp/yang/invalmod/'
SUBMIT_YANG_IANA_MODEL_DIR = '/assets/ietf-ftp/yang/ianamod/'
SUBMIT_YANG_RFC_MODEL_DIR   = '/assets/ietf-ftp/yang/rfcmod/'

# Set INTERNAL_IPS for use within Docker. See https://knasmueller.net/fix-djangos-debug-toolbar-not-showing-inside-docker
import socket
hostname, _, ips = socket.gethostbyname_ex(socket.gethostname())
INTERNAL_IPS = [".".join(ip.split(".")[:-1] + ["1"]) for ip in ips] + ['127.0.0.1']

# DEV_TEMPLATE_CONTEXT_PROCESSORS = [
#    'ietf.context_processors.sql_debug',
# ]

DOCUMENT_PATH_PATTERN = '/assets/ietfdata/doc/{doc.type_id}/'
INTERNET_DRAFT_PATH = '/assets/ietf-ftp/internet-drafts/'
RFC_PATH = '/assets/ietf-ftp/rfc/'
CHARTER_PATH = '/assets/ietf-ftp/charter/'
BOFREQ_PATH = '/assets/ietf-ftp/bofreq/'
CONFLICT_REVIEW_PATH = '/assets/ietf-ftp/conflict-reviews/'
STATUS_CHANGE_PATH = '/assets/ietf-ftp/status-changes/'
INTERNET_DRAFT_ARCHIVE_DIR = '/assets/collection/draft-archive'
INTERNET_ALL_DRAFTS_ARCHIVE_DIR = '/assets/archive/id'
BIBXML_BASE_PATH = '/assets/ietfdata/derived/bibxml'
IDSUBMIT_REPOSITORY_PATH = INTERNET_DRAFT_PATH
FTP_DIR = '/assets/ftp'

NOMCOM_PUBLIC_KEYS_DIR = 'data/nomcom_keys/public_keys/'
SLIDE_STAGING_PATH = '/assets/www6s/staging/'

DE_GFM_BINARY = '/usr/local/bin/de-gfm'

STATIC_IETF_ORG = "/_static"
STATIC_IETF_ORG_INTERNAL = "http://static"
