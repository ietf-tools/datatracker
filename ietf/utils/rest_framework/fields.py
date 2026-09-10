# Copyright The IETF Trust 2026, All Rights Reserved
"""Serializer fields shared across the datatracker's DRF APIs"""

from django.utils import timezone
from rest_framework import serializers


class AwareDateTimeField(serializers.DateTimeField):
    """DateTimeField that requires the value to carry a UTC offset

    DateTimeField applies default_timezone to a value that has none, so an offsetless
    timestamp is silently assigned a zone the caller did not choose. Require the offset
    instead of guessing at it.
    """

    default_error_messages = {  # noqa: RUF012
        "naive": "Datetime must include a UTC offset.",
    }

    def enforce_timezone(self, value):
        # The hook that receives the parsed value while it is still naive; checking
        # after to_internal_value() would be too late, the zone is already applied.
        if timezone.is_naive(value):
            self.fail("naive")
        return super().enforce_timezone(value)
