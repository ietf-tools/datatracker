import json
import uuid
from typing import Dict

from oic.oauth2.message import OPTIONAL_LIST_OF_STRINGS
from oic.oauth2.message import SINGLE_REQUIRED_STRING
from oic.oauth2.message import Message
from oic.oic.message import SINGLE_REQUIRED_INT
from oic.utils.jwt import JWT
from oic.utils.sdb import Token
from oic.utils.time_util import utc_time_sans_frac

__author__ = "roland"


class TokenAssertion(Message):
    c_param = {
        "iss": SINGLE_REQUIRED_STRING,
        "azp": SINGLE_REQUIRED_STRING,
        "sub": SINGLE_REQUIRED_STRING,
        "kid": SINGLE_REQUIRED_STRING,
        "exp": SINGLE_REQUIRED_INT,
        "jti": SINGLE_REQUIRED_STRING,
        "aud": OPTIONAL_LIST_OF_STRINGS,  # Array of strings or string
    }


class JWTToken(Token, JWT):
    usage = "authorization_grant"

    def __init__(self, typ, keyjar, lt_pattern=None, extra_claims=None, **kwargs):
        self.type = typ
        Token.__init__(self, typ, **kwargs)
        kwargs.pop("token_storage", None)
        JWT.__init__(self, keyjar, msgtype=TokenAssertion, **kwargs)
        self.lt_pattern = lt_pattern or {}
        self.db: Dict[str, str] = {}
        self.session_info = {"": 600}
        self.exp_args = ["sinfo"]
        self.extra_claims = extra_claims or {}

    def __call__(self, sid, *args, **kwargs):
        """
        Return a token.

        :return:
        """
        try:
            _sinfo = kwargs["sinfo"]
        except KeyError:
            exp = self.do_exp(**kwargs)
            _tid = kwargs["target_id"]
        else:
            if "lifetime" in kwargs:
                _sinfo["lifetime"] = kwargs["lifetime"]
            exp = self.do_exp(**_sinfo)
            _tid = _sinfo["client_id"]
            if "scope" not in kwargs:
                _scope = None
                try:
                    _scope = _sinfo["scope"]
                except KeyError:
                    ar = json.loads(_sinfo["authzreq"])
                    try:
                        _scope = ar["scope"]
                    except KeyError:
                        pass
                if _scope:
                    kwargs["scope"] = " ".join(_scope)

            if self.usage == "authorization_grant":
                try:
                    kwargs["sub"] = _sinfo["sub"]
                except KeyError:
                    pass

            del kwargs["sinfo"]

        if "aud" in kwargs:
            if _tid not in kwargs["aud"]:
                kwargs["aud"].append(_tid)
        else:
            kwargs["aud"] = [_tid]

        if self.usage == "client_authentication":
            try:
                kwargs["sub"] = _tid
            except KeyError:
                pass
        else:
            if "azp" not in kwargs:
                kwargs["azp"] = _tid

        for param in ["lifetime", "grant_type", "response_type", "target_id"]:
            try:
                del kwargs[param]
            except KeyError:
                pass

        try:
            kwargs["kid"] = self.extra_claims["kid"]
        except KeyError:
            pass

        _jti = "{}-{}".format(self.type, uuid.uuid4().hex)
        _jwt = self.pack(jti=_jti, exp=exp, **kwargs)
        self.db[_jti] = sid
        return _jwt

    def do_exp(self, **kwargs):
        try:
            lifetime = kwargs["lifetime"]
        except KeyError:
            try:
                rt = " ".join(kwargs["response_type"])
            except KeyError:
                rt = " ".join(kwargs["grant_type"])

            try:
                lifetime = self.lt_pattern[rt]
            except KeyError:
                lifetime = self.lt_pattern[""]

        return utc_time_sans_frac() + lifetime

    def type_and_key(self, token):
        """
        Return type of Token (A=Access code, T=Token, R=Refresh token) and the session id.

        :param token: A token
        :return: tuple of token type and session id
        """
        msg = self.unpack(token)
        return self.type, self.db[msg["jti"]]

    def get_key(self, token):
        """
        Return session id.

        :param token: A token
        :return: The session id
        """
        msg = self.unpack(token)
        return self.db[msg["jti"]]

    def get_type(self, token):
        """
        Return token type.

        :param token: A token
        :return: Type of Token (A=Access code, T=Token, R=Refresh token)
        """
        self.unpack(token)
        return self.type

    def invalidate(self, token):
        info = self.unpack(token)
        try:
            del self.db[info["jti"]]
        except KeyError:
            return False

        return True

    def is_valid(self, info):
        if info["jti"] in self.db:
            if info["exp"] >= utc_time_sans_frac():
                return True

        return False

    def expires_at(self, token):
        info = self.unpack(token)
        return info["exp"]

    def valid(self, token):
        info = self.unpack(token)
        return self.is_valid(info)

    def get_info(self, token):
        return self.unpack(token)


class Authorization_Grant(JWTToken):
    usage = "authorization_grant"


class Client_Authentication(JWTToken):
    usage = "client_authentication"
