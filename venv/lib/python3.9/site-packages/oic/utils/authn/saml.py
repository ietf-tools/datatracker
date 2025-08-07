try:
    import saml2
except ImportError:
    raise ImportError("This module can be used only with saml2 installed.")


import base64
import importlib
import json
import logging
from typing import Dict
from typing import List
from urllib.parse import parse_qs
from urllib.parse import urlencode

from saml2 import BINDING_HTTP_ARTIFACT
from saml2 import BINDING_HTTP_POST
from saml2 import BINDING_HTTP_REDIRECT
from saml2.client import Saml2Client
from saml2.config import SPConfig
from saml2.s_utils import UnknownPrincipal
from saml2.s_utils import UnsupportedBinding
from saml2.s_utils import rndstr
from saml2.s_utils import sid

from oic.oauth2.exception import VerificationError
from oic.utils.authn.user import UserAuthnMethod
from oic.utils.authn.user import create_return_url
from oic.utils.http_util import Response
from oic.utils.http_util import SeeOther
from oic.utils.http_util import Unauthorized

logger = logging.getLogger(__name__)


class ServiceErrorException(Exception):
    pass


# This class handles user authentication with CAS.
class SAMLAuthnMethod(UserAuthnMethod):
    CONST_QUERY = "query"
    CONST_SAML_COOKIE = "samlauthc"
    CONST_HASIDP = "hasidp"

    def __init__(
        self,
        srv,
        lookup,
        userdb,
        spconf,
        url,
        return_to,
        cache=None,
        bindings=None,
        userinfo=None,
        samlcache=None,
    ):
        """
        Construct the class.

        :param srv: Usually none, but otherwise the oic server.
        :param return_to: The URL to return to after a successful
        authentication.
        """
        self.userdb = userdb
        self.userinfo = userinfo

        if cache is None:
            self.cache_outstanding_queries: Dict[str, str] = {}
        else:
            self.cache_outstanding_queries = cache
        UserAuthnMethod.__init__(self, srv)
        self.return_to = return_to
        self.idp_query_param = "IdpQuery"
        if bindings:
            self.bindings = bindings
        else:
            self.bindings = [
                BINDING_HTTP_REDIRECT,
                BINDING_HTTP_POST,
                BINDING_HTTP_ARTIFACT,
            ]
        # TODO Why does this exist?
        self.verification_endpoint = ""
        # Configurations for the SP handler.
        self.sp_conf = importlib.import_module(spconf)
        config = SPConfig().load(self.sp_conf.CONFIG)  # type: ignore
        self.sp = Saml2Client(config=config)
        mte = lookup.get_template("unauthorized.mako")
        argv = {"message": "You are not authorized!"}
        self.not_authorized = mte.render(**argv)
        self.samlcache = self.sp_conf.SAML_CACHE  # type: ignore

    def __call__(self, query="", end_point_index=None, *args, **kwargs):
        (done, response) = self._pick_idp(query, end_point_index)
        if done == 0:
            entity_id = response
            # Do the AuthnRequest
            resp = self._redirect_to_auth(self.sp, entity_id, query, end_point_index)
            return resp
        return response

    def verify(self, request, cookie, path, requrl, end_point_index=None, **kwargs):
        """
        Verify if the authentication was successful.

        :rtype : Response
        :param request: Contains the request parameters.
        :param cookie: Cookies sent with the request.
        :param kwargs: Any other parameters.
        :return: If the authentication was successful: a redirect to the
        return_to url. Otherwise a unauthorized response.
        :raise: ValueError
        """
        if isinstance(request, str):
            request = parse_qs(request)
        elif isinstance(request, dict):
            pass
        else:
            raise ValueError("Wrong type of input")

        acs = self.sp.config.getattr("endpoints", "sp")["assertion_consumer_service"]
        acs_endpoints = [(ep[0].rsplit("/", 1)[1], ep[1]) for ep in acs]
        binding = None
        path = path[1:]
        for endp in acs_endpoints:
            if path == endp[0]:
                binding = endp[1]
                break

        saml_cookie, _ts, _typ = self.getCookieValue(cookie, self.CONST_SAML_COOKIE)
        data = json.loads(saml_cookie)

        rp_query_cookie = self.get_multi_auth_cookie(cookie)

        query = rp_query_cookie

        if not query:
            query = base64.b64decode(data[self.CONST_QUERY]).decode("ascii")

        if data[self.CONST_HASIDP] == "False":
            (done, response) = self._pick_idp(request, end_point_index)
            if done == 0:
                entity_id = response
                # Do the AuthnRequest
                resp = self._redirect_to_auth(
                    self.sp, entity_id, query, end_point_index
                )
                return resp, False
            return response, False

        if not request:
            logger.info("Missing Response")
            return Unauthorized("You are not authorized!"), False

        try:
            response = self.sp.parse_authn_request_response(
                request["SAMLResponse"][0], binding, self.cache_outstanding_queries
            )
        except UnknownPrincipal as excp:
            logger.error("UnknownPrincipal: %s" % (excp,))
            return Unauthorized(self.not_authorized), False
        except UnsupportedBinding as excp:
            logger.error("UnsupportedBinding: %s" % (excp,))
            return Unauthorized(self.not_authorized), False
        except VerificationError as err:
            logger.error("Verification error: %s" % (err,))
            return Unauthorized(self.not_authorized), False
        except Exception as err:
            logger.error("Other error: %s" % (err,))
            return Unauthorized(self.not_authorized), False

        if self.sp_conf.VALID_ATTRIBUTE_RESPONSE is not None:  # type: ignore
            for k, v in self.sp_conf.VALID_ATTRIBUTE_RESPONSE.items():  # type: ignore
                if k not in response.ava:
                    return Unauthorized(self.not_authorized), False
                else:
                    allowed = False
                    for allowed_attr_value in v:
                        if isinstance(response.ava[k], list):
                            for resp_value in response.ava[k]:
                                if allowed_attr_value in resp_value:
                                    allowed = True
                                    break
                        elif allowed_attr_value in response.ava[k]:
                            allowed = True
                            break
                    if not allowed:
                        return Unauthorized(self.not_authorized), False

        # logger.info("parsed OK")'
        uid = response.assertion.subject.name_id.text
        if self.userinfo == "AA":
            if response.entity_id is not None and self.samlcache is not None:
                self.samlcache["AA_ENTITYID"] = response.entity_id
        self.setup_userdb(uid, response.ava)

        return_to = create_return_url(self.return_to, uid, **{self.query_param: "true"})
        if "?" in return_to:
            return_to += "&"
        else:
            return_to += "?"
        return_to += query

        auth_cookie = self.create_cookie(uid, "samlm")
        resp = SeeOther(str(return_to), headers=[auth_cookie])
        return resp, True

    def setup_userdb(self, uid, samldata):
        attributes = {}
        if self.sp_conf.ATTRIBUTE_WHITELIST is not None:  # type: ignore
            for (
                attr,
                allowed,
            ) in self.sp_conf.ATTRIBUTE_WHITELIST.items():  # type: ignore
                if attr in samldata:
                    if allowed is not None:
                        tmp_attr_list = []
                        for tmp_value in samldata[attr]:
                            for allowed_str in allowed:
                                if allowed_str in tmp_value:
                                    tmp_attr_list.append(tmp_value)
                        if len(tmp_attr_list) > 0:
                            attributes[attr] = tmp_attr_list
                    else:
                        attributes[attr] = samldata[attr]
        else:
            attributes = samldata
        userdb: Dict[str, List[str]] = {}

        if self.sp_conf.OPENID2SAMLMAP is None:  # type: ignore
            userdb = attributes.copy()
        else:
            for oic, saml in self.sp_conf.OPENID2SAMLMAP.items():  # type: ignore
                if saml in attributes:
                    userdb[oic] = attributes[saml]
        self.userdb[uid] = userdb

    def _pick_idp(self, query, end_point_index):
        """If more than one idp and if none is selected, I have to do wayf or disco."""
        query_dict: Dict[str, List[str]] = {}
        if isinstance(query, str):
            query_dict = dict(parse_qs(query))
        else:
            for key, value in query.items():
                if isinstance(value, list):
                    query_dict[key] = value[0]
                else:
                    query_dict[key] = value
            query = urlencode(query_dict)

        _cli = self.sp
        # Find all IdPs
        idps = self.sp.metadata.with_descriptor("idpsso")

        idp_entity_id = None

        if len(idps) == 1:
            # idps is a dictionary
            idp_entity_id = list(idps.keys())[0]

        if not idp_entity_id and query:
            try:
                _idp_entity_id = query_dict[self.idp_query_param][0]
                if _idp_entity_id in idps:
                    idp_entity_id = _idp_entity_id
            except KeyError:
                logger.debug("No IdP entity ID in query: %s" % query)
                pass

        if not idp_entity_id:
            cookie = self.create_cookie(
                '{"'
                + self.CONST_QUERY
                + '": "'
                + base64.b64encode(query).decode()
                + '" , "'
                + self.CONST_HASIDP
                + '": "False" }',
                self.CONST_SAML_COOKIE,
                self.CONST_SAML_COOKIE,
            )
            if self.sp_conf.WAYF:  # type: ignore
                if query:
                    try:
                        wayf_selected = query_dict["wayf_selected"][0]
                    except KeyError:
                        return self._wayf_redirect(cookie)
                    idp_entity_id = wayf_selected
                else:
                    return self._wayf_redirect(cookie)
            elif self.sp_conf.DISCOSRV:  # type: ignore
                if query:
                    idp_entity_id = _cli.parse_discovery_service_response(query=query)
                if not idp_entity_id:
                    sid_ = sid()
                    self.cache_outstanding_queries[sid_] = self.verification_endpoint
                    eid = _cli.config.entityid

                    disco_end_point_index = end_point_index["disco_end_point_index"]
                    ret = _cli.config.getattr("endpoints", "sp")["discovery_response"][
                        disco_end_point_index
                    ][0]
                    ret += "?sid=%s" % sid_
                    loc = _cli.create_discovery_service_request(
                        self.sp_conf.DISCOSRV, eid, **{"return": ret}  # type: ignore
                    )
                    return -1, SeeOther(loc, headers=[cookie])
            elif not len(idps):
                raise ServiceErrorException(
                    "Misconfiguration for the SAML Service Provider!"
                )
            else:
                return -1, NotImplemented
        return 0, idp_entity_id

    def _wayf_redirect(self, cookie):
        sid_ = sid()
        self.cache_outstanding_queries[sid_] = self.verification_endpoint
        return (
            -1,
            SeeOther(
                headers=[
                    ("Location", "%s?%s" % (self.sp_conf.WAYF, sid_)),  # type: ignore
                    cookie,
                ]
            ),
        )

    def _redirect_to_auth(self, _cli, entity_id, query, end_point_index, vorg_name=""):
        try:
            binding, destination = _cli.pick_binding(
                "single_sign_on_service", self.bindings, "idpsso", entity_id=entity_id
            )
            logger.debug("binding: %s, destination: %s" % (binding, destination))

            extensions = None
            kwargs = {}

            if end_point_index:
                kwargs["assertion_consumer_service_index"] = str(
                    end_point_index[binding]
                )

            if _cli.authn_requests_signed:
                _sid = saml2.s_utils.sid(_cli.seed)
                req_id, msg_str = _cli.create_authn_request(
                    destination,
                    vorg=vorg_name,
                    sign=_cli.authn_requests_signed,
                    message_id=_sid,
                    extensions=extensions,
                    **kwargs,
                )
                _sid = req_id
            else:
                req_id, req = _cli.create_authn_request(
                    destination, vorg=vorg_name, sign=False, **kwargs
                )
                msg_str = "%s" % req
                _sid = req_id

            _rstate = rndstr()
            ht_args = _cli.apply_binding(
                binding, msg_str, destination, relay_state=_rstate
            )

            logger.debug("ht_args: %s" % ht_args)
        except Exception as exc:
            logger.exception("%s", exc)
            raise ServiceErrorException(
                "Failed to construct the AuthnRequest: %s" % exc
            )

        # remember the request
        self.cache_outstanding_queries[_sid] = self.return_to
        return self.response(binding, ht_args, query)

    def response(self, binding, http_args, query):
        cookie = self.create_cookie(
            '{"'
            + self.CONST_QUERY
            + '": "'
            + base64.b64encode(query.encode("ascii")).decode("ascii")
            + '" , "'
            + self.CONST_HASIDP
            + '": "True" }',
            self.CONST_SAML_COOKIE,
            self.CONST_SAML_COOKIE,
        )
        if binding == BINDING_HTTP_ARTIFACT:
            resp: Response = SeeOther()
        elif binding == BINDING_HTTP_REDIRECT:
            for param, value in http_args["headers"]:
                if param == "Location":
                    resp = SeeOther(str(value), headers=[cookie])
                    break
            else:
                raise ServiceErrorException("Parameter error")
        else:
            http_args["headers"].append(cookie)
            resp = Response(http_args["data"], headers=http_args["headers"])

        return resp
