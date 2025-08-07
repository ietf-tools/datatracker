import copy
import hashlib
import logging
import os
import sys
import traceback
import warnings
from functools import cmp_to_key
from typing import Dict
from typing import List
from typing import Optional
from typing import Union
from urllib.parse import parse_qs
from urllib.parse import unquote
from urllib.parse import urljoin
from urllib.parse import urlparse

from jwkest import jws

from oic import rndstr
from oic.exception import AuthzError
from oic.exception import FailedAuthentication
from oic.exception import InvalidRequest
from oic.exception import MissingParameter
from oic.exception import ParameterError
from oic.exception import RedirectURIError
from oic.exception import UnknownClient
from oic.exception import UnSupported
from oic.exception import URIError
from oic.oauth2 import ErrorResponse
from oic.oauth2 import Server
from oic.oauth2 import error_response
from oic.oauth2 import none_response
from oic.oauth2 import redirect_authz_error
from oic.oauth2.message import AccessTokenResponse
from oic.oauth2.message import AuthorizationResponse
from oic.oauth2.message import Message
from oic.oauth2.message import MissingRequiredAttribute
from oic.oauth2.message import MissingRequiredValue
from oic.oauth2.message import OauthMessageFactory
from oic.oauth2.message import TokenErrorResponse
from oic.oauth2.message import add_non_standard
from oic.oauth2.message import by_schema
from oic.utils import sort_sign_alg
from oic.utils.authn.client import AuthnFailure
from oic.utils.authn.user import NoSuchAuthentication
from oic.utils.authn.user import TamperAllert
from oic.utils.authn.user import ToOld
from oic.utils.clientdb import BaseClientDatabase
from oic.utils.http_util import OAUTH2_NOCACHE_HEADERS
from oic.utils.http_util import BadRequest
from oic.utils.http_util import CookieDealer
from oic.utils.http_util import Response
from oic.utils.http_util import SeeOther
from oic.utils.http_util import Unauthorized
from oic.utils.http_util import make_cookie
from oic.utils.keyio import KeyJar
from oic.utils.sanitize import sanitize
from oic.utils.sdb import AccessCodeUsed
from oic.utils.session_backend import AuthnEvent
from oic.utils.settings import OauthProviderSettings
from oic.utils.settings import PyoidcSettings

__author__ = "rohe0002"

logger = logging.getLogger(__name__)

STR = 5 * "_"

CAPABILITIES = {
    "response_types_supported": ["code", "token"],
    "response_modes_supported": ["query", "fragment", "form_post"],
    "grant_types_supported": [
        "authorization_code",
        "implicit",
        "urn:ietf:params:oauth:grant-type:jwt-bearer",
    ],
}

AUTH_METHODS_SUPPORTED = [
    "client_secret_post",
    "client_secret_basic",
    "client_secret_jwt",
    "private_key_jwt",
]


class Endpoint(object):
    """
    Endpoint class.

    @var etype: Endpoint type
    @url: Relative part of the url (will be joined with server.baseurl)
    """

    etype = ""
    url = ""

    def __init__(self, func=None):
        self.func = func

    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)


class AuthorizationEndpoint(Endpoint):
    etype = "authorization"
    url = "authorization"


class TokenEndpoint(Endpoint):
    etype = "token"
    url = "token"


def endpoint_ava(endp, baseurl):
    key = "{}_endpoint".format(endp.etype)
    val = urljoin(baseurl, endp.url)
    return {key: val}


def code_response(**kwargs):
    aresp = AuthorizationResponse()
    _areq = kwargs["areq"]
    try:
        aresp["state"] = _areq["state"]
    except KeyError:
        pass
    aresp["code"] = kwargs["scode"]
    # TODO Add 'iss' and 'client_id'
    if kwargs["myself"]:
        aresp["iss"] = kwargs["myself"]
    aresp["client_id"] = _areq["client_id"]
    add_non_standard(_areq, aresp)
    return aresp


def token_response(**kwargs):
    _areq = kwargs["areq"]
    _scode = kwargs["scode"]
    _sdb = kwargs["sdb"]
    _dic = _sdb.upgrade_to_token(_scode, issue_refresh=False)

    aresp = AccessTokenResponse(**by_schema(AccessTokenResponse, **_dic))

    try:
        aresp["state"] = _areq["state"]
    except KeyError:
        pass

    add_non_standard(_areq, aresp)
    return aresp


def location_url(response_type, redirect_uri, query):
    if response_type in [["code"], ["token"], ["none"]]:
        return "%s?%s" % (redirect_uri, query)
    else:
        return "%s#%s" % (redirect_uri, query)


def max_age(areq):
    try:
        return areq["request"]["max_age"]
    except KeyError:
        try:
            return areq["max_age"]
        except KeyError:
            return 0


def re_authenticate(areq, authn):
    if "prompt" in areq and "login" in areq["prompt"]:
        if authn.done(areq):
            return True

    return False


DELIM = "]["


class Provider(object):
    endp = [AuthorizationEndpoint, TokenEndpoint]

    def __init__(
        self,
        name,
        sdb,
        cdb,
        authn_broker,
        authz,
        client_authn,
        symkey=None,
        urlmap=None,
        iv=0,
        default_scope="",
        verify_ssl=None,
        default_acr="",
        keyjar=None,
        baseurl="",
        server_cls=Server,
        client_cert=None,
        message_factory=OauthMessageFactory,
        capabilities=None,
        jwks_uri="",
        settings: Optional[PyoidcSettings] = None,
    ):
        self.settings = settings or OauthProviderSettings()
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

        self.name = name
        self.sdb = sdb
        if not isinstance(cdb, BaseClientDatabase):
            warnings.warn(
                "ClientDatabase should be an instance of "
                "oic.utils.clientdb.BaseClientDatabase to ensure proper API."
            )
        self.cdb = cdb
        self.server = server_cls(
            keyjar=keyjar,
            message_factory=message_factory,
            settings=self.settings,
        )

        self.authn_broker = authn_broker
        if authn_broker is None:
            # default cookie function
            self.cookie_func = CookieDealer(srv=self).create_cookie
        else:
            self.cookie_func = self.authn_broker[0][0].create_cookie
            for item in self.authn_broker:
                item.srv = self

        self.authz = authz
        self.client_authn = client_authn
        self.symkey = symkey
        self.seed = rndstr().encode("utf-8")
        self.iv = iv or os.urandom(16)
        self.cookie_name = "pyoidc"
        self.cookie_domain = ""
        self.cookie_path = ""
        self.default_scope = default_scope
        self.sso_ttl = 0
        self.default_acr = default_acr

        if urlmap is None:
            self.urlmap: Dict[str, List[str]] = {}
        else:
            self.urlmap = urlmap

        self.response_type_map = {
            "code": code_response,
            "token": token_response,
            "none": none_response,
        }

        self.session_cookie_name = "pyoic_session"
        self.sso_cookie_name = "pyoidc_sso"
        self.baseurl = baseurl
        self.keyjar: Optional[KeyJar] = None
        self.trace = None
        self.events = None
        self.scopes = ["offline_access"]

        self.jwks_uri = jwks_uri

        if capabilities:
            self.verify_capabilities(capabilities)
            self.capabilities = message_factory.get_response_type(
                "configuration_endpoint"
            )(**capabilities)
        else:
            self.capabilities = self.provider_features()
        self.capabilities["issuer"] = self.name

    @staticmethod
    def input(query="", post=None):
        # Support GET and POST
        if query:
            return query
        elif post:
            return post
        else:
            raise MissingParameter("No input")

    @property
    def default_capabilities(self):
        """Define default capabilities for implementation."""
        return CAPABILITIES

    def endpoints(self):
        return [endp.url for endp in self.endp]

    def _verify_redirect_uri(self, areq):
        """
        Verify that redirect_uri is valid.

        MUST NOT contain a fragment
        MAY contain query component

        :return: An error response if the redirect URI is faulty otherwise None
        """
        try:
            _redirect_uri = unquote(areq["redirect_uri"])

            part = urlparse(_redirect_uri)
            if part.fragment:
                raise URIError("Contains fragment")

            _query = parse_qs(part.query) if part.query else None
            _base = part._replace(query="").geturl()

            match = False
            for regbase, rquery in self.cdb[str(areq["client_id"])]["redirect_uris"]:
                # The URI MUST exactly match one of the Redirection URI
                if _base != regbase:
                    continue

                if not rquery and not _query:
                    match = True
                    break

                if not rquery or not _query:
                    continue

                # every registered query component must exist in the
                # redirect_uri
                is_match_query = True
                for key, vals in _query.items():
                    if key not in rquery:
                        is_match_query = False
                        break

                    for val in vals:
                        if val not in rquery[key]:
                            is_match_query = False
                            break

                    if not is_match_query:
                        break

                if not is_match_query:
                    continue

                match = True
                break

            if not match:
                raise RedirectURIError("Doesn't match any registered uris")
            # ignore query components that are not registered
            return None
        except Exception:
            logger.error("Faulty redirect_uri: %s" % areq["redirect_uri"])
            try:
                _cinfo = self.cdb[str(areq["client_id"])]
            except KeyError:
                try:
                    cid = areq["client_id"]
                except KeyError:
                    logger.error("No client id found")
                    raise UnknownClient("No client_id provided")
                else:
                    logger.info("Unknown client: %s" % cid)
                    raise UnknownClient(areq["client_id"])
            else:
                logger.info("Registered redirect_uris: %s" % sanitize(_cinfo))
                raise RedirectURIError("Faulty redirect_uri: %s" % areq["redirect_uri"])

    def verify_capabilities(self, capabilities) -> bool:
        """
        Verify that what the admin wants the server to do actually can be done by this implementation.

        :param capabilities: The asked for capabilities as a dictionary
        or a ProviderConfigurationResponse instance. The later can be
        treated as a dictionary.
        """
        _pinfo = self.provider_features()
        not_supported: Dict[str, Union[str, List[str]]] = {}
        for key, val in capabilities.items():
            if isinstance(val, str):
                if val not in _pinfo.get(key, ""):
                    not_supported[key] = val
            elif isinstance(val, bool):
                if not _pinfo.get(key) and val:
                    not_supported[key] = ""
            elif isinstance(val, list):
                unsup = []
                for v in val:
                    if v not in _pinfo.get(key, ""):
                        unsup.append(v)
                if unsup:
                    not_supported[key] = unsup
        if not_supported:
            logger.error(
                "Server does not support the following features: %s", not_supported
            )
            return False
        return True

    def provider_features(self, provider_config=None):
        """
        Present what the server capabilities are.

        :return: ProviderConfigurationResponse instance
        """
        pcr_class = self.server.message_factory.get_response_type(
            "configuration_endpoint"
        )

        _provider_info = pcr_class(**self.default_capabilities)
        _provider_info["scopes_supported"] = self.scopes

        sign_algs = list(jws.SIGNER_ALGS.keys())
        sign_algs.remove("none")
        sign_algs = sorted(sign_algs, key=cmp_to_key(sort_sign_alg))

        _pat1 = "{}_endpoint_auth_signing_alg_values_supported"
        _pat2 = "{}_endpoint_auth_methods_supported"
        for typ in ["token", "revocation", "introspection"]:
            _provider_info[_pat1.format(typ)] = sign_algs
            _provider_info[_pat2.format(typ)] = AUTH_METHODS_SUPPORTED

        if provider_config:
            _provider_info.update(provider_config)

        return _provider_info

    def create_providerinfo(self, setup=None):
        """
        Dynamically create the provider info response.

        :param setup:
        :return:
        """
        pcr_class = self.server.message_factory.get_response_type(
            "configuration_endpoint"
        )
        _provider_info = copy.deepcopy(self.capabilities.to_dict())

        if self.jwks_uri and self.keyjar:
            _provider_info["jwks_uri"] = self.jwks_uri

        for endp in self.endp:
            if not self.baseurl.endswith("/"):
                baseurl = self.baseurl + "/"
            else:
                baseurl = self.baseurl
            _provider_info["{}_endpoint".format(endp.etype)] = urljoin(
                baseurl, endp.url
            )

        if setup and isinstance(setup, dict):
            for key in pcr_class.c_param.keys():
                if key in setup:
                    _provider_info[key] = setup[key]

        _provider_info["issuer"] = self.name
        _provider_info["version"] = "3.0"

        return pcr_class(**_provider_info)

    def providerinfo_endpoint(self, handle="", **kwargs):
        _log_info = logger.info

        _log_info("@providerinfo_endpoint")
        try:
            _response = self.create_providerinfo()
            msg = "provider_info_response: {}"
            _log_info(msg.format(sanitize(_response.to_dict())))
            if self.events:
                self.events.store("Protocol response", _response)

            headers = [("Cache-Control", "no-store")]
            if handle:
                (key, timestamp) = handle
                if key.startswith(STR) and key.endswith(STR):
                    cookie = self.cookie_func(
                        key, self.cookie_name, "pinfo", self.sso_ttl
                    )
                    headers.append(cookie)

            resp = Response(
                _response.to_json(), content="application/json", headers=headers
            )
        except Exception:
            message = traceback.format_exception(*sys.exc_info())
            logger.error(message)
            resp = error_response("service_error", message)

        return resp

    def get_redirect_uri(self, areq):
        """
        Verify that the redirect URI is reasonable.

        :param areq: The Authorization request
        :return: Tuple of (redirect_uri, Response instance)
            Response instance is not None of matching redirect_uri failed
        """
        if "redirect_uri" in areq:
            self._verify_redirect_uri(areq)
            uri = areq["redirect_uri"]
        else:
            raise ParameterError(
                "Missing redirect_uri and more than one or none registered"
            )

        return uri

    def pick_auth(self, areq, comparision_type=""):
        """
        Select an authentication method suitable for request.

        :param areq: AuthorizationRequest instance
        :param comparision_type: How to pick the authentication method
        :return: An authentication method and its authn class ref
        """
        if comparision_type == "any":
            return self.authn_broker[0]

        try:
            if len(self.authn_broker) == 1:
                return self.authn_broker[0]
            elif "acr_values" in areq:
                if not comparision_type:
                    comparision_type = "exact"

                if not isinstance(areq["acr_values"], list):
                    areq["acr_values"] = [areq["acr_values"]]

                for acr in areq["acr_values"]:
                    res = self.authn_broker.pick(acr, comparision_type)
                    logger.debug(
                        "Picked AuthN broker for ACR %s: %s" % (str(acr), str(res))
                    )
                    if res:
                        # Return the best guess by pick.
                        return res[0]
            else:  # same as any
                try:
                    acrs = areq["claims"]["id_token"]["acr"]["values"]
                except KeyError:
                    return self.authn_broker[0]
                else:
                    for acr in acrs:
                        res = self.authn_broker.pick(acr, comparision_type)
                        logger.debug(
                            "Picked AuthN broker for ACR %s: %s" % (str(acr), str(res))
                        )
                        if res:
                            # Return the best guess by pick.
                            return res[0]

        except KeyError as exc:
            logger.debug(
                "An error occured while picking the authN broker: %s" % str(exc)
            )

        # return the best I have
        return None, None

    def filter_request(self, req):
        return req

    def auth_init(self, request):
        """
        Start the authentication process.

        :param request: The AuthorizationRequest
        :return:
        """
        request_class = self.server.message_factory.get_request_type(
            "authorization_endpoint"
        )
        logger.debug("Request: '%s'" % sanitize(request))
        # Same serialization used for GET and POST

        try:
            areq = self.server.parse_authorization_request(query=request)
        except (MissingRequiredValue, MissingRequiredAttribute, AuthzError) as err:
            logger.debug("%s", err)
            areq = request_class()
            areq.lax = True
            if isinstance(request, dict):
                areq.from_dict(request)
            else:
                areq.deserialize(request, "urlencoded")
            try:
                redirect_uri = self.get_redirect_uri(areq)
            except (RedirectURIError, ParameterError, UnknownClient) as err:
                return error_response("invalid_request", "%s" % err)
            try:
                _rtype = areq["response_type"]
            except KeyError:
                _rtype = ["code"]
            try:
                _state = areq["state"]
            except KeyError:
                _state = ""

            return redirect_authz_error(
                "invalid_request", redirect_uri, "%s" % err, _state, _rtype
            )
        except KeyError:
            areq = request_class().deserialize(request, "urlencoded")
            # verify the redirect_uri
            try:
                self.get_redirect_uri(areq)
            except (RedirectURIError, ParameterError) as err:
                return error_response("invalid_request", "%s" % err)
        except Exception as err:
            message = traceback.format_exception(*sys.exc_info())
            logger.error(message)
            logger.debug("Bad request: %s (%s)" % (err, err.__class__.__name__))
            error = ErrorResponse(error="invalid_request", error_description=str(err))
            return BadRequest(error.to_json(), content="application/json")

        if not areq:
            logger.debug("No AuthzRequest")
            return error_response("invalid_request", "Can not parse AuthzRequest")

        if isinstance(areq, Response):
            return areq

        areq = self.filter_request(areq)

        if self.events:
            self.events.store("Protocol request", areq)

        try:
            _cinfo = self.cdb[areq["client_id"]]
        except KeyError:
            logger.error(
                "Client ID ({}) not in client database".format(areq["client_id"])
            )
            return error_response("unauthorized_client", "unknown client")
        else:
            try:
                _registered = [set(rt.split(" ")) for rt in _cinfo["response_types"]]
            except KeyError:
                # If no response_type is registered by the client then we'll
                # code which it the default according to the OIDC spec.
                _registered = [{"code"}]

            _wanted = set(areq["response_type"])
            if _wanted not in _registered:
                return error_response(
                    "invalid_request", "Trying to use unregistered response_typ"
                )

        logger.debug("AuthzRequest: %s" % (sanitize(areq.to_dict()),))
        try:
            redirect_uri = self.get_redirect_uri(areq)
        except (RedirectURIError, ParameterError, UnknownClient) as err:
            return error_response(
                "invalid_request", "{}:{}".format(err.__class__.__name__, err)
            )

        try:
            keyjar = self.keyjar
        except AttributeError:
            keyjar = None

        try:
            # verify that the request message is correct
            areq.verify(keyjar=keyjar, opponent_id=areq["client_id"])
        except (MissingRequiredAttribute, ValueError, MissingRequiredValue) as err:
            return redirect_authz_error("invalid_request", redirect_uri, "%s" % err)

        return {"areq": areq, "redirect_uri": redirect_uri}

    @staticmethod
    def _acr_claims(areq):
        try:
            acrdef = areq["claims"]["id_token"]["acr"]
        except KeyError:
            return None
        else:
            if isinstance(acrdef, dict):
                try:
                    return [acrdef["value"]]
                except KeyError:
                    try:
                        return acrdef["values"]
                    except KeyError:
                        pass

        return None

    def do_auth(self, areq, redirect_uri, cinfo, request, cookie, **kwargs):
        """
        Perform the authentication.

        :param areq:
        :param redirect_uri:
        :param cinfo:
        :param request:
        :param cookie:
        :param authn:
        :param kwargs:
        :return:
        """
        acrs = self._acr_claims(areq)
        if acrs:
            # If acr claims are present the picked acr value MUST match
            # one of the given
            tup = (None, None)
            for acr in acrs:
                res = self.authn_broker.pick(acr, "exact")
                logger.debug(
                    "Picked AuthN broker for ACR %s: %s" % (str(acr), str(res))
                )
                if res:  # Return the best guess by pick.
                    tup = res[0]
                    break
            authn, authn_class_ref = tup
        else:
            authn, authn_class_ref = self.pick_auth(areq)
            if not authn:
                authn, authn_class_ref = self.pick_auth(areq, "better")
                if not authn:
                    authn, authn_class_ref = self.pick_auth(areq, "any")

        if authn is None:
            return redirect_authz_error(
                "access_denied", redirect_uri, return_type=areq["response_type"]
            )

        try:
            try:
                _auth_info = kwargs["authn"]
            except KeyError:
                _auth_info = ""

            if "upm_answer" in areq and areq["upm_answer"] == "true":
                _max_age = 0
            else:
                _max_age = max_age(areq)

            identity, _ts = authn.authenticated_as(
                cookie, authorization=_auth_info, max_age=_max_age
            )
        except (NoSuchAuthentication, TamperAllert):
            identity = None
            _ts = 0
        except ToOld:
            logger.info("Too old authentication")
            identity = None
            _ts = 0
        else:
            logger.info("No active authentication")

        # gather information to be used by the authentication method
        authn_args = {"authn_class_ref": authn_class_ref}
        # Can't be something like JSON because it can't contain '"'
        if isinstance(request, Message):
            authn_args["query"] = request.to_urlencoded()
        elif isinstance(request, dict):
            authn_args["query"] = Message(**request).to_urlencoded()
        else:
            authn_args["query"] = request

        if "req_user" in kwargs:
            authn_args["as_user"] = (kwargs["req_user"],)

        for attr in ["policy_uri", "logo_uri", "tos_uri"]:
            try:
                authn_args[attr] = cinfo[attr]
            except KeyError:
                pass

        for attr in ["ui_locales", "acr_values"]:
            try:
                authn_args[attr] = areq[attr]
            except KeyError:
                pass

        # To authenticate or Not
        if identity is None:  # No!
            if "prompt" in areq and "none" in areq["prompt"]:
                # Need to authenticate but not allowed
                return redirect_authz_error(
                    "login_required", redirect_uri, return_type=areq["response_type"]
                )
            else:
                return authn(**authn_args)
        else:
            if re_authenticate(areq, authn):
                # demand re-authentication
                return authn(**authn_args)
            else:
                # I get back a dictionary
                user = identity["uid"]
                if "req_user" in kwargs:
                    sids_for_sub = self.sdb.get_by_sub(kwargs["req_user"])
                    if (
                        sids_for_sub
                        and user
                        != self.sdb.get_authentication_event(sids_for_sub[-1]).uid
                    ):
                        logger.debug("Wanted to be someone else!")
                        if "prompt" in areq and "none" in areq["prompt"]:
                            # Need to authenticate but not allowed
                            return redirect_authz_error("login_required", redirect_uri)
                        else:
                            return authn(**authn_args)

        authn_event = AuthnEvent(
            identity["uid"],
            identity.get("salt", ""),
            authn_info=authn_class_ref,
            time_stamp=_ts,
        )

        return {"authn_event": authn_event, "identity": identity, "user": user}

    def setup_session(self, areq, authn_event, cinfo):
        sid = self.sdb.create_authz_session(authn_event, areq)
        self.sdb.do_sub(sid, "")
        return sid

    def authorization_endpoint(self, request="", cookie="", **kwargs):
        """
        Authorize client.

        :param request: The client request
        """
        info = self.auth_init(request)
        if isinstance(info, Response):
            return info

        _cid = info["areq"]["client_id"]
        cinfo = self.cdb[_cid]

        authnres = self.do_auth(
            info["areq"], info["redirect_uri"], cinfo, request, cookie, **kwargs
        )

        if isinstance(authnres, Response):
            return authnres

        logger.debug("- authenticated -")
        logger.debug("AREQ keys: %s" % info["areq"].keys())

        sid = self.setup_session(info["areq"], authnres["authn_event"], cinfo)

        return self.authz_part2(authnres["user"], info["areq"], sid, cookie=cookie)

    def aresp_check(self, aresp, areq):
        return ""

    def create_authn_response(self, areq, sid):
        rtype = areq["response_type"][0]
        _func = self.response_type_map[rtype]
        aresp = _func(
            areq=areq, scode=self.sdb[sid]["code"], sdb=self.sdb, myself=self.baseurl
        )

        if rtype == "code":
            fragment_enc = False
        else:
            fragment_enc = True

        return aresp, fragment_enc

    def response_mode(self, areq, fragment_enc, **kwargs):
        resp_mode = areq["response_mode"]

        if resp_mode == "fragment" and not fragment_enc:
            # Can't be done
            raise InvalidRequest("wrong response_mode")
        elif resp_mode == "query" and fragment_enc:
            # Can't be done
            raise InvalidRequest("wrong response_mode")
        return None

    def authz_part2(self, user, areq, sid, **kwargs):
        """
        After the authentication this is where you should end up.

        :param user:
        :param areq: The Authorization Request
        :param sid: Session key
        :param kwargs: possible other parameters
        :return: A redirect to the redirect_uri of the client
        """
        result = self._complete_authz(user, areq, sid, **kwargs)
        if isinstance(result, Response):
            return result
        else:
            aresp, headers, redirect_uri, fragment_enc = result

        # Mix-Up mitigation
        aresp["iss"] = self.baseurl
        aresp["client_id"] = areq["client_id"]

        # Just do whatever is the default
        location = aresp.request(redirect_uri, fragment_enc)
        logger.debug("Redirected to: '%s' (%s)" % (location, type(location)))
        return SeeOther(str(location), headers=headers)

    def _complete_authz(self, user, areq, sid, **kwargs):
        _log_debug = logger.debug
        _log_debug("- in authenticated() -")

        # Do the authorization
        try:
            permission = self.authz(user, client_id=areq["client_id"])
            self.sdb.update(sid, "permission", permission)
        except Exception:
            raise

        _log_debug("response type: %s" % areq["response_type"])

        if self.sdb.is_revoked(sid):
            return error_response("access_denied", descr="Token is revoked")

        try:
            info = self.create_authn_response(areq, sid)
        except UnSupported as err:
            return error_response(*err.args)

        if isinstance(info, Response):
            return info
        else:
            aresp, fragment_enc = info

        try:
            redirect_uri = self.get_redirect_uri(areq)
        except (RedirectURIError, ParameterError) as err:
            return BadRequest("%s" % err)

        # Must not use HTTP unless implicit grant type and native application

        info = self.aresp_check(aresp, areq)
        if isinstance(info, Response):
            return info

        headers = []
        try:
            _kaka = kwargs["cookie"]
        except KeyError:
            _kaka = None

        c_val = "{}{}{}".format(user, DELIM, areq["client_id"])

        cookie_header = None
        if _kaka is not None:
            if self.cookie_name not in _kaka:  # Don't overwrite
                cookie_header = self.cookie_func(
                    c_val, typ="sso", cookie_name=self.sso_cookie_name, ttl=self.sso_ttl
                )
        else:
            cookie_header = self.cookie_func(
                c_val, typ="sso", cookie_name=self.sso_cookie_name, ttl=self.sso_ttl
            )

        if cookie_header is not None:
            headers.append(cookie_header)
        # Now about the response_mode. Should not be set if it's obvious
        # from the response_type. Knows about 'query', 'fragment' and
        # 'form_post'.

        if "response_mode" in areq:
            try:
                resp = self.response_mode(
                    areq,
                    fragment_enc,
                    aresp=aresp,
                    redirect_uri=redirect_uri,
                    headers=headers,
                )
            except InvalidRequest as err:
                return error_response("invalid_request", str(err))
            else:
                if resp is not None:
                    return resp

        return aresp, headers, redirect_uri, fragment_enc

    def token_scope_check(self, areq, info):
        """Not implemented here."""
        return None

    def token_endpoint(self, request="", authn="", dtype="urlencoded", **kwargs):
        """
        Provide clients with access tokens.

        :param authn: Auhentication info, comes from HTTP header.
        :param request: The request.
        :param dtype: deserialization method for the request.
        """
        logger.debug("- token -")
        logger.debug("token_request: %s" % sanitize(request))

        areq = self.server.message_factory.get_request_type(
            "token_endpoint"
        )().deserialize(request, dtype)

        # Verify client authentication
        try:
            client_id = self.client_authn(self, areq, authn)
        except (FailedAuthentication, AuthnFailure) as err:
            logger.error("%s", err)
            error = TokenErrorResponse(
                error="unauthorized_client", error_description="%s" % err
            )
            return Unauthorized(error.to_json(), content="application/json")

        logger.debug("AccessTokenRequest: %s" % sanitize(areq))

        # `code` is not mandatory for all requests
        if "code" in areq:
            try:
                _info = self.sdb[areq["code"]]
            except KeyError:
                logger.error("Code not present in SessionDB")
                error = TokenErrorResponse(
                    error="unauthorized_client", error_description="Invalid code."
                )
                return Unauthorized(error.to_json(), content="application/json")

            resp = self.token_scope_check(areq, _info)
            if resp:
                return resp
            # If redirect_uri was in the initial authorization request verify that they match
            if (
                "redirect_uri" in _info
                and areq["redirect_uri"] != _info["redirect_uri"]
            ):
                logger.error("Redirect_uri mismatch")
                error = TokenErrorResponse(
                    error="unauthorized_client",
                    error_description="Redirect_uris do not match.",
                )
                return Unauthorized(error.to_json(), content="application/json")
            if "state" in areq:
                if _info["state"] != areq["state"]:
                    logger.error("State value mismatch")
                    error = TokenErrorResponse(
                        error="unauthorized_client",
                        error_description="State values do not match.",
                    )
                    return Unauthorized(error.to_json(), content="application/json")

        # Propagate the client_id further
        areq.setdefault("client_id", client_id)
        grant_type = areq["grant_type"]
        if grant_type == "authorization_code":
            return self.code_grant_type(areq)
        elif grant_type == "refresh_token":
            return self.refresh_token_grant_type(areq)
        elif grant_type == "client_credentials":
            return self.client_credentials_grant_type(areq)
        elif grant_type == "password":
            return self.password_grant_type(areq)
        else:
            raise UnSupported("grant_type: {}".format(grant_type))

    def code_grant_type(self, areq):
        """
        Token authorization using Code Grant.

        RFC6749 section 4.1
        """
        try:
            _tinfo = self.sdb.upgrade_to_token(areq["code"], issue_refresh=True)
        except AccessCodeUsed:
            error = TokenErrorResponse(
                error="invalid_grant", error_description="Access grant used"
            )
            return Unauthorized(error.to_json(), content="application/json")

        logger.debug("_tinfo: %s" % sanitize(_tinfo))

        atr = AccessTokenResponse(**by_schema(AccessTokenResponse, **_tinfo))

        logger.debug("AccessTokenResponse: %s" % sanitize(atr))

        return Response(
            atr.to_json(), content="application/json", headers=OAUTH2_NOCACHE_HEADERS
        )

    def refresh_token_grant_type(self, areq):
        """
        Token refresh.

        RFC6749 section 6
        """
        # This is not implemented here, please see oic.extension.provider.
        return error_response("unsupported_grant_type", descr="Unsupported grant_type")

    def client_credentials_grant_type(self, areq):
        """
        Token authorization using client credentials.

        RFC6749 section 4.4
        """
        # This is not implemented here, please see oic.extension.provider.
        return error_response("unsupported_grant_type", descr="Unsupported grant_type")

    def password_grant_type(self, areq):
        """
        Token authorization using Resource owner password credentials.

        RFC6749 section 4.3
        """
        # This is not implemented here, please see oic.extension.provider.
        return error_response("unsupported_grant_type", descr="Unsupported grant_type")

    def verify_endpoint(self, request="", cookie=None, **kwargs):
        _req = parse_qs(request)
        try:
            areq = parse_qs(_req["query"][0])
        except KeyError:
            return BadRequest("Could not verify endpoint")

        authn, acr = self.pick_auth(areq=areq)
        kwargs["cookie"] = cookie
        return authn.verify(_req, **kwargs)

    def write_session_cookie(self, value, http_only=True, same_site=""):
        return make_cookie(
            self.session_cookie_name,
            value,
            self.seed,
            path="/",
            httponly=http_only,
            same_site=same_site,
        )

    def delete_session_cookie(self):
        return make_cookie(self.session_cookie_name, "", b"", path="/", expire=-1)

    def _compute_session_state(self, state, salt, client_id, redirect_uri):
        parsed_uri = urlparse(redirect_uri)
        rp_origin_url = "{uri.scheme}://{uri.netloc}".format(uri=parsed_uri)

        logger.debug(
            "Calculating sessions state using, client_id:%s origin:%s state:%s salt:%s",
            client_id,
            rp_origin_url,
            state,
            salt,
        )

        session_str = client_id + " " + rp_origin_url + " " + state + " " + salt
        return hashlib.sha256(session_str.encode("utf-8")).hexdigest() + "." + salt
