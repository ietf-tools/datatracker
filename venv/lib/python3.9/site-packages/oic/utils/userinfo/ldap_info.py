try:
    import ldap
except ImportError:
    raise ImportError("This module can be used only with pyldap installed.")

import logging
from typing import Dict
from typing import List

from ldap import LDAPError
from ldap import LDAPObject

from oic.utils.sanitize import sanitize
from oic.utils.userinfo import UserInfo

__author__ = "rolandh"

logger = logging.getLogger(__name__)

OPENID2LDAP = {
    "sub": "uid",
    "name": "displayName",
    "given_name": "givenname",
    "family_name": "sn",
    "middle_name": "",
    "nickname": "eduPersonNickname",
    "preferred_username": "uid",
    "profile": "labeledURI",
    "picture": "jpegPhoto",
    "website": "labeledURI",
    "email": "mail",
    # "email_verified":
    "gender": "schacGender",
    "birthdate": "schacDateOfBirth",
    # zoneinfo
    "locale": "preferredLanguage",
    "phone_number": "telephoneNumber",
    # phone_number_verified
    "address": "postalAddress",
    "updated_at": "",  # Nothing equivalent
}


class UserInfoLDAP(UserInfo):
    def __init__(  # nosec
        self,
        uri,
        base,
        filter_pattern,
        scope=ldap.SCOPE_SUBTREE,
        tls=False,
        user="",
        passwd="",
        attr=None,
        attrsonly=False,
        attrmap=OPENID2LDAP,
    ):
        super(UserInfoLDAP, self).__init__(None)
        self.ldapuri = uri
        self.base = base
        self.filter_pattern = filter_pattern
        self.scope = scope
        self.tls = tls
        self.attr = attr
        self.attrsonly = attrsonly
        self.ldapuser = user
        self.ldappasswd = passwd
        self.bind()
        self.ld: LDAPObject = None
        self.openid2ldap = attrmap
        self.ldap2openid = dict([(v, k) for k, v in self.openid2ldap.items()])

    def bind(self):
        self.ld = ldap.initialize(self.ldapuri)
        self.ld.protocol_version = ldap.VERSION3
        if self.tls:
            self.ld.start_tls_s()
        self.ld.simple_bind_s(self.ldapuser, self.ldappasswd)

    def __call__(
        self, userid, client_id, user_info_claims=None, first_only=True, **kwargs
    ):
        _filter = self.filter_pattern % userid
        logger.debug("CLAIMS: %s" % sanitize(user_info_claims))
        _attr = self.attr
        if user_info_claims:
            try:
                _claims = user_info_claims["claims"]
            except KeyError:
                pass
            else:
                avaspec: Dict[str, List[str]] = {}
                for key, val in _claims.items():
                    try:
                        attr = self.openid2ldap[key]
                    except KeyError:
                        logger.warn("OIDC attribute '%s' not defined in map" % key)
                    else:
                        try:
                            avaspec[attr].append(val)
                        except KeyError:
                            avaspec[attr] = [val]

                _attr.extend(list(avaspec.keys()))

        arg = [self.base, self.scope, _filter, _attr, self.attrsonly]
        try:
            res = self.ld.search_s(*arg)
        except LDAPError:
            try:
                self.ld.close()
            except LDAPError:
                pass
            self.bind()
            res = self.ld.search_s(*arg)
        if len(res) == 1:
            # should only be one entry and the information per entry is
            # the tuple (dn, ava)
            newres = {}
            for key, val in res[0][1].items():
                if first_only:
                    val = val[0]  # if more than one just return the first
                try:
                    newres[self.ldap2openid[key]] = val
                except KeyError:
                    newres[key] = val
            return newres
        else:
            return {}
