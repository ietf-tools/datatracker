# Copyright The IETF Trust 2024, All Rights Reserved
"""Custom django-rest-framework routers"""
from django.core.exceptions import ImproperlyConfigured
from rest_framework import routers

class PrefixedSimpleRouter(routers.SimpleRouter):
    """SimpleRouter that adds a dot-separated prefix to its basename"""
    def __init__(self, name_prefix="", *args, **kwargs):
        self.name_prefix = name_prefix
        if len(self.name_prefix) == 0 or self.name_prefix[-1] == ".":
            raise ImproperlyConfigured("Cannot use a name_prefix that is empty or ends with '.'")
        super().__init__(*args, **kwargs)

    def get_default_basename(self, viewset):
        basename = super().get_default_basename(viewset)
        return f"{self.name_prefix}.{basename}"
