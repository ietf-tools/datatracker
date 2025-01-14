# Copyright The IETF Trust 2024, All Rights Reserved

from django.apps import AppConfig


class CommunityConfig(AppConfig):
    name = "ietf.community"

    def ready(self):
        """Initialize the app after the registry is populated"""
        # implicitly connects @receiver-decorated signals
        from . import signals  # pyflakes: ignore
