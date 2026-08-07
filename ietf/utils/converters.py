# Copyright The IETF Trust 2026, All Rights Reserved
"""URL path converters

Importing this module registers the converters, so import it from any URLconf that names
one.
"""

from django.urls import register_converter
from django.urls.converters import UUIDConverter


class AnyCaseUUIDConverter(UUIDConverter):
    """UUIDConverter that also accepts upper-case hex

    Django's built-in "uuid" converter matches lower case only, so an upper-cased
    identifier would 404 rather than resolve.
    """

    regex = (
        "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
    )


register_converter(AnyCaseUUIDConverter, "anycase_uuid")
