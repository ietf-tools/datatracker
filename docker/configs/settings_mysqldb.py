DATABASES = {
    'default': {
        'HOST': 'db',
        'PORT': 3306,
        'NAME': 'ietf_utf8',
        'ENGINE': 'django.db.backends.mysql',
        'USER': 'django',
        'PASSWORD': 'RkTkDPFnKpko',
        'OPTIONS': {
            'sql_mode': 'STRICT_TRANS_TABLES',
            'init_command': 'SET storage_engine=InnoDB; SET names "utf8"',
        },
    },
}

DATABASE_TEST_OPTIONS = {
    'init_command': 'SET storage_engine=InnoDB',
}
