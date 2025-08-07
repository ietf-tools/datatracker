# coding=utf-8

import datetime as dt
import logging
import re

from scout_apm.compat import iteritems

logger = logging.getLogger(__name__)

key_regex = re.compile(r"^[a-zA-Z0-9]{20}$")


def format_dt_for_core_agent(event_time: dt.datetime) -> str:
    """
    Returns expected format for Core Agent compatibility.
    Coerce any tz-aware datetime to UTC just in case.
    """
    # if we somehow got a naive datetime, convert it to UTC
    if event_time.tzinfo is None:
        logger.warning("Naive datetime passed to format_dt_for_core_agent")
        event_time = event_time.astimezone(dt.timezone.utc)
    return event_time.isoformat()


class Register(object):
    __slots__ = ("app", "key", "hostname")

    def __init__(self, app, key, hostname):
        self.app = app
        self.key = key
        self.hostname = hostname

    def message(self):
        key_prefix = self.key[:3]
        key_matches_regex = bool(key_regex.match(self.key))
        logger.info(
            "Registering with app=%s key_prefix=%s key_format_validated=%s host=%s"
            % (self.app, key_prefix, key_matches_regex, self.hostname)
        )
        return {
            "Register": {
                "app": self.app,
                "key": self.key,
                "host": self.hostname,
                "language": "python",
                "api_version": "1.0",
            }
        }


class StartSpan(object):
    __slots__ = ("timestamp", "request_id", "span_id", "parent", "operation")

    def __init__(self, timestamp, request_id, span_id, parent, operation):
        self.timestamp = timestamp
        self.request_id = request_id
        self.span_id = span_id
        self.parent = parent
        self.operation = operation

    def message(self):
        return {
            "StartSpan": {
                "timestamp": format_dt_for_core_agent(self.timestamp),
                "request_id": self.request_id,
                "span_id": self.span_id,
                "parent_id": self.parent,
                "operation": self.operation,
            }
        }


class StopSpan(object):
    __slots__ = ("timestamp", "request_id", "span_id")

    def __init__(self, timestamp, request_id, span_id):
        self.timestamp = timestamp
        self.request_id = request_id
        self.span_id = span_id

    def message(self):
        return {
            "StopSpan": {
                "timestamp": format_dt_for_core_agent(self.timestamp),
                "request_id": self.request_id,
                "span_id": self.span_id,
            }
        }


class StartRequest(object):
    __slots__ = ("timestamp", "request_id")

    def __init__(self, timestamp, request_id):
        self.timestamp = timestamp
        self.request_id = request_id

    def message(self):
        return {
            "StartRequest": {
                "timestamp": format_dt_for_core_agent(self.timestamp),
                "request_id": self.request_id,
            }
        }


class FinishRequest(object):
    __slots__ = ("timestamp", "request_id")

    def __init__(self, timestamp, request_id):
        self.timestamp = timestamp
        self.request_id = request_id

    def message(self):
        return {
            "FinishRequest": {
                "timestamp": format_dt_for_core_agent(self.timestamp),
                "request_id": self.request_id,
            }
        }


class TagSpan(object):
    __slots__ = ("timestamp", "request_id", "span_id", "tag", "value")

    def __init__(self, timestamp, request_id, span_id, tag, value):
        self.timestamp = timestamp
        self.request_id = request_id
        self.span_id = span_id
        self.tag = tag
        self.value = value

    def message(self):
        return {
            "TagSpan": {
                "timestamp": format_dt_for_core_agent(self.timestamp),
                "request_id": self.request_id,
                "span_id": self.span_id,
                "tag": self.tag,
                "value": self.value,
            }
        }


class TagRequest(object):
    __slots__ = ("timestamp", "request_id", "tag", "value")

    def __init__(self, timestamp, request_id, tag, value):
        self.timestamp = timestamp
        self.request_id = request_id
        self.tag = tag
        self.value = value

    def message(self):
        return {
            "TagRequest": {
                "timestamp": format_dt_for_core_agent(self.timestamp),
                "request_id": self.request_id,
                "tag": self.tag,
                "value": self.value,
            }
        }


class ApplicationEvent(object):
    __slots__ = ("event_type", "event_value", "source", "timestamp")

    def __init__(self, event_type, event_value, source, timestamp):
        self.event_type = event_type
        self.event_value = event_value
        self.source = source
        self.timestamp = timestamp

    def message(self):
        return {
            "ApplicationEvent": {
                "timestamp": format_dt_for_core_agent(self.timestamp),
                "event_type": self.event_type,
                "event_value": self.event_value,
                "source": self.source,
            }
        }


class BatchCommand(object):
    __slots__ = ("commands",)

    def __init__(self, commands):
        self.commands = commands

    def message(self):
        return {
            "BatchCommand": {
                "commands": [command.message() for command in self.commands]
            }
        }

    @classmethod
    def from_tracked_request(cls, request):
        # The TrackedRequest must be finished
        commands = []
        commands.append(
            StartRequest(timestamp=request.start_time, request_id=request.request_id)
        )
        for key, value in iteritems(request.tags):
            commands.append(
                TagRequest(
                    timestamp=request.start_time,
                    request_id=request.request_id,
                    tag=key,
                    value=value,
                )
            )

        for span in request.complete_spans:
            commands.append(
                StartSpan(
                    timestamp=span.start_time,
                    request_id=span.request_id,
                    span_id=span.span_id,
                    parent=span.parent,
                    operation=span.operation,
                )
            )

            for key, value in iteritems(span.tags):
                commands.append(
                    TagSpan(
                        timestamp=span.start_time,
                        request_id=request.request_id,
                        span_id=span.span_id,
                        tag=key,
                        value=value,
                    )
                )

            commands.append(
                StopSpan(
                    timestamp=span.end_time,
                    request_id=span.request_id,
                    span_id=span.span_id,
                )
            )

        commands.append(
            FinishRequest(timestamp=request.end_time, request_id=request.request_id)
        )

        return cls(commands)
