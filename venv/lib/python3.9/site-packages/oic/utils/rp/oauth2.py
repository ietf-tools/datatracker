import copy
import hashlib
import logging
from typing import Dict
from typing import Type
from typing import Union
from typing import cast
from urllib.parse import urlsplit

from oic import rndstr
from oic.extension import client
from oic.extension.message import ClientInfoResponse
from oic.oauth2 import AccessTokenResponse
from oic.oauth2 import AuthorizationRequest
from oic.oauth2 import AuthorizationResponse
from oic.oauth2 import ErrorResponse
from oic.oauth2 import ResponseError
from oic.oauth2 import TokenError
from oic.oauth2.message import ASConfigurationResponse
from oic.utils.authn.client import CLIENT_AUTHN_METHOD
from oic.utils.http_util import Redirect
from oic.utils.sanitize import sanitize
from oic.utils.webfinger import WebFinger

__author__ = "roland"


logger = logging.getLogger(__name__)


class OAuth2Error(Exception):
    pass


class OAuthClient(client.Client):
    def __init__(
        self,
        client_id=None,
        client_prefs=None,
        client_authn_method=None,
        keyjar=None,
        verify_ssl=True,
        behaviour=None,
        jwks_uri="",
        kid=None,
    ):
        client.Client.__init__(
            self, client_id, client_authn_method, keyjar=keyjar, verify_ssl=verify_ssl
        )
        self.behaviour = behaviour or {}
        self.userinfo_request_method = ""
        self.allow_sign_alg_none = False
        self.authz_req = {}
        self.get_userinfo = True
        self.jwks_uri = jwks_uri
        self.kid = kid
        self.client_prefs = client_prefs
        # Make it the same. Been bitten by this too many times !
        self.keyjar.verify_ssl = verify_ssl

    def create_authn_request(self, session, acr_value=None, **kwargs):
        assert self.registration_response is not None  # nosec
        session["state"] = rndstr(32)
        request_args = {
            "response_type": self.behaviour["response_type"],
            "state": session["state"],
            "redirect_uri": self.registration_response["redirect_uris"][0],
        }

        try:
            request_args["scope"] = self.behaviour["scope"]
        except KeyError:
            pass

        request_args.update(kwargs)
        cis = self.construct_AuthorizationRequest(request_args=request_args)
        logger.debug("request: %s" % sanitize(cis))

        url, body, ht_args, cis = cast(
            AuthorizationRequest,
            self.uri_and_body(
                AuthorizationRequest, cis, method="GET", request_args=request_args
            ),
        )

        self.authz_req[request_args["state"]] = cis
        logger.debug("body: %s" % sanitize(body))
        logger.info("URL: %s" % sanitize(url))
        logger.debug("ht_args: %s" % sanitize(ht_args))

        resp = Redirect(str(url))
        if ht_args:
            resp.headers.extend([(a, b) for a, b in ht_args.items()])
        logger.debug("resp_headers: %s" % sanitize(resp.headers))
        return resp

    def has_access_token(self, **kwargs):
        try:
            token = self.get_token(**kwargs)
        except TokenError:
            pass
        else:
            if token.access_token:
                return True
        return False

    def _err(self, txt):
        logger.error(sanitize(txt))
        raise OAuth2Error(txt)

    def callback(self, response, session, format="dict"):
        """
        Call when an AuthN response has been received from the OP.

        :param response: The URL returned by the OP
        :return:
        """
        if self.behaviour["response_type"] == "code":
            respcls: Union[Type[AuthorizationResponse], Type[AccessTokenResponse]] = (
                AuthorizationResponse
            )
        else:
            respcls = AccessTokenResponse

        try:
            authresp = self.parse_response(
                respcls, response, sformat=format, keyjar=self.keyjar
            )
        except ResponseError:
            msg = "Could not parse response: '{}'"
            logger.error(msg.format(sanitize(response)))
            raise OAuth2Error("Problem parsing response")

        logger.info("{}: {}".format(respcls.__name__, sanitize(authresp)))

        if isinstance(authresp, ErrorResponse):
            if authresp["error"] == "login_required":
                return self.create_authn_request(session)
            else:
                raise OAuth2Error("Access denied")

        if authresp["state"] not in self.authz_req:
            self._err("Received state not the same as expected.")

        if self.behaviour["response_type"] == "code":
            # get the access token
            assert self.registration_response is not None  # nosec
            try:
                args = {
                    "code": authresp["code"],
                    "redirect_uri": self.registration_response["redirect_uris"][
                        0
                    ],  # type: ignore
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                }

                try:
                    args["scope"] = response["scope"]
                except KeyError:
                    pass

                atresp = self.do_access_token_request(
                    state=authresp["state"],
                    request_args=args,
                    authn_method=self.registration_response[
                        "token_endpoint_auth_method"
                    ],
                )
                logger.info("Access token response: {}".format(sanitize(atresp)))
            except Exception as err:
                logger.error("%s", err)
                raise

            if isinstance(atresp, ErrorResponse):
                self._err("Error response: {}".format(atresp.to_dict()))

            _token = atresp["access_token"]
        else:
            _token = authresp["access_token"]

        return {"access_token": _token}


class OAuthClients(object):
    def __init__(self, config, base_url, seed="", jwks_info=None, verify_ssl=True):
        """
        Initialize the client.

        :param config: Imported configuration module
        :return:
        """
        self.client: Dict[str, OAuthClient] = {}
        self.client_cls = OAuthClient
        self.config = config
        self.seed = seed or rndstr(16)
        self.seed = self.seed.encode("utf8")
        self.path: Dict[str, str] = {}
        self.base_url = base_url
        self.jwks_info = jwks_info
        self.verify_ssl = verify_ssl

        for key, val in config.CLIENTS.items():
            if self.jwks_info:
                _val = val.copy()
                _val.update(self.jwks_info)
            else:
                _val = val

            if key == "":
                continue
            else:
                self.client[key] = self.create_client(**_val)

    def get_path(self, redirect_uris, issuer):
        for ruri in redirect_uris:
            p = urlsplit(ruri)
            self.path[p.path[1:]] = issuer

    def create_client(self, **kwargs):
        """
        Do an instantiation of a client instance.

        :param: Keyword arguments
            Keys are:
                srv_discovery_url
                client_info
                client_registration
                provider_info
                behaviour
        :return: client instance
        """
        _key_set = set(list(kwargs.keys()))
        try:
            _verify_ssl = kwargs["verify_ssl"]
        except KeyError:
            _verify_ssl = self.verify_ssl
        else:
            _key_set.discard("verify_ssl")

        _client = self.client_cls(
            client_authn_method=CLIENT_AUTHN_METHOD,
            behaviour=kwargs["behaviour"],
            verify_ssl=_verify_ssl,
        )

        # The behaviour parameter is not significant for the election process
        _key_set.discard("behaviour")

        for param in ["allow"]:
            try:
                setattr(_client, param, kwargs[param])
            except KeyError:
                pass
            else:
                _key_set.discard(param)

        if _key_set == {"client_info", "srv_discovery_url"}:
            # Ship the webfinger part
            # Gather OP information
            _client.provider_config(kwargs["srv_discovery_url"])
            # register the client
            _client.register(
                _client.provider_info["registration_endpoint"], **kwargs["client_info"]
            )
            self.get_path(
                kwargs["client_info"]["redirect_uris"], kwargs["srv_discovery_url"]
            )
        elif _key_set == {"provider_info", "client_info"}:
            _client.handle_provider_config(
                ASConfigurationResponse(**kwargs["provider_info"]),
                kwargs["provider_info"]["issuer"],
            )
            _client.register(
                _client.provider_info["registration_endpoint"], **kwargs["client_info"]
            )

            self.get_path(
                kwargs["client_info"]["redirect_uris"],
                kwargs["provider_info"]["issuer"],
            )
        elif _key_set == {"provider_info", "client_registration"}:
            _client.handle_provider_config(
                ASConfigurationResponse(**kwargs["provider_info"]),
                kwargs["provider_info"]["issuer"],
            )
            _client.store_registration_info(
                ClientInfoResponse(**kwargs["client_registration"])
            )
            self.get_path(
                kwargs["client_info"]["redirect_uris"],
                kwargs["provider_info"]["issuer"],
            )
        elif _key_set == {"srv_discovery_url", "client_registration"}:
            _client.provider_config(kwargs["srv_discovery_url"])
            _client.store_registration_info(
                ClientInfoResponse(**kwargs["client_registration"])
            )
            self.get_path(
                kwargs["client_registration"]["redirect_uris"],
                kwargs["srv_discovery_url"],
            )
        else:
            raise Exception("Configuration error ?")

        return client

    def dynamic_client(self, issuer="", userid=""):
        client = self.client_cls(
            client_authn_method=CLIENT_AUTHN_METHOD,
            verify_ssl=self.verify_ssl,
            **self.jwks_info,
        )
        if userid:
            wf = WebFinger(httpd=client)
            issuer = wf.discovery_query(userid)

        if not issuer:
            raise OAuth2Error("Missing issuer")

        logger.info("issuer: {}".format(issuer))

        if issuer in self.client:
            return self.client[issuer]
        else:
            # Gather OP information
            _pcr = client.provider_config(issuer)
            logger.info("Provider info: {}".format(sanitize(_pcr.to_dict())))
            issuer = _pcr["issuer"]  # So no hickup later about trailing '/'
            # register the client
            _cinfo = self.config.CLIENTS[""]["client_info"]
            reg_args = copy.copy(_cinfo)
            h = hashlib.sha256(self.seed)
            h.update(issuer.encode("utf8"))  # issuer has to be bytes
            base_urls = _cinfo["redirect_uris"]

            reg_args["redirect_uris"] = [
                u.format(base=self.base_url, iss=h.hexdigest()) for u in base_urls
            ]
            try:
                reg_args["post_logout_redirect_uris"] = [
                    u.format(base=self.base_url, iss=h.hexdigest())
                    for u in reg_args["post_logout_redirect_uris"]
                ]
            except KeyError:
                pass

            self.get_path(reg_args["redirect_uris"], issuer)
            if client.jwks_uri:
                reg_args["jwks_uri"] = client.jwks_uri

            rr = client.register(_pcr["registration_endpoint"], **reg_args)
            msg = "Registration response: {}"
            logger.info(msg.format(sanitize(rr.to_dict())))

            try:
                client.behaviour.update(**self.config.CLIENTS[""]["behaviour"])
            except KeyError:
                pass

            self.client[issuer] = client
            return client

    def __getitem__(self, item):
        """
        Given a service identifier return a suitable client.

        :param item:
        :return:
        """
        try:
            return self.client[item]
        except KeyError:
            return self.dynamic_client(issuer=item)

    def __delitem__(self, key):
        del self.client[key]

    def keys(self):
        return list(self.client.keys())

    def return_paths(self):
        return self.path.keys()
