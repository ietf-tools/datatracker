import copy
import hashlib
import logging
from typing import Dict
from urllib.parse import urlsplit

from oic import oic
from oic import rndstr
from oic.exception import MissingAttribute
from oic.oauth2 import ErrorResponse
from oic.oauth2 import ResponseError
from oic.oauth2 import TokenError
from oic.oauth2.message import ASConfigurationResponse
from oic.oic import AuthorizationRequest
from oic.oic import AuthorizationResponse
from oic.oic import RegistrationResponse
from oic.oic.message import OpenIDSchema
from oic.utils.authn.client import CLIENT_AUTHN_METHOD
from oic.utils.http_util import Redirect
from oic.utils.sanitize import sanitize

__author__ = "roland"


logger = logging.getLogger(__name__)


class OIDCError(Exception):
    pass


class Client(oic.Client):
    def __init__(
        self,
        client_id=None,
        client_prefs=None,
        client_authn_method=None,
        keyjar=None,
        verify_ssl=True,
        behaviour=None,
        config=None,
        jwks_uri="",
        kid=None,
    ):
        oic.Client.__init__(
            self,
            client_id,
            client_prefs,
            client_authn_method,
            keyjar,
            verify_ssl,
            config=config,
        )
        if behaviour:
            self.behaviour = behaviour
        self.userinfo_request_method = ""
        self.allow_sign_alg_none = False
        self.authz_req = {}
        self.get_userinfo = True
        self.oidc = True
        self.jwks_uri = jwks_uri
        self.kid = kid

    def create_authn_request(self, session, acr_value=None, **kwargs):
        session["state"] = rndstr(32)
        request_args = {
            "response_type": self.behaviour["response_type"],
            "scope": self.behaviour["scope"],
            "state": session["state"],
            "redirect_uri": self.registration_response["redirect_uris"][0],
        }

        if self.oidc:
            session["nonce"] = rndstr(32)
            request_args["nonce"] = session["nonce"]

        if acr_value is not None:
            request_args["acr_values"] = acr_value

        request_args.update(kwargs)
        cis = self.construct_AuthorizationRequest(request_args=request_args)
        logger.debug("request: %s" % sanitize(cis))

        url, body, ht_args, cis = self.uri_and_body(
            AuthorizationRequest, cis, method="GET", request_args=request_args
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
        raise OIDCError(txt)

    def _do_code(self, response, authresp):
        """Perform code flow."""
        # get the access token
        try:
            args = {
                "code": authresp["code"],
                "redirect_uri": self.registration_response["redirect_uris"][0],
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
                authn_method=self.registration_response["token_endpoint_auth_method"],
            )
            msg = "Access token response: {}"
            logger.info(msg.format(sanitize(atresp)))
        except Exception as err:
            logger.error("%s", err)
            raise

        if isinstance(atresp, ErrorResponse):
            msg = "Error response: {}"
            self._err(msg.format(sanitize(atresp.to_dict())))

        _token = atresp["access_token"]

        _id_token = atresp.get("id_token")
        return _token, _id_token

    def callback(self, response, session, format="dict"):
        """
        Call when an AuthN response has been received from the OP.

        :param response: The URL returned by the OP
        :return:
        """
        try:
            authresp = self.parse_response(
                AuthorizationResponse, response, sformat=format, keyjar=self.keyjar
            )
        except ResponseError:
            msg = "Could not parse response: '{}'"
            logger.error(msg.format(sanitize(response)))
            raise OIDCError("Problem parsing response")

        logger.info("AuthorizationReponse: {}".format(sanitize(authresp)))
        if isinstance(authresp, ErrorResponse):
            if authresp["error"] == "login_required":
                return self.create_authn_request(session)
            else:
                raise OIDCError("Access denied")

        _state = authresp["state"]

        _id_token = authresp.get("id_token")
        if (
            _id_token is not None
            and _id_token["nonce"] != self.authz_req[_state]["nonce"]
        ):
            self._err("Received nonce not the same as expected.")

        if self.behaviour["response_type"] == "code":
            _token, new_id_token = self._do_code(response, authresp)
            if new_id_token is not None:
                _id_token = new_id_token
        else:
            _token = authresp["access_token"]

        if not self.oidc:
            return {"access_token": _token}

        if _id_token is None:
            self._err("Invalid response: no IdToken")

        if _id_token["iss"] != self.provider_info["issuer"]:
            self._err("Issuer mismatch")

        if _id_token["nonce"] != self.authz_req[_state]["nonce"]:
            self._err("Nonce mismatch")

        if not self.allow_sign_alg_none:
            if _id_token.jws_header["alg"] == "none":
                self._err('Do not allow "none" signature algorithm')

        user_id = "{}:{}".format(_id_token["iss"], _id_token["sub"])

        if self.get_userinfo:
            if self.userinfo_request_method:
                kwargs = {"method": self.userinfo_request_method}
            else:
                kwargs = {}

            if self.has_access_token(state=authresp["state"]):
                inforesp = self.do_user_info_request(state=authresp["state"], **kwargs)

                if isinstance(inforesp, ErrorResponse):
                    self._err("Invalid response %s." % inforesp["error"])

                userinfo = inforesp.to_dict()

                if _id_token["sub"] != userinfo["sub"]:
                    self._err("Invalid response: userid mismatch")

                logger.debug("UserInfo: %s" % sanitize(inforesp))

                try:
                    self.id_token[user_id] = _id_token
                except TypeError:
                    self.id_token = {user_id: _id_token}
            else:
                userinfo = {}
                for attr in OpenIDSchema.c_param:
                    try:
                        userinfo[attr] = _id_token[attr]
                    except KeyError:
                        pass

            return {
                "user_id": user_id,
                "userinfo": userinfo,
                "id_token": _id_token,
                "access_token": _token,
            }
        else:
            return {"user_id": user_id, "id_token": _id_token, "access_token": _token}


class OIDCClients(object):
    def __init__(self, config, base_url, seed="", jwks_info=None, verify_ssl=True):
        """
        Initialize the client.

        :param config: Imported configuration module
        :return:
        """
        self.client: Dict[str, Client] = {}
        self.client_cls = Client
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

    def create_client(self, userid="", **kwargs):
        """
        Do an instantiation of a client instance.

        :param userid: An identifier of the user
        :param: Keyword arguments
            Keys are ["srv_discovery_url", "client_info", "client_registration",
            "provider_info"]
        :return: client instance
        """
        _key_set = set(list(kwargs.keys()))
        try:
            _verify_ssl = kwargs["verify_ssl"]
        except KeyError:
            _verify_ssl = self.verify_ssl
        else:
            _key_set.discard("verify_ssl")

        client = self.client_cls(
            client_authn_method=CLIENT_AUTHN_METHOD,
            behaviour=kwargs["behaviour"],
            verify_ssl=_verify_ssl,
        )

        try:
            client.userinfo_request_method = kwargs["userinfo_request_method"]
        except KeyError:
            pass
        else:
            _key_set.discard("userinfo_request_method")

        # The behaviour parameter is not significant for the election process
        _key_set.discard("behaviour")
        for param in ["allow"]:
            try:
                setattr(client, param, kwargs[param])
            except KeyError:
                pass
            else:
                _key_set.discard(param)

        if _key_set == {"client_info"}:  # Everything dynamic
            # There has to be a userid
            if not userid:
                raise MissingAttribute("Missing userid specification")

            # Find the service that provides information about the OP
            issuer = client.wf.discovery_query(userid)
            # Gather OP information
            client.provider_config(issuer)
            # register the client
            client.register(
                client.provider_info["registration_endpoint"], **kwargs["client_info"]
            )
            self.get_path(kwargs["client_info"]["redirect_uris"], issuer)
        elif _key_set == set(["client_info", "srv_discovery_url"]):
            # Ship the webfinger part
            # Gather OP information
            client.provider_config(kwargs["srv_discovery_url"])
            # register the client
            client.register(
                client.provider_info["registration_endpoint"], **kwargs["client_info"]
            )
            self.get_path(
                kwargs["client_info"]["redirect_uris"], kwargs["srv_discovery_url"]
            )
        elif _key_set == set(["provider_info", "client_info"]):
            client.handle_provider_config(
                ASConfigurationResponse(**kwargs["provider_info"]),
                kwargs["provider_info"]["issuer"],
            )
            client.register(
                client.provider_info["registration_endpoint"], **kwargs["client_info"]
            )

            self.get_path(
                kwargs["client_info"]["redirect_uris"],
                kwargs["provider_info"]["issuer"],
            )
        elif _key_set == set(["provider_info", "client_registration"]):
            client.handle_provider_config(
                ASConfigurationResponse(**kwargs["provider_info"]),
                kwargs["provider_info"]["issuer"],
            )
            client.store_registration_info(
                RegistrationResponse(**kwargs["client_registration"])
            )
            self.get_path(
                kwargs["client_info"]["redirect_uris"],
                kwargs["provider_info"]["issuer"],
            )
        elif _key_set == set(["srv_discovery_url", "client_registration"]):
            client.provider_config(kwargs["srv_discovery_url"])
            client.store_registration_info(
                RegistrationResponse(**kwargs["client_registration"])
            )
            self.get_path(
                kwargs["client_registration"]["redirect_uris"],
                kwargs["srv_discovery_url"],
            )
        else:
            raise Exception("Configuration error ?")

        return client

    def dynamic_client(self, userid="", issuer=""):
        client = self.client_cls(
            client_authn_method=CLIENT_AUTHN_METHOD,
            verify_ssl=self.verify_ssl,
            **self.jwks_info,
        )

        if userid:
            issuer = client.wf.discovery_query(userid)

        if not issuer:
            raise OIDCError("Missing issuer")

        logger.info("issuer: {}".format(issuer))
        if issuer in self.client:
            return self.client[issuer]
        else:
            # Gather OP information
            _pcr = client.provider_config(issuer)
            logger.info("Provider info: {}".format(sanitize(_pcr.to_dict())))
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
        Given a service or user identifier return a suitable client.

        :param item:
        :return:
        """
        try:
            return self.client[item]
        except KeyError:
            return self.dynamic_client(issuer=item)

    def keys(self):
        return list(self.client.keys())

    def return_paths(self):
        return self.path.keys()
