import hashlib
import logging
import os
import warnings
from base64 import b64encode
from json import JSONDecodeError
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple
from typing import Type
from typing import Union
from typing import cast
from urllib.parse import parse_qs
from urllib.parse import urlparse

from jwkest import BadSyntax
from jwkest import as_bytes
from jwkest import jwe
from jwkest import jws
from jwkest import jwt
from jwkest.jwe import JWE
from requests import ConnectionError

from oic import oauth2
from oic import rndstr
from oic.exception import AccessDenied
from oic.exception import AuthnToOld
from oic.exception import AuthzError
from oic.exception import CommunicationError
from oic.exception import MissingParameter
from oic.exception import ParameterError
from oic.exception import PyoidcError
from oic.exception import RegistrationError
from oic.exception import RequestError
from oic.exception import SubMismatch
from oic.oauth2 import HTTP_ARGS
from oic.oauth2 import authz_error
from oic.oauth2.consumer import ConfigurationError
from oic.oauth2.exception import MissingRequiredAttribute
from oic.oauth2.exception import OtherError
from oic.oauth2.exception import ParseError
from oic.oauth2.message import ErrorResponse
from oic.oauth2.message import Message
from oic.oauth2.message import MessageFactory
from oic.oauth2.message import WrongSigningAlgorithm
from oic.oauth2.util import get_or_post
from oic.oic.message import SCOPE2CLAIMS
from oic.oic.message import AccessTokenResponse
from oic.oic.message import AuthorizationErrorResponse
from oic.oic.message import AuthorizationRequest
from oic.oic.message import AuthorizationResponse
from oic.oic.message import Claims
from oic.oic.message import ClaimsRequest
from oic.oic.message import ClientRegistrationErrorResponse
from oic.oic.message import EndSessionRequest
from oic.oic.message import IdToken
from oic.oic.message import JasonWebToken
from oic.oic.message import OIDCMessageFactory
from oic.oic.message import OpenIDRequest
from oic.oic.message import OpenIDSchema
from oic.oic.message import RefreshSessionRequest
from oic.oic.message import RegistrationRequest
from oic.oic.message import RegistrationResponse
from oic.oic.message import TokenErrorResponse
from oic.oic.message import UserInfoErrorResponse
from oic.oic.message import UserInfoRequest
from oic.utils import time_util
from oic.utils.http_util import Response
from oic.utils.keyio import KeyJar
from oic.utils.sanitize import sanitize
from oic.utils.settings import OicClientSettings
from oic.utils.settings import OicServerSettings
from oic.utils.settings import PyoidcSettings
from oic.utils.webfinger import OIC_ISSUER
from oic.utils.webfinger import WebFinger

__author__ = "rohe0002"

logger = logging.getLogger(__name__)

ENDPOINTS = [
    "authorization_endpoint",
    "token_endpoint",
    "userinfo_endpoint",
    "refresh_session_endpoint",
    "end_session_endpoint",
    "registration_endpoint",
    "check_id_endpoint",
]

RESPONSE2ERROR: Dict[str, List] = {
    "AuthorizationResponse": [AuthorizationErrorResponse, TokenErrorResponse],
    "AccessTokenResponse": [TokenErrorResponse],
    "IdToken": [ErrorResponse],
    "RegistrationResponse": [ClientRegistrationErrorResponse],
    "OpenIDSchema": [UserInfoErrorResponse],
}

REQUEST2ENDPOINT = {
    "AuthorizationRequest": "authorization_endpoint",
    "OpenIDRequest": "authorization_endpoint",
    "AccessTokenRequest": "token_endpoint",
    "RefreshAccessTokenRequest": "token_endpoint",
    "UserInfoRequest": "userinfo_endpoint",
    "CheckSessionRequest": "check_session_endpoint",
    "CheckIDRequest": "check_id_endpoint",
    "EndSessionRequest": "end_session_endpoint",
    "RefreshSessionRequest": "refresh_session_endpoint",
    "RegistrationRequest": "registration_endpoint",
    "RotateSecret": "registration_endpoint",
    # ---
    "ResourceRequest": "resource_endpoint",
    "TokenIntrospectionRequest": "introspection_endpoint",
    "TokenRevocationRequest": "revocation_endpoint",
    "ROPCAccessTokenRequest": "token_endpoint",
}

# -----------------------------------------------------------------------------

JWT_BEARER = "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
SAML2_BEARER_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:saml2-bearer"

# This should probably be part of the configuration
MAX_AUTHENTICATION_AGE = 86400
DEF_SIGN_ALG = {
    "id_token": "RS256",
    "openid_request_object": "RS256",
    "client_secret_jwt": "HS256",
    "private_key_jwt": "RS256",
}

# -----------------------------------------------------------------------------
ACR_LISTS = [["0", "1", "2", "3", "4"]]


def verify_acr_level(req, level):
    if req is None:
        return level
    elif "values" in req:
        for _r in req["values"]:
            for alist in ACR_LISTS:
                try:
                    if alist.index(_r) <= alist.index(level):
                        return level
                except ValueError:
                    pass
    else:  # Required or Optional
        return level

    raise AccessDenied("", req)


def deser_id_token(inst, txt=""):
    if not txt:
        return None
    else:
        return IdToken().from_jwt(txt, keyjar=inst.keyjar)


# -----------------------------------------------------------------------------
def make_openid_request(
    arq,
    keys=None,
    userinfo_claims=None,
    idtoken_claims=None,
    request_object_signing_alg=None,
    **kwargs,
):
    """
    Construct the specification of what I want returned.

    The request will be signed.

    :param arq: The Authorization request
    :param keys: Keys to use for signing/encrypting
    :param userinfo_claims: UserInfo claims
    :param idtoken_claims: IdToken claims
    :param request_object_signing_alg: Which signing algorithm to use
    :return: JWT encoded OpenID request
    """
    oir_args = {}
    for prop in OpenIDRequest.c_param.keys():
        try:
            oir_args[prop] = arq[prop]
        except KeyError:
            pass

    for attr in ["scope", "response_type"]:
        if attr in oir_args:
            oir_args[attr] = " ".join(oir_args[attr])

    c_args = {}
    if userinfo_claims is not None:
        # UserInfoClaims
        c_args["userinfo"] = Claims(**userinfo_claims)

    if idtoken_claims is not None:
        # IdTokenClaims
        c_args["id_token"] = Claims(**idtoken_claims)

    if c_args:
        oir_args["claims"] = ClaimsRequest(**c_args)

    oir = OpenIDRequest(**oir_args)

    return oir.to_jwt(key=keys, algorithm=request_object_signing_alg)


class Token(oauth2.Token):
    pass


class Grant(oauth2.Grant):
    _authz_resp = AuthorizationResponse
    _acc_resp = AccessTokenResponse
    _token_class = Token

    def add_token(self, resp):
        tok = self._token_class(resp)
        if tok.access_token:
            self.tokens.append(tok)
        else:
            _tmp = getattr(tok, "id_token", None)
            if _tmp:
                self.tokens.append(tok)


PREFERENCE2PROVIDER = {
    "request_object_signing_alg": "request_object_signing_alg_values_supported",
    "request_object_encryption_alg": "request_object_encryption_alg_values_supported",
    "request_object_encryption_enc": "request_object_encryption_enc_values_supported",
    "userinfo_signed_response_alg": "userinfo_signing_alg_values_supported",
    "userinfo_encrypted_response_alg": "userinfo_encryption_alg_values_supported",
    "userinfo_encrypted_response_enc": "userinfo_encryption_enc_values_supported",
    "id_token_signed_response_alg": "id_token_signing_alg_values_supported",
    "id_token_encrypted_response_alg": "id_token_encryption_alg_values_supported",
    "id_token_encrypted_response_enc": "id_token_encryption_enc_values_supported",
    "default_acr_values": "acr_values_supported",
    "subject_type": "subject_types_supported",
    "token_endpoint_auth_method": "token_endpoint_auth_methods_supported",
    "token_endpoint_auth_signing_alg": "token_endpoint_auth_signing_alg_values_supported",
    "response_types": "response_types_supported",
    "grant_types": "grant_types_supported",
}

PROVIDER2PREFERENCE = dict([(v, k) for k, v in PREFERENCE2PROVIDER.items()])

PROVIDER_DEFAULT = {
    "token_endpoint_auth_method": "client_secret_basic",
    "id_token_signed_response_alg": "RS256",
}

PARAMMAP = {
    "sign": "%s_signed_response_alg",
    "alg": "%s_encrypted_response_alg",
    "enc": "%s_encrypted_response_enc",
}

rt2gt = {
    "code": ["authorization_code"],
    "id_token": ["implicit"],
    "id_token token": ["implicit"],
    "code id_token": ["authorization_code", "implicit"],
    "code token": ["authorization_code", "implicit"],
    "code id_token token": ["authorization_code", "implicit"],
}


def response_types_to_grant_types(resp_types, **kwargs):
    _res = set()

    if "grant_types" in kwargs:
        _res.update(set(kwargs["grant_types"]))

    for response_type in resp_types:
        _rt = response_type.split(" ")
        _rt.sort()
        try:
            _gt = rt2gt[" ".join(_rt)]
        except KeyError:
            raise ValueError("No such response type combination: {}".format(resp_types))
        else:
            _res.update(set(_gt))

    return list(_res)


def claims_match(value, claimspec):
    """
    Implement matching according to section 5.5.1 of http://openid.net/specs/openid-connect-core-1_0.html.

    The lack of value is not checked here.
    Also the text doesn't prohibit having both 'value' and 'values'.

    :param value: single value or list of values
    :param claimspec: None or dictionary with 'essential', 'value' or 'values'
    as key
    :return: Boolean
    """
    if claimspec is None:  # match anything
        return True

    matched = False
    for key, val in claimspec.items():
        if key == "value":
            if value == val:
                matched = True
        elif key == "values":
            if value in val:
                matched = True
        elif key == "essential":
            # Whether it's essential or not doesn't change anything here
            continue

        if matched:
            break

    if matched is False:
        if list(claimspec.keys()) == ["essential"]:
            return True

    return matched


class Client(oauth2.Client):
    _endpoints = ENDPOINTS

    def __init__(
        self,
        client_id=None,
        client_prefs=None,
        client_authn_method=None,
        keyjar=None,
        verify_ssl=None,
        config=None,
        client_cert=None,
        requests_dir="requests",
        message_factory: Type[MessageFactory] = OIDCMessageFactory,
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
        """
        self.settings = settings or OicClientSettings()
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
        oauth2.Client.__init__(
            self,
            client_id,
            client_authn_method=client_authn_method,
            keyjar=keyjar,
            config=config,
            message_factory=message_factory,
            settings=self.settings,
        )

        self.file_store = "./file/"
        self.file_uri = "http://localhost/"
        self.base_url = ""

        # OpenID connect specific endpoints
        for endpoint in ENDPOINTS:
            setattr(self, endpoint, "")

        self.id_token: Dict[str, Token] = {}
        self.log = None

        self.request2endpoint = REQUEST2ENDPOINT
        self.response2error = RESPONSE2ERROR

        self.provider_info = Message()
        self.registration_response: RegistrationResponse = RegistrationResponse()
        self.client_prefs = client_prefs or {}

        self.behaviour: Dict[str, Any] = {}
        self.scope = ["openid"]

        self.wf = WebFinger(OIC_ISSUER)
        self.wf.httpd = self
        self.allow = {}
        self.post_logout_redirect_uris: List[str] = []
        self.registration_expires = 0
        self.registration_access_token = None
        self.id_token_max_age = 0

        # Default key by kid for different key types
        # For instance {'sig': {"RSA":"abc"}}
        self.kid = {"sig": {}, "enc": {}}
        self.requests_dir = requests_dir

    def _get_id_token(self, **kwargs):
        try:
            return kwargs["id_token"]
        except KeyError:
            grant = self.get_grant(**kwargs)

        if grant:
            try:
                _scope = kwargs["scope"]
            except KeyError:
                _scope = None

            for token in grant.tokens:
                if token.scope and _scope:
                    flag = True
                    for item in _scope:
                        if item not in token.scope:
                            flag = False
                            break
                    if not flag:
                        break
                if token.id_token:
                    return token.id_token.jwt

        return None

    def request_object_encryption(self, msg, **kwargs):
        try:
            encalg = kwargs["request_object_encryption_alg"]
        except KeyError:
            try:
                encalg = self.behaviour["request_object_encryption_alg"]
            except KeyError:
                return msg

        try:
            encenc = kwargs["request_object_encryption_enc"]
        except KeyError:
            try:
                encenc = self.behaviour["request_object_encryption_enc"]
            except KeyError:
                raise MissingRequiredAttribute(
                    "No request_object_encryption_enc specified"
                )

        _jwe = JWE(msg, alg=encalg, enc=encenc)
        _kty = jwe.alg2keytype(encalg)

        try:
            _kid = kwargs["enc_kid"]
        except KeyError:
            _kid = ""

        if "target" not in kwargs:
            raise MissingRequiredAttribute("No target specified")

        if _kid:
            _keys = self.keyjar.get_encrypt_key(_kty, owner=kwargs["target"], kid=_kid)
            _jwe["kid"] = _kid
        else:
            _keys = self.keyjar.get_encrypt_key(_kty, owner=kwargs["target"])

        return _jwe.encrypt(_keys)

    @staticmethod
    def construct_redirect_uri(**kwargs):
        _filedir = kwargs["local_dir"]
        if not os.path.isdir(_filedir):
            os.makedirs(_filedir)
        _webpath = kwargs["base_path"]
        _name = rndstr(10) + ".jwt"
        filename = os.path.join(_filedir, _name)
        while os.path.exists(filename):
            _name = rndstr(10)
            filename = os.path.join(_filedir, _name)
        _webname = "%s%s" % (_webpath, _name)
        return filename, _webname

    def filename_from_webname(self, webname):
        _filedir = self.requests_dir
        if not os.path.isdir(_filedir):
            os.makedirs(_filedir)

        if webname.startswith(self.base_url):
            return webname[len(self.base_url) :]
        else:
            raise ValueError("Invalid webname, must start with base_url")

    def construct_AuthorizationRequest(
        self, request=None, request_args=None, extra_args=None, **kwargs
    ):
        if request_args is not None:
            if "nonce" not in request_args:
                _rt = request_args["response_type"]
                if "token" in _rt or "id_token" in _rt:
                    request_args["nonce"] = rndstr(32)
        elif "response_type" in kwargs:
            if "token" in kwargs["response_type"]:
                request_args = {"nonce": rndstr(32)}
        else:  # Never wrong to specify a nonce
            request_args = {"nonce": rndstr(32)}

        request_param = kwargs.get("request_param")
        if "request_method" in kwargs:
            if kwargs["request_method"] == "file":
                request_param = "request_uri"
            else:
                request_param = "request"
            del kwargs["request_method"]

        areq = super().construct_AuthorizationRequest(
            request=request, request_args=request_args, extra_args=extra_args, **kwargs
        )

        if request_param:
            alg = None
            for arg in ["request_object_signing_alg", "algorithm"]:
                try:  # Trumps everything
                    alg = kwargs[arg]
                except KeyError:
                    pass
                else:
                    break

            if not alg:
                try:
                    alg = self.behaviour["request_object_signing_alg"]
                except KeyError:
                    alg = "none"

            kwargs["request_object_signing_alg"] = alg

            if "keys" not in kwargs and alg and alg != "none":
                _kty = jws.alg2keytype(alg)
                try:
                    _kid = kwargs["sig_kid"]
                except KeyError:
                    _kid = self.kid["sig"].get(_kty, None)

                kwargs["keys"] = self.keyjar.get_signing_key(_kty, kid=_kid)

            _req = make_openid_request(areq, **kwargs)

            # Should the request be encrypted
            _req = self.request_object_encryption(_req, **kwargs)

            if request_param == "request":
                areq["request"] = _req
            else:
                try:
                    _webname = self.registration_response["request_uris"][0]
                    filename = self.filename_from_webname(_webname)
                except KeyError:
                    filename, _webname = self.construct_redirect_uri(**kwargs)
                with open(filename, mode="w") as fid:
                    fid.write(_req)
                areq["request_uri"] = _webname

        return areq

    def construct_UserInfoRequest(
        self, request=None, request_args=None, extra_args=None, **kwargs
    ):
        if request is None:
            request = self.message_factory.get_request_type("userinfo_endpoint")
        if request_args is None:
            request_args = {}

        if "access_token" in request_args:
            pass
        else:
            if "scope" not in kwargs:
                kwargs["scope"] = "openid"
            token = self.get_token(**kwargs)
            if token is None:
                raise MissingParameter("No valid token available")

            request_args["access_token"] = token.access_token

        return self.construct_request(request, request_args, extra_args)

    def construct_RegistrationRequest(
        self, request=None, request_args=None, extra_args=None, **kwargs
    ):
        if request is None:
            request = self.message_factory.get_request_type("registration_endpoint")
        return self.construct_request(request, request_args, extra_args)

    def construct_RefreshSessionRequest(
        self, request=None, request_args=None, extra_args=None, **kwargs
    ):
        if request is None:
            request = self.message_factory.get_request_type("refreshsession_endpoint")
        return self.construct_request(request, request_args, extra_args)

    def _id_token_based(self, request, request_args=None, extra_args=None, **kwargs):
        if request_args is None:
            request_args = {}

        try:
            _prop = kwargs["prop"]
        except KeyError:
            _prop = "id_token"

        if _prop in request_args:
            pass
        else:
            raw_id_token = self._get_id_token(**kwargs)
            if raw_id_token is None:
                raise MissingParameter("No valid id token available")

            request_args[_prop] = raw_id_token

        return self.construct_request(request, request_args, extra_args)

    def construct_CheckSessionRequest(
        self, request=None, request_args=None, extra_args=None, **kwargs
    ):
        if request is None:
            request = self.message_factory.get_request_type("checksession_endpoint")

        return self._id_token_based(request, request_args, extra_args, **kwargs)

    def construct_CheckIDRequest(
        self, request=None, request_args=None, extra_args=None, **kwargs
    ):
        if request is None:
            request = self.message_factory.get_request_type("checkid_endpoint")
        # access_token is where the id_token will be placed
        return self._id_token_based(
            request, request_args, extra_args, prop="access_token", **kwargs
        )

    def construct_EndSessionRequest(
        self,
        request=None,
        request_args=None,
        extra_args=None,
        prop="id_token_hint",
        **kwargs,
    ):
        if request is None:
            request = self.message_factory.get_request_type("endsession_endpoint")
        if request_args is None:
            request_args = {}

        if "state" in request_args and "state" not in kwargs:
            kwargs["state"] = request_args["state"]

        return self._id_token_based(
            request, request_args, extra_args, prop=prop, **kwargs
        )

    def do_authorization_request(
        self,
        state="",
        body_type="",
        method="GET",
        request_args=None,
        extra_args=None,
        http_args=None,
        **kwargs,
    ):
        algs = self.sign_enc_algs("id_token")

        if "code_challenge" in self.config:
            _args, code_verifier = self.add_code_challenge()
            request_args.update(_args)

        return super().do_authorization_request(
            state=state,
            body_type=body_type,
            method=method,
            request_args=request_args,
            extra_args=extra_args,
            http_args=http_args,
            algs=algs,
        )

    def do_access_token_request(
        self,
        scope="",
        state="",
        body_type="json",
        method="POST",
        request_args=None,
        extra_args=None,
        http_args=None,
        authn_method="client_secret_basic",
        **kwargs,
    ):
        atr = super().do_access_token_request(
            scope=scope,
            state=state,
            body_type=body_type,
            method=method,
            request_args=request_args,
            extra_args=extra_args,
            http_args=http_args,
            authn_method=authn_method,
            **kwargs,
        )
        try:
            _idt = atr["id_token"]
        except KeyError:
            pass
        else:
            try:
                if self.state2nonce[state] != _idt["nonce"]:
                    raise ParameterError('Someone has messed with "nonce"')
            except KeyError:
                pass
        return atr

    def do_registration_request(
        self,
        scope="",
        state="",
        body_type="json",
        method="POST",
        request_args=None,
        extra_args=None,
        http_args=None,
    ):
        request = self.message_factory.get_request_type("registration_endpoint")
        url, body, ht_args, csi = self.request_info(
            request,
            method=method,
            request_args=request_args,
            extra_args=extra_args,
            scope=scope,
            state=state,
        )

        if http_args is None:
            http_args = ht_args
        else:
            http_args.update(http_args)

        response_cls = self.message_factory.get_response_type("registration_endpoint")
        response = self.request_and_return(
            url, response_cls, method, body, body_type, state=state, http_args=http_args
        )
        return response

    def do_check_session_request(
        self,
        scope="",
        state="",
        body_type="json",
        method="GET",
        request_args=None,
        extra_args=None,
        http_args=None,
    ):
        request = self.message_factory.get_request_type("checksession_endpoint")
        response_cls = self.message_factory.get_response_type("checksession_endpoint")

        url, body, ht_args, csi = self.request_info(
            request,
            method=method,
            request_args=request_args,
            extra_args=extra_args,
            scope=scope,
            state=state,
        )

        if http_args is None:
            http_args = ht_args
        else:
            http_args.update(http_args)

        return self.request_and_return(
            url, response_cls, method, body, body_type, state=state, http_args=http_args
        )

    def do_check_id_request(
        self,
        scope="",
        state="",
        body_type="json",
        method="GET",
        request_args=None,
        extra_args=None,
        http_args=None,
    ):
        request = self.message_factory.get_request_type("checkid_endpoint")
        response_cls = self.message_factory.get_response_type("checkid_endpoint")

        url, body, ht_args, csi = self.request_info(
            request,
            method=method,
            request_args=request_args,
            extra_args=extra_args,
            scope=scope,
            state=state,
        )

        if http_args is None:
            http_args = ht_args
        else:
            http_args.update(http_args)

        return self.request_and_return(
            url, response_cls, method, body, body_type, state=state, http_args=http_args
        )

    def do_end_session_request(
        self,
        scope="",
        state="",
        body_type="",
        method="GET",
        request_args=None,
        extra_args=None,
        http_args=None,
        prop="id_token_hint",
    ):
        request = self.message_factory.get_request_type("endsession_endpoint")
        response_cls = self.message_factory.get_response_type("endsession_endpoint")
        url, body, ht_args, _ = self.request_info(
            request,
            method=method,
            request_args=request_args,
            extra_args=extra_args,
            scope=scope,
            state=state,
            prop=prop,
        )

        if http_args is None:
            http_args = ht_args
        else:
            http_args.update(http_args)

        return self.request_and_return(
            url, response_cls, method, body, body_type, state=state, http_args=http_args
        )

    def user_info_request(self, method="GET", state="", scope="", **kwargs):
        uir = self.message_factory.get_request_type("userinfo_endpoint")()
        logger.debug("[user_info_request]: kwargs:%s" % (sanitize(kwargs),))
        token: Optional[Token] = None
        if "token" in kwargs:
            if kwargs["token"]:
                uir["access_token"] = kwargs["token"]
                token = Token()
                token.token_type = "Bearer"  # nosec
                token.access_token = kwargs["token"]
                kwargs["behavior"] = "use_authorization_header"
            else:
                # What to do ? Need a callback
                pass
        elif "access_token" in kwargs and kwargs["access_token"]:
            uir["access_token"] = kwargs["access_token"]
            del kwargs["access_token"]
        elif state:
            token = self.grant[state].get_token(scope)
            if token is None:
                raise AccessDenied("invalid_token")
            if token.is_valid():
                uir["access_token"] = token.access_token
                if (
                    token.token_type
                    and token.token_type.lower() == "bearer"
                    and method == "GET"
                ):
                    kwargs["behavior"] = "use_authorization_header"
            else:
                # raise oauth2.OldAccessToken
                if self.log:
                    self.log.info("do access token refresh")
                try:
                    self.do_access_token_refresh(token=token, state=state)
                    tokenval = self.get_grant(state).get_token(scope)
                    if tokenval is None:
                        raise KeyError("No token")
                    token = cast(Token, tokenval)
                    uir["access_token"] = token.access_token
                except Exception:
                    raise

        uri = self._endpoint("userinfo_endpoint", **kwargs)
        # If access token is a bearer token it might be sent in the
        # authorization header
        # 4 ways of sending the access_token:
        # - POST with token in authorization header
        # - POST with token in message body
        # - GET with token in authorization header
        # - GET with token as query parameter
        if "behavior" in kwargs:
            _behav = kwargs["behavior"]
            _token = uir["access_token"]
            _ttype = ""
            try:
                _ttype = kwargs["token_type"]
            except KeyError:
                if token:
                    try:
                        _ttype = cast(str, token.token_type)
                    except AttributeError:
                        raise MissingParameter("Unspecified token type")

            if "as_query_parameter" == _behav:
                method = "GET"
            elif token:
                # use_authorization_header, token_in_message_body
                if "use_authorization_header" in _behav:
                    token_header = "{type} {token}".format(
                        type=_ttype.capitalize(), token=_token
                    )
                    if "headers" in kwargs:
                        kwargs["headers"].update({"Authorization": token_header})
                    else:
                        kwargs["headers"] = {"Authorization": token_header}

                if "token_in_message_body" not in _behav:
                    # remove the token from the request
                    del uir["access_token"]

        path, body, kwargs = get_or_post(uri, method, uir, **kwargs)

        h_args = dict([(k, v) for k, v in kwargs.items() if k in HTTP_ARGS])

        return path, body, method, h_args

    def do_user_info_request(
        self, method="POST", state="", scope="openid", request="openid", **kwargs
    ):
        kwargs["request"] = request
        path, body, method, h_args = self.user_info_request(
            method, state, scope, **kwargs
        )

        logger.debug(
            "[do_user_info_request] PATH:%s BODY:%s H_ARGS: %s"
            % (sanitize(path), sanitize(body), sanitize(h_args))
        )

        if self.events:
            self.events.store("Request", {"body": body})
            self.events.store("request_url", path)
            self.events.store("request_http_args", h_args)

        try:
            resp = self.http_request(path, method, data=body, **h_args)
        except oauth2.exception.MissingRequiredAttribute:
            raise

        if resp.status_code == 200:
            if "application/json" in resp.headers["content-type"]:
                sformat = "json"
            elif "application/jwt" in resp.headers["content-type"]:
                sformat = "jwt"
            else:
                raise PyoidcError(
                    "ERROR: Unexpected content-type: %s" % resp.headers["content-type"]
                )
        elif resp.status_code == 500:
            raise PyoidcError("ERROR: Something went wrong: %s" % resp.text)
        elif resp.status_code == 405:
            # Method not allowed error
            allowed_methods = [x.strip() for x in resp.headers["allow"].split(",")]
            raise CommunicationError(
                "Server responded with HTTP Error Code 405", "", allowed_methods
            )
        elif 400 <= resp.status_code < 500:
            # the response text might be a OIDC message
            try:
                res = ErrorResponse().from_json(resp.text)
            except Exception:
                raise RequestError(resp.text)
            else:
                self.store_response(res, resp.text)
                return res
        else:
            raise PyoidcError(
                "ERROR: Something went wrong [%s]: %s" % (resp.status_code, resp.text)
            )

        try:
            _schema = kwargs["user_info_schema"]
        except KeyError:
            _schema = OpenIDSchema

        logger.debug("Reponse text: '%s'" % sanitize(resp.text))

        _txt = resp.text
        if sformat == "json":
            res = _schema().from_json(txt=_txt)
        else:
            verify = kwargs.get("verify", True)
            res = _schema().from_jwt(
                _txt,
                keyjar=self.keyjar,
                sender=self.provider_info["issuer"],
                verify=verify,
            )

        if "error" in res:  # Error response
            res = UserInfoErrorResponse(**res.to_dict())

        if state:
            # Verify userinfo sub claim against what's returned in the ID Token
            idt = self.get_grant(state).get_id_token()
            if idt:
                if idt["sub"] != res["sub"]:
                    raise SubMismatch(
                        "Sub identifier not the same in userinfo and Id Token"
                    )

        self.store_response(res, _txt)

        return res

    def get_userinfo_claims(
        self, access_token, endpoint, method="POST", schema_class=OpenIDSchema, **kwargs
    ):
        uir = UserInfoRequest(access_token=access_token)

        h_args = dict([(k, v) for k, v in kwargs.items() if k in HTTP_ARGS])

        if "authn_method" in kwargs:
            http_args = self.init_authentication_method(**kwargs)
        else:
            # If nothing defined this is the default
            http_args = self.init_authentication_method(uir, "bearer_header", **kwargs)

        h_args.update(http_args)
        path, body, kwargs = get_or_post(endpoint, method, uir, **kwargs)

        try:
            resp = self.http_request(path, method, data=body, **h_args)
        except MissingRequiredAttribute:
            raise

        if resp.status_code == 200:
            # FIXME: Could this also encounter application/jwt for encrypted userinfo
            #        the do_userinfo_request method already handles it
            if "application/json" not in resp.headers["content-type"]:
                raise PyoidcError(
                    "ERROR: content-type in response unexpected: %s"
                    % resp.headers["content-type"]
                )
        elif resp.status_code == 500:
            raise PyoidcError("ERROR: Something went wrong: %s" % resp.text)
        else:
            raise PyoidcError(
                "ERROR: Something went wrong [%s]: %s" % (resp.status_code, resp.text)
            )

        res = schema_class().from_json(txt=resp.text)
        self.store_response(res, resp.text)
        return res

    def unpack_aggregated_claims(self, userinfo):
        if userinfo["_claim_sources"]:
            for csrc, spec in userinfo["_claim_sources"].items():
                if "JWT" in spec:
                    aggregated_claims = Message().from_jwt(
                        spec["JWT"].encode("utf-8"), keyjar=self.keyjar, sender=csrc
                    )
                    claims = [
                        value
                        for value, src in userinfo["_claim_names"].items()
                        if src == csrc
                    ]

                    if set(claims) != set(list(aggregated_claims.keys())):
                        logger.warning(
                            "Claims from claim source doesn't match what's in "
                            "the userinfo"
                        )

                    for key, vals in aggregated_claims.items():
                        userinfo[key] = vals

        return userinfo

    def fetch_distributed_claims(self, userinfo, callback=None):
        for csrc, spec in userinfo["_claim_sources"].items():
            if "endpoint" in spec:
                if not spec["endpoint"].startswith("https://"):
                    logger.warning(
                        "Fetching distributed claims from an untrusted source: %s",
                        spec["endpoint"],
                    )
                if "access_token" in spec:
                    _uinfo = self.do_user_info_request(
                        method="GET",
                        token=spec["access_token"],
                        userinfo_endpoint=spec["endpoint"],
                        verify=False,
                    )
                else:
                    if callback:
                        _uinfo = self.do_user_info_request(
                            method="GET",
                            token=callback(spec["endpoint"]),
                            userinfo_endpoint=spec["endpoint"],
                            verify=False,
                        )
                    else:
                        _uinfo = self.do_user_info_request(
                            method="GET",
                            userinfo_endpoint=spec["endpoint"],
                            verify=False,
                        )

                claims = [
                    value
                    for value, src in userinfo["_claim_names"].items()
                    if src == csrc
                ]

                if set(claims) != set(list(_uinfo.keys())):
                    logger.warning(
                        "Claims from claim source doesn't match what's in "
                        "the userinfo"
                    )

                for key, vals in _uinfo.items():
                    userinfo[key] = vals

        # Remove the `_claim_sources` and `_claim_names` from userinfo and better be safe than sorry
        if "_claim_sources" in userinfo:
            del userinfo["_claim_sources"]
        if "_claim_names" in userinfo:
            del userinfo["_claim_names"]
        return userinfo

    def verify_alg_support(self, alg, usage, other):
        """
        Verify that the algorithm to be used are supported by the other side.

        :param alg: The algorithm specification
        :param usage: In which context the 'alg' will be used.
            The following values are supported:
            - userinfo
            - id_token
            - request_object
            - token_endpoint_auth
        :param other: The identifier for the other side
        :return: True or False
        """
        try:
            _pcr = self.provider_info
            supported = _pcr["%s_algs_supported" % usage]
        except KeyError:
            try:
                supported = getattr(self, "%s_algs_supported" % usage)
            except AttributeError:
                supported = None

        if supported is None:
            return True
        else:
            if alg in supported:
                return True
            else:
                return False

    def match_preferences(self, pcr=None, issuer=None):
        """
        Match the clients preferences against what the provider can do.

        :param pcr: Provider configuration response if available
        :param issuer: The issuer identifier
        """
        if not pcr:
            pcr = self.provider_info

        regreq = self.message_factory.get_request_type("registration_endpoint")

        for _pref, _prov in PREFERENCE2PROVIDER.items():
            try:
                vals = self.client_prefs[_pref]
            except KeyError:
                continue

            try:
                _pvals = pcr[_prov]
            except KeyError:
                try:
                    self.behaviour[_pref] = PROVIDER_DEFAULT[_pref]
                except KeyError:
                    if isinstance(pcr.c_param[_prov][0], list):
                        self.behaviour[_pref] = []
                    else:
                        self.behaviour[_pref] = None
                continue

            if isinstance(vals, str):
                if vals in _pvals:
                    self.behaviour[_pref] = vals
            else:
                vtyp = regreq.c_param[_pref]

                if isinstance(vtyp[0], list):
                    self.behaviour[_pref] = []
                    for val in vals:
                        if val in _pvals:
                            self.behaviour[_pref].append(val)
                else:
                    for val in vals:
                        if val in _pvals:
                            self.behaviour[_pref] = val
                            break

            if _pref not in self.behaviour:
                raise ConfigurationError("OP couldn't match preference:%s" % _pref, pcr)

        for key, val in self.client_prefs.items():
            if key in self.behaviour:
                continue

            try:
                vtyp = regreq.c_param[key]
                if isinstance(vtyp[0], list):
                    pass
                elif isinstance(val, list) and not isinstance(val, str):
                    val = val[0]
            except KeyError:
                pass
            if key not in PREFERENCE2PROVIDER:
                self.behaviour[key] = val

    def store_registration_info(self, reginfo):
        self.registration_response = reginfo
        if "token_endpoint_auth_method" not in self.registration_response:
            self.registration_response["token_endpoint_auth_method"] = (  # nosec
                "client_secret_basic"
            )
        self.client_id = reginfo["client_id"]
        try:
            self.client_secret = reginfo["client_secret"]
        except KeyError:  # Not required
            pass
        else:
            try:
                self.registration_expires = reginfo["client_secret_expires_at"]
            except KeyError:
                pass
        try:
            self.registration_access_token = reginfo["registration_access_token"]
        except KeyError:
            pass

    def handle_registration_info(self, response):
        err_msg = "Got error response: {}"
        unk_msg = "Unknown response: {}"
        if response.status_code in [200, 201]:
            resp = self.message_factory.get_response_type(
                "registration_endpoint"
            )().deserialize(response.text, "json")
            # Some implementations sends back a 200 with an error message inside
            try:
                resp.verify()
            except oauth2.message.MissingRequiredAttribute as err:
                logger.error("%s", err)
                raise RegistrationError(err)
            except Exception:
                resp = ErrorResponse().deserialize(response.text, "json")
                if resp.verify():
                    logger.error(err_msg.format(sanitize(resp.to_json())))
                    if self.events:
                        self.events.store("protocol response", resp)
                    raise RegistrationError(resp.to_dict())
                else:  # Something else
                    logger.error(unk_msg.format(sanitize(response.text)))
                    raise RegistrationError(response.text)
            else:
                # got a proper registration response
                self.store_response(resp, response.text)
                self.store_registration_info(resp)
        elif 400 <= response.status_code <= 499:
            try:
                resp = ErrorResponse().deserialize(response.text, "json")
            except JSONDecodeError:
                logger.error(unk_msg.format(sanitize(response.text)))
                raise RegistrationError(response.text)

            if resp.verify():
                logger.error(err_msg.format(sanitize(resp.to_json())))
                if self.events:
                    self.events.store("protocol response", resp)
                raise RegistrationError(resp.to_dict())
            else:  # Something else
                logger.error(unk_msg.format(sanitize(response.text)))
                raise RegistrationError(response.text)
        else:
            raise RegistrationError(response.text)

        return resp

    def registration_read(self, url="", registration_access_token=None):
        """
        Read the client registration info from the given url.

        :raises RegistrationError: If an error happend
        :return: RegistrationResponse
        """
        if not url:
            url = self.registration_response["registration_client_uri"]

        if not registration_access_token:
            registration_access_token = self.registration_access_token

        headers = {"Authorization": "Bearer %s" % registration_access_token}
        rsp = self.http_request(url, "GET", headers=headers)

        return self.handle_registration_info(rsp)

    def generate_request_uris(self, request_dir):
        """
        Need to generate a path that is unique for the OP combo.

        :return: A list of uris
        """
        m = hashlib.new("sha256")
        m.update(as_bytes(self.provider_info["issuer"]))
        m.update(as_bytes(self.base_url))
        return "{}{}/{}".format(self.base_url, request_dir, m.hexdigest())

    def create_registration_request(self, **kwargs):
        """
        Create a registration request.

        :param kwargs: parameters to the registration request
        :return:
        """
        req = self.message_factory.get_request_type("registration_endpoint")()

        for prop in req.parameters():
            try:
                req[prop] = kwargs[prop]
            except KeyError:
                try:
                    req[prop] = self.behaviour[prop]
                except KeyError:
                    pass

        if "post_logout_redirect_uris" not in req:
            try:
                req["post_logout_redirect_uris"] = self.post_logout_redirect_uris
            except AttributeError:
                pass

        if "redirect_uris" not in req:
            try:
                req["redirect_uris"] = self.redirect_uris
            except AttributeError:
                raise MissingRequiredAttribute("redirect_uris", req)

        try:
            if self.provider_info["require_request_uri_registration"] is True:
                req["request_uris"] = self.generate_request_uris(self.requests_dir)
        except KeyError:
            pass

        if "response_types" in req:
            req["grant_types"] = response_types_to_grant_types(
                req["response_types"], **kwargs
            )

        return req

    def register(self, url, registration_token=None, **kwargs):
        """
        Register the client at an OP.

        :param url: The OPs registration endpoint
        :param registration_token: Initial Access Token for registration endpoint
        :param kwargs: parameters to the registration request
        :return:
        """
        req = self.create_registration_request(**kwargs)

        logger.debug("[registration_request]: kwargs:%s" % (sanitize(kwargs),))

        if self.events:
            self.events.store("Protocol request", req)

        headers = {"content-type": "application/json"}
        if registration_token is not None:
            try:
                token = jwt.JWT()
                token.unpack(registration_token)
            except BadSyntax:
                # no JWT
                registration_token = b64encode(registration_token.encode()).decode()
            finally:
                headers["Authorization"] = "Bearer " + registration_token

        rsp = self.http_request(url, "POST", data=req.to_json(), headers=headers)

        return self.handle_registration_info(rsp)

    def normalization(self, principal, idtype="mail"):
        if idtype == "mail":
            (_, domain) = principal.split("@")
            subject = "acct:%s" % principal
        elif idtype == "url":
            p = urlparse(principal)
            domain = p.netloc
            subject = principal
        else:
            domain = ""
            subject = principal

        return subject, domain

    def discover(self, principal, host=None):
        return self.wf.discovery_query(principal, host=host)

    def sign_enc_algs(self, typ):
        resp = {}
        for key, val in PARAMMAP.items():
            try:
                resp[key] = self.registration_response[val % typ]
            except (TypeError, KeyError):
                if key == "sign":
                    resp[key] = DEF_SIGN_ALG["id_token"]
        return resp

    def _verify_id_token(
        self,
        id_token,
        nonce="",
        acr_values=None,
        auth_time=0,
        max_age=0,
        response_type="",
    ):
        """
        Verify IdToken.

        If the JWT alg Header Parameter uses a MAC based algorithm such as
        HS256, HS384, or HS512, the octets of the UTF-8 representation of the
        client_secret corresponding to the client_id contained in the aud
        (audience) Claim are used as the key to validate the signature. For MAC
        based algorithms, the behavior is unspecified if the aud is
        multi-valued or if an azp value is present that is different than the
        aud value.

        :param id_token: The ID Token tp check
        :param nonce: The nonce specified in the authorization request
        :param acr_values: Asked for acr values
        :param auth_time: An auth_time claim
        :param max_age: Max age of authentication
        """
        if self.provider_info["issuer"] != id_token["iss"]:
            raise OtherError("issuer != iss")

        if self.client_id not in id_token["aud"]:
            raise OtherError("not intended for me")
        if len(id_token["aud"]) > 1:
            if "azp" not in id_token or id_token["azp"] != self.client_id:
                raise OtherError("not intended for me")

        _now = time_util.utc_time_sans_frac()

        if _now > id_token["exp"]:
            raise OtherError("Passed best before date")

        if response_type != ["code"] and id_token.jws_header["alg"] == "none":
            raise WrongSigningAlgorithm(
                "none is not allowed outside Authorization Flow."
            )

        if (
            self.id_token_max_age
            and _now > int(id_token["iat"]) + self.id_token_max_age
        ):
            raise OtherError("I think this ID token is to old")

        if nonce and nonce != id_token["nonce"]:
            raise OtherError("nonce mismatch")

        if acr_values and id_token["acr"] not in acr_values:
            raise OtherError("acr mismatch")

        if max_age and _now > int(id_token["auth_time"] + max_age):
            raise AuthnToOld("To old authentication")

        if auth_time:
            if not claims_match(id_token["auth_time"], {"auth_time": auth_time}):
                raise AuthnToOld("To old authentication")

    def verify_id_token(self, id_token, authn_req):
        kwa = {}
        try:
            kwa["nonce"] = authn_req["nonce"]
        except KeyError:
            pass

        for param in ["acr_values", "max_age", "response_type"]:
            try:
                kwa[param] = authn_req[param]
            except KeyError:
                pass

        self._verify_id_token(id_token, **kwa)


class Server(oauth2.Server):
    """OIC Server class."""

    def __init__(
        self,
        verify_ssl: Optional[bool] = None,
        keyjar: Optional[KeyJar] = None,
        client_cert: Optional[Union[str, Tuple[str, str]]] = None,
        timeout: Optional[float] = None,
        message_factory: Type[MessageFactory] = OIDCMessageFactory,
        settings: Optional[PyoidcSettings] = None,
    ):
        """Initialize the server."""
        self.settings = settings or OicServerSettings()
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

        super().__init__(
            keyjar=keyjar,
            message_factory=message_factory,
            settings=self.settings,
        )

    @staticmethod
    def _parse_urlencoded(url=None, query=None):
        if url:
            parts = urlparse(url)
            scheme, netloc, path, params, query, fragment = parts[:6]

        return parse_qs(query)

    def handle_request_uri(self, request_uri, verify=True, sender=""):
        """
        Handle request URI.

        :param request_uri: URL pointing to where the signed request should be fetched from.
        :param verify: Whether the signature on the request should be verified.
        Don't use anything but the default unless you REALLY know what you're doing
        :param sender: The issuer of the request JWT.
        :return:
        """
        # Do a HTTP get
        logger.debug("Get request from request_uri: {}".format(request_uri))
        try:
            http_req = self.http_request(request_uri)
        except ConnectionError:
            logger.error("Connection Error")
            return authz_error("invalid_request_uri")

        if not http_req:
            logger.error("Nothing returned")
            return authz_error("invalid_request_uri")
        elif http_req.status_code >= 400:
            logger.error("HTTP error {}:{}".format(http_req.status_code, http_req.text))
            raise AuthzError("invalid_request")

        # http_req.text is a signed JWT
        try:
            logger.debug("request txt: {}".format(http_req.text))
            req = self.parse_jwt_request(
                txt=http_req.text, verify=verify, sender=sender
            )
        except Exception as err:
            logger.error(
                "{}:{} encountered while parsing fetched request".format(
                    err.__class__, err
                )
            )
            raise AuthzError("invalid_openid_request_object")

        logger.debug("Fetched request: {}".format(req))
        return req

    def parse_authorization_request(
        self, request=AuthorizationRequest, url=None, query=None, keys=None
    ):
        if url:
            parts = urlparse(url)
            scheme, netloc, path, params, query, fragment = parts[:6]

        if isinstance(query, dict):
            sformat = "dict"
        else:
            sformat = "urlencoded"

        _req = self._parse_request(request, query, sformat, verify=False)

        if self.events:
            self.events.store("Request", _req)

        _req_req: Union[Message, Dict[str, Any]] = {}
        try:
            _request = _req["request"]
        except KeyError:
            try:
                _url = _req["request_uri"]
            except KeyError:
                pass
            else:
                _req_req = self.handle_request_uri(
                    _url, verify=False, sender=_req["client_id"]
                )
        else:
            if isinstance(_request, Message):
                _req_req = _request
            else:
                try:
                    _req_req = self.parse_jwt_request(
                        request, txt=_request, verify=False
                    )
                except Exception:
                    _req_req = self._parse_request(
                        request, _request, "urlencoded", verify=False
                    )
                else:  # remove JWT attributes
                    for attr in JasonWebToken.c_param:
                        try:
                            del _req_req[attr]
                        except KeyError:
                            pass

        if isinstance(_req_req, Response):
            return _req_req

        if _req_req:
            if self.events:
                self.events.store("Signed Request", _req_req)

            for key, val in _req.items():
                if key in ["request", "request_uri"]:
                    continue
                if key not in _req_req:
                    _req_req[key] = val
            _req = _req_req

        if self.events:
            self.events.store("Combined Request", _req)

        try:
            _req.verify(keyjar=self.keyjar)
        except Exception as err:
            if self.events:
                self.events.store("Exception", err)
            logger.error("%s", err)
            raise

        return _req

    def parse_jwt_request(
        self,
        request=AuthorizationRequest,
        txt="",
        keyjar=None,
        verify=True,
        sender="",
        **kwargs,
    ):
        """Overridden to use OIC Message type."""
        if "keys" in kwargs:
            keyjar = kwargs["keys"]
            warnings.warn(
                "`keys` was renamed to `keyjar`, please update your code.",
                DeprecationWarning,
                stacklevel=2,
            )
        return super().parse_jwt_request(
            request=request, txt=txt, keyjar=keyjar, verify=verify, sender=sender
        )

    def parse_check_session_request(self, url=None, query=None):
        param = self._parse_urlencoded(url, query)
        assert "id_token" in param  # nosec, ignore the rest
        return deser_id_token(self, param["id_token"][0])

    def parse_check_id_request(self, url=None, query=None):
        param = self._parse_urlencoded(url, query)
        assert "access_token" in param  # nosec, ignore the rest
        return deser_id_token(self, param["access_token"][0])

    def _parse_request(self, request_cls, data, sformat, client_id=None, verify=True):
        if sformat == "json":
            request = request_cls().from_json(data)
        elif sformat == "jwt":
            request = request_cls().from_jwt(data, keyjar=self.keyjar, sender=client_id)
        elif sformat == "urlencoded":
            if "?" in data:
                parts = urlparse(data)
                scheme, netloc, path, params, query, fragment = parts[:6]
            else:
                query = data
            request = request_cls().from_urlencoded(query)
        elif sformat == "dict":
            request = request_cls(**data)
        else:
            raise ParseError(
                "Unknown package format: '{}'".format(sformat), request_cls
            )

        # get the verification keys
        if client_id:
            keys = self.keyjar.verify_keys(client_id)
            sender = client_id
        else:
            try:
                keys = self.keyjar.verify_keys(request["client_id"])
                sender = request["client_id"]
            except KeyError:
                keys = None
                sender = ""

        logger.debug("Found {} verify keys".format(len(keys or "")))
        if verify:
            request.verify(key=keys, keyjar=self.keyjar, sender=sender)
        return request

    def parse_open_id_request(self, data, sformat="urlencoded", client_id=None):
        return self._parse_request(OpenIDRequest, data, sformat, client_id)

    def parse_user_info_request(self, data, sformat="urlencoded"):
        return self._parse_request(UserInfoRequest, data, sformat)

    def parse_userinfo_request(self, data, sformat="urlencoded"):
        return self._parse_request(UserInfoRequest, data, sformat)

    def parse_refresh_session_request(self, url=None, query=None):
        if url:
            parts = urlparse(url)
            query = parts.query
        return RefreshSessionRequest().from_urlencoded(query)

    def parse_registration_request(self, data, sformat="urlencoded"):
        return self._parse_request(RegistrationRequest, data, sformat)

    def parse_end_session_request(self, query, sformat="urlencoded"):
        esr = self._parse_request(EndSessionRequest, query, sformat)
        # if there is a id_token in there it is as a string
        esr["id_token"] = deser_id_token(self, esr["id_token"])
        return esr

    @staticmethod
    def update_claims(session, where, about, old_claims=None):
        """
        Update claims dictionary.

        :param session:
        :param where: Which request
        :param about: userinfo or id_token
        :param old_claims:
        :return: claims or None
        """
        if old_claims is None:
            old_claims = {}

        req = None
        if where == "oidreq":
            try:
                req = OpenIDRequest().deserialize(session[where], "json")
            except KeyError:
                pass
        else:  # where == "authzreq"
            try:
                req = AuthorizationRequest().deserialize(session[where], "json")
            except KeyError:
                pass

        if req:
            logger.debug("%s: %s" % (where, sanitize(req.to_dict())))
            try:
                _claims = req["claims"][about]
                if _claims:
                    # update with old claims, do not overwrite
                    for key, val in old_claims.items():
                        if key not in _claims:
                            _claims[key] = val
                    return _claims
            except KeyError:
                pass

        return old_claims

    def id_token_claims(self, session):
        """
        Pick the IdToken claims from the request.

        :param session: Session information
        :return: The IdToken claims
        """
        itc: Dict[str, str] = {}
        itc = self.update_claims(session, "authzreq", "id_token", itc)
        itc = self.update_claims(session, "oidreq", "id_token", itc)
        return itc

    def make_id_token(
        self,
        session,
        loa="2",
        issuer="",
        alg="RS256",
        code=None,
        access_token=None,
        user_info=None,
        auth_time=0,
        exp=None,
        extra_claims=None,
    ):
        """
        Create ID Token.

        :param session: Session information
        :param loa: Level of Assurance/Authentication context
        :param issuer: My identifier
        :param alg: Which signing algorithm to use for the IdToken
        :param code: Access grant
        :param access_token: Access Token
        :param user_info: If user info are to be part of the IdToken
        :return: IDToken instance
        """
        # defaults
        if exp is None:
            inawhile = {"days": 1}
        else:
            inawhile = exp
        # Handle the idtoken_claims
        extra = {}
        itc = self.id_token_claims(session)
        if itc.keys():
            try:
                inawhile = {"seconds": itc["max_age"]}
            except KeyError:
                pass
            for key, val in itc.items():
                if key == "auth_time":
                    extra["auth_time"] = auth_time
                elif key == "acr":
                    extra["acr"] = verify_acr_level(val, loa)
        else:
            if auth_time:
                extra["auth_time"] = auth_time
            if loa:
                extra["acr"] = loa

        if not user_info:
            _args: Dict[str, str] = {}
        else:
            try:
                _args = user_info.to_dict()
            except AttributeError:
                _args = user_info

        # Make sure that there are no name clashes
        for key in ["iss", "sub", "aud", "exp", "acr", "nonce", "auth_time"]:
            try:
                del _args[key]
            except KeyError:
                pass

        halg = "HS%s" % alg[-3:]

        if extra_claims is not None:
            _args.update(extra_claims)
        if code:
            _args["c_hash"] = jws.left_hash(code.encode("utf-8"), halg)
        if access_token:
            _args["at_hash"] = jws.left_hash(access_token.encode("utf-8"), halg)

        idt = IdToken(
            iss=issuer,
            sub=session["sub"],
            aud=session["client_id"],
            exp=time_util.epoch_in_a_while(**inawhile),
            acr=loa,
            iat=time_util.utc_time_sans_frac(),
            **_args,
        )

        for key, val in extra.items():
            idt[key] = val

        if "nonce" in session:
            idt["nonce"] = session["nonce"]

        return idt


def scope2claims(scopes, extra_scope_dict=None):
    res: Dict[str, None] = {}
    # Construct the scope translation map
    trans_map: Dict[str, Any] = SCOPE2CLAIMS.copy()
    if extra_scope_dict is not None:
        trans_map.update(extra_scope_dict)
    for scope in scopes:
        try:
            claims = dict([(name, None) for name in trans_map[scope]])
            res.update(claims)
        except KeyError:
            continue
    return res
