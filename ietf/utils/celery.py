# Copyright The IETF Trust 2024, All Rights Reserved
"""IETF Celery utilities"""
from contextlib import contextmanager
from django.core.cache import cache
import hashlib
import json
import time


@contextmanager
def celery_task_lock(task, expiration_seconds):
    """Cache-based task lock context manager
    
    Usage:
    
    Use bind=true when defining the task to make the task record available, then:
    @shared_task(bind=True)
    def some_task(self, some_arg, some_kwarg=None):
        # ...
        with celery_task_lock(self, expiration_seconds=30) as acquired:
            if acquired:
                do_it()
            else:
                print("well now I'm not doing it")
        print("no longer protected by the lock")
        # ...

    Based on 
    https://docs.celeryq.dev/en/5.4.0/tutorials/task-cookbook.html#ensuring-a-task-is-only-executed-one-at-a-time
    by Ask Solem & contributors
    
    Atomically adds a key to the default cache, assumed to be provided via memcached. The add will fail if the
    key already exists in the cache and has not yet expired, indicating that the lock is still held. When the
    context provided by this context manager is exited, deletes the cache item if the timeout has not yet
    expired.
    
    When using, ensure that the protected section of the task is guaranteed to exit within the expiration
    time. A brute force way to accomplish this is by setting a time_limit on the celery task.
    """
    # Set timeout_at to slightly before the actual cache item expires. This ensures that our cache.delete()
    # call will delete _our_ lock - once the cache item expires, another task may have taken the lock! This
    # means we may occasionally wait an extra second for the cache item to expire rather than deleting it
    # as soon as we could have.
    timeout_at = time.monotonic() + expiration_seconds - 1
    arg_hash = hashlib.sha1(f"{json.dumps(task.request.args)}{json.dumps(task.request.kwargs)}".encode()).hexdigest()
    key = f"celery-lock-{task.name}-{arg_hash}"
    add_succeeded = cache.add(key, "locked", expiration_seconds)
    try:
        yield add_succeeded  # value seen by "as acquired" in the with statement
    finally:
        # clean up
        if add_succeeded and time.monotonic() < timeout_at:
            cache.delete(key)
