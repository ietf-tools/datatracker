# Copyright The IETF Trust 2024, All Rights Reserved
#
from drf_spectacular.extensions import OpenApiAuthenticationExtension


class ApiKeyAuthenticationScheme(OpenApiAuthenticationExtension):
    """Authentication scheme extension for the ApiKeyAuthentication

    Used by drf-spectacular when rendering the OpenAPI schema
    """
    target_class = "ietf.api.authentication.ApiKeyAuthentication"
    name = "apiKeyAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey",
            "description": "Shared secret in the X-Api-Key header",
            "name": "X-Api-Key",
            "in": "header",
        }
