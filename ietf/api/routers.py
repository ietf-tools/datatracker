# Copyright The IETF Trust 2024, All Rights Reserved
"""Custom django-rest-framework routers"""
from django.core.exceptions import ImproperlyConfigured
from rest_framework import routers


class PrefixedBasenameMixin:
    """Mixin to add a prefix to the basename of a rest_framework BaseRouter"""
    def __init__(self, name_prefix="", *args, **kwargs):
        self.name_prefix = name_prefix
        if len(self.name_prefix) == 0 or self.name_prefix[-1] == ".":
            raise ImproperlyConfigured("Cannot use a name_prefix that is empty or ends with '.'")
        super().__init__(*args, **kwargs)

    def register(self, prefix, viewset, basename=None):
        # Get the superclass "register" method from the class this is mixed-in with.
        # This avoids typing issues with calling super().register() directly in a
        # mixin class.
        super_register = getattr(super(), "register")
        if not super_register or not callable(super_register):
            raise TypeError("Must mixin with superclass that has register() method")
        super_register(prefix, viewset, basename=f"{self.name_prefix}.{basename}")


class PrefixedSimpleRouter(PrefixedBasenameMixin, routers.SimpleRouter):
    """SimpleRouter that adds a dot-separated prefix to its basename"""


class PrefixedDefaultRouter(PrefixedBasenameMixin, routers.DefaultRouter):
    """SimpleRouter that adds a dot-separated prefix to its basename"""

