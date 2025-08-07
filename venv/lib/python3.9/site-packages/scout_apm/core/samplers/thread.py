# coding=utf-8

import datetime as dt
import logging
import os
import threading

from scout_apm.core.agent.commands import ApplicationEvent
from scout_apm.core.agent.socket import CoreAgentSocketThread
from scout_apm.core.samplers.cpu import Cpu
from scout_apm.core.samplers.memory import Memory
from scout_apm.core.threading import SingletonThread

logger = logging.getLogger(__name__)


class SamplersThread(SingletonThread):
    _instance_lock = threading.Lock()
    _stop_event = threading.Event()

    def run(self):
        logger.debug("Starting Samplers.")
        instances = [Cpu(), Memory()]

        while True:
            for instance in instances:
                event_value = instance.run()
                if event_value is not None:
                    event_type = instance.metric_type + "/" + instance.metric_name
                    event = ApplicationEvent(
                        event_value=event_value,
                        event_type=event_type,
                        timestamp=dt.datetime.now(dt.timezone.utc),
                        source="Pid: " + str(os.getpid()),
                    )
                    CoreAgentSocketThread.send(event)

            should_stop = self._stop_event.wait(timeout=60)
            if should_stop:
                logger.debug("Stopping Samplers.")
                break
