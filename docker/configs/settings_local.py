# Copyright The IETF Trust 2007-2025, All Rights Reserved
# -*- coding: utf-8 -*-

from ietf.settings import *  # pyflakes:ignore
from ietf.settings import (
    ARTIFACT_STORAGE_NAMES,
    STORAGES,
    BLOBSTORAGE_MAX_ATTEMPTS,
    BLOBSTORAGE_READ_TIMEOUT,
    BLOBSTORAGE_CONNECT_TIMEOUT,
)

ALLOWED_HOSTS = ['*']

from ietf.settings_postgresqldb import DATABASES  # pyflakes:ignore
DATABASE_ROUTERS = ["ietf.blobdb.routers.BlobdbStorageRouter"]
BLOBDB_DATABASE = "blobdb"
BLOBDB_REPLICATION = {
    "ENABLED": True,
    "DEST_STORAGE_PATTERN": "r2-{bucket}",
    "INCLUDE_BUCKETS": ARTIFACT_STORAGE_NAMES,
    "EXCLUDE_BUCKETS": ["staging"],
    "VERBOSE_LOGGING": True,
}

IDSUBMIT_IDNITS_BINARY = "/usr/local/bin/idnits"
IDSUBMIT_IDNITS3_BINARY = "/usr/local/bin/idnits3"
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
NFS_METRICS_TMP_DIR = '/assets/tmp'

NOMCOM_PUBLIC_KEYS_DIR = 'data/nomcom_keys/public_keys/'

DE_GFM_BINARY = '/usr/local/bin/de-gfm'

STATIC_IETF_ORG = "/_static"
STATIC_IETF_ORG_INTERNAL = "http://static"


# Blob replication storage for dev
import botocore.config
for storagename in ARTIFACT_STORAGE_NAMES:
    replica_storagename = f"r2-{storagename}"
    STORAGES[replica_storagename] = {
        "BACKEND": "ietf.doc.storage.MetadataS3Storage",
        "OPTIONS": dict(
            endpoint_url="http://blobstore:9000",
            access_key="minio_root",
            secret_key="minio_pass",
            security_token=None,
            client_config=botocore.config.Config(
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
                signature_version="s3v4",
                connect_timeout=BLOBSTORAGE_CONNECT_TIMEOUT,
                read_timeout=BLOBSTORAGE_READ_TIMEOUT,
                retries={"total_max_attempts": BLOBSTORAGE_MAX_ATTEMPTS},
            ),
            verify=False,
            bucket_name=f"{storagename}",
        ),
    }

# For dev on rfc-index generation, create a red_bucket/ directory in the project root
# and uncomment these settings. Generated files will appear in this directory. To
# generate an accurate index, put up-to-date copies of unusable-rfc-numbers.json,
# april-first-rfc-numbers.json, and publication-std-levels.json in this directory
# before generating the index.
#
# STORAGES["red_bucket"] = {
#     "BACKEND": "django.core.files.storage.FileSystemStorage",
#     "OPTIONS": {"location": "red_bucket"},
# }

# For dev involving RFC popularity, create a reef_bucket/ directory in the project
# root and uncomment. Popularity belongs in popularity.json.
# STORAGES["reef_bucket"] = {
#     "BACKEND": "django.core.files.storage.FileSystemStorage",
#     "OPTIONS": {"location": "reef_bucket"},
# }

APP_API_TOKENS = {
    "ietf.api.red_api" : ["devtoken", "redtoken"],  # Not a real secret
    "ietf.api.views_rpc" : ["devtoken"],  # Not a real secret
    "ietf.ietfauth.api_migration.claim_email" : ["devtoken"],  # Not a real secret
    "ietf.ietfauth.api_migration.verify" : ["devtoken"],  # Not a real secret
    "ietf.person.api_uuid" : ["devtoken"],  # Not a real secret
    "ietf.person.api_uuid_by_pk" : ["devtoken"],  # Not a real secret
}

# Private key the account migration API decrypts passwords with. Not a real secret - the
# account app encrypts to the matching public key, which
#   openssl rsa -pubout -in <this key>
# prints.
ACCOUNT_MIGRATION_PRIVATE_KEY = b"""\
-----BEGIN PRIVATE KEY-----
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
iQYoVN6njxYZu9Rew7Njrlw=
-----END PRIVATE KEY-----
"""

# Errata system api configuration
ERRATA_METADATA_NOTIFICATION_URL = "http://host.docker.internal:8808/api/rfc_metadata_update/"
ERRATA_METADATA_NOTIFICATION_API_KEY = "not a real secret"
