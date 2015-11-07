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
