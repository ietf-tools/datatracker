import logging
import warnings
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple
from typing import Type
from typing import Union
from typing import cast
from urllib.parse import urlparse

import requests
from jwkest import b64e

from oic import CC_METHOD
from oic import OIDCONF_PATTERN
from oic import unreserved
from oic.exception import CommunicationError
from oic.oauth2.base import PBase
from oic.oauth2.exception import GrantError
from oic.oauth2.exception import HttpError
from oic.oauth2.exception import MissingEndpoint
from oic.oauth2.exception import ParseError
from oic.oauth2.exception import ResponseError
from oic.oauth2.exception import TokenError
from oic.oauth2.exception import Unsupported
from oic.oauth2.grant import Grant
from oic.oauth2.grant import Token
from oic.oauth2.message import AccessTokenRequest
from oic.oauth2.message import AccessTokenResponse
from oic.oauth2.message import ASConfigurationResponse
from oic.oauth2.message import AuthorizationErrorResponse
from oic.oauth2.message import AuthorizationRequest
from oic.oauth2.message import AuthorizationResponse
from oic.oauth2.message import CCAccessTokenRequest
from oic.oauth2.message import ErrorResponse
from oic.oauth2.message import ExtensionTokenRequest
from oic.oauth2.message import GrantExpired
from oic.oauth2.message import Message
from oic.oauth2.message import MessageFactory
from oic.oauth2.message import NoneResponse
from oic.oauth2.message import OauthMessageFactory
from oic.oauth2.message import PyoidcError
from oic.oauth2.message import RefreshAccessTokenRequest
from oic.oauth2.message import ResourceRequest
from oic.oauth2.message import ROPCAccessTokenRequest
from oic.oauth2.message import TokenErrorResponse
from oic.oauth2.message import sanitize
from oic.oauth2.util import ENCODINGS
from oic.oauth2.util import get_or_post
from oic.oauth2.util import verify_header
from oic.utils.http_util import BadRequest
from oic.utils.http_util import Response
from oic.utils.http_util import SeeOther
from oic.utils.keyio import KeyJar
from oic.utils.sdb import SessionBackend
from oic.utils.sdb import session_update
from oic.utils.settings import OauthClientSettings
from oic.utils.settings import OauthServerSettings
from oic.utils.settings import PyoidcSettings
from oic.utils.time_util import utc_time_sans_frac

__author__ = "rohe0002"

logger = logging.getLogger(__name__)

DEF_SIGN_ALG = "HS256"
SUCCESSFUL = [200, 201, 202, 203, 204, 205, 206]

Version = "2.0"

HTTP_ARGS = ["headers", "redirections", "connection_type"]

REQUEST2ENDPOINT = {
    "AuthorizationRequest": "authorization_endpoint",
    "AccessTokenRequest": "token_endpoint",
    "ROPCAccessTokenRequest": "token_endpoint",
    "CCAccessTokenRequest": "token_endpoint",
    "RefreshAccessTokenRequest": "token_endpoint",
    "ExtensionTokenRequest": "token_endpoint",
    "TokenRevocationRequest": "token_endpoint",
}

RESPONSE2ERROR: Dict[str, List] = {
    "AuthorizationResponse": [AuthorizationErrorResponse, TokenErrorResponse],
    "AccessTokenResponse": [TokenErrorResponse],
}

ENDPOINTS = ["authorization_endpoint", "token_endpoint", "token_revocation_endpoint"]


class ExpiredToken(PyoidcError):
    pass


# =============================================================================


def error_response(error, descr=None, status_code=400):
    logger.error("%s" % sanitize(error))
    response = ErrorResponse(error=error, error_description=descr)
    return Response(
        response.to_json(), content="application/json", status_code=status_code
    )


def none_response(**kwargs):
    _areq = kwargs["areq"]
    aresp = NoneResponse()
    if "state" in _areq:
        aresp["state"] = _areq["state"]

    return aresp


def authz_error(error, descr=None):
    response = AuthorizationErrorResponse(error=error)
    if descr:
        response["error_description"] = descr

    return Response(response.to_json(), content="application/json", status_code=400)


def redirect_authz_error(error, redirect_uri, descr=None, state="", return_type=None):
    err = AuthorizationErrorResponse(error=error)
    if descr:
        err["error_description"] = descr
    if state:
        err["state"] = state
    if return_type is None or return_type == ["code"]:
        location = err.request(redirect_uri)
    else:
        location = err.request(redirect_uri, True)
    return SeeOther(location)


def exception_to_error_mesg(excep):
    if isinstance(excep, PyoidcError):
        if excep.content_type:
            if isinstance(excep.args, tuple):
                resp = BadRequest(excep.args[0], content=excep.content_type)
            else:
                resp = BadRequest(excep.args, content=excep.content_type)
        else:
            resp = BadRequest()
    else:
        err = ErrorResponse(
            error="service_error",
            error_description="{}:{}".format(excep.__class__.__name__, excep.args),
        )
        resp = BadRequest(err.to_json(), content="application/json")
    return resp


def compact(qsdict):
    res = {}
    for key, val in qsdict.items():
        if len(val) == 1:
            res[key] = val[0]
        else:
            res[key] = val
    return res


# =============================================================================


class Client(PBase):
    _endpoints = ENDPOINTS

    def __init__(
        self,
        client_id=None,
        client_authn_method=None,
        keyjar=None,
        verify_ssl=None,
        config=None,
        client_cert=None,
        timeout=None,
        message_factory: Type[MessageFactory] = OauthMessageFactory,
        settings: Optional[PyoidcSettings] = None,
    ):
        """
        Initialize the instance.

        Keyword Args:
            settings
                Instance of :class:`OauthClientSettings` with configuration options.
                Currently used settings are:
                 - verify_ssl
                 - client_cert
                 - timeout

        :param client_id: The client identifier
        :param client_authn_method: Methods that this client can use to
            authenticate itself. It's a dictionary with method names as
            keys and method classes as values.
        :param keyjar: The keyjar for this client.
        :param verify_ssl: Whether the SSL certificate should be verified. Deprecated in favor of settings.
        :param client_cert: A client certificate to use. Deprecated in favor of settings.
        :param timeout: Timeout for requests library. Can be specified either as
            a single integer or as a tuple of integers. For more details, refer to
            ``requests`` documentation. Deprecated in favor of settings.
        :param: message_factory: Factory for message classes, should inherit from OauthMessageFactory
        :return: Client instance

        """
        self.settings = settings or OauthClientSettings()
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
        PBase.__init__(self, keyjar=keyjar, settings=self.settings)

        self.sso_db: Optional[SessionBackend] = None
        self.client_id = client_id
        self.client_authn_method = client_authn_method

        self.nonce: Optional[str] = None

        self.message_factory = message_factory
        self.grant: Dict[str, Grant] = {}
        self.state2nonce: Dict[str, str] = {}
        # own endpoint
        self.redirect_uris: List[str] = []
        # Default behaviour
        self.response_type = ["code"]

        # service endpoints
        self.authorization_endpoint: Optional[str] = None
        self.token_endpoint: Optional[str] = None
        self.token_revocation_endpoint: Optional[str] = None

        self.request2endpoint = REQUEST2ENDPOINT
        self.response2error: Dict[str, List] = RESPONSE2ERROR
        self.grant_class = Grant
        self.token_class = Token

        self.provider_info: Message = ASConfigurationResponse()
        self._c_secret: str = ""
        self.kid: Dict[str, Dict] = {"sig": {}, "enc": {}}
        self.authz_req: Dict[str, Message] = {}

        # the OAuth issuer is the URL of the authorization server's
        # configuration information location
        self.config = config or {}
        try:
            self.issuer = self.config["issuer"]
        except KeyError:
            self.issuer = ""
        self.allow: Dict[str, Any] = {}

    def store_response(self, clinst, text):
        pass

    def get_client_secret(self) -> str:
        return self._c_secret

    def set_client_secret(self, val: str):
        if not val:
            self._c_secret = ""  # nosec
        else:
            self._c_secret = val
            # client uses it for signing
            # Server might also use it for signing which means the
            # client uses it for verifying server signatures
            if self.keyjar is None:
                self.keyjar = KeyJar()
            self.keyjar.add_symmetric("", str(val))

    client_secret = property(get_client_secret, set_client_secret)

    def reset(self) -> None:
        self.nonce = None

        self.grant = {}

        self.authorization_endpoint = None
        self.token_endpoint = None
        self.redirect_uris = []

    def _parse_args(self, request: Type[Message], **kwargs) -> Dict:
        ar_args = kwargs.copy()

        for prop in request.c_param.keys():
            if prop in ar_args:
                continue
            else:
                if prop == "redirect_uri":
                    _val = getattr(self, "redirect_uris", [None])[0]
                    if _val:
                        ar_args[prop] = _val
                else:
                    _val = getattr(self, prop, None)
                    if _val:
                        ar_args[prop] = _val

        return ar_args

    def _endpoint(self, endpoint: str, **kwargs) -> str:
        try:
            uri = kwargs[endpoint]
            if uri:
                del kwargs[endpoint]
        except KeyError:
            uri = ""

        if not uri:
            try:
                uri = getattr(self, endpoint)
            except Exception:
                raise MissingEndpoint("No '%s' specified" % endpoint)

        if not uri:
            raise MissingEndpoint("No '%s' specified" % endpoint)

        return uri

    def get_grant(self, state: str, **kwargs) -> Grant:
        """
        Get the Grant associated with the given state.

        :param state: The state to check
        :return: The `Grant`.
        :raises GrantError: When the state has no associated grant.
        """
        try:
            return self.grant[state]
        except KeyError:
            raise GrantError("No grant found for state:'%s'" % state)

    def get_token(self, also_expired: bool = False, **kwargs) -> Token:
        """
        Get a specific token.

        :param also_expired: Return tokens that have expired
        :param state: The state associated with the token grant. Optional.
        :param scope: The scope associated with the token. Optional.
        :param token: Pass through the token. Optional.
        :raises TokenError: If no acceptable Token could be found.
        """
        try:
            token = kwargs["token"]
        except KeyError:
            grant = self.get_grant(**kwargs)

            try:
                token = grant.get_token(kwargs["scope"])
            except KeyError:
                token = grant.get_token("")
                if not token:
                    try:
                        token = self.get_grant(kwargs["state"]).get_token("")
                    except (KeyError, GrantError):
                        raise TokenError("No token found for scope")

        if token is None:
            raise TokenError("No suitable token found")

        if also_expired:
            return token
        elif token.is_valid():
            return token
        else:
            raise TokenError("Token has expired")

    def clean_tokens(self) -> None:
        """Clean replaced and invalid tokens."""
        for grant in self.grant.values():
            for token in grant.tokens:
                if token.replaced or not token.is_valid():
                    grant.delete_token(token)

    def construct_request(
        self, request: Type[Message], request_args=None, extra_args=None
    ):
        if request_args is None:
            request_args = {}

        kwargs = self._parse_args(request, **request_args)

        if extra_args:
            kwargs.update(extra_args)
        logger.debug("request: %s" % sanitize(request))
        return request(**kwargs)

    def construct_Message(
        self,
        request: Type[Message] = Message,
        request_args=None,
        extra_args=None,
        **kwargs,
    ) -> Message:
        return self.construct_request(request, request_args, extra_args)

    def construct_AuthorizationRequest(
        self,
        request: Optional[Type[AuthorizationRequest]] = None,
        request_args=None,
        extra_args=None,
        **kwargs,
    ) -> AuthorizationRequest:
        if request is None:
            request = self.message_factory.get_request_type("authorization_endpoint")
        if request_args is not None:
            try:  # change default
                new = request_args["redirect_uri"]
                if new:
                    self.redirect_uris = [new]
            except KeyError:
                pass
        else:
            request_args = {}

        if "client_id" not in request_args:
            request_args["client_id"] = self.client_id
        elif not request_args["client_id"]:
            request_args["client_id"] = self.client_id

        return self.construct_request(request, request_args, extra_args)

    def construct_AccessTokenRequest(
        self,
        request: Optional[
            Union[
                Type[AccessTokenRequest],
                Type[ROPCAccessTokenRequest],
                Type[CCAccessTokenRequest],
                Type[ExtensionTokenRequest],
            ]
        ] = None,
        request_args=None,
        extra_args=None,
        **kwargs,
    ) -> AccessTokenRequest:
        if request is None:
            request = self.message_factory.get_request_type("token_endpoint")
        if request_args is None:
            request_args = {}
        if not issubclass(
            request,
            (
                ROPCAccessTokenRequest,
                CCAccessTokenRequest,
                ExtensionTokenRequest,
            ),
        ):
            grant = self.get_grant(**kwargs)

            if not grant.is_valid():
                raise GrantExpired(
                    "Authorization Code to old %s > %s"
                    % (utc_time_sans_frac(), grant.grant_expiration_time)
                )

            request_args["code"] = grant.code

        try:
            request_args["state"] = kwargs["state"]
        except KeyError:
            pass

        if "grant_type" not in request_args:
            request_args["grant_type"] = "authorization_code"

        if "client_id" not in request_args:
            request_args["client_id"] = self.client_id
        elif not request_args["client_id"]:
            request_args["client_id"] = self.client_id
        return self.construct_request(request, request_args, extra_args)

    def construct_RefreshAccessTokenRequest(
        self,
        request: Optional[Type[RefreshAccessTokenRequest]] = None,
        request_args=None,
        extra_args=None,
        **kwargs,
    ) -> RefreshAccessTokenRequest:
        if request is None:
            request = self.message_factory.get_request_type("refresh_endpoint")
        if request_args is None:
            request_args = {}

        token = self.get_token(also_expired=True, **kwargs)

        request_args["refresh_token"] = token.refresh_token

        try:
            request_args["scope"] = token.scope
        except AttributeError:
            pass

        return self.construct_request(request, request_args, extra_args)

    def construct_ResourceRequest(
        self,
        request: Optional[Type[ResourceRequest]] = None,
        request_args=None,
        extra_args=None,
        **kwargs,
    ) -> ResourceRequest:
        if request is None:
            request = self.message_factory.get_request_type("resource_endpoint")
        if request_args is None:
            request_args = {}

        token = self.get_token(**kwargs)

        request_args["access_token"] = token.access_token
        return self.construct_request(request, request_args, extra_args)

    def uri_and_body(
        self,
        reqmsg: Type[Message],
        cis: Message,
        method="POST",
        request_args=None,
        **kwargs,
    ) -> Tuple[str, str, Dict, Message]:
        if "endpoint" in kwargs and kwargs["endpoint"]:
            uri = kwargs["endpoint"]
        else:
            uri = self._endpoint(self.request2endpoint[reqmsg.__name__], **request_args)

        uri, body, kwargs = get_or_post(uri, method, cis, **kwargs)
        try:
            h_args = {"headers": kwargs["headers"]}
        except KeyError:
            h_args = {}

        return uri, body, h_args, cis

    def request_info(
        self,
        request: Type[Message],
        method="POST",
        request_args=None,
        extra_args=None,
        lax=False,
        **kwargs,
    ) -> Tuple[str, str, Dict, Message]:
        if request_args is None:
            request_args = {}

        try:
            cls = getattr(self, "construct_%s" % request.__name__)
            cis = cls(request_args=request_args, extra_args=extra_args, **kwargs)
        except AttributeError:
            cis = self.construct_request(request, request_args, extra_args)

        if self.events:
            self.events.store("Protocol request", cis)

        if "nonce" in cis and "state" in cis:
            self.state2nonce[cis["state"]] = cis["nonce"]

        cis.lax = lax

        if "authn_method" in kwargs:
            h_arg = self.init_authentication_method(
                cis, request_args=request_args, **kwargs
            )
        else:
            h_arg = None

        if h_arg:
            if "headers" in kwargs.keys():
                kwargs["headers"].update(h_arg["headers"])
            else:
                kwargs["headers"] = h_arg["headers"]

        return self.uri_and_body(request, cis, method, request_args, **kwargs)

    def authorization_request_info(self, request_args=None, extra_args=None, **kwargs):
        return self.request_info(
            self.message_factory.get_request_type("authorization_endpoint"),
            "GET",
            request_args,
            extra_args,
            **kwargs,
        )

    @staticmethod
    def get_urlinfo(info: str) -> str:
        if "?" in info or "#" in info:
            parts = urlparse(info)
            scheme, netloc, path, params, query, fragment = parts[:6]
            # either query of fragment
            if query:
                info = query
            else:
                info = fragment
        return info

    def parse_response(
        self,
        response: Type[Message],
        info: Union[str, Dict] = "",
        sformat: ENCODINGS = "json",
        state: str = "",
        **kwargs,
    ) -> Message:
        """
        Parse a response.

        :param response: Response type
        :param info: The response, can be either in a JSON or an urlencoded
            format
        :param sformat: Which serialization that was used
        :param state: The state
        :param kwargs: Extra key word arguments
        :return: The parsed and to some extend verified response
        """
        _r2e = self.response2error

        if isinstance(info, dict) and sformat != "dict":
            raise TypeError("If info is a dict sformat must be dict")

        if sformat == "urlencoded":
            info = self.get_urlinfo(cast(str, info))

        resp = response().deserialize(info, sformat, **kwargs)
        msg = 'Initial response parsing => "{}"'
        logger.debug(msg.format(sanitize(resp.to_dict())))
        if self.events:
            self.events.store("Response", resp.to_dict())

        if "error" in resp and not isinstance(resp, ErrorResponse):
            resp = None
            errmsgs: List[Any] = []
            try:
                errmsgs = _r2e[response.__name__]
            except KeyError:
                errmsgs = [ErrorResponse]

            try:
                for errmsg in errmsgs:
                    try:
                        resp = errmsg().deserialize(info, sformat)
                        resp.verify()
                        break
                    except Exception:
                        resp = None
            except KeyError:
                pass
        elif resp.only_extras():
            resp = None
        else:
            kwargs["client_id"] = self.client_id
            try:
                kwargs["iss"] = self.provider_info["issuer"]
            except (KeyError, AttributeError):
                if self.issuer:
                    kwargs["iss"] = self.issuer

            if "key" not in kwargs and "keyjar" not in kwargs:
                kwargs["keyjar"] = self.keyjar

            logger.debug("Verify response with {}".format(sanitize(kwargs)))
            verf = resp.verify(**kwargs)

            if not verf:
                logger.error("Verification of the response failed")
                raise PyoidcError("Verification of the response failed")
            if resp.type() == "AuthorizationResponse" and "scope" not in resp:
                try:
                    resp["scope"] = kwargs["scope"]
                except KeyError:
                    pass

        if not resp:
            logger.error("Missing or faulty response")
            raise ResponseError("Missing or faulty response")

        self.store_response(resp, info)

        if isinstance(resp, (AuthorizationResponse, AccessTokenResponse)):
            try:
                _state = resp["state"]
            except (AttributeError, KeyError):
                _state = ""

            if not _state:
                _state = state

            try:
                self.get_grant(_state).update(resp)
            except GrantError:
                self.grant[_state] = self.grant_class(resp=resp)

            if "id_token" in resp and self.sso_db is not None:
                session_update(self.sso_db, _state, "sub", resp["id_token"]["sub"])
                session_update(self.sso_db, _state, "issuer", resp["id_token"]["iss"])
                if "sid" in resp["id_token"]:
                    session_update(self.sso_db, _state, "smid", resp["id_token"]["sid"])
        return resp

    def init_authentication_method(
        self, cis, authn_method, request_args=None, http_args=None, **kwargs
    ):
        if http_args is None:
            http_args = {}
        if request_args is None:
            request_args = {}

        if authn_method:
            return self.client_authn_method[authn_method](self).construct(
                cis, request_args, http_args, **kwargs
            )
        else:
            return http_args

    def parse_request_response(
        self,
        reqresp: requests.Response,
        response: Optional[Type[Message]] = None,
        body_type: Optional[ENCODINGS] = None,
        state="",
        **kwargs,
    ) -> Union[Message, requests.Response]:
        # Handle the early return stuff
        if reqresp.status_code in [302, 303]:  # redirect
            return reqresp
        elif reqresp.status_code == 500:
            logger.error("(%d) %s" % (reqresp.status_code, sanitize(reqresp.text)))
            raise ParseError("ERROR: Something went wrong: %s" % reqresp.text)

        if reqresp.status_code in SUCCESSFUL or (
            reqresp.status_code in [400, 401] and response
        ):
            verified_body_type = verify_header(reqresp, body_type)
        else:
            # Any other error
            logger.error("(%d) %s" % (reqresp.status_code, sanitize(reqresp.text)))
            raise HttpError(
                "HTTP ERROR: %s [%s] on %s"
                % (reqresp.text, reqresp.status_code, reqresp.url)
            )

        # we expect some specific response message type, try to parse it
        if response:
            # Just let the parser throw if we cannot parse it.
            if verified_body_type is None:
                verified_body_type = "urlencoded"

            return self.parse_response(
                response, reqresp.text, verified_body_type, state, **kwargs
            )

        # No one told us what to expect, so try to decode an error response
        if reqresp.status_code in [200, 400, 401]:
            if verified_body_type == "txt":
                body_type = "urlencoded"
            try:
                err = ErrorResponse().deserialize(reqresp.text, method=body_type)
                try:
                    err.verify()
                except PyoidcError:
                    pass
                else:
                    return err
            except Exception:
                logger.exception(
                    "Failed to decode error response (%d) %s",
                    reqresp.status_code,
                    sanitize(reqresp.text),
                )

        return reqresp

    def request_and_return(
        self,
        url: str,
        response: Optional[Type[Message]] = None,
        method="GET",
        body=None,
        body_type: ENCODINGS = "json",
        state: str = "",
        http_args=None,
        **kwargs,
    ):
        """
        Perform a request and return the response.

        :param url: The URL to which the request should be sent
        :param response: Response type
        :param method: Which HTTP method to use
        :param body: A message body if any
        :param body_type: The expected format of the body of the return message.
        :param http_args: Arguments for the HTTP client
        :return: A cls or ErrorResponse instance or the HTTP response instance if no response body was expected.
        """
        # FIXME: Cannot annotate return value as Message since it disrupts all other methods
        if http_args is None:
            http_args = {}

        resp = self.http_request(url, method, data=body, **http_args)

        kwargs.setdefault("keyjar", self.keyjar)

        # Handle older usage, does not match type annotations
        if body_type == "":
            body_type = None

        return self.parse_request_response(resp, response, body_type, state, **kwargs)

    def do_authorization_request(
        self,
        state="",
        body_type="",
        method="GET",
        request_args=None,
        extra_args=None,
        http_args=None,
        **kwargs,
    ) -> AuthorizationResponse:
        request = self.message_factory.get_request_type("authorization_endpoint")
        response_cls = self.message_factory.get_response_type("authorization_endpoint")

        if state:
            try:
                request_args["state"] = state
            except TypeError:
                request_args = {"state": state}

        kwargs["authn_endpoint"] = "authorization"
        url, body, ht_args, csi = self.request_info(
            request, method, request_args, extra_args, **kwargs
        )

        try:
            self.authz_req[request_args["state"]] = csi
        except TypeError:
            pass

        if http_args is None:
            http_args = ht_args
        else:
            http_args.update(ht_args)

        try:
            algs = kwargs["algs"]
        except KeyError:
            algs = {}

        resp = self.request_and_return(
            url,
            response_cls,
            method,
            body,
            body_type,
            state=state,
            http_args=http_args,
            algs=algs,
        )

        if isinstance(resp, Message):
            # FIXME: The Message classes do not have classical attrs
            if resp.type() in RESPONSE2ERROR["AuthorizationResponse"]:  # type: ignore
                resp.state = csi.state  # type: ignore

        return resp

    def do_access_token_request(
        self,
        scope: str = "",
        state: str = "",
        body_type: ENCODINGS = "json",
        method="POST",
        request_args=None,
        extra_args=None,
        http_args=None,
        authn_method="",
        **kwargs,
    ) -> AccessTokenResponse:
        request = self.message_factory.get_request_type("token_endpoint")
        response_cls = self.message_factory.get_response_type("token_endpoint")

        if extra_args is None:
            extra_args = {}
        kwargs["authn_endpoint"] = "token"
        if http_args is not None and "password" in http_args:
            extra_args["password"] = http_args.pop("password")

        # method is default POST
        url, body, ht_args, csi = self.request_info(
            request,
            method=method,
            request_args=request_args,
            extra_args=extra_args,
            scope=scope,
            state=state,
            authn_method=authn_method,
            **kwargs,
        )

        if http_args is None:
            http_args = ht_args
        else:
            http_args.update(ht_args)

        if self.events is not None:
            self.events.store("request_url", url)
            self.events.store("request_http_args", http_args)
            self.events.store("Request", body)

        logger.debug("<do_access_token> URL: %s, Body: %s" % (url, sanitize(body)))
        logger.debug("<do_access_token> response_cls: %s" % response_cls)

        return self.request_and_return(
            url,
            response_cls,
            method,
            body,
            body_type,
            state=state,
            http_args=http_args,
            **kwargs,
        )

    def do_access_token_refresh(
        self,
        state: str = "",
        body_type: ENCODINGS = "json",
        method="POST",
        request_args=None,
        extra_args=None,
        http_args=None,
        authn_method="",
        **kwargs,
    ) -> AccessTokenResponse:
        request = self.message_factory.get_request_type("refresh_endpoint")
        response_cls = self.message_factory.get_response_type("refresh_endpoint")

        token = self.get_token(also_expired=True, state=state, **kwargs)
        kwargs["authn_endpoint"] = "refresh"
        url, body, ht_args, csi = self.request_info(
            request,
            method=method,
            request_args=request_args,
            extra_args=extra_args,
            token=token,
            authn_method=authn_method,
        )

        if http_args is None:
            http_args = ht_args
        else:
            http_args.update(ht_args)

        response = self.request_and_return(
            url,
            response_cls,
            method,
            body,
            body_type,
            state=state,
            http_args=http_args,
            **kwargs,
        )
        if token.replaced:
            grant = self.get_grant(state)
            grant.delete_token(token)
        return response

    def do_any(
        self,
        request: Type[Message],
        endpoint="",
        scope="",
        state="",
        body_type="json",
        method="POST",
        request_args=None,
        extra_args=None,
        http_args=None,
        response: Optional[Type[Message]] = None,
        authn_method="",
    ) -> Message:
        url, body, ht_args, _ = self.request_info(
            request,
            method=method,
            request_args=request_args,
            extra_args=extra_args,
            scope=scope,
            state=state,
            authn_method=authn_method,
            endpoint=endpoint,
        )

        if http_args is None:
            http_args = ht_args
        else:
            http_args.update(ht_args)

        return self.request_and_return(
            url, response, method, body, body_type, state=state, http_args=http_args
        )

    def fetch_protected_resource(
        self, uri, method="GET", headers=None, state="", **kwargs
    ):
        if "token" in kwargs and kwargs["token"]:
            token = kwargs["token"]
            request_args = {"access_token": token}
        else:
            try:
                token = self.get_token(state=state, **kwargs)
            except ExpiredToken:
                # The token is to old, refresh
                self.do_access_token_refresh(state=state)
                token = self.get_token(state=state, **kwargs)
            request_args = {"access_token": token.access_token}

        if headers is None:
            headers = {}

        if "authn_method" in kwargs:
            http_args = self.init_authentication_method(
                request_args=request_args, **kwargs
            )
        else:
            # If nothing defined this is the default
            http_args = self.client_authn_method["bearer_header"](self).construct(
                request_args=request_args
            )

        headers.update(http_args["headers"])

        logger.debug("Fetch URI: %s" % uri)
        return self.http_request(uri, method, headers=headers)

    def add_code_challenge(self):
        """
        PKCE RFC 7636 support.

        :return:
        """
        try:
            cv_len = self.config["code_challenge"]["length"]
        except KeyError:
            cv_len = 64  # Use default

        code_verifier = unreserved(cv_len)
        _cv = code_verifier.encode("ascii")

        try:
            _method = self.config["code_challenge"]["method"]
        except KeyError:
            _method = "S256"

        try:
            _h = CC_METHOD[_method](_cv).digest()
            code_challenge = b64e(_h).decode("ascii")
        except KeyError:
            raise Unsupported("PKCE Transformation method:{}".format(_method))

        # TODO store code_verifier

        return (
            {"code_challenge": code_challenge, "code_challenge_method": _method},
            code_verifier,
        )

    def handle_provider_config(
        self,
        pcr: ASConfigurationResponse,
        issuer: str,
        keys: bool = True,
        endpoints: bool = True,
    ) -> None:
        """
        Deal with Provider Config Response.

        :param pcr: The ProviderConfigResponse instance
        :param issuer: The one I thought should be the issuer of the config
        :param keys: Should I deal with keys
        :param endpoints: Should I deal with endpoints, that is store them as attributes in self.
        """
        if "issuer" in pcr:
            _pcr_issuer = pcr["issuer"]
            if pcr["issuer"].endswith("/"):
                if issuer.endswith("/"):
                    _issuer = issuer
                else:
                    _issuer = issuer + "/"
            else:
                if issuer.endswith("/"):
                    _issuer = issuer[:-1]
                else:
                    _issuer = issuer

            if not self.allow.get("issuer_mismatch", False) and _issuer != _pcr_issuer:
                raise PyoidcError(
                    "provider info issuer mismatch '%s' != '%s'"
                    % (_issuer, _pcr_issuer)
                )

            self.provider_info = pcr
        else:
            _pcr_issuer = issuer

        self.issuer = _pcr_issuer

        if endpoints:
            for key, val in pcr.items():
                if key.endswith("_endpoint"):
                    setattr(self, key, val)

        if keys:
            if self.keyjar is None:
                self.keyjar = KeyJar()

            self.keyjar.load_keys(pcr, _pcr_issuer)

    def provider_config(
        self,
        issuer: str,
        keys: bool = True,
        endpoints: bool = True,
        serv_pattern: str = OIDCONF_PATTERN,
    ) -> ASConfigurationResponse:
        response_cls = self.message_factory.get_response_type("configuration_endpoint")
        if issuer.endswith("/"):
            _issuer = issuer[:-1]
        else:
            _issuer = issuer

        url = serv_pattern % _issuer

        pcr = None
        r = self.http_request(url, allow_redirects=True)
        if r.status_code == 200:
            try:
                pcr = response_cls().from_json(r.text)
            except Exception as e:
                # FIXME: This should catch specific exception from `from_json()`
                _err_txt = "Faulty provider config response: {}".format(e)
                logger.error(sanitize(_err_txt))
                raise ParseError(_err_txt)
        else:
            raise CommunicationError("Trying '%s', status %s" % (url, r.status_code))

        self.store_response(pcr, r.text)
        self.handle_provider_config(pcr, issuer, keys, endpoints)
        return pcr


class Server(PBase):
    """OAuth Server class."""

    def __init__(
        self,
        verify_ssl: Optional[bool] = None,
        keyjar: Optional[KeyJar] = None,
        client_cert: Optional[Union[str, Tuple[str, str]]] = None,
        timeout: Optional[float] = None,
        message_factory: Type[MessageFactory] = OauthMessageFactory,
        settings: Optional[PyoidcSettings] = None,
    ):
        """
        Initialize the server.

        Keyword Args:
            settings
                Instance of :class:`OauthServerSettings` with configuration options.

        """
        self.settings = settings or OauthServerSettings()
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
        super().__init__(keyjar=keyjar, settings=self.settings)
        self.message_factory = message_factory

    @staticmethod
    def parse_url_request(request, url=None, query=None):
        if url:
            parts = urlparse(url)
            query = parts.query

        if isinstance(query, dict):
            req = request(**query)
        else:
            req = request().deserialize(query, "urlencoded")
        req.verify()
        return req

    def parse_authorization_request(
        self, url: Optional[str] = None, query: Optional[dict] = None
    ) -> AuthorizationRequest:
        request = self.message_factory.get_request_type("authorization_endpoint")
        return self.parse_url_request(request, url, query)

    def parse_jwt_request(
        self,
        request: Type[Message] = AuthorizationRequest,
        txt: str = "",
        keyjar: Optional[KeyJar] = None,
        verify: bool = True,
        **kwargs,
    ) -> Message:
        if not keyjar:
            keyjar = self.keyjar

        areq = request().deserialize(txt, "jwt", keyjar=keyjar, verify=verify, **kwargs)
        if verify:
            areq.verify()
        return areq

    def parse_body_request(
        self, request: Type[Message] = AccessTokenRequest, body: Optional[str] = None
    ):
        req = request().deserialize(body, "urlencoded")
        req.verify()
        return req

    def parse_token_request(self, body: Optional[str] = None) -> AccessTokenRequest:
        request = self.message_factory.get_request_type("token_endpoint")
        return self.parse_body_request(request, body)

    def parse_refresh_token_request(
        self, body: Optional[str] = None
    ) -> RefreshAccessTokenRequest:
        request = self.message_factory.get_request_type("refresh_endpoint")
        return self.parse_body_request(request, body)
