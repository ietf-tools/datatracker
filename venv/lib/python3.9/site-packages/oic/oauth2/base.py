import copy
import logging
import warnings
from http import cookiejar as cookielib
from http.cookies import CookieError
from http.cookies import SimpleCookie
from typing import Optional
from typing import cast

import requests

from oic.oauth2.exception import NonFatalException
from oic.oauth2.util import set_cookie
from oic.utils.keyio import KeyJar
from oic.utils.sanitize import sanitize
from oic.utils.settings import PyoidcSettings

__author__ = "roland"

logger = logging.getLogger(__name__)


class PBase(object):
    """Class for OAuth2 clients and servers."""

    def __init__(
        self,
        verify_ssl=None,
        keyjar=None,
        client_cert=None,
        timeout=None,
        settings: Optional[PyoidcSettings] = None,
    ):
        """
        Initialize the instance.

        Keyword Args:
            settings
                Instance of :class:`PyoidcSettings` with configuration options.

        Note that the following params are deprecated in favor of settings.
        :param verify_ssl: Control TLS server certificate validation. If set to
            True the certificate is validated against the global settings,
            if set to False, no validation is performed. If set to a filename
            this is used as a certificate bundle in openssl format. If set
            to a directory name this is used as a CA directory in
            the openssl format.
        :param keyjar: A place to keep keys for signing/encrypting messages
                       Creates a default keyjar if not set.
        :param client_cert: local cert to use as client side certificate, as a
            single file (containing the private key and the certificate) or as
            a tuple of both file's path
        :param timeout: Timeout for requests library. Can be specified either as
            a single integer or as a tuple of integers. For more details, refer to
            ``requests`` documentation.

        """
        self.settings = settings or PyoidcSettings()
        if verify_ssl is not None:
            warnings.warn(
                "`verify_ssl` is deprecated, please use `settings` instead if you need to set a non-default value.",
                DeprecationWarning,
                stacklevel=2,
            )
            self.settings.verify_ssl = verify_ssl
        if client_cert is not None:
            warnings.warn(
                "`client_cert` is deprecated, please use `settings` instead if you need to set a non-default value.",
                DeprecationWarning,
                stacklevel=2,
            )
            self.settings.client_cert = client_cert
        if timeout is not None:
            warnings.warn(
                "`timeout` is deprecated, please use `settings` instead if you need to set a non-default value.",
                DeprecationWarning,
                stacklevel=2,
            )
            self.settings.timeout = timeout

        self.keyjar = keyjar or KeyJar(verify_ssl=self.settings.verify_ssl)

        self.cookiejar = cookielib.FileCookieJar()

        # Additional args for the requests library calls
        self.request_args = {
            "allow_redirects": False,
            "cert": self.settings.client_cert,
            "verify": self.settings.verify_ssl,
            "timeout": self.settings.timeout,
        }

        # Event collector, for tracing
        self.events = None
        self.req_callback = None

    def _cookies(self):
        """Turn cookiejar into a dict."""
        cookie_dict = {}

        for _, a in list(self.cookiejar._cookies.items()):  # type: ignore
            for _, b in list(a.items()):
                for cookie in list(b.values()):
                    cookie_dict[cookie.name] = cookie.value

        return cookie_dict

    def http_request(self, url: str, method="GET", **kwargs) -> requests.Response:
        """
        Run a HTTP request to fetch the given url.

        This wraps the requests library, so you can pass
        most requests kwargs to this method to override
        defaults.

        :param url: The URL to fetch
        :param method: The HTTP method to use.
        :param kwargs: Additional keyword arguments to pass through.

        """
        _kwargs = copy.copy(self.request_args)
        _kwargs.update(kwargs)

        if self.cookiejar:
            _kwargs["cookies"] = self._cookies()
            logger.debug("SENT %s COOKIES", len(_kwargs["cookies"]))  # type: ignore

        if self.req_callback is not None:
            _kwargs = self.req_callback(method, url, **_kwargs)

        try:
            req = getattr(self.settings, "requests_session", None) or requests
            r = cast(
                requests.Response,
                req.request(method, url, **_kwargs),
            )
        except Exception as err:
            logger.error(
                "http_request failed: %s, url: %s, htargs: %s, method: %s"
                % (err, url, sanitize(_kwargs), method)
            )
            raise

        if self.events is not None:
            self.events.store("HTTP response", r, ref=url)

        try:
            _cookie = r.headers["set-cookie"]
            logger.debug("RECEIVED COOKIE")
            try:
                set_cookie(self.cookiejar, SimpleCookie(_cookie))
            except CookieError as err:
                logger.error("%s", err)
                raise NonFatalException(r, "{}".format(err))
        except (AttributeError, KeyError):
            pass

        return r

    def send(self, url, method="GET", **kwargs):
        return self.http_request(url, method, **kwargs)

    def load_cookies_from_file(
        self, filename, ignore_discard=False, ignore_expires=False
    ):
        self.cookiejar.load(filename, ignore_discard, ignore_expires)

    def save_cookies_to_file(
        self, filename, ignore_discard=False, ignore_expires=False
    ):
        self.cookiejar.save(filename, ignore_discard, ignore_expires)
