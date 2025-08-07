# coding=utf-8

import datetime as dt
import logging
import time
import typing

from scout_apm.compat import datetime_to_timestamp
from scout_apm.core.tracked_request import TrackedRequest

logger = logging.getLogger(__name__)

# Cutoff epoch is used for determining ambiguous timestamp boundaries
CUTOFF_EPOCH_S = time.mktime((dt.date.today().year - 10, 1, 1, 0, 0, 0, 0, 0, 0))
CUTOFF_EPOCH_MS = CUTOFF_EPOCH_S * 1000.0
CUTOFF_EPOCH_US = CUTOFF_EPOCH_S * 1000000.0
CUTOFF_EPOCH_NS = CUTOFF_EPOCH_S * 1000000000.0


def _convert_ambiguous_timestamp_to_ns(timestamp: float) -> float:
    """
    Convert an ambiguous float timestamp that could be in nanoseconds,
    microseconds, milliseconds, or seconds to nanoseconds. Return 0.0 for
    values in the more than 10 years ago.
    """
    if timestamp > CUTOFF_EPOCH_NS:
        converted_timestamp = timestamp
    elif timestamp > CUTOFF_EPOCH_US:
        converted_timestamp = timestamp * 1000.0
    elif timestamp > CUTOFF_EPOCH_MS:
        converted_timestamp = timestamp * 1000000.0
    elif timestamp > CUTOFF_EPOCH_S:
        converted_timestamp = timestamp * 1000000000.0
    else:
        return 0.0
    return converted_timestamp


def track_request_queue_time(
    header_value: typing.Any, tracked_request: TrackedRequest
) -> bool:
    """
    Attempt to parse a queue time header and store the result in the tracked request.

    Returns:
        bool: Whether we succeeded in marking queue time. Used for testing.
    """
    if header_value.startswith("t="):
        header_value = header_value[2:]

    try:
        first_char = header_value[0]
    except IndexError:
        return False

    if not first_char.isdigit():  # filter out negatives, nan, inf, etc.
        return False

    try:
        ambiguous_start_timestamp = float(header_value)
    except ValueError:
        return False

    start_timestamp_ns = _convert_ambiguous_timestamp_to_ns(ambiguous_start_timestamp)
    if start_timestamp_ns == 0.0:
        return False

    tr_start_timestamp_ns = datetime_to_timestamp(tracked_request.start_time) * 1e9

    # Ignore if in the future
    if start_timestamp_ns > tr_start_timestamp_ns:
        return False

    queue_time_ns = int(tr_start_timestamp_ns - start_timestamp_ns)
    tracked_request.tag("scout.queue_time_ns", queue_time_ns)
    return True


def track_job_queue_time(
    header_value: typing.Any, tracked_request: TrackedRequest
) -> bool:
    """
    Attempt to parse a queue/latency time header and store the result in the request.

    Returns:
        bool: Whether we succeeded in marking queue time for the job. Used for testing.
    """
    if header_value is not None:
        now = datetime_to_timestamp(dt.datetime.now(dt.timezone.utc)) * 1e9
        try:
            ambiguous_float_start = typing.cast(float, header_value)
            start = _convert_ambiguous_timestamp_to_ns(ambiguous_float_start)
            queue_time_ns = int(now - start)
        except TypeError:
            logger.debug("Invalid job queue time header: %r", header_value)
            return False
        else:
            tracked_request.tag("scout.job_queue_time_ns", queue_time_ns)
            return True
