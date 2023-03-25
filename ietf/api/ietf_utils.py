# Copyright The IETF Trust 2023, All Rights Reserved

# This is not utils.py because Tastypie implicitly consumes ietf.api.utils.
# See ietf.api.__init__.py for details.

from django.conf import settings

def is_valid_token(endpoint, token):
    # This is where we would consider integration with vault
    # Settings implementation for now.
    if hasattr(settings, "APP_API_TOKENS"):
        token_store = settings.APP_API_TOKENS
        if endpoint in token_store and token in token_store[endpoint]:
            return True
    return False
