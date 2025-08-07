from dataclasses import dataclass
from typing import Final, List, Literal, Optional, TypedDict

from rest_framework.request import Request
from rest_framework.views import APIView


class ExceptionHandlerContext(TypedDict):
    view: APIView
    args: tuple
    kwargs: dict
    request: Optional[Request]


VALIDATION_ERROR: Final = "validation_error"
CLIENT_ERROR: Final = "client_error"
SERVER_ERROR: Final = "server_error"
ErrorType = Literal["validation_error", "client_error", "server_error"]


@dataclass
class Error:
    code: str
    detail: str
    attr: Optional[str]


@dataclass
class ErrorResponse:
    type: ErrorType
    errors: List[Error]


class SetValidationErrorsKwargs(TypedDict):
    error_codes: List[str]
    field_name: Optional[str]
    actions: Optional[List[str]]
    methods: Optional[List[str]]
    versions: Optional[List[str]]
