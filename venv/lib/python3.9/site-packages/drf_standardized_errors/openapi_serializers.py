from django.db import models
from rest_framework import serializers


class ValidationErrorEnum(models.TextChoices):
    VALIDATION_ERROR = "validation_error"


class ClientErrorEnum(models.TextChoices):
    CLIENT_ERROR = "client_error"


class ServerErrorEnum(models.TextChoices):
    SERVER_ERROR = "server_error"


class ParseErrorCodeEnum(models.TextChoices):
    PARSE_ERROR = "parse_error"


class ErrorCode401Enum(models.TextChoices):
    AUTHENTICATION_FAILED = "authentication_failed"
    NOT_AUTHENTICATED = "not_authenticated"


class ErrorCode403Enum(models.TextChoices):
    PERMISSION_DENIED = "permission_denied"


class ErrorCode404Enum(models.TextChoices):
    NOT_FOUND = "not_found"


class ErrorCode405Enum(models.TextChoices):
    METHOD_NOT_ALLOWED = "method_not_allowed"


class ErrorCode406Enum(models.TextChoices):
    NOT_ACCEPTABLE = "not_acceptable"


class ErrorCode415Enum(models.TextChoices):
    UNSUPPORTED_MEDIA_TYPE = "unsupported_media_type"


class ErrorCode429Enum(models.TextChoices):
    THROTTLED = "throttled"


class ErrorCode500Enum(models.TextChoices):
    ERROR = "error"


class ValidationErrorSerializer(serializers.Serializer):
    code = serializers.CharField()
    detail = serializers.CharField()
    attr = serializers.CharField()


class ValidationErrorResponseSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=ValidationErrorEnum.choices)
    errors = ValidationErrorSerializer(many=True)


class ParseErrorSerializer(serializers.Serializer):
    code = serializers.ChoiceField(choices=ParseErrorCodeEnum.choices)
    detail = serializers.CharField()
    attr = serializers.CharField(allow_null=True)


class ParseErrorResponseSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=ClientErrorEnum.choices)
    errors = ParseErrorSerializer(many=True)


class Error401Serializer(serializers.Serializer):
    code = serializers.ChoiceField(choices=ErrorCode401Enum.choices)
    detail = serializers.CharField()
    attr = serializers.CharField(allow_null=True)


class ErrorResponse401Serializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=ClientErrorEnum.choices)
    errors = Error401Serializer(many=True)


class Error403Serializer(serializers.Serializer):
    code = serializers.ChoiceField(choices=ErrorCode403Enum.choices)
    detail = serializers.CharField()
    attr = serializers.CharField(allow_null=True)


class ErrorResponse403Serializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=ClientErrorEnum.choices)
    errors = Error403Serializer(many=True)


class Error404Serializer(serializers.Serializer):
    code = serializers.ChoiceField(choices=ErrorCode404Enum.choices)
    detail = serializers.CharField()
    attr = serializers.CharField(allow_null=True)


class ErrorResponse404Serializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=ClientErrorEnum.choices)
    errors = Error404Serializer(many=True)


class Error405Serializer(serializers.Serializer):
    code = serializers.ChoiceField(choices=ErrorCode405Enum.choices)
    detail = serializers.CharField()
    attr = serializers.CharField(allow_null=True)


class ErrorResponse405Serializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=ClientErrorEnum.choices)
    errors = Error405Serializer(many=True)


class Error406Serializer(serializers.Serializer):
    code = serializers.ChoiceField(choices=ErrorCode406Enum.choices)
    detail = serializers.CharField()
    attr = serializers.CharField(allow_null=True)


class ErrorResponse406Serializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=ClientErrorEnum.choices)
    errors = Error406Serializer(many=True)


class Error415Serializer(serializers.Serializer):
    code = serializers.ChoiceField(choices=ErrorCode415Enum.choices)
    detail = serializers.CharField()
    attr = serializers.CharField(allow_null=True)


class ErrorResponse415Serializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=ClientErrorEnum.choices)
    errors = Error415Serializer(many=True)


class Error429Serializer(serializers.Serializer):
    code = serializers.ChoiceField(choices=ErrorCode429Enum.choices)
    detail = serializers.CharField()
    attr = serializers.CharField(allow_null=True)


class ErrorResponse429Serializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=ClientErrorEnum.choices)
    errors = Error429Serializer(many=True)


class Error500Serializer(serializers.Serializer):
    code = serializers.ChoiceField(choices=ErrorCode500Enum.choices)
    detail = serializers.CharField()
    attr = serializers.CharField(allow_null=True)


class ErrorResponse500Serializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=ServerErrorEnum.choices)
    errors = Error500Serializer(many=True)
