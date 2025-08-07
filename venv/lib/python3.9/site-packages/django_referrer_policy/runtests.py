"""
A standalone test runner script, configuring the minimum settings
required for tests to execute.

Re-use at your own risk: many Django applications will require
different settings and/or templates to run their tests.

"""

import os
import sys


# Make sure the app is (at least temporarily) on the import path.
APP_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, APP_DIR)


# Minimum settings required for the app's tests.
SETTINGS_DICT = {
    'BASE_DIR': APP_DIR,
    'INSTALLED_APPS': (
        'django_referrer_policy',
    ),
    'ROOT_URLCONF': 'django_referrer_policy.tests.urls',
    'DATABASES': {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': os.path.join(APP_DIR, 'db.sqlite3'),
        },
    },
    'MIDDLEWARE': (
        'django.middleware.common.CommonMiddleware',
        'django_referrer_policy.middleware.ReferrerPolicyMiddleware',
    ),
}


def run_tests():
    # Making Django run this way is a two-step process. First, call
    # settings.configure() to give Django settings to work with:
    from django.conf import settings
    settings.configure(**SETTINGS_DICT)

    # Then, call django.setup() to initialize the application cache
    # and other bits:
    import django
    django.setup()

    # Now we instantiate a test runner...
    from django.test.utils import get_runner
    TestRunner = get_runner(settings)

    # And then we run tests and return the results.
    test_runner = TestRunner(verbosity=2, interactive=True)
    failures = test_runner.run_tests(
        ['django_referrer_policy.tests']
    )
    sys.exit(bool(failures))


if __name__ == '__main__':
    run_tests()
