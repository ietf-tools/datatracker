# Copyright The IETF Trust 2023, All Rights Reserved
# -*- coding: utf-8 -*-

from django.core.cache.backends.base import DEFAULT_TIMEOUT
from django.core.cache.backends.memcached import PyMemcacheCache
from pymemcache.exceptions import MemcacheServerError

from .log import log


class LenientMemcacheCache(PyMemcacheCache):
    """PyMemcacheCache backend that tolerates failed inserts due to object size"""
    def set(self, key, value, timeout=DEFAULT_TIMEOUT, version=None):
        try:
            super().set(key, value, timeout, version)
        except MemcacheServerError as err:
            if "object too large for cache" in str(err):
                log(f"Memcache failed to cache large object for {key}")
            else:
                raise
