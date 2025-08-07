import copy
import logging
from typing import Any
from typing import Dict
from typing import List

from oic.exception import MissingAttribute
from oic.oic import OpenIDSchema
from oic.oic.claims_provider import ClaimsClient
from oic.utils.sanitize import sanitize
from oic.utils.userinfo import UserInfo

__author__ = "rolandh"

logger = logging.getLogger(__name__)


class DistributedAggregatedUserInfo(UserInfo):
    def __init__(self, db, oidcsrv, client_info=None):
        UserInfo.__init__(self, db)
        self.oidcsrv = oidcsrv
        self.claims_clients = self.init_claims_clients(client_info)

        for _, cc in self.claims_clients.items():
            oidcsrv.keyjar.update(cc.keyjar)

    def dynamic_init_claims_client(self, issuer, req_args):
        cc = ClaimsClient()
        # dynamic provider info discovery
        cc.provider_config(issuer)
        resp = cc.do_registration_request(request_args=req_args)
        cc.client_id = resp.client_id
        cc.client_secret = resp.client_secret
        return cc

    def init_claims_clients(self, client_info):
        res: Dict[str, ClaimsClient] = {}
        if client_info is None:
            return res

        for cid, specs in client_info.items():
            if "dynamic" in specs:
                cc = self.dynamic_init_claims_client(cid, specs["client"])
            else:
                cc = ClaimsClient(client_id=specs["client_id"])
                cc.client_secret = specs["client_secret"]
                try:
                    cc.keyjar.add(specs["client_id"], specs["jwks_uri"])
                except KeyError:
                    pass
                cc.userclaims_endpoint = specs["userclaims_endpoint"]
            res[cid] = cc
        return res

    def _collect_distributed(self, srv, cc, sub, what, alias=""):
        try:
            resp = cc.do_claims_request(request_args={"sub": sub, "claims_names": what})
        except Exception:
            raise

        result: Dict[str, Any] = {"_claims_names": {}, "_claims_sources": {}}

        if not alias:
            alias = srv

        for key in resp["claims_names"]:
            result["_claims_names"][key] = alias

        if "jwt" in resp:
            result["_claims_sources"][alias] = {"JWT": resp["jwt"]}
        else:
            result["_claims_sources"][alias] = {"endpoint": resp["endpoint"]}
            if "access_token" in resp:
                result["_claims_sources"][alias]["access_token"] = resp["access_token"]

        return result

    def __call__(self, userid, client_id, user_info_claims=None, **kwargs):
        """
        Collect the claims.

        :param userid: The local user id
        :param user_info_claims: Possible userinfo claims (a dictionary)
        :return: A schema dependent userinfo instance
        """
        logger.info("User_info about '%s'" % userid)
        identity = copy.copy(self.db[userid])

        if user_info_claims:
            result = {}
            missing = []
            optional = []
            if "claims" in user_info_claims:
                for key, restr in user_info_claims["claims"].items():
                    try:
                        result[key] = identity[key]
                    except KeyError:
                        if restr == {"essential": True}:
                            missing.append(key)
                        else:
                            optional.append(key)

            # Check if anything asked for is somewhere else
            if (missing or optional) and "_external_" in identity:
                cpoints: Dict[str, List[str]] = {}
                remaining = missing[:]
                missing.extend(optional)
                for key in missing:
                    for _srv, what in identity["_external_"].items():
                        if key in what:
                            try:
                                cpoints[_srv].append(key)
                            except KeyError:
                                cpoints[_srv] = [key]
                            try:
                                remaining.remove(key)
                            except ValueError:
                                pass

                if remaining:
                    raise MissingAttribute("Missing properties '%s'" % remaining)

                for srv, what in cpoints.items():
                    cc = self.oidcsrv.claims_clients[srv]
                    logger.debug("srv: %s, what: %s" % (sanitize(srv), sanitize(what)))
                    _res = self._collect_distributed(srv, cc, userid, what)
                    logger.debug("Got: %s" % sanitize(_res))
                    for key, val in _res.items():
                        if key in result:
                            result[key].update(val)
                        else:
                            result[key] = val

        else:
            # default is what "openid" demands which is sub
            result = {"sub": userid}

        return OpenIDSchema(**result)
