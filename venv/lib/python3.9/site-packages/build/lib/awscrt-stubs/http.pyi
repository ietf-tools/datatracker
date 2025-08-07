"""
Type annotations for awscrt.http module.

Copyright 2024 Vlad Emelianov
"""

from concurrent.futures import Future
from enum import IntEnum
from typing import IO, Any, Callable, Iterator, TypeVar

from awscrt import NativeResource as NativeResource
from awscrt.io import ClientBootstrap as ClientBootstrap
from awscrt.io import InputStream as InputStream
from awscrt.io import SocketOptions as SocketOptions
from awscrt.io import TlsConnectionOptions as TlsConnectionOptions

_R = TypeVar("_R")

class HttpVersion(IntEnum):
    Unknown = 0
    Http1_0 = 1
    Http1_1 = 2
    Http2 = 3

class Http2SettingID(IntEnum):
    HEADER_TABLE_SIZE = 1
    ENABLE_PUSH = 2
    MAX_CONCURRENT_STREAMS = 3
    INITIAL_WINDOW_SIZE = 4
    MAX_FRAME_SIZE = 5
    MAX_HEADER_LIST_SIZE = 6

class Http2Setting:
    VALID_RANGES: dict[Http2SettingID, tuple[int, int]] = ...
    def __init__(
        self,
        id: Http2SettingID,
        value: int,
    ) -> None:
        self.id: Http2SettingID
        self.value: int

class HttpConnectionBase(NativeResource):
    def __init__(self) -> None: ...
    @property
    def shutdown_future(self) -> Future[None]: ...
    @property
    def version(self) -> str: ...
    def close(self) -> Future[None]: ...
    def is_open(self) -> bool: ...

class HttpClientConnection(HttpConnectionBase):
    @classmethod
    def new(
        cls: type[_R],
        host_name: str,
        port: int,
        bootstrap: ClientBootstrap | None = ...,
        socket_options: SocketOptions | None = ...,
        tls_connection_options: TlsConnectionOptions | None = ...,
        proxy_options: HttpProxyOptions | None = ...,
    ) -> Future[_R]: ...
    @property
    def host_name(self) -> str: ...
    @property
    def port(self) -> int: ...
    def request(
        self,
        request: HttpRequest,
        on_response: Callable[[HttpClientStream, int, list[tuple[str, str]]], None] | None = ...,
        on_body: Callable[[HttpClientStream, bytes], None] | None = ...,
    ) -> HttpClientStream: ...

class Http2ClientConnection(HttpClientConnection):
    @classmethod
    def new(  # type: ignore[override]
        cls,
        host_name: str,
        port: int,
        bootstrap: ClientBootstrap | None = ...,
        socket_options: SocketOptions | None = ...,
        tls_connection_options: TlsConnectionOptions | None = ...,
        proxy_options: HttpProxyOptions | None = ...,
        initial_settings: list[Http2Setting] | None = ...,
        on_remote_settings_changed: Callable[[list[Http2Setting]], None] | None = ...,
    ) -> Future[HttpClientConnection]: ...
    def request(
        self,
        request: HttpRequest,
        on_response: Callable[[HttpClientStream, int, list[tuple[str, str]]], None] | None = ...,
        on_body: Callable[[HttpClientStream, bytes], None] | None = ...,
        manual_write: bool = ...,
    ) -> Http2ClientStream: ...

class HttpStreamBase(NativeResource):
    def __init__(
        self,
        connection: HttpClientConnection,
        on_body: Callable[[HttpClientStream, bytes], None] | None = ...,
    ) -> None: ...
    @property
    def connection(self) -> HttpClientConnection: ...
    @property
    def completion_future(self) -> Future[int]: ...

class HttpClientStream(HttpStreamBase):
    def __init__(
        self,
        connection: HttpClientConnection,
        request: HttpRequest,
        on_response: Callable[[HttpClientStream, int, list[tuple[str, str]]], None] | None = ...,
        on_body: Callable[[HttpClientStream, bytes], None] | None = ...,
    ) -> None: ...
    @property
    def response_status_code(self) -> int: ...
    def activate(self) -> None: ...
    @property
    def version(self) -> HttpVersion: ...

class Http2ClientStream(HttpClientStream):
    def __init__(
        self,
        connection: HttpClientConnection,
        request: HttpRequest,
        on_response: Callable[[HttpClientStream, int, list[tuple[str, str]]], None] | None = ...,
        on_body: Callable[[HttpClientStream, bytes], None] | None = ...,
        manual_write: bool = ...,
    ) -> None: ...
    def write_data(self, data_stream: IO[Any], end_stream: bool = ...) -> None: ...

class HttpMessageBase(NativeResource):
    def __init__(
        self, binding: Any, headers: HttpHeaders, body_stream: IO[Any] | None = ...
    ) -> None: ...
    @property
    def headers(self) -> HttpHeaders: ...
    @property
    def body_stream(self) -> IO[Any] | None: ...
    @body_stream.setter
    def body_stream(self, stream: IO[Any]) -> None: ...

class HttpRequest(HttpMessageBase):
    def __init__(
        self,
        method: str = ...,
        path: str = ...,
        headers: HttpHeaders | None = ...,
        body_stream: IO[Any] | None = ...,
    ) -> None: ...
    @property
    def method(self) -> str: ...
    @method.setter
    def method(self, method: str) -> None: ...
    @property
    def path(self) -> str: ...
    @path.setter
    def path(self, path: str) -> None: ...

class HttpHeaders(NativeResource):
    def __init__(self, name_value_pairs: list[tuple[str, str]] | None = ...) -> None: ...
    def add(self, name: str, value: str) -> None: ...
    def add_pairs(self, name_value_pairs: list[tuple[str, str]]) -> None: ...
    def set(self, name: str, value: str) -> None: ...
    def get_values(self, name: str) -> Iterator[tuple[str, str]]: ...
    def get(self, name: str, default: str | None = ...) -> str | None: ...
    def remove(self, name: str) -> None: ...
    def remove_value(self, name: str, value: str) -> None: ...
    def clear(self) -> None: ...
    def __iter__(self) -> Iterator[tuple[str, str]]: ...

class HttpProxyConnectionType(IntEnum):
    Legacy = 0
    Forwarding = 1
    Tunneling = 2

class HttpProxyAuthenticationType(IntEnum):
    Nothing = 0
    Basic = 1

class HttpProxyOptions:
    def __init__(
        self,
        host_name: str,
        port: int,
        tls_connection_options: TlsConnectionOptions | None = ...,
        auth_type: HttpProxyAuthenticationType = ...,
        auth_username: str | None = ...,
        auth_password: str | None = ...,
        connection_type: HttpProxyConnectionType | None = ...,
    ) -> None:
        self.host_name: str
        self.port: int
        self.tls_connection_options: TlsConnectionOptions | None
        self.auth_type: HttpProxyAuthenticationType
        self.auth_username: str | None
        self.auth_password: str | None
        self.connection_type: HttpProxyConnectionType
