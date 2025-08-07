# coding=utf-8

import threading
import time
from threading import local as ThreadLocal

from scout_apm.core.tracked_request import TrackedRequest

try:
    from asgiref.local import Local as AsgiRefLocal
except ImportError:
    # Old versions of Python or asgiref < 3.1
    AsgiRefLocal = None

try:
    import asyncio
except ImportError:
    asyncio = None

try:
    from contextvars import ContextVar

    scout_context_var = ContextVar("__scout_trackedrequest")
except ImportError:
    scout_context_var = None


SCOUT_REQUEST_ATTR = "__scout_trackedrequest"


def get_current_asyncio_task():
    """
    Cross-version implementation of asyncio.current_task()
    Returns None if there is no task.
    """
    if asyncio:
        try:
            if hasattr(asyncio, "current_task"):
                # Python 3.7 and up
                return asyncio.current_task()
            else:
                # Python 3.6
                return asyncio.Task.current_task()
        except RuntimeError:
            return None


class SimplifiedAsgirefLocal:
    """
    A copy of asgiref 3.1+'s Local class without the sync_to_async /
    async_to_sync compatibility.
    """

    CLEANUP_INTERVAL = 60  # seconds

    def __init__(self):
        self._storage = {}
        self._last_cleanup = time.time()
        self._clean_lock = threading.Lock()

    def _get_context_id(self):
        """
        Get the ID we should use for looking up variables
        """
        # First, pull the current task if we can
        context_id = get_current_asyncio_task()
        # OK, let's try for a thread ID
        if context_id is None:
            context_id = threading.current_thread()
        return context_id

    def _cleanup(self):
        """
        Cleans up any references to dead threads or tasks
        """
        for key in list(self._storage.keys()):
            if isinstance(key, threading.Thread):
                if not key.is_alive():
                    del self._storage[key]
            elif isinstance(key, asyncio.Task):
                if key.done():
                    del self._storage[key]
        self._last_cleanup = time.time()

    def _maybe_cleanup(self):
        """
        Cleans up if enough time has passed
        """
        if time.time() - self._last_cleanup > self.CLEANUP_INTERVAL:
            with self._clean_lock:
                self._cleanup()

    def __getattr__(self, key):
        context_id = self._get_context_id()
        if key in self._storage.get(context_id, {}):
            return self._storage[context_id][key]
        else:
            raise AttributeError("%r object has no attribute %r" % (self, key))

    def __setattr__(self, key, value):
        if key in ("_storage", "_last_cleanup", "_clean_lock", "_thread_critical"):
            return super().__setattr__(key, value)
        self._maybe_cleanup()
        self._storage.setdefault(self._get_context_id(), {})[key] = value

    def __delattr__(self, key):
        context_id = self._get_context_id()
        if key in self._storage.get(context_id, {}):
            del self._storage[context_id][key]
        else:
            raise AttributeError("%r object has no attribute %r" % (self, key))


class LocalContext(object):
    def __init__(self):
        if AsgiRefLocal is not None:
            self._local = AsgiRefLocal()
        elif asyncio is not None:
            self._local = SimplifiedAsgirefLocal()
        else:
            self._local = ThreadLocal()
        self.use_context_var = scout_context_var is not None

    def get_tracked_request(self):
        if scout_context_var:
            if not scout_context_var.get(None):
                scout_context_var.set(TrackedRequest())
            return scout_context_var.get()
        if not hasattr(self._local, "tracked_request"):
            self._local.tracked_request = TrackedRequest()
        return self._local.tracked_request

    def clear_tracked_request(self, instance):
        if getattr(self._local, "tracked_request", None) is instance:
            del self._local.tracked_request
        if scout_context_var and scout_context_var.get(None) is instance:
            scout_context_var.set(None)


context = LocalContext()
