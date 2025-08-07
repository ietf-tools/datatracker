# coding=utf-8

import json
import logging
import os
import threading
import time

from scout_apm.compat import (
    escape,
    gzip_compress,
    queue,
    urlencode,
    urljoin,
    urllib3_cert_pool_manager,
)
from scout_apm.core.config import scout_config
from scout_apm.core.threading import SingletonThread

# Time unit - monkey-patched in tests to make them run faster
SECOND = 1

logger = logging.getLogger(__name__)


class ErrorServiceThread(SingletonThread):
    _instance_lock = threading.Lock()
    _stop_event = threading.Event()
    _queue = queue.Queue(maxsize=500)

    @classmethod
    def _on_stop(cls):
        super(ErrorServiceThread, cls)._on_stop()
        # Unblock _queue.get()
        try:
            cls._queue.put(None, False)
        except queue.Full as exc:
            logger.debug("ErrorServiceThread full for stop: %r", exc, exc_info=exc)
            pass

    @classmethod
    def send(cls, error):
        try:
            cls._queue.put(error, False)
        except queue.Full as exc:
            logger.debug("ErrorServiceThread full for send: %r", exc, exc_info=exc)

        cls.ensure_started()

    @classmethod
    def wait_until_drained(cls, timeout_seconds=2.0, callback=None):
        interval_seconds = min(timeout_seconds, 0.05)
        start = time.time()
        while True:
            queue_size = cls._queue.qsize()
            queue_empty = queue_size == 0
            elapsed = time.time() - start
            if queue_empty or elapsed >= timeout_seconds:
                break

            if callback is not None:
                callback(queue_size)
                callback = None

            cls.ensure_started()

            time.sleep(interval_seconds)
        return queue_empty

    def run(self):
        batch_size = scout_config.value("errors_batch_size") or 1
        http = urllib3_cert_pool_manager()
        try:
            while True:
                errors = []
                try:
                    # Attempt to fetch the batch size off of the queue.
                    for _ in range(batch_size):
                        error = self._queue.get(block=True, timeout=1 * SECOND)
                        if error:
                            errors.append(error)
                except queue.Empty:
                    pass

                if errors and self._send(http, errors):
                    for _ in range(len(errors)):
                        self._queue.task_done()

                # Check for stop event after each read. This allows opening,
                # sending, and then immediately stopping.
                if self._stop_event.is_set():
                    logger.debug("ErrorServiceThread stopping.")
                    break
        except Exception as exc:
            logger.debug("ErrorServiceThread exception: %r", exc, exc_info=exc)
        finally:
            http.clear()
            logger.debug("ErrorServiceThread stopped.")

    def _send(self, http, errors):
        try:
            data = json.dumps(
                {
                    "notifier": "scout_apm_python",
                    "environment": scout_config.value("environment"),
                    "root": scout_config.value("application_root"),
                    "problems": errors,
                }
            ).encode("utf-8")
        except (ValueError, TypeError) as exc:
            logger.debug(
                "Exception when serializing error message: %r", exc, exc_info=exc
            )
            return False

        params = {
            "key": scout_config.value("key"),
            "name": escape(scout_config.value("name"), quote=False),
        }
        headers = {
            "Agent-Hostname": scout_config.value("hostname") or "",
            "Content-Encoding": "gzip",
            "Content-Type": "application/json",
            "X-Error-Count": "{}".format(len(errors)),
        }

        encoded_args = urlencode(params)
        full_url = urljoin(
            scout_config.value("errors_host"), "apps/error.scout"
        ) + "?{}".format(encoded_args)

        try:
            # urllib3 requires all parameters to be the same type for
            # python 2.7.
            # Since gzip can only return a str, convert all unicode instances
            # to str.
            response = http.request(
                str("POST"),
                str(full_url),
                body=gzip_compress(data),
                headers={str(key): str(value) for key, value in headers.items()},
            )
            if response.status >= 400:
                logger.debug(
                    (
                        "ErrorServiceThread %r response error on _send:"
                        + " %r on PID: %s on thread: %s"
                    ),
                    response.status,
                    response.data,
                    os.getpid(),
                    threading.current_thread(),
                )
                return False
        except Exception as exc:
            logger.debug(
                (
                    "ErrorServiceThread exception on _send:"
                    + " %r on PID: %s on thread: %s"
                ),
                exc,
                os.getpid(),
                threading.current_thread(),
                exc_info=exc,
            )
            return False
        return True
