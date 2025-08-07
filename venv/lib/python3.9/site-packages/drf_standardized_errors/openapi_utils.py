from dataclasses import dataclass, field as dataclass_field
from typing import Any, Dict, List, Optional, Set, Type, Union

from django import forms
from django.core.validators import (
    DecimalValidator,
    validate_image_file_extension,
    validate_integer,
    validate_ipv4_address,
    validate_ipv6_address,
    validate_ipv46_address,
)
from drf_spectacular.plumbing import (
    force_instance,
    get_view_model,
    is_basic_serializer,
    is_list_serializer,
    is_serializer,
)
from drf_spectacular.utils import OpenApiExample, PolymorphicProxySerializer
from inflection import camelize
from rest_framework import exceptions, serializers
from rest_framework.settings import api_settings as drf_settings
from rest_framework.status import is_client_error
from rest_framework.validators import (
    BaseUniqueForValidator,
    UniqueTogetherValidator,
    UniqueValidator,
)
from rest_framework.views import APIView

from .openapi_serializers import ValidationErrorEnum
from .settings import package_settings


def get_flat_serializer_fields(
    field: Union[serializers.Field, List[serializers.Field]],
    prefix: Optional[str] = None,
) -> "List[InputDataField]":
    """
    return a flat list of serializer fields. The fields list will later be used
    to identify error codes that can be raised by each field. So, it contains
    at least one field representing "non field errors" and accounts properly
    for composite fields by returning 2 fields: one for the errors linked to
    the parent field and another one for errors linked to the child field.
    """
    if not field or getattr(field, "read_only", False):
        return []

    field = force_instance(field)
    if is_list_serializer(field):
        prefix = get_prefix(prefix, field.field_name)
        non_field_errors_name = get_prefix(prefix, drf_settings.NON_FIELD_ERRORS_KEY)
        f = InputDataField(non_field_errors_name, field)
        prefix = get_prefix(prefix, package_settings.LIST_INDEX_IN_API_SCHEMA)
        return [f] + get_flat_serializer_fields(field.child, prefix)
    elif isinstance(field, PolymorphicProxySerializer):
        if isinstance(field.serializers, dict):
            return get_flat_serializer_fields(list(field.serializers.values()), prefix)
        else:
            return get_flat_serializer_fields(field.serializers, prefix)
    elif is_serializer(field):
        prefix = get_prefix(prefix, field.field_name)
        non_field_errors_name = get_prefix(prefix, drf_settings.NON_FIELD_ERRORS_KEY)
        f = InputDataField(non_field_errors_name, field)
        return [f] + get_flat_serializer_fields(list(field.fields.values()), prefix)
    elif isinstance(field, (list, tuple)):
        first, *remaining = field
        return get_flat_serializer_fields(first, prefix) + get_flat_serializer_fields(
            remaining, prefix
        )
    elif hasattr(field, "child"):
        # composite field (List or Dict fields)
        prefix = get_prefix(prefix, field.field_name)
        f = InputDataField(prefix, field)
        if isinstance(field, serializers.ListField):
            child_prefix = get_prefix(prefix, package_settings.LIST_INDEX_IN_API_SCHEMA)
        else:
            child_prefix = get_prefix(prefix, package_settings.DICT_KEY_IN_API_SCHEMA)
        return [f] + get_flat_serializer_fields(field.child, child_prefix)
    else:
        name = get_prefix(prefix, field.field_name)
        return [InputDataField(name, field)]


def get_prefix(prefix: Optional[str], name: str) -> str:
    if prefix and name:
        return f"{prefix}{package_settings.NESTED_FIELD_SEPARATOR}{name}"
    elif prefix:
        return prefix
    else:
        return name


def get_serializer_fields_with_error_codes(
    serializer_fields: "List[InputDataField]",
) -> "List[InputDataField]":
    fields_with_error_codes = []
    for sfield in serializer_fields:
        if error_codes := get_serializer_field_error_codes(sfield.field, sfield.name):
            sfield.error_codes = error_codes
            fields_with_error_codes.append(sfield)

    # add error codes that correspond to unique together and unique for date validators
    sfields_with_unique_together_validators = [
        sfield
        for sfield in fields_with_error_codes
        if is_basic_serializer(sfield.field)
        and has_validator(sfield.field, UniqueTogetherValidator)
    ]
    add_unique_together_error_codes(
        sfields_with_unique_together_validators, fields_with_error_codes
    )

    sfields_with_unique_for_validators = [
        sfield
        for sfield in fields_with_error_codes
        if is_basic_serializer(sfield.field)
        and has_validator(sfield.field, BaseUniqueForValidator)
    ]
    add_unique_for_error_codes(
        sfields_with_unique_for_validators, fields_with_error_codes
    )

    return fields_with_error_codes


def get_serializer_field_error_codes(field: serializers.Field, attr: str) -> Set[str]:
    if field.read_only or isinstance(field, serializers.HiddenField):
        return set()

    error_codes = set()
    if field.required:
        error_codes.add("required")
    if not field.allow_null:
        error_codes.add("null")
    if (
        hasattr(field, "allow_blank")
        and not field.allow_blank
        and not isinstance(field, serializers.ChoiceField)
    ):
        error_codes.add("blank")
    if getattr(field, "max_digits", None) is not None:
        error_codes.add("max_digits")
    if getattr(field, "decimal_places", None) is not None:
        error_codes.add("max_decimal_places")
    if getattr(field, "max_whole_digits", None) is not None:
        error_codes.add("max_whole_digits")
    if isinstance(field, serializers.DateTimeField):
        field_timezone = getattr(field, "timezone", field.default_timezone())
        if field_timezone is not None:
            error_codes.update(["overflow", "make_aware"])
    if (hasattr(field, "allow_empty") and not field.allow_empty) or (
        hasattr(field, "allow_empty_file") and not field.allow_empty_file
    ):
        error_codes.add("empty")
    if isinstance(field, serializers.FileField) and field.max_length is not None:
        error_codes.add("max_length")
    if isinstance(field, serializers.IPAddressField) and field.protocol in (
        "both",
        "ipv6",
    ):
        error_codes.add("invalid")

    # identify error codes based on DRF and django built-in validators
    error_codes.update(get_error_codes_from_validators(field))
    if has_validator(field, UniqueValidator):
        error_codes.add("unique")

    error_codes_with_specific_conditions = [
        "required",
        "null",
        "blank",
        "max_length",
        "min_length",
        "max_value",
        "min_value",
        "max_digits",
        "max_decimal_places",
        "max_whole_digits",
        "overflow",
        "make_aware",
        "empty",
        # for slug field, "invalid_unicode" is added to error_messages but it is
        # not set as the validator code. "invalid" is the code used instead.
        "invalid_unicode",
    ]
    fields_where_invalid_is_enforced_by_validators = (
        serializers.EmailField,
        serializers.RegexField,
        serializers.SlugField,
        serializers.URLField,
        serializers.IPAddressField,
    )
    if isinstance(field, fields_where_invalid_is_enforced_by_validators):
        # the "invalid" error code is enforced by a validator and is also added
        # to error messages, so it should not be added automatically to error codes
        error_codes_with_specific_conditions.append("invalid")

    remaining_error_codes = set(field.error_messages).difference(
        error_codes_with_specific_conditions
    )
    error_codes.update(remaining_error_codes)

    # for top-level (as opposed to nested) serializer non_field_errors,
    # "required" and "null" errors are not raised
    if attr == drf_settings.NON_FIELD_ERRORS_KEY:
        error_codes = set(error_codes).difference(["required"])

    # for ManyRelatedFields, add the error codes from the child_relation
    # to the parent error codes. That's because DRF raises child_relation
    # errors as if raised by the parent (which is a different behavior
    # from ListSerializer and ListField). For example, ManyRelatedField
    # would return the errors like this:
    # {'zones': [ErrorDetail(string='Invalid pk "0" - object does not exist.', code='does_not_exist')]}
    # while ListField returns them like this:
    # {'zones': {0: [ErrorDetail(string='A valid integer is required.', code='invalid')]}}
    if isinstance(field, serializers.ManyRelatedField):
        # required and null are added depending on the ManyRelatedField definition
        child_error_codes = set(field.child_relation.error_messages).difference(
            ["required", "null"]
        )
        error_codes.update(child_error_codes)

    return error_codes


def add_unique_together_error_codes(
    sfields_with_unique_together_validators: "List[InputDataField]",
    sfields_with_error_codes: "List[InputDataField]",
) -> None:
    for sfield in sfields_with_unique_together_validators:
        sfield.error_codes.add("unique")
        unique_together_validators = [
            validator
            for validator in sfield.field.validators
            if isinstance(validator, UniqueTogetherValidator)
        ]
        # fields involved in a unique together constraint have an implied
        # "required" state, so we're adding the "required" error code to them
        implicitly_required_fields = set()
        for validator in unique_together_validators:
            implicitly_required_fields.update(validator.fields)
        for field in implicitly_required_fields:
            add_error_code(sfield.name, field, "required", sfields_with_error_codes)


def add_unique_for_error_codes(
    sfields_with_unique_for_validators: "List[InputDataField]",
    sfields_with_error_codes: "List[InputDataField]",
) -> None:
    for sfield in sfields_with_unique_for_validators:
        unique_for_validators = [
            validator
            for validator in sfield.field.validators
            if isinstance(validator, BaseUniqueForValidator)
        ]
        for v in unique_for_validators:
            add_error_code(
                sfield.name, v.date_field, "required", sfields_with_error_codes
            )
            add_error_code(sfield.name, v.field, "required", sfields_with_error_codes)
            add_error_code(sfield.name, v.field, "unique", sfields_with_error_codes)


def add_error_code(
    attr: str, field_name: str, error_code: str, sfields: "List[InputDataField]"
) -> None:
    """
    To add the error code to the right serializer field, we need to
    determine the full field name taking into account nested serializers.
    attr ends with drf_settings.NON_FIELD_ERRORS_KEY, so we remove that
    and replace it with the field_name.
    """
    parts = attr.split(package_settings.NESTED_FIELD_SEPARATOR)
    parts[-1] = field_name
    full_field_name = package_settings.NESTED_FIELD_SEPARATOR.join(parts)

    for sfield in sfields:
        if sfield.name == full_field_name:
            sfield.error_codes.add(error_code)
            break


def get_filter_forms(view: APIView, filter_backends: list) -> List[forms.Form]:
    filter_forms = []
    for backend in filter_backends:
        model = get_view_model(view)
        if not model:
            continue
        filterset = backend.get_filterset(
            view.request, model._default_manager.none(), view
        )
        if filterset:
            filter_forms.append(filterset.form)
    return filter_forms


def get_form_fields_with_error_codes(form: forms.Form) -> "List[InputDataField]":
    data_fields = []
    for field_name, field in form.fields.items():
        error_codes = set()
        fields = get_form_fields(field)
        for f in fields:
            error_codes.update(get_form_field_error_codes(f))
        if error_codes:
            data_fields.append(InputDataField(field_name, field, error_codes))
    return data_fields


def get_form_fields(field: Union[forms.Field, List[forms.Field]]) -> List[forms.Field]:
    if not field:
        return []

    if isinstance(field, (list, tuple)):
        first, *rest = field
        return get_form_fields(first) + get_form_fields(rest)
    elif isinstance(field, (forms.ComboField, forms.MultiValueField)):
        return [field] + get_form_fields(field.fields)
    else:
        return [field]


def get_form_field_error_codes(field: forms.Field) -> Set[str]:
    if field.disabled:
        return set()

    error_codes = set()
    if field.required:
        error_codes.add("required")
    if isinstance(field, forms.FileField) and field.max_length is not None:
        error_codes.add("max_length")
    if isinstance(field, forms.FileField) and not field.allow_empty_file:
        error_codes.add("empty")
    if isinstance(field, forms.GenericIPAddressField):
        # because to_python calls clean_ipv6_address which can raise an error
        # with this code
        error_codes.add("invalid")

    # add the error codes of built-in django validators
    error_codes.update(get_error_codes_from_validators(field))

    # add the error codes defined in error_messages after excluding the ones
    # that are conditionally raised
    error_codes_with_specific_conditions = ["required", "max_length", "empty"]
    remaining_error_codes = set(field.error_messages).difference(
        error_codes_with_specific_conditions
    )
    error_codes.update(remaining_error_codes)

    # the "missing" error code is defined but never used by FileField
    # the "incomplete" error code is not used when raising the related
    # ValidationError in forms.MultiValueField
    return error_codes.difference(["missing", "incomplete"])


def has_validator(
    field: Union[serializers.Field, forms.Field], validator: Type
) -> bool:
    return any(isinstance(v, validator) for v in field.validators)


def get_error_codes_from_validators(
    field: Union[serializers.Field, forms.Field]
) -> Set[str]:
    error_codes = set()

    for validator in field.validators:
        if code := getattr(validator, "code", None):
            error_codes.add(code)

    if validators := [v for v in field.validators if isinstance(v, DecimalValidator)]:
        validator = validators[0]
        if validator.max_digits is not None:
            error_codes.add("max_digits")
        if validator.decimal_places is not None:
            error_codes.add("max_decimal_places")
        if validator.decimal_places is not None and validator.max_digits is not None:
            error_codes.add("max_whole_digits")

    if (
        validate_ipv4_address in field.validators
        or validate_ipv6_address in field.validators
        or validate_ipv46_address in field.validators
        or validate_integer in field.validators
    ):
        error_codes.add("invalid")

    if validate_image_file_extension in field.validators:
        error_codes.add("invalid_extension")

    return error_codes


def get_validation_error_serializer(
    operation_id: str, error_codes_by_field: Dict[str, Set[str]]
) -> Type[serializers.Serializer]:
    validation_error_component_name = f"{camelize(operation_id)}ValidationError"
    errors_component_name = f"{camelize(operation_id)}Error"

    sub_serializers = {
        field_name: get_error_serializer(operation_id, field_name, error_codes)
        for field_name, error_codes in error_codes_by_field.items()
    }

    class ValidationErrorSerializer(serializers.Serializer):
        type = serializers.ChoiceField(choices=ValidationErrorEnum.choices)
        errors = PolymorphicProxySerializer(
            component_name=errors_component_name,
            resource_type_field_name="attr",
            serializers=sub_serializers,
            many=True,
        )

        class Meta:
            ref_name = validation_error_component_name

    return ValidationErrorSerializer


def get_error_serializer(
    operation_id: str, attr: Optional[str], error_codes: Set[str]
) -> Type[serializers.Serializer]:
    attr_kwargs: Dict[str, Any] = {"choices": [(attr, attr)]}
    if not attr:
        attr_kwargs["allow_null"] = True
    error_code_choices = sorted(zip(error_codes, error_codes))

    camelcase_operation_id = camelize(operation_id)
    attr_with_underscores = (attr or "").replace(
        package_settings.NESTED_FIELD_SEPARATOR, "_"
    )
    camelcase_attr = camelize(attr_with_underscores)
    suffix = package_settings.ERROR_COMPONENT_NAME_SUFFIX
    component_name = f"{camelcase_operation_id}{camelcase_attr}{suffix}"

    class ErrorSerializer(serializers.Serializer):
        attr = serializers.ChoiceField(**attr_kwargs)
        code = serializers.ChoiceField(choices=error_code_choices)
        detail = serializers.CharField()

        class Meta:
            ref_name = component_name

    return ErrorSerializer


@dataclass
class InputDataField:
    name: str
    field: Union[serializers.Field, forms.Field]
    error_codes: Set[str] = dataclass_field(default_factory=set)


def get_django_filter_backends(backends: list) -> list:
    """determine django filter backends that raise validation errors"""
    try:
        from django_filters.rest_framework import DjangoFilterBackend
    except ImportError:
        return []

    filter_backends = [filter_backend() for filter_backend in backends]
    return [
        backend
        for backend in filter_backends
        if isinstance(backend, DjangoFilterBackend) and backend.raise_exception
    ]


def get_error_examples() -> List[OpenApiExample]:
    """
    error examples for media type "application/json". The main reason for
    adding them is that they will show `"attr": null` instead of the
    auto-generated `"attr": "string"`
    """
    errors = [
        exceptions.AuthenticationFailed(),
        exceptions.NotAuthenticated(),
        exceptions.PermissionDenied(),
        exceptions.NotFound(),
        exceptions.MethodNotAllowed("get"),
        exceptions.NotAcceptable(),
        exceptions.UnsupportedMediaType("application/json"),
        exceptions.Throttled(),
        exceptions.APIException(),
    ]
    return [get_example_from_exception(error) for error in errors]


def get_example_from_exception(exc: exceptions.APIException) -> OpenApiExample:
    if is_client_error(exc.status_code):
        type_ = "client_error"
    else:
        type_ = "server_error"
    return OpenApiExample(
        exc.__class__.__name__,
        value={
            "type": type_,
            "errors": [{"code": exc.get_codes(), "detail": exc.detail, "attr": None}],
        },
        response_only=True,
        status_codes=[str(exc.status_code)],
    )
