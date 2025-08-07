# coding=utf-8

import threading


class SingletonThread(threading.Thread):
    _instance = None
    # Copy these variables into subclasses to avoid sharing:
    # (Would use __init_subclass__() but Python 2 doesn't support it and using
    # metaclasses to achieve the same is a lot of faff.)
    # _instance_lock = threading.Lock()
    # _stop_event = threading.Event()

    @classmethod
    def ensure_started(cls):
        instance = cls._instance
        if instance is not None and instance.is_alive():
            # No need to grab the lock
            return
        with cls._instance_lock:
            if cls._instance is None or not cls._instance.is_alive():
                cls._instance = cls()
                cls._instance.start()

    @classmethod
    def ensure_stopped(cls):
        if cls._instance is None:
            # No need to grab the lock
            return
        with cls._instance_lock:
            if cls._instance is None:
                # Nothing to stop
                return
            elif not cls._instance.is_alive():
                # Thread died
                cls._instance = None
                return

            # Signal stopping
            cls._stop_event.set()
            cls._on_stop()
            cls._instance.join()

            cls._instance = None
            cls._stop_event.clear()

    @classmethod
    def _on_stop(cls):
        """
        Hook to allow subclasses to add extra behaviour to stopping.
        """
        pass

    def __init__(self, *args, **kwargs):
        super(SingletonThread, self).__init__(*args, **kwargs)
        self.daemon = True
