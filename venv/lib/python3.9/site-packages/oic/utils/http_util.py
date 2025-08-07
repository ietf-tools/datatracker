import base64
import hashlib
import hmac
import logging
import os
import time
from http import client
from http.cookies import SimpleCookie
from typing import List
from typing import Tuple
from urllib.parse import quote

from jwkest import as_unicode

from oic import rndstr
from oic.exception import ImproperlyConfigured
from oic.exception import UnsupportedMethod
from oic.utils import time_util
from oic.utils.aes import AEAD
from oic.utils.aes import AESError

__author__ = "rohe0002"

logger = logging.getLogger(__name__)

SUCCESSFUL = [200, 201, 202, 203, 204, 205, 206]

CORS_HEADERS = [
    ("Access-Control-Allow-Origin", "*"),
    ("Access-Control-Allow-Methods", "GET"),
    ("Access-Control-Allow-Headers", "Authorization"),
]

OAUTH2_NOCACHE_HEADERS = [("Pragma", "no-cache"), ("Cache-Control", "no-store")]


class Response(object):
    _template = ""
    _status_code = 200
    _content_type = "text/html"
    _mako_template = None
    _mako_lookup = None

    def __init__(self, message=None, **kwargs):
        self.status_code = kwargs.get("status_code", self._status_code)
        self.response = kwargs.get("response", self._response)
        self.template = kwargs.get("template", self._template)
        self.mako_template = kwargs.get("mako_template", self._mako_template)
        self.mako_lookup = kwargs.get("template_lookup", self._mako_lookup)

        self.message = message

        self.headers: List[Tuple[str, str]] = []
        self.headers.extend(kwargs.get("headers", []))
        _content_type = kwargs.get("content", self._content_type)

        self.headers.append(("Content-type", _content_type))

    def _start_response(self, start_response):
        name = client.responses.get(self.status_code, "UNKNOWN")
        start_response("{} {}".format(self.status_code, name), self.headers)

    def __call__(self, environ, start_response, **kwargs):
        self._start_response(start_response)
        return self.response(self.message, **kwargs)

    def _response(self, message="", **argv):
        # Have to be more specific, this might be a bit to much.
        if message:
            try:
                if "<script>" in message:
                    message = message.replace("<script>", "&lt;script&gt;").replace(
                        "</script>", "&lt;/script&gt;"
                    )
            except TypeError:
                if b"<script>" in message:
                    message = message.replace(b"<script>", b"&lt;script&gt;").replace(
                        b"</script>", b"&lt;/script&gt;"
                    )

        if self.template:
            if ("Content-type", "application/json") in self.headers:
                return [message.encode("utf-8")]
            else:
                return [str(self.template % message).encode("utf-8")]
        elif self.mako_lookup and self.mako_template:
            argv["message"] = message
            mte = self.mako_lookup.get_template(self.mako_template)
            return [mte.render(**argv)]
        else:
            if [x for x in self._c_types() if x.startswith("image/")]:
                return [message]
            elif [x for x in self._c_types() if x == "application/x-gzip"]:
                return [message]

            try:
                return [message.encode("utf-8")]
            except AttributeError:
                return [message]

    def info(self):
        return {
            "status_code": self.status_code,
            "headers": self.headers,
            "message": self.message,
        }

    def add_header(self, ava):
        self.headers.append(ava)

    def reply(self, **kwargs):
        return self.response(self.message, **kwargs)

    def _c_types(self):
        return [y for x, y in self.headers if x == "Content-type"]


class Created(Response):
    _status_code = 201


class Accepted(Response):
    _status_code = 202


class NonAuthoritativeInformation(Response):
    _status_code = 203


class NoContent(Response):
    _status_code = 204


class Redirect(Response):
    _template = (
        "<html>\n<head><title>Redirecting to %s</title></head>\n"
        '<body>\nYou are being redirected to <a href="%s">%s</a>\n'
        "</body>\n</html>"
    )
    _status_code = 302

    def __call__(self, environ, start_response, **kwargs):
        location = self.message
        self.headers.append(("location", location))
        self._start_response(start_response)
        return self.response((location, location, location))


class SeeOther(Response):
    _template = (
        "<html>\n<head><title>Redirecting to %s</title></head>\n"
        '<body>\nYou are being redirected to <a href="%s">%s</a>\n'
        "</body>\n</html>"
    )
    _status_code = 303

    def __call__(self, environ, start_response, **kwargs):
        location = self.message
        self.headers.append(("location", location))
        self._start_response(start_response)
        return self.response((location, location, location))


class Forbidden(Response):
    _status_code = 403
    _template = "<html>Not allowed to mess with: '%s'</html>"


class BadRequest(Response):
    _status_code = 400
    _template = "<html>%s</html>"


class Unauthorized(Response):
    _status_code = 401
    _template = "<html>%s</html>"


class NotFound(Response):
    _status_code = 404


class NotSupported(Response):
    _status_code = 405


class NotAcceptable(Response):
    _status_code = 406


class ServiceError(Response):
    _status_code = 500


class InvalidCookieSign(Exception):
    pass


R2C = {
    200: Response,
    201: Created,
    202: Accepted,
    203: NonAuthoritativeInformation,
    204: NoContent,
    302: Redirect,
    303: SeeOther,
    400: BadRequest,
    401: Unauthorized,
    403: Forbidden,
    404: NotFound,
    405: NotSupported,
    406: NotAcceptable,
    500: ServiceError,
}


def factory(code, message, **kwargs):
    return R2C[code](message, **kwargs)


def geturl(environ, query=True, path=True):
    """
    Rebuild a request URL (from PEP 333).

    :param query: Is QUERY_STRING included in URI (default: True)
    :param path: Is path included in URI (default: True)
    """
    url = [environ["wsgi.url_scheme"] + "://"]
    if environ.get("HTTP_HOST"):
        url.append(environ["HTTP_HOST"])
    else:
        url.append(environ["SERVER_NAME"])
        if environ["wsgi.url_scheme"] == "https":
            if environ["SERVER_PORT"] != "443":
                url.append(":" + environ["SERVER_PORT"])
        else:
            if environ["SERVER_PORT"] != "80":
                url.append(":" + environ["SERVER_PORT"])
    if path:
        url.append(getpath(environ))
    if query and environ.get("QUERY_STRING"):
        url.append("?" + environ["QUERY_STRING"])
    return "".join(url)


def getpath(environ):
    """Build a path."""
    return "".join(
        [quote(environ.get("SCRIPT_NAME", "")), quote(environ.get("PATH_INFO", ""))]
    )


def _expiration(timeout, time_format=None):
    if timeout == "now":
        return time_util.instant(time_format)
    else:
        # validity time should match lifetime of assertions
        return time_util.in_a_while(minutes=timeout, time_format=time_format)


def cookie_signature(key, *parts):
    """
    Generate a cookie signature.

    :param key: The HMAC key to use.
    :type key: bytes
    :param parts: List of parts to include in the MAC
    :type parts: list of bytes or strings
    :returns: hexdigest of the HMAC
    """
    assert isinstance(key, bytes)  # nosec
    sha1 = hmac.new(key, digestmod=hashlib.sha1)
    for part in parts:
        if part:
            if isinstance(part, str):
                sha1.update(part.encode("utf-8"))
            else:
                sha1.update(part)
    return str(sha1.hexdigest())


def verify_cookie_signature(sig, key, *parts):
    """
    Constant time verifier for signatures.

    :param sig: The signature hexdigest to check
    :type sig: str
    :param key: The HMAC key to use.
    :type key: bytes
    :param parts: List of parts to include in the MAC
    :type parts: list of bytes or strings
    :raises: `InvalidCookieSign` when the signature is wrong
    """
    assert isinstance(sig, str)  # nosec
    return hmac.compare_digest(sig, cookie_signature(key, *parts))


def _make_hashed_key(parts, hashfunc="sha256"):
    """
    Construct a key via hashing the parts.

    If the parts do not have enough entropy of their own, this doesn't help.
    The size of the hash digest determines the size.
    """
    h = hashlib.new(hashfunc)
    for part in parts:
        if isinstance(part, str):
            part = part.encode("utf-8")
        if part:
            h.update(part)
    return h.digest()


def make_cookie(
    name,
    load,
    seed,
    expire=0,
    domain="",
    path="",
    timestamp="",
    enc_key=None,
    secure=True,
    httponly=True,
    same_site="",
):
    """
    Create and return a cookie.

    The cookie is secured against tampering.

    If you only provide a `seed`, a HMAC gets added to the cookies value
    and this is checked, when the cookie is parsed again.

    If you provide both `seed` and `enc_key`, the cookie gets protected
    by using AEAD encryption. This provides both a MAC over the whole cookie
    and encrypts the `load` in a single step.

    The `seed` and `enc_key` parameters should be byte strings of at least
    16 bytes length each. Those are used as cryptographic keys.

    :param name: Cookie name
    :type name: text
    :param load: Cookie load
    :type load: text
    :param seed: A seed key for the HMAC function
    :type seed: byte string
    :param expire: Number of minutes before this cookie goes stale
    :type expire: int
    :param domain: The domain of the cookie
    :param path: The path specification for the cookie
    :param timestamp: A time stamp
    :type timestamp: text
    :param enc_key: The key to use for cookie encryption.
    :type enc_key: byte string
    :param secure: A secure cookie is only sent to the server with an encrypted request over the
    HTTPS protocol.
    :type enc_key: boolean
    :param httponly: HttpOnly cookies are inaccessible to JavaScript's Document.cookie API
    :type enc_key: boolean
    :param same_site: Whether SameSite (None,Strict or Lax) should be added to the cookie
    :type enc_key: byte string
    :return: A tuple to be added to headers
    """
    cookie: SimpleCookie = SimpleCookie()
    if not timestamp:
        timestamp = str(int(time.time()))

    bytes_load = load.encode("utf-8")
    bytes_timestamp = timestamp.encode("utf-8")

    if enc_key:
        # Make sure the key is 256-bit long, for AES-128-SIV
        #
        # This should go away once we push the keysize requirements up
        # to the top level APIs.
        key = _make_hashed_key((enc_key, seed))

        # Random 128-Bit IV
        iv = os.urandom(16)

        crypt = AEAD(key, iv)

        # timestamp does not need to be encrypted, just MAC'ed,
        # so we add it to 'Associated Data' only.
        crypt.add_associated_data(bytes_timestamp)

        ciphertext, tag = crypt.encrypt_and_tag(bytes_load)
        cookie_payload = [
            bytes_timestamp,
            base64.b64encode(iv),
            base64.b64encode(ciphertext),
            base64.b64encode(tag),
        ]
    else:
        cookie_payload = [
            bytes_load,
            bytes_timestamp,
            cookie_signature(seed, load, timestamp).encode("utf-8"),
        ]

    cookie[name] = (b"|".join(cookie_payload)).decode("utf-8")
    cookie[name]._reserved[str("samesite")] = str("SameSite")  # type: ignore

    if path:
        cookie[name]["path"] = path
    if domain:
        cookie[name]["domain"] = domain
    if expire:
        cookie[name]["expires"] = _expiration(expire, "%a, %d-%b-%Y %H:%M:%S GMT")
    if secure:
        cookie[name]["Secure"] = secure
    if httponly:
        cookie[name]["httponly"] = httponly
    if same_site:
        cookie[name]["SameSite"] = same_site

    return tuple(cookie.output().split(": ", 1))


def parse_cookie(name, seed, kaka, enc_key=None):
    """
    Parse and verify a cookie value.

    Parses a cookie created by `make_cookie` and verifies it has not been tampered with.

    You need to provide the same `seed` and `enc_key`
    used when creating the cookie, otherwise the verification
    fails. See `make_cookie` for details about the verification.

    :param seed: A seed key used for the HMAC signature
    :type seed: bytes
    :param kaka: The cookie
    :param enc_key: The encryption key used.
    :type enc_key: bytes or None
    :raises InvalidCookieSign: When verification fails.
    :return: A tuple consisting of (payload, timestamp) or None if parsing fails
    """
    if not kaka:
        return None

    if isinstance(seed, str):
        seed = seed.encode("utf-8")

    parts = cookie_parts(name, kaka)
    if parts is None:
        return None
    elif len(parts) == 3:
        # verify the cookie signature
        cleartext, timestamp, sig = parts
        if not verify_cookie_signature(sig, seed, cleartext, timestamp):
            raise InvalidCookieSign()
        return cleartext, timestamp
    elif len(parts) == 4:
        # encrypted and signed
        timestamp = parts[0]
        iv = base64.b64decode(parts[1])
        ciphertext = base64.b64decode(parts[2])
        tag = base64.b64decode(parts[3])

        # Make sure the key is 32-Bytes long
        key = _make_hashed_key((enc_key, seed))

        crypt = AEAD(key, iv)
        # timestamp does not need to be encrypted, just MAC'ed,
        # so we add it to 'Associated Data' only.
        crypt.add_associated_data(timestamp.encode("utf-8"))
        try:
            cleartext = crypt.decrypt_and_verify(ciphertext, tag)
        except AESError:
            raise InvalidCookieSign()
        return cleartext.decode("utf-8"), timestamp
    return None


def cookie_parts(name, kaka):
    if not isinstance(kaka, SimpleCookie):
        cookie_obj: SimpleCookie = SimpleCookie(str(kaka))
    else:
        cookie_obj = kaka
    morsel = cookie_obj.get(name)
    if morsel:
        return morsel.value.split("|")
    else:
        return None


def get_post(environ):
    # the environment variable CONTENT_LENGTH may be empty or missing
    try:
        request_body_size = int(environ.get("CONTENT_LENGTH", 0))
    except ValueError:
        request_body_size = 0

    # When the method is POST the query string will be sent
    # in the HTTP request body which is passed by the WSGI server
    # in the file like wsgi.input environment variable.
    text = environ["wsgi.input"].read(request_body_size)
    try:
        text = text.decode("utf-8")
    except AttributeError:
        pass
    return text


def get_or_post(environ):
    _method = environ["REQUEST_METHOD"]

    if _method == "GET":
        data = environ.get("QUERY_STRING", "")
    elif _method == "POST":
        data = get_post(environ)
    else:
        raise UnsupportedMethod(_method)

    return data


def extract_from_request(environ, kwargs=None):
    if kwargs is None:
        kwargs = {}

    request = None
    try:
        request = environ["QUERY_STRING"]
    except KeyError:
        pass
    if not request:
        try:
            request = as_unicode(get_post(environ))
        except KeyError:
            pass
    kwargs["request"] = request
    # authentication information
    try:
        kwargs["authn"] = environ["HTTP_AUTHORIZATION"]
    except KeyError:
        pass
    try:
        kwargs["cookie"] = environ["HTTP_COOKIE"]
    except KeyError:
        pass

    # intended audience
    kwargs["requrl"] = geturl(environ)
    kwargs["url"] = geturl(environ, query=False)
    kwargs["baseurl"] = geturl(environ, query=False, path=False)
    kwargs["path"] = getpath(environ)
    return kwargs


def wsgi_wrapper(environ, start_response, func, **kwargs):
    kwargs = extract_from_request(environ, kwargs)
    args = func(**kwargs)

    try:
        resp, state = args
        return resp(environ, start_response)
    except TypeError:
        resp = args
        return resp(environ, start_response)
    except Exception as err:
        logger.error("%s", err)
        raise


class CookieDealer(object):
    @property
    def srv(self):
        return self._srv

    @srv.setter
    def srv(self, server):
        self._srv = server

    def __init__(self, srv, ttl=5, secure=True, httponly=True):
        self.init_srv(srv)
        # minutes before the interaction should be completed
        self.cookie_ttl = ttl  # N minutes
        self.secure = secure
        self.httponly = httponly

    def init_srv(self, srv):
        if not srv:
            return
        self.srv = srv

        symkey = getattr(self.srv, "symkey", None)
        if symkey is not None and symkey == "":
            msg = "CookieDealer.srv.symkey cannot be an empty value"
            raise ImproperlyConfigured(msg)

        if not getattr(srv, "seed", None):
            setattr(srv, "seed", rndstr().encode("utf-8"))

    def delete_cookie(self, cookie_name=None):
        return self.create_cookie("", "", cookie_name=cookie_name, ttl=-1, kill=True)

    def create_cookie(self, value, typ, cookie_name=None, ttl=-1, kill=False):
        if kill:
            ttl = -1
        elif ttl < 0:
            ttl = self.cookie_ttl
        if cookie_name is None:
            cookie_name = self.srv.cookie_name

        try:
            srvdomain = self.srv.cookie_domain
            cookie_domain = "" if not srvdomain else srvdomain
        except AttributeError:
            cookie_domain = ""

        try:
            srvpath = self.srv.cookie_path
            cookie_path = "" if not srvpath else srvpath
        except AttributeError:
            cookie_path = ""

        timestamp = str(int(time.time()))
        try:
            _msg = "::".join([value, timestamp, typ])
        except TypeError:
            _msg = "::".join([value[0], timestamp, typ])

        cookie = make_cookie(
            cookie_name,
            _msg,
            self.srv.seed,
            expire=ttl,
            domain=cookie_domain,
            path=cookie_path,
            timestamp=timestamp,
            enc_key=self.srv.symkey,
            secure=self.secure,
            httponly=self.httponly,
        )
        return cookie

    def getCookieValue(self, cookie=None, cookie_name=None):
        return self.get_cookie_value(cookie, cookie_name)

    def get_cookie_value(self, cookie=None, cookie_name=None):
        """
        Return information stored in the Cookie.

        :param cookie:
        :param cookie_name: The name of the cookie I'm looking for
        :return: tuple (value, timestamp, type)
        """
        if cookie is None or cookie_name is None:
            return None
        else:
            try:
                info, timestamp = parse_cookie(
                    cookie_name, self.srv.seed, cookie, self.srv.symkey
                )
            except (TypeError, AssertionError):
                return None
            else:
                value, _ts, typ = info.split("::")
                if timestamp == _ts:
                    return value, _ts, typ
        return None
