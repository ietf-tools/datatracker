import time
from typing import List
from typing import Optional

from oic.oauth2.message import AccessTokenResponse
from oic.oauth2.message import AuthorizationResponse
from oic.utils.time_util import utc_time_sans_frac

__author__ = "roland"


class Token(object):
    def __init__(self, resp=None):
        self.scope: List[str] = []
        self.token_expiration_time = 0
        self.access_token = None
        self.refresh_token = None
        self.token_type: Optional[str] = None
        self.replaced = False
        self.id_token = None

        if resp:
            for prop, val in resp.items():
                setattr(self, prop, val)

            try:
                _expires_in = resp["expires_in"]
            except KeyError:
                return

            if _expires_in:
                _tet = utc_time_sans_frac() + int(_expires_in)
            else:
                _tet = 0
            self.token_expiration_time = int(_tet)

    def is_valid(self):
        if self.token_expiration_time:
            if utc_time_sans_frac() > self.token_expiration_time:
                return False

        return True

    def __str__(self):
        return "%s" % self.__dict__

    def keys(self):
        return self.__dict__.keys()

    def __eq__(self, other):
        skeys = self.keys()
        okeys = other.keys()
        if set(skeys) != set(okeys):
            return False

        for key in skeys:
            if getattr(self, key) != getattr(other, key):
                return False

        return True


class Grant(object):
    _authz_resp = AuthorizationResponse
    _acc_resp = AccessTokenResponse
    _token_class = Token

    def __init__(self, exp_in=600, resp=None, seed=""):
        self.grant_expiration_time = 0
        self.exp_in = exp_in
        self.seed = seed
        self.tokens: List[Token] = []
        self.id_token = None
        self.code: Optional[str] = None
        if resp:
            self.add_code(resp)
            self.add_token(resp)

    @classmethod
    def from_code(cls, resp):
        instance = cls()
        instance.add_code(resp)
        return instance

    def add_code(self, resp):
        try:
            self.code = resp["code"]
            self.grant_expiration_time = utc_time_sans_frac() + self.exp_in
        except KeyError:
            pass

    def add_token(self, resp):
        """
        Add token to store.

        :param resp: An Authorization Response instance
        """
        if "access_token" in resp:
            tok = self._token_class(resp)
            self.tokens.append(tok)

    def is_valid(self):
        if utc_time_sans_frac() > self.grant_expiration_time:
            return False
        else:
            return True

    def __str__(self):
        return "%s" % self.__dict__

    def keys(self):
        return self.__dict__.keys()

    def update(self, resp):
        if "access_token" in resp or "id_token" in resp:
            tok = self._token_class(resp)
            if tok not in self.tokens:
                for otok in self.tokens:
                    otok.replaced = True
                self.tokens.append(tok)

        if "code" in resp:
            self.add_code(resp)

    def get_token(self, scope=""):
        token = None
        if scope:
            for token in self.tokens:
                if scope in token.scope and not token.replaced:
                    return token
        else:
            for token in self.tokens:
                if token.is_valid() and not token.replaced:
                    return token

        return token

    def delete_token(self, token):
        """Remove the specified token if it exists."""
        try:
            self.tokens.remove(token)
        except ValueError:
            pass

    def get_id_token(self):
        if self.id_token:
            if self.id_token["exp"] >= time.time():
                return self.id_token
        else:
            for tok in self.tokens:
                try:
                    _idt = tok.id_token
                except AttributeError:
                    pass
                else:
                    if _idt:
                        if _idt["exp"] >= time.time():
                            return _idt
        return None

    def join(self, grant):
        if not self.exp_in:
            self.exp_in = grant.exp_in
        if not self.grant_expiration_time:
            self.grant_expiration_time = grant.grant_expiration_time
        if not self.seed:
            self.seed = grant.seed
        for token in grant.tokens:
            if token not in self.tokens:
                for otok in self.tokens:
                    if token.scope == otok.scope:
                        otok.replaced = True
                self.tokens.append(token)
