try:
    import ldap
except ImportError:
    raise ImportError("This module can be used only with pyldap installed.")

from oic.exception import PyoidcError
from oic.utils.authn.user import UsernamePasswordMako

SCOPE_MAP = {
    "base": ldap.SCOPE_BASE,
    "onelevel": ldap.SCOPE_ONELEVEL,
    "subtree": ldap.SCOPE_SUBTREE,
}


class LDAPCError(PyoidcError):
    pass


class LDAPAuthn(UsernamePasswordMako):
    def __init__(  # nosec
        self,
        srv,
        ldapsrv,
        return_to,
        pattern,
        mako_template,
        template_lookup,
        ldap_user="",
        ldap_pwd="",
        verification_endpoints=["verify"],
    ):
        """
        Authenticate user against LDAP.

        :param srv: The server instance
        :param ldapsrv: Which LDAP server to us
        :param return_to: Where to send the user after authentication
        :param pattern: How to find the entry to log in to.
            Expected to be a dictionary where key is one of "dn" or "search".
            And the value a dictionary with values depends on the key:
            If "dn" only "pattern".
            If "search": "base", "filterstr", "scope"
                "base" and "filterstr" MUST be present
        :param ldap_user: If a search has to be done first which user to do
            that as. "" is a anonymous user
        :param ldap_pwd: The password for the ldap_user
        """
        UsernamePasswordMako.__init__(
            self,
            srv,
            mako_template,
            template_lookup,
            None,
            return_to,
            verification_endpoints=verification_endpoints,
        )

        self.ldap = ldap.initialize(ldapsrv)
        self.ldap.protocol_version = 3
        self.ldap.set_option(ldap.OPT_REFERRALS, 0)
        self.pattern = pattern
        self.ldap_user = ldap_user
        self.ldap_pwd = ldap_pwd

    def _verify(self, pwd, user):
        """
        Verify the username and password against a LDAP server.

        :param pwd: The password
        :param user: The username
        :return: AssertionError if the LDAP verification failed.
        """
        try:
            _dn = self.pattern["dn"]["pattern"] % user
        except KeyError:
            if "search" not in self.pattern:
                raise LDAPCError("unknown search pattern")
            else:
                args = {
                    "filterstr": self.pattern["filterstr"] % user,
                    "base": self.pattern["base"],
                }
                if "scope" not in args:
                    args["scope"] = ldap.SCOPE_SUBTREE
                else:
                    args["scope"] = SCOPE_MAP[args["scope"]]

                self.ldap.simple_bind_s(self.ldap_user, self.ldap_pwd)

                result = self.ldap.search_s(**args)
                # result is a list of tuples (dn, entry)
                if not result:
                    raise AssertionError()
                elif len(result) > 1:
                    raise AssertionError()
                else:
                    _dn = result[0][0]

        try:
            self.ldap.simple_bind_s(_dn, pwd)
        except Exception:
            raise AssertionError()
