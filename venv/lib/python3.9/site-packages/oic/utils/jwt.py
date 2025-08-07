import json
import uuid

from jwkest import jwe
from jwkest import jws
from jwkest.jwe import JWE
from jwkest.jws import NoSuitableSigningKeys

from oic.oic.message import JasonWebToken
from oic.utils.time_util import utc_time_sans_frac

__author__ = "roland"


class JWT(object):
    def __init__(
        self,
        keyjar,
        iss="",
        lifetime=0,
        sign_alg="RS256",
        msgtype=JasonWebToken,
        encrypt=False,
        enc_enc="A128CBC-HS256",
        enc_alg="RSA1_5",
    ):
        self.iss = iss
        self.lifetime = lifetime
        self.sign_alg = sign_alg
        self.keyjar = keyjar  # my signing key
        self.message_type = msgtype
        self.encrypt = encrypt
        self.enc_alg = enc_alg
        self.enc_enc = enc_enc

    def _encrypt(self, payload, cty="JWT"):
        keys = self.keyjar.get_encrypt_key(owner="")
        kwargs = {"alg": self.enc_alg, "enc": self.enc_enc}

        if cty:
            kwargs["cty"] = cty

        # use the clients public key for encryption
        _jwe = JWE(payload, **kwargs)
        return _jwe.encrypt(keys, context="public")

    def pack_init(self):
        argv = {"iss": self.iss, "iat": utc_time_sans_frac()}
        argv["exp"] = argv["iat"] + self.lifetime
        return argv

    def pack_key(self, owner="", kid=""):
        keys = self.keyjar.get_signing_key(
            jws.alg2keytype(self.sign_alg), owner=owner, kid=kid
        )

        if not keys:
            raise NoSuitableSigningKeys("kid={}".format(kid))

        return keys[0]  # Might be more then one if kid == ''

    def pack(self, kid="", owner="", cls_instance=None, **kwargs):
        _args = self.pack_init()
        if self.sign_alg != "none":
            _key = self.pack_key(owner, kid)
            _args["kid"] = _key.kid
        else:
            _key = None

        try:
            _encrypt = kwargs["encrypt"]
        except KeyError:
            _encrypt = self.encrypt
        else:
            del kwargs["encrypt"]

        _args.update(kwargs)

        if cls_instance:
            cls_instance.update(_args)
            _jwt = cls_instance
        else:
            _jwt = self.message_type(**_args)

        if "jti" in self.message_type.c_param:
            try:
                _jti = kwargs["jti"]
            except KeyError:
                _jti = uuid.uuid4().hex

            _jwt["jti"] = _jti

        _jws = _jwt.to_jwt([_key], self.sign_alg)
        if _encrypt:
            return self._encrypt(_jws)
        else:
            return _jws

    def _verify(self, rj, token):
        _msg = json.loads(rj.jwt.part[1].decode("utf8"))
        if _msg["iss"] == self.iss:
            owner = ""
        else:
            owner = _msg["iss"]

        keys = self.keyjar.get_verify_key(
            jws.alg2keytype(rj.jwt.headers["alg"]), owner=owner
        )
        return rj.verify_compact(token, keys)

    def _decrypt(self, rj, token):
        keys = self.keyjar.get_verify_key(owner="")
        msg = rj.decrypt(token, keys)
        _rj = jws.factory(msg)
        if not _rj:
            raise KeyError()
        else:
            return self._verify(_rj, msg)

    def unpack(self, token):
        if not token:
            raise KeyError

        _rj = jws.factory(token)
        if _rj:
            info = self._verify(_rj, token)
        else:
            _rj = jwe.factory(token)
            if not _rj:
                raise KeyError()
            info = self._decrypt(_rj, token)

        if self.message_type:
            return self.message_type(**info)
        else:
            return info
