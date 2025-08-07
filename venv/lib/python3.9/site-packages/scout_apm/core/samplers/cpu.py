# coding=utf-8

import datetime as dt
import logging

import psutil

logger = logging.getLogger(__name__)


class Cpu(object):
    metric_type = "CPU"
    metric_name = "Utilization"
    human_name = "Process CPU"

    def __init__(self):
        self.last_run = dt.datetime.now(dt.timezone.utc)
        self.last_cpu_times = psutil.Process().cpu_times()
        self.num_processors = psutil.cpu_count()
        if self.num_processors is None:
            logger.debug("Could not determine CPU count - assuming there is one.")
            self.num_processors = 1

    def run(self):
        now = dt.datetime.now(dt.timezone.utc)
        process = psutil.Process()  # get a handle on the current process
        cpu_times = process.cpu_times()

        wall_clock_elapsed = (now - self.last_run).total_seconds()
        if wall_clock_elapsed < 0:
            self.save_times(now, cpu_times)
            logger.debug(
                "%s: Negative time elapsed. now: %s, last_run: %s.",
                self.human_name,
                now,
                self.last_run,
            )
            return None

        utime_elapsed = cpu_times.user - self.last_cpu_times.user
        stime_elapsed = cpu_times.system - self.last_cpu_times.system
        process_elapsed = utime_elapsed + stime_elapsed

        # This can happen right after a fork.  This class starts up in
        # pre-fork, records {u,s}time, then forks. This resets {u,s}time to 0
        if process_elapsed < 0:
            self.save_times(now, cpu_times)
            logger.debug(
                "%s: Negative process time elapsed. "
                "utime: %s, stime: %s, total time: %s. "
                "This is normal to see when starting a forking web server.",
                self.human_name,
                utime_elapsed,
                stime_elapsed,
                process_elapsed,
            )
            return None

        # Normalized to # of processors
        normalized_wall_clock_elapsed = wall_clock_elapsed * self.num_processors

        # If somehow we run for 0 seconds between calls, don't try to divide by 0
        if normalized_wall_clock_elapsed == 0:
            res = 0
        else:
            res = (process_elapsed / normalized_wall_clock_elapsed) * 100

        self.save_times(now, cpu_times)

        logger.debug("%s: %s [%s CPU(s)]", self.human_name, res, self.num_processors)

        return res

    def save_times(self, now, cpu_times):
        self.last_run = now
        self.cpu_times = cpu_times
