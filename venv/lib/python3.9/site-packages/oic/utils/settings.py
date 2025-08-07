"""
Settings for oic objects.

.. CAUTION::
    This part is under development.
    Most of the configuration options are being converted from keyword arguments to settings class.
    Using the settings class is optional for now, but will become a necessity later on.

In order to configure some objects in PyOIDC, you need a settings object.
If you need to add some settings, make sure that you settings class inherits from the appropriate class in this module.

The settings make use of `pydantic-settings <https://docs.pydantic.dev/usage/settings/>`_ library.
It is possible to instance them directly or use environment values to fill the settings.
"""

from typing import Optional
from typing import Tuple
from typing import Union

import requests
from pydantic_settings import BaseSettings


class PyoidcSettings(BaseSettings):
    """Main class for all settings shared among consumer and client."""

    verify_ssl: Union[bool, str] = True
    """
    Control TLS server certificate validation:

    * If set to True the certificate is validated against the global settings,
    * If set to False, no validation is performed.
    * If set to a filename this is used as a certificate bundle in openssl format.
    * If set to a directory name this is used as a CA directory in the openssl format.
    """
    client_cert: Union[None, str, Tuple[str, str]] = None
    """
    Local cert to use as client side certificate.
    Can be a single file (containing the private key and the certificate) or a tuple of both file's path.
    """
    timeout: Union[float, Tuple[float, float]] = 5
    """
    Timeout for requests library.
    Can be specified either as a single float or as a tuple of floats.
    For more details, refer to ``requests`` documentation.
    """


class ClientSettings(PyoidcSettings):
    """Base settings for consumer shared among OAuth 2.0 and OpenID Connect."""

    requests_session: Optional[requests.Session] = None
    """Instance of `requests.Session` with configuration options."""


class OauthClientSettings(ClientSettings):
    """Specific settings for OAuth 2.0 consumer."""


class OicClientSettings(OauthClientSettings):
    """Settings for OpenID Connect Client."""


class OauthConsumerSettings(OauthClientSettings):
    """Settings for OAuth 2.0 client."""


class ServerSettings(PyoidcSettings):
    """Base settings for server shared among OAuth 2.0 and OpenID Connect."""


class OauthServerSettings(ServerSettings):
    """Specific settings for OAuth 2.0 server."""


class OicServerSettings(OauthServerSettings):
    """Specific settings for OpenID Connect server."""


class OauthProviderSettings(OauthServerSettings):
    """Specific settings for OAuth 2.0 provider."""


class OicProviderSettings(OicServerSettings):
    """Specific settings for OpenID Connect provider."""
