import inspect
from collections import defaultdict
from typing import Dict, List, Set, Type, Union

from drf_spectacular.drainage import warn
from drf_spectacular.extensions import OpenApiFilterExtension
from drf_spectacular.openapi import AutoSchema as BaseAutoSchema
from drf_spectacular.utils import (
    Direction,
    OpenApiExample,
    PolymorphicProxySerializer,
    _SchemaType,
)
from inflection import camelize
from rest_framework import serializers
from rest_framework.negotiation import DefaultContentNegotiation
from rest_framework.pagination import CursorPagination, PageNumberPagination
from rest_framework.parsers import FileUploadParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.versioning import (
    AcceptHeaderVersioning,
    HostNameVersioning,
    NamespaceVersioning,
    QueryParameterVersioning,
    URLPathVersioning,
)

from .handler import exception_handler as standardized_errors_handler
from .openapi_serializers import (
    ClientErrorEnum,
    ErrorResponse401Serializer,
    ErrorResponse403Serializer,
    ErrorResponse404Serializer,
    ErrorResponse405Serializer,
    ErrorResponse406Serializer,
    ErrorResponse415Serializer,
    ErrorResponse429Serializer,
    ErrorResponse500Serializer,
    ParseErrorResponseSerializer,
    ValidationErrorEnum,
)
from .openapi_utils import (
    InputDataField,
    get_django_filter_backends,
    get_error_examples,
    get_filter_forms,
    get_flat_serializer_fields,
    get_form_fields_with_error_codes,
    get_serializer_fields_with_error_codes,
    get_validation_error_serializer,
)
from .openapi_validation_errors import get_validation_errors
from .settings import package_settings

S = Union[Type[serializers.Serializer], serializers.Serializer]


class AutoSchema(BaseAutoSchema):
    def _get_response_bodies(self, direction: Direction = "response") -> _SchemaType:
        responses = super()._get_response_bodies(direction=direction)
        if direction == "response":
            error_responses = {}

            status_codes = self._get_allowed_error_status_codes()
            for status_code in status_codes:
                if self._should_add_error_response(responses, status_code):
                    serializer = self._get_error_response_serializer(status_code)
                    if not serializer:
                        warn(
                            f"drf-standardized-errors: The status code '{status_code}' "
                            "is one of the allowed error status codes in the setting "
                            "'ALLOWED_ERROR_STATUS_CODES'. However, a corresponding "
                            "error response serializer could not be determined. Make "
                            "sure to add one to the 'ERROR_SCHEMAS' setting: this "
                            "setting is a dict where the key is the status code and "
                            "the value is the serializer."
                        )
                        continue
                    error_responses[status_code] = self._get_response_for_code(
                        serializer, status_code
                    )

            return {**error_responses, **responses}
        else:
            # for callbacks (direction=request), we should not add the error responses
            return responses

    def _get_allowed_error_status_codes(self) -> List[str]:
        allowed_status_codes = package_settings.ALLOWED_ERROR_STATUS_CODES or []
        return [str(status_code) for status_code in allowed_status_codes]

    def _should_add_error_response(self, responses: dict, status_code: str) -> bool:
        if (
            self.view.get_exception_handler() is not standardized_errors_handler
            or status_code in responses
        ):
            # this means that the exception handler has been overridden for this view
            # or the error response has already been added via extend_schema, so we
            # should not override that
            return False

        if status_code == "400":
            return (
                self._should_add_parse_error_response()
                or self._should_add_validation_error_response()
            )
        elif status_code == "401":
            return self._should_add_http401_error_response()
        elif status_code == "403":
            return self._should_add_http403_error_response()
        elif status_code == "404":
            return self._should_add_http404_error_response()
        elif status_code == "405":
            return self._should_add_http405_error_response()
        elif status_code == "406":
            return self._should_add_http406_error_response()
        elif status_code == "415":
            return self._should_add_http415_error_response()
        elif status_code == "429":
            return self._should_add_http429_error_response()
        elif status_code == "500":
            return self._should_add_http500_error_response()
        else:
            # user might add extra status codes and their serializers, so we
            # should always add corresponding error responses
            return True

    def _should_add_parse_error_response(self) -> bool:
        parsers = self.view.get_parsers()
        parsers_that_raise_parse_errors = (
            JSONParser,
            MultiPartParser,
            FileUploadParser,
        )
        return any(
            isinstance(parser, parsers_that_raise_parse_errors) for parser in parsers
        )

    def _should_add_validation_error_response(self) -> bool:
        """
        add a validation error response when unsafe methods have a request body
        or when a list view implements filtering with django-filters.
        """

        has_request_body = False
        if self.method in ("PUT", "PATCH", "POST"):
            request_serializer = self.get_request_serializer()
            has_request_body = isinstance(request_serializer, serializers.Field) or (
                inspect.isclass(request_serializer)
                and issubclass(request_serializer, serializers.Field)
            )

        filter_backends = get_django_filter_backends(self.get_filter_backends())
        filter_extensions = [
            OpenApiFilterExtension.get_match(backend) for backend in filter_backends
        ]
        has_filters = any(
            filter_extension.get_schema_operation_parameters(self)
            for filter_extension in filter_extensions
            if filter_extension
        )
        has_extra_validation_errors = bool(self._get_extra_validation_errors())
        return has_request_body or has_filters or has_extra_validation_errors

    def _should_add_http401_error_response(self) -> bool:
        # empty dicts are appended to auth methods if AllowAny or
        # IsAuthenticatedOrReadOnly are in permission classes, so
        # we need to account for that.
        auth_methods = [auth_method for auth_method in self.get_auth() if auth_method]
        return bool(auth_methods)

    def _should_add_http403_error_response(self) -> bool:
        permissions = self.view.get_permissions()
        is_allow_any = len(permissions) == 1 and type(permissions[0]) == AllowAny
        # if the only permission class is IsAuthenticated and there are auth classes
        # in the view, then the error raised is a 401 not a 403 (check implementation
        # of rest_framework.views.APIView.permission_denied)
        is_authenticated = (
            len(permissions) == 1
            and type(permissions[0]) == IsAuthenticated
            and self.view.get_authenticators()
        )
        return bool(permissions) and not is_allow_any and not is_authenticated

    def _should_add_http404_error_response(self) -> bool:
        paginator = self._get_paginator()
        paginator_can_raise_404 = isinstance(
            paginator, (PageNumberPagination, CursorPagination)
        )
        versioning_scheme_can_raise_404 = self.view.versioning_class and issubclass(
            self.view.versioning_class,
            (
                URLPathVersioning,
                NamespaceVersioning,
                HostNameVersioning,
                QueryParameterVersioning,
            ),
        )
        has_path_parameters = bool(
            [
                parameter
                for parameter in self._get_parameters()
                if parameter["in"] == "path"
            ]
        )
        return (
            paginator_can_raise_404
            or versioning_scheme_can_raise_404
            or has_path_parameters
        )

    def _should_add_http405_error_response(self) -> bool:
        # API consumers can at all ties use the wrong method against any endpoint
        return True

    def _should_add_http406_error_response(self) -> bool:
        content_negotiator = self.view.get_content_negotiator()
        return isinstance(content_negotiator, DefaultContentNegotiation) or (
            self.view.versioning_class
            and issubclass(self.view.versioning_class, AcceptHeaderVersioning)
        )

    def _should_add_http415_error_response(self) -> bool:
        """
        This is raised whenever the default content negotiator is unable to
        determine a parser. So, if the view does not have a parser that
        handles everything (media type "*/*"), then this error can be raised.
        """
        content_negotiator = self.view.get_content_negotiator()
        parsers_that_handle_everything = [
            parser for parser in self.view.get_parsers() if parser.media_type == "*/*"
        ]
        return (
            isinstance(content_negotiator, DefaultContentNegotiation)
            and not parsers_that_handle_everything
        )

    def _should_add_http429_error_response(self) -> bool:
        return bool(self.view.get_throttles())

    def _should_add_http500_error_response(self) -> bool:
        # bugs are inevitable
        return True

    def _get_error_response_serializer(self, status_code: str) -> S:
        error_schemas = package_settings.ERROR_SCHEMAS or {}
        error_schemas = {
            str(status_code): schema for status_code, schema in error_schemas.items()
        }
        if serializer := error_schemas.get(status_code):
            return serializer

        # the user did not provide a serializer for the status code so we will
        # fall back to the default error serializers
        if status_code == "400":
            return self._get_http400_serializer()
        else:
            error_serializers = {
                "401": ErrorResponse401Serializer,
                "403": ErrorResponse403Serializer,
                "404": ErrorResponse404Serializer,
                "405": ErrorResponse405Serializer,
                "406": ErrorResponse406Serializer,
                "415": ErrorResponse415Serializer,
                "429": ErrorResponse429Serializer,
                "500": ErrorResponse500Serializer,
            }
            return error_serializers.get(status_code)

    def _get_http400_serializer(self) -> S:
        # using the operation id (which is unique) to generate a unique
        # component name
        operation_id = self.get_operation_id()
        component_name = f"{camelize(operation_id)}ErrorResponse400"

        http400_serializers = {}
        if self._should_add_validation_error_response():
            serializer = self._get_serializer_for_validation_error_response()
            http400_serializers[ValidationErrorEnum.VALIDATION_ERROR.value] = serializer  # type: ignore[attr-defined]
        if self._should_add_parse_error_response():
            serializer = ParseErrorResponseSerializer
            http400_serializers[ClientErrorEnum.CLIENT_ERROR.value] = serializer  # type: ignore[attr-defined]

        return PolymorphicProxySerializer(
            component_name=component_name,
            serializers=http400_serializers,
            resource_type_field_name="type",
        )

    def _get_serializer_for_validation_error_response(self) -> S:
        fields_with_error_codes = self._determine_fields_with_error_codes()
        error_codes_by_field = self._get_validation_error_codes_by_field(
            fields_with_error_codes
        )

        operation_id = self.get_operation_id()
        return get_validation_error_serializer(operation_id, error_codes_by_field)

    def _determine_fields_with_error_codes(self) -> "List[InputDataField]":
        if self.method in ("PUT", "PATCH", "POST"):
            serializer = self.get_request_serializer()
            fields = get_flat_serializer_fields(serializer)
            return get_serializer_fields_with_error_codes(fields)
        else:
            filter_backends = get_django_filter_backends(self.get_filter_backends())
            filter_forms = get_filter_forms(self.view, filter_backends)
            fields_with_error_codes = []
            for form in filter_forms:
                fields = get_form_fields_with_error_codes(form)
                fields_with_error_codes.extend(fields)
            return fields_with_error_codes

    def _get_validation_error_codes_by_field(
        self, data_fields: "List[InputDataField]"
    ) -> Dict[str, Set[str]]:
        # When there are multiple fields with the same name in the list of data_fields,
        # their error codes are combined. This can happen when using a PolymorphicProxySerializer
        error_codes_by_field = defaultdict(set)
        for field in data_fields:
            error_codes_by_field[field.name].update(field.error_codes)

        # add error codes set by the @extend_validation_errors decorator
        extra_errors = self._get_extra_validation_errors()
        for field_name, error_codes in extra_errors.items():
            error_codes_by_field[field_name].update(error_codes)

        return error_codes_by_field

    def _get_extra_validation_errors(self) -> Dict[str, Set[str]]:
        extra_codes_by_field = {}
        validation_errors = get_validation_errors(self.view)
        for field_name, field_errors in validation_errors.items():
            # Get the first encountered error when looping in reverse order.
            # That will return errors defined in child views over ones
            # defined in the parent class.
            for err in reversed(field_errors):
                if err.is_in_scope(self):
                    extra_codes_by_field[field_name] = err.error_codes
                    break

        return extra_codes_by_field

    def _get_examples(
        self, serializer, direction, media_type, status_code=None, extras=None
    ):
        if direction == "response":
            all_examples = (extras or []) + self._get_error_response_examples()
        else:
            all_examples = extras
        return super()._get_examples(
            serializer,
            direction,
            media_type,
            status_code=status_code,
            extras=all_examples,
        )

    def _get_error_response_examples(self) -> List[OpenApiExample]:
        status_codes = set(self._get_allowed_error_status_codes())
        examples = get_error_examples()
        return [
            example
            for example in examples
            if status_codes.intersection(example.status_codes)
        ]
