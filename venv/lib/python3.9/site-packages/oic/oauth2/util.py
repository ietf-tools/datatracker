import logging
import sys
from http import cookiejar as http_cookiejar
from http.cookiejar import http2time  # type: ignore
from typing import Any
from typing import Dict
from typing import Optional
from urllib.parse import parse_qs
from urllib.parse import urlsplit
from urllib.parse import urlunsplit

from oic.exception import UnSupported
from oic.oauth2.exception import TimeFormatError
from oic.utils.sanitize import sanitize

if sys.version_info >= (3, 8):
    from typing import Literal
else:
    from typing_extensions import Literal

logger = logging.getLogger(__name__)

__author__ = "roland"

URL_ENCODED = "application/x-www-form-urlencoded"
JSON_ENCODED = "application/json"

DEFAULT_POST_CONTENT_TYPE = URL_ENCODED

PAIRS = {
    "port": "port_specified",
    "domain": "domain_specified",
    "path": "path_specified",
}

ATTRS: Dict[str, Any] = {
    "version": None,
    "name": "",
    "value": None,
    "port": None,
    "port_specified": False,
    "domain": "",
    "domain_specified": False,
    "domain_initial_dot": False,
    "path": "",
    "path_specified": False,
    "secure": False,
    "expires": None,
    "discard": True,
    "comment": None,
    "comment_url": None,
    "rest": "",
    "rfc2109": True,
}

# The encodings understood by our Message class
ENCODINGS = Literal["json", "urlencoded", "dict", "jwt", "jwe"]


def get_or_post(
    uri, method, req, content_type=DEFAULT_POST_CONTENT_TYPE, accept=None, **kwargs
):
    """
    Construct HTTP request.

    :param uri:
    :param method:
    :param req:
    :param content_type:
    :param accept:
    :param kwargs:
    :return:
    """
    if method in ["GET", "DELETE"]:
        if req.keys():
            _req = req.copy()
            comp = urlsplit(str(uri))
            if comp.query:
                _req.update(parse_qs(comp.query))

            _query = str(_req.to_urlencoded())
            path = urlunsplit(
                (comp.scheme, comp.netloc, comp.path, _query, comp.fragment)
            )
        else:
            path = uri
        body = None
    elif method in ["POST", "PUT"]:
        path = uri
        if content_type == URL_ENCODED:
            body = req.to_urlencoded()
        elif content_type == JSON_ENCODED:
            body = req.to_json()
        else:
            raise UnSupported("Unsupported content type: '%s'" % content_type)

        header_ext = {"Content-Type": content_type}
        if accept:
            header_ext = {"Accept": accept}

        if "headers" in kwargs.keys():
            kwargs["headers"].update(header_ext)
        else:
            kwargs["headers"] = header_ext
    else:
        raise UnSupported("Unsupported HTTP method: '%s'" % method)

    return path, body, kwargs


def set_cookie(cookiejar, kaka):
    """
    Place a cookie (a http_cookielib.Cookie based on a set-cookie header line) in the cookie jar.

    Always chose the shortest expires time.

    :param cookiejar:
    :param kaka: Cookie
    """
    # default rfc2109=False
    # max-age, httponly
    for cookie_name, morsel in kaka.items():
        std_attr = ATTRS.copy()
        std_attr["name"] = cookie_name
        _tmp = morsel.coded_value
        if _tmp.startswith('"') and _tmp.endswith('"'):
            std_attr["value"] = _tmp[1:-1]
        else:
            std_attr["value"] = _tmp

        std_attr["version"] = 0
        attr = ""
        # copy attributes that have values
        try:
            for attr in morsel.keys():
                if attr in ATTRS:
                    if morsel[attr]:
                        if attr == "expires":
                            std_attr[attr] = http2time(morsel[attr])
                        else:
                            std_attr[attr] = morsel[attr]
                elif attr == "max-age":
                    if morsel[attr]:
                        std_attr["expires"] = http2time(morsel[attr])
        except TimeFormatError:
            # Ignore cookie
            logger.info(
                "Time format error on %s parameter in received cookie"
                % (sanitize(attr),)
            )
            continue

        for att, spec in PAIRS.items():
            if std_attr[att]:
                std_attr[spec] = True

        if std_attr["domain"] and std_attr["domain"].startswith("."):
            std_attr["domain_initial_dot"] = True

        if morsel["max-age"] == 0:
            try:
                cookiejar.clear(
                    domain=std_attr["domain"],
                    path=std_attr["path"],
                    name=std_attr["name"],
                )
            except ValueError:
                pass
        else:
            # Fix for Microsoft cookie error
            if "version" in std_attr:
                try:
                    std_attr["version"] = std_attr["version"].split(",")[0]
                except (TypeError, AttributeError):
                    pass

            new_cookie = http_cookiejar.Cookie(**std_attr)  # type: ignore

            cookiejar.set_cookie(new_cookie)


def match_to_(val, vlist):
    if isinstance(vlist, str):
        if vlist.startswith(val):
            return True
    else:
        for v in vlist:
            if v.startswith(val):
                return True
    return False


def guess_body_type(reqresp):
    """Try to guess the body type of the message from a response object."""
    # try to handle chunked responses.
    if "chunked" not in reqresp.headers.get("transfer-encoding", ""):
        if int(reqresp.headers["content-length"]) == 0:
            return None

    _ctype = reqresp.headers["content-type"]
    if match_to_("application/json", _ctype):
        body_type = "json"
    elif match_to_("application/jwt", _ctype):
        body_type = "jwt"
    elif match_to_("application/jwe", _ctype):
        body_type = "jwe"
    elif match_to_(URL_ENCODED, _ctype):
        body_type = "urlencoded"
    else:
        body_type = None
    return body_type


def verify_header(reqresp, body_type: Optional[ENCODINGS]) -> Optional[ENCODINGS]:
    logger.debug("resp.headers: %s" % (sanitize(reqresp.headers),))
    logger.debug("resp.txt: %s" % (sanitize(reqresp.text),))

    if body_type is None:
        return guess_body_type(reqresp)

    if body_type == "json":
        if not match_to_("application/json", reqresp.headers["content-type"]):
            if match_to_("application/jwt", reqresp.headers["content-type"]):
                body_type = "jwt"
            else:
                raise ValueError(
                    "content-type: %s" % (reqresp.headers["content-type"],)
                )
    elif body_type == "jwt":
        if not match_to_("application/jwt", reqresp.headers["content-type"]):
            raise ValueError(
                "Wrong content-type in header, got: {} expected "
                "'application/jwt'".format(reqresp.headers["content-type"])
            )
    elif body_type == "urlencoded":
        if not match_to_(DEFAULT_POST_CONTENT_TYPE, reqresp.headers["content-type"]):
            if not match_to_("text/plain", reqresp.headers["content-type"]):
                raise ValueError("Wrong content-type")
    else:
        raise ValueError("Unknown return format: %s" % body_type)

    return body_type
