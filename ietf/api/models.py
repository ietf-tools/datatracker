# Copyright The IETF Trust 2026, All Rights Reserved
import secrets

from django.db import models


DEFAULT_TOKEN_LENGTH = 40  # bytes of randomness (actual token is longer due to base64)


def _generate_token():
    """Generate a default API token"""
    tries = 50  # implausibly large number of collisions
    while tries > 0:
        new_token = secrets.token_urlsafe(DEFAULT_TOKEN_LENGTH)
        if not AppApiToken.objects.filter(token=new_token).exists():
            return new_token
        tries = tries - 1
    # never expected to reach this
    raise RuntimeError("Unable to generate a unique API token")


class AppApiToken(models.Model):
    endpoints = models.ManyToManyField("api.KnownApiEndpoint", related_name="tokens")
    token = models.CharField(
        max_length=1000,
        unique=True,
        default=_generate_token,
        help_text="API token value",
    )
    client = models.CharField(
        max_length=255, help_text="Brief description of client using the token"
    )
    description = models.TextField(
        blank=True, help_text="Extended description of the purpose of the token"
    )
    enabled = models.BooleanField(
        default=True, help_text="Is bearer of this token allowed access?"
    )

    class Meta:
        verbose_name = "API token"

    def __str__(self) -> str:
        return f"AppApiToken for {self.client}"


class KnownApiEndpoint(models.Model):
    """API endpoint that has or had an API token

    API endpoint names are generated dynamically from view names or explicit tags on
    class-based views and we do not have a registry. This model tracks the endpoint
    names that have had a token assigned.

    Disabling an endpoint here disables access to it by any API key.
    """

    name = models.CharField(max_length=1000, help_text="API endpoint name")
    enabled = models.BooleanField(
        default=True,
        help_text="Are bearers of tokens for this endpoint allowed access?",
    )

    class Meta:
        verbose_name = "API endpoint"

    def __str__(self) -> str:
        return self.name
