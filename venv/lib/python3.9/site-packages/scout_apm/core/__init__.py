# coding=utf-8

import atexit
import logging
import os
import sys

from scout_apm import instruments
from scout_apm.compat import kwargs_only
from scout_apm.core import objtrace
from scout_apm.core.agent.manager import CoreAgentManager
from scout_apm.core.agent.socket import CoreAgentSocketThread
from scout_apm.core.config import scout_config
from scout_apm.core.error_service import ErrorServiceThread
from scout_apm.core.metadata import report_app_metadata

logger = logging.getLogger(__name__)


@kwargs_only
def install(config=None):
    global shutdown_registered
    if config is not None:
        scout_config.set(**config)
    scout_config.log()

    if os.name == "nt":
        logger.info(
            "APM Not Launching on PID: %s - Windows is not supported", os.getpid()
        )
        return False

    if not scout_config.value("monitor"):
        logger.info(
            "APM Not Launching on PID: %s - Configuration 'monitor' is not true",
            os.getpid(),
        )
        return False

    instruments.ensure_all_installed()
    objtrace.enable()

    logger.debug("APM Launching on PID: %s", os.getpid())
    launched = CoreAgentManager().launch()

    report_app_metadata()
    if launched:
        # Stop the thread to avoid running threads pre-fork
        CoreAgentSocketThread.ensure_stopped()

    if scout_config.value("shutdown_timeout_seconds") > 0.0 and not shutdown_registered:
        atexit.register(shutdown)
        shutdown_registered = True

    return True


shutdown_registered = False


def shutdown():
    timeout_seconds = scout_config.value("shutdown_timeout_seconds")

    def apm_callback(queue_size):
        if scout_config.value("shutdown_message_enabled"):
            print(  # noqa: T001,T201
                (
                    "Scout draining {queue_size} event{s} for up to"
                    + " {timeout_seconds} seconds"
                ).format(
                    queue_size=queue_size,
                    s=("" if queue_size == 1 else "s"),
                    timeout_seconds=timeout_seconds,
                ),
                file=sys.stderr,
            )

    def error_callback(queue_size):
        if scout_config.value("shutdown_message_enabled"):
            print(  # noqa: T001,T201
                (
                    "Scout draining {queue_size} error{s} for up to"
                    + " {timeout_seconds} seconds"
                ).format(
                    queue_size=queue_size,
                    s=("" if queue_size == 1 else "s"),
                    timeout_seconds=timeout_seconds,
                ),
                file=sys.stderr,
            )

    CoreAgentSocketThread.wait_until_drained(
        timeout_seconds=timeout_seconds, callback=apm_callback
    )

    if scout_config.value("errors_enabled"):
        ErrorServiceThread.wait_until_drained(
            timeout_seconds=timeout_seconds, callback=error_callback
        )
