# Copyright The IETF Trust 2026, All Rights Reserved
import hashlib
import secrets

from django.conf import settings
from django.db import models


DEFAULT_TOKEN_LENGTH = 40  # bytes of randomness (actual token is longer due to base64)
MIN_TOKEN_LENGTH = 20


class AppApiToken(models.Model):
    endpoints = models.ManyToManyField("api.KnownApiEndpoint", related_name="tokens")
    token = models.CharField(
        max_length=128,
        unique=True,
        help_text="API token",
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

    def set_token(self, raw_token: str):
        if len(raw_token) < MIN_TOKEN_LENGTH:
            raise ValueError(f"Token must be at least {MIN_TOKEN_LENGTH} characters")
        self.token = self.hash(raw_token)

    @staticmethod
    def hash(token: str):
        """Hash a token for storage / comparison

        Salts the value as a precaution. Tokens will generally be long, high-entropy
        byte strings that are not vulnerable to rainbow table attacks, but this will
        provide some insurance if someone ill-advisedly adds a simple token.
        """
        salt = getattr(settings, "APP_API_TOKEN_SALT_BYTES", b"5a1+Y&+45t`/")
        return hashlib.sha384(salt + token.encode()).hexdigest()

    def validate_new_token(self, token: str):
        if len(token) < MIN_TOKEN_LENGTH:
            raise ValueError(
                f"Token is too short, must be at least {MIN_TOKEN_LENGTH} characters."
            )
        if (
            AppApiToken.objects.filter(token=AppApiToken.hash(token))
            .exclude(pk=self.pk)
            .exists()
        ):
            raise ValueError("Token already exists.")

    @classmethod
    def generate_token(cls) -> str:
        """Generate a default API token"""
        tries = 50  # implausibly large number of collisions
        while tries > 0:
            new_token = secrets.token_urlsafe(DEFAULT_TOKEN_LENGTH)
            new_hash = AppApiToken.hash(new_token)
            if not AppApiToken.objects.filter(token=new_hash).exists():
                return new_token
            tries = tries - 1
        # never expected to reach this
        raise RuntimeError("Unable to generate a unique API token")


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
