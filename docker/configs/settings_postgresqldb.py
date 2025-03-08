DATABASES = {
    'default': {
        'HOST': 'db',
        'PORT': 5432,
        'NAME': 'datatracker',
        'ENGINE': 'django.db.backends.postgresql',
        'USER': 'django',
        'PASSWORD': 'RkTkDPFnKpko',
    },
    'blobdb': {
        'HOST': 'blobdb',
        'PORT': 5432,
        'NAME': 'blob',
        'ENGINE': 'django.db.backends.postgresql',
        'USER': 'dt',
        'PASSWORD': 'abcd1234',
    },
}
