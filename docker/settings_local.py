import os

SECRET_KEY = 'jzv$o93h_lzw4a0%0oz-5t5lk+ai=3f8x@uo*9ahu8w4i300o6'

DATABASES = {
    'default': {
        'NAME': 'ietf_utf8',
        'ENGINE': 'django.db.backends.mysql',
        'USER': 'django',
        'PASSWORD': 'RkTkDPFnKpko',
        },
    }

DATABASE_TEST_OPTIONS = {
    'init_command': 'SET storage_engine=InnoDB',
    }

IDSUBMIT_IDNITS_BINARY = "/usr/local/bin/idnits"
IDSUBMIT_REPOSITORY_PATH = "test/id/"
IDSUBMIT_STAGING_PATH = "test/staging/"
INTERNET_DRAFT_ARCHIVE_DIR = "test/archive/"
INTERNET_ALL_DRAFTS_ARCHIVE_DIR = "test/archive/"
RFC_PATH = "test/rfc/"

AGENDA_PATH = 'data/developers/www6s/proceedings/'

USING_DEBUG_EMAIL_SERVER=True
EMAIL_HOST='localhost'
EMAIL_PORT=2025

TRAC_WIKI_DIR_PATTERN = "test/wiki/%s"
TRAC_SVN_DIR_PATTERN = "test/svn/%s"
TRAC_CREATE_ADHOC_WIKIS = [
]

MEDIA_BASE_DIR = 'test'
MEDIA_ROOT = MEDIA_BASE_DIR + '/media/'
MEDIA_URL = '/media/'

PHOTOS_DIRNAME = 'photo'
PHOTOS_DIR = MEDIA_ROOT + PHOTOS_DIRNAME

DOCUMENT_PATH_PATTERN = 'data/developers/ietf-ftp/{doc.type_id}/'

SUBMIT_YANG_RFC_MODEL_DIR   = 'data/developers/ietf-ftp/yang/rfcmod/'
SUBMIT_YANG_DRAFT_MODEL_DIR = 'data/developers/ietf-ftp/yang/draftmod/'
SUBMIT_YANG_INVAL_MODEL_DIR = 'data/developers/ietf-ftp/yang/invalmod/'
SUBMIT_YANG_IANA_MODEL_DIR = 'data/developers/ietf-ftp/yang/ianamod/'
SUBMIT_YANGLINT_COMMAND = 'yanglint --verbose -p {rfclib} -p {draftlib} -p {tmplib} {model}'


API_PUBLIC_KEY_PEM = """
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAuIm3wBpMEhFmy40ZBNHU
jn6cMVeDwynedDtww+071mQFIyidDn0UYCTfLn8dLQDpbdoreMz9Zzb0tMygMyMb
5fsOItkEd7J5jVqpPWqlvspaa5qb5zuB8NHAxRjPfomgn0Sl1Uvwl1Gc3N2UElCb
mJ+wEK+C55YVLj1k/9GU34G//XLcSnBF7bmjcycP+z8wkAtjE51ZR2Y6oP6o11jO
yL5X7Y+1Nk9cPlUbtrvmmyXEKnjUXbRUoK4CJ87dYjFk8CHWmqolY++bgp4Ro6gK
k6RAy1XaC6uCaVnlJQKpIZ8XvJyv34ku65KUuLQMlxBbVt7z+ybrMvU7NNpCVTGp
kwIDAQAB
-----END PUBLIC KEY-----
"""

API_PRIVATE_KEY_PEM = """
-----BEGIN PRIVATE KEY-----
MIIEvwIBADANBgkqhkiG9w0BAQEFAASCBKkwggSlAgEAAoIBAQC4ibfAGkwSEWbL
jRkE0dSOfpwxV4PDKd50O3DD7TvWZAUjKJ0OfRRgJN8ufx0tAOlt2it4zP1nNvS0
zKAzIxvl+w4i2QR3snmNWqk9aqW+ylprmpvnO4Hw0cDFGM9+iaCfRKXVS/CXUZzc
3ZQSUJuYn7AQr4LnlhUuPWT/0ZTfgb/9ctxKcEXtuaNzJw/7PzCQC2MTnVlHZjqg
/qjXWM7Ivlftj7U2T1w+VRu2u+abJcQqeNRdtFSgrgInzt1iMWTwIdaaqiVj75uC
nhGjqAqTpEDLVdoLq4JpWeUlAqkhnxe8nK/fiS7rkpS4tAyXEFtW3vP7Jusy9Ts0
2kJVMamTAgMBAAECggEBAKV46EnbysaQ0ApKFVsbBGxZ35jnDoGcM5sqCa3GNlfC
DFFAg8SQKAsmRPIejXzjSm10qnKB7d/1iWvt6OCx5LxOaJia3MSwRwqXdxZZYRI5
xOakFpQ76gKVMzQJUVX39w2ZstIWbEBjsDLkhXf+y+cJmgj8OHeNPqTd7Ijv13yq
B8JVFhtrARTE9X5bxxl5FMrqchVv7HyCS6FBTK+rPPaE3gK2XyiNKHokcV2NfmeF
OHqqDn9LPN4ERRU13FNv5/wvH6/Z0AXsRWFkxuCdYcVzG9xEnf/72b0jumRqnSAN
bVK+/b37SOky/L0mwfXwhQoMvePgbYE1qv2Lx4maVcECgYEA5Im7Ys2FfFAGWV3Y
eNizNHmJYXuvLVsEEYtxT1tM/yPTvlljA27s5rrXdtRDS67Hnj28b9nrHp0COlZp
GycbppQcPEKiDupLlvstdQ+b+t1MO3xAqW2ZeM47A1SmPKa7XmTAL+6ZReeN/Eg6
QCmqY5HHANhX+OwN+zwAg9ZQlBECgYEAzrZ1qr8RBBP4/0NY3WMkAiJpluIOc6kO
8lP0tNk6FJ9OaIMAI6FKxh/7KKcgWzINWSVqz+8te5HUCUt5JWZXcn2NMkk2ufm4
4OV0vXz3ba6RhIXtDxJW9qbihhZ+EJYPvgwWUF3W1Onu4BuirD+74LSTWG8Ko3lK
m0qbAl5s92MCgYEAuJQxHwyE6jEr35O3GWtT2WbruSsPAd/Hum/X9VL1Lf/+rXc+
S/CUL4nqKdQoAgFIwhp0jhYAGrqOqRVPUJnWcEShRV4/yzIaGPgG78vKm+OOBWFG
TFDzqilOalM87DFxlTxkKJJZgqcQ+xhOy7GbJ03+30TcUHQ+mpIMjG5UqDECgYBG
yc8T0OiX1+seJ0cIUYokPPqh0/oU+6EFtWCIihdMtp1YRvxGN1bu8EbHTixTbpmJ
nLmuSX7u4SqWoET1XM23hG1U+iOGnpEEWy+WMHRfGDf3BRIAZkxnnRDX0F4NegYc
E/GURf5q3U2Ta4NSr2S8d7o5v5UKFGBLO8pHjmSMdwKBgQCbZMPV/ogqNbsuEXsP
rZQg+DTonX55os7Dnii715NAzzP7zaZ/RF/zEJrYKKATiaYFNIpz66wuAIX6UrcO
N1mb6IlkRXoou2mawSFAPuwOFyKHDfohlA7lCiUsgB40uc90pa1evX8tctSXOuzh
qlOfAYmntqZaggU8f3gGh7EPjw==
-----END PRIVATE KEY-----
"""
