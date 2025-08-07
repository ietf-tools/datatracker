from urllib.parse import urlparse

from oic.oauth2.message import REQUIRED_LIST_OF_STRINGS
from oic.oauth2.message import SINGLE_REQUIRED_STRING
from oic.oic.message import SINGLE_REQUIRED_INT
from oic.oic.message import JasonWebToken
from oic.utils.keyio import KeyBundle

__author__ = "roland"


class PrivateKeyJWT(JasonWebToken):
    c_param = JasonWebToken.c_param.copy()
    c_param.update(
        {
            "aud": SINGLE_REQUIRED_STRING,
            "iss": SINGLE_REQUIRED_STRING,
            "sub": SINGLE_REQUIRED_STRING,
            "aud": SINGLE_REQUIRED_STRING,
            "exp": SINGLE_REQUIRED_INT,
            "iat": SINGLE_REQUIRED_INT,
            "jti": SINGLE_REQUIRED_STRING,
        }
    )


def verify_url(url):
    """
    Verify security of URL.

    Hosted on a website with Transport Layer Security (TLS) protection
    (a Hypertext Transfer Protocol – Secure (HTTPS) URI)
    Hosted on the local domain of the client (e.g., http://localhost/)
    Hosted on a client-specific non-remote-protocol URI scheme (e.g., myapp://)

    :param url:
    :return:
    """
    if url.startswith("http://localhost"):
        return True
    else:
        p = urlparse(url)
        if p.scheme == "http":
            return False

    return True


class HeartSoftwareStatement(JasonWebToken):
    c_param = JasonWebToken.c_param.copy()
    c_param.update(
        {
            "redirect_uris": REQUIRED_LIST_OF_STRINGS,
            "grant_types": SINGLE_REQUIRED_STRING,
            "jwks_uri": SINGLE_REQUIRED_STRING,
            "jwks": SINGLE_REQUIRED_STRING,
            "client_name": SINGLE_REQUIRED_STRING,
            "client_uri": SINGLE_REQUIRED_STRING,
        }
    )
    c_allowed_values = {"grant_types": ["authorization_code", "implicit"]}

    def verify(self, **kwargs):
        if "jwks" in self:
            try:
                _keys = self["jwks"]["keys"]
            except KeyError:
                raise SyntaxError('"keys" parameter missing')
            else:
                # will raise an exception if syntax error
                KeyBundle(_keys)
        for param in ["jwks_uri", "client_uri"]:
            verify_url(self[param])

        JasonWebToken.verify(self, **kwargs)
