# Copyright The IETF Trust 2026, All Rights Reserved
"""URL path converters

Registered in the root URLconf, not here - Django does not allow registering a converter
twice, so a module-level register_converter() would break as soon as two URLconfs
imported this module.
"""

from django.urls.converters import UUIDConverter


class AnyCaseUUIDConverter(UUIDConverter):
    """UUIDConverter that also accepts upper-case hex

    Django's built-in "uuid" converter matches lower case only, so an upper-cased
    identifier would 404 rather than resolve.
    """

    regex = (
        "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
    )
