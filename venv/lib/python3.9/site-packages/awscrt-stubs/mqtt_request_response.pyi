"""
Type annotations for awscrt.mqtt_request_response module.

Copyright 2025 Vlad Emelianov
"""

from collections.abc import Sequence
from concurrent.futures import Future
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Callable

import typing_extensions
from awscrt import NativeResource, mqtt, mqtt5

class SubscriptionStatusEventType(IntEnum):
    SUBSCRIPTION_ESTABLISHED = 0
    SUBSCRIPTION_LOST = 1
    SUBSCRIPTION_HALTED = 2

@dataclass
class SubscriptionStatusEvent:
    type: SubscriptionStatusEventType | None = ...
    error: Exception | None = ...

@dataclass
class IncomingPublishEvent:
    topic: str
    payload: bytes | None = ...

SubscriptionStatusListener: typing_extensions.TypeAlias = Callable[[SubscriptionStatusEvent], None]
IncomingPublishListener: typing_extensions.TypeAlias = Callable[[IncomingPublishEvent], None]

@dataclass
class StreamingOperationOptions:
    subscription_topic_filter: str
    subscription_status_listener: SubscriptionStatusListener | None = ...
    incoming_publish_listener: IncomingPublishListener | None = ...

    def validate(self) -> None: ...

@dataclass
class Response:
    topic: str
    payload: bytes | None = None

@dataclass
class ResponsePath:
    topic: str
    correlation_token_json_path: str | None = None

    def validate(self) -> None: ...

@dataclass
class RequestOptions:
    subscription_topic_filters: Sequence[str]
    response_paths: Sequence[ResponsePath]
    publish_topic: str
    payload: bytes
    correlation_token: str | None = None

    def validate(self) -> None: ...

@dataclass
class ClientOptions:
    max_request_response_subscriptions: int
    max_streaming_subscriptions: int
    operation_timeout_in_seconds: int | None = 60

    def validate(self) -> None: ...

class Client(NativeResource):
    def __init__(
        self, protocol_client: mqtt5.Client | mqtt.Connection, client_options: ClientOptions
    ) -> None: ...
    def make_request(self, options: RequestOptions) -> Future[Response]: ...
    def create_stream(self, options: StreamingOperationOptions) -> StreamingOperation: ...

class StreamingOperation(NativeResource):
    def __init__(self, binding: Any) -> None: ...
    def open(self) -> None: ...
