# Copyright The IETF Trust 2016-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime

from decorator import decorator, decorate

from django.conf import settings
from django.contrib.auth import login
from django.http import HttpResponse
from django.shortcuts import render
from django.utils.encoding import force_bytes

import debug                            # pyflakes:ignore

from ietf.utils.test_runner import set_coverage_checking
from ietf.person.models import Person, PersonalApiKey, PersonApiKeyEvent
from ietf.utils import log

@decorator
def skip_coverage(f, *args, **kwargs):
    if settings.TEST_CODE_COVERAGE_CHECKER:
        set_coverage_checking(False)
        result = f(*args, **kwargs)
        set_coverage_checking(True)
        return result
    else:
        return  f(*args, **kwargs)

@decorator
def person_required(f, request, *args, **kwargs):
    if not request.user.is_authenticated:
        raise ValueError("The @person_required decorator should be called after @login_required.")
    try:
        request.user.person
    except Person.DoesNotExist:
        return render(request, 'registration/missing_person.html')
    return  f(request, *args, **kwargs)

@decorator
def require_api_key(f, request, *args, **kwargs):
    
    def err(code, text):
        return HttpResponse(text, status=code, content_type='text/plain')
    # Check method and get hash
    if request.method == 'POST':
        hash = request.POST.get('apikey')
    elif request.method == 'GET':
        hash = request.GET.get('apikey')
    else:
        return err(405, "Method not allowed")
    if not hash:
        return err(400, "Missing apikey parameter")
    # Check hash
    key = PersonalApiKey.validate_key(force_bytes(hash))
    if not key:
        return err(403, "Invalid apikey")
    # Check endpoint
    urlpath = request.META.get('PATH_INFO')
    if not (urlpath and urlpath == key.endpoint):
        return err(400, "Apikey endpoint mismatch") 
    # Check time since regular login
    person = key.person
    last_login = person.user.last_login
    if not person.user.is_staff:
        time_limit = (datetime.datetime.now() - datetime.timedelta(days=settings.UTILS_APIKEY_GUI_LOGIN_LIMIT_DAYS))
        if last_login == None or last_login < time_limit:
            return err(400, "Too long since last regular login")
    # Log in
    login(request, person.user)
    # restore the user.last_login field, so it reflects only gui logins
    person.user.last_login = last_login
    person.user.save()
    # Update stats
    key.count += 1
    key.latest = datetime.datetime.now()
    key.save()
    PersonApiKeyEvent.objects.create(person=person, type='apikey_login', key=key, desc="Logged in with key ID %s, endpoint %s" % (key.id, key.endpoint))
    # Execute decorated function
    try:
        ret = f(request, *args, **kwargs)
    except AttributeError as e:
        log.log("Bad API call: args: %s, kwargs: %s, exception: %s" % (args, kwargs, e))
        return err(400, "Bad or missing parameters")
    return ret


def _memoize(func, self, *args, **kwargs):
    ''''Memoize wrapper for instance methouds.  Use @lru_cache for functions.'''
    if kwargs:  # frozenset is used to ensure hashability
        key = args, frozenset(list(kwargs.items()))
    else:
        key = args
    # instance method, set up cache if needed
    if not hasattr(self, '_cache'):
        self._cache = {}
    if not func in self._cache:
        self._cache[func] = {}            
    #
    cache = self._cache[func]
    if key not in cache:
        cache[key] = func(self, *args, **kwargs)
    return cache[key]
def memoize(func):
    if not hasattr(func, '__class__'):
        raise NotImplementedError("Use @lru_cache instead of memoize() for funcitons.")
    # For methods, we want the cache on the object, not on the class, in order
    # to not having to think about cache bloat and content becoming stale, so
    # we cannot set up the cache here.
    return decorate(func, _memoize)

