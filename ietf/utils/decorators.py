# Copyright The IETF Trust 2016-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from functools import wraps

from django.shortcuts import render

import debug                            # pyflakes:ignore

from ietf.person.models import Person


def person_required(f):
    @wraps(f)
    def _wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise ValueError("The @person_required decorator should be called after @login_required.")
        try:
            request.user.person
        except Person.DoesNotExist:
            return render(request, 'registration/missing_person.html')
        return  f(request, *args, **kwargs)
    return _wrapper


def memoize(func):
    @wraps(func)
    def _memoize(self, *args, **kwargs):
        '''Memoize wrapper for instance methods.  Use @lru_cache for functions.'''
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

    if not hasattr(func, '__class__'):
        raise NotImplementedError("Use @lru_cache instead of memoize() for functions.")
    # For methods, we want the cache on the object, not on the class, in order
    # to not having to think about cache bloat and content becoming stale, so
    # we cannot set up the cache here.
    return _memoize


def ignore_view_kwargs(*args):
    """Ignore the specified kwargs if they are present

    Usage: 
      @ignore_view_kwargs("ignore_arg1", "ignore_arg2")
      def my_view(request, good_arg):
        ...

      This will allow my_view() to be used in url() paths that have zero, one, or both of
      ignore_arg1 and ignore_arg2 captured. These will be ignored, while good_arg will still
      be captured as usual.
    """
    kwargs_to_ignore = args

    def decorate(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            for kwarg in kwargs_to_ignore:
                kwargs.pop(kwarg, None)
            return view(*args, **kwargs)

        return wrapped

    return decorate


