# coding=utf-8

from collections import defaultdict


class NPlusOneTrackedItem(object):
    __slots__ = ("count", "duration", "captured")

    def __init__(self):
        self.count = 0
        self.duration = 0.0
        self.captured = False


class NPlusOneTracker(object):
    # Fetch backtraces on this number of same SQL calls
    COUNT_THRESHOLD = 5

    # Minimum time in seconds before we start performing any work.
    DURATION_THRESHOLD = 0.150

    __slots__ = ("_map",)

    def __init__(self):
        self._map = defaultdict(NPlusOneTrackedItem)

    def should_capture_backtrace(self, sql, duration, count=1):
        item = self._map[sql]
        if item.captured:
            return False

        item.duration += duration
        item.count += count

        if (
            item.duration >= self.DURATION_THRESHOLD
            and item.count >= self.COUNT_THRESHOLD
        ):
            item.captured = True
            return True
        return False
