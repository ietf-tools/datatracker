# Copyright The IETF Trust 2016, All Rights Reserved

from decorator import decorator

from django.conf import settings

from test_runner import set_coverage_checking

@decorator
def skip_coverage(f, *args, **kwargs):
    if settings.TEST_CODE_COVERAGE_CHECKER:
        set_coverage_checking(False)
        result = f(*args, **kwargs)
        set_coverage_checking(True)
        return result
    else:
        return  f(*args, **kwargs)
