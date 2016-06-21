# Copyright The IETF Trust 2016, All Rights Reserved

from decorator import decorator

from django.conf import settings

@decorator
def skip_coverage(f, *args, **kwargs):
    if settings.TEST_CODE_COVERAGE_CHECKER:
        checker = settings.TEST_CODE_COVERAGE_CHECKER
        checker.collector.pause()
        result = f(*args, **kwargs)
        checker.collector.resume()
        return result
    else:
        return  f(*args, **kwargs)
