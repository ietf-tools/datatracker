# coding=utf-8

import logging

import psutil

logger = logging.getLogger(__name__)


def get_rss_in_mb():
    rss_in_bytes = psutil.Process().memory_info().rss
    return rss_in_bytes / (1024 * 1024)


class Memory(object):
    metric_type = "Memory"
    metric_name = "Physical"
    human_name = "Process Memory"

    def run(self):
        value = get_rss_in_mb()
        logger.debug("%s: #%s", self.human_name, value)
        return value
