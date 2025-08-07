import json

from oic.oic.message import REQUIRED_MESSAGE
from oic.oic.message import JasonWebToken
from oic.utils.time_util import utc_time_sans_frac

__author__ = "roland"


class PJWT(JasonWebToken):
    c_param = JasonWebToken.c_param.copy()
    c_param.update({"cnf": REQUIRED_MESSAGE})


class PopJWT(object):
    def __init__(
        self, iss="", aud="", lifetime=3600, in_a_while=0, sub="", jwe=None, keys=None
    ):
        """
        Initialize the class.

        :param iss: issuer
        :param aud: audience
        :param lifetime: the JWT expires at now + lifetime
        :param in_a_while: this JWT should not be used before now + in_a_while
        :param sub: Subject identifier
        :param jwe: A jwkest.jwe.JWE instance
        :param keys: A jwkest.jwk.KEYS instance
        """
        self.iss = iss
        self.aud = aud
        self.lifetime = lifetime
        self.in_a_while = in_a_while
        self.sub = sub
        self.jwe = jwe
        self.keys = keys

    def _init_jwt(self):
        kwargs = {}
        for para in ["iss", "aud", "sub"]:
            _val = getattr(self, para)
            if _val:
                kwargs[para] = _val

        _iat = utc_time_sans_frac()
        kwargs["iat"] = _iat
        if self.lifetime:
            kwargs["exp"] = _iat + self.lifetime
        if self.in_a_while:
            kwargs["nbf"] = _iat + self.in_a_while

        return PJWT(**kwargs)

    def pack_jwk(self, jwk):
        """
        Pack JWK.

        :param jwk:
        :return:
        """
        pjwt = self._init_jwt()
        pjwt["cnf"] = {"jwk": jwk}
        return pjwt

    def pack_jwe(self, jwe=None, jwk=None, kid=""):
        """
        Pack JWE.

        :param jwe: An encrypted JWT
        :param jwk: A dictionary representing a JWK
        :param kid: key ID of key to use for encrypting
        :return:
        """
        pjwt = self._init_jwt()

        if jwe:
            pjwt["cnf"] = {"jwe": jwe}
        elif jwk:
            self.jwe.msg = json.dumps(jwk)
            pjwt["cnf"] = {"jwe": self.jwe.encrypt(keys=self.keys.keys(), kid=kid)}
        return pjwt

    def pack_kid(self, kid):
        pjwt = self._init_jwt()
        pjwt["cnf"] = {"kid": kid}
        return pjwt

    def unpack(self, jwt, jwe=None):
        """
        Unpack object.

        :param jwt: A json encoded POP JWT
        :param jwe: A jwkest.jwe.JWE instance to use when decrypting
        :return:
        """
        _pjwt = PJWT().from_json(jwt)

        try:
            _jwe = _pjwt["cnf"]["jwe"]
        except KeyError:
            pass
        else:
            if not jwe:
                jwe = self.jwe

            msg = jwe.decrypt(_jwe, self.keys.keys())
            _pjwt["cnf"]["jwk"] = json.loads(msg.decode("utf8"))

        return _pjwt
