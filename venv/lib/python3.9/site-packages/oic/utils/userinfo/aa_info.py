import importlib
from tempfile import NamedTemporaryFile

from oic.utils.userinfo import UserInfo

__author__ = "danielevertsson"

try:
    from saml2.client import Saml2Client
except ImportError:

    class AaUserInfo(UserInfo):
        pass

else:

    class AaUserInfo(UserInfo):  # type: ignore
        def __init__(self, spconf, url, db=None):
            UserInfo.__init__(self, db)

            # Configurations for the SP handler. (pyOpSamlProxy.client.sp.conf)
            self.sp_conf = importlib.import_module(spconf)
            ntf = NamedTemporaryFile(suffix="pyoidc.py", delete=True)
            ntf.write(
                b"CONFIG = "
                + str(self.sp_conf.CONFIG).replace("%s", url)  # type: ignore
            )
            ntf.seek(0)
            self.sp = Saml2Client(config_file="%s" % ntf.name)
            self.samlcache = self.sp_conf.SAML_CACHE  # type: ignore

        def __call__(self, userid, client_id, user_info_claims=None, **kwargs):
            try:
                ava = self.db[userid]
                entity_id = self.sp_conf.AA_ENTITY_ID  # type: ignore
                if entity_id is None:
                    entity_id = self.samlcache["AA_ENTITYID"]
                response = self.sp.do_attribute_query(
                    entity_id,
                    ava[self.sp_conf.AA_NAMEID_ATTRIBUTE][0],  # type: ignore
                    nameid_format=self.sp_conf.AA_NAMEID_FORMAT,  # type: ignore
                    attribute=self.sp_conf.AA_REQUEST_ATTRIBUTES,  # type: ignore
                )

                response_dict = response.ava.copy()
                if self.sp_conf.AA_ATTRIBUTE_SAML_IDP is True:  # type: ignore
                    for key, value in ava.items():
                        if (
                            self.sp_conf.AA_ATTRIBUTE_SAML_IDP_WHITELIST  # type: ignore
                            is None
                            or key
                            in self.sp_conf.AA_ATTRIBUTE_SAML_IDP_WHITELIST  # type: ignore
                        ) and key not in response_dict:
                            response_dict[key] = value

                return response_dict
            except Exception:
                return {}

        def filter(self, userinfo, user_info_claims=None):
            return userinfo
