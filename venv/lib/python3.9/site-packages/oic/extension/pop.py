import json
from typing import Dict
from urllib.parse import parse_qs
from urllib.parse import urlparse

from Cryptodome.PublicKey import RSA
from jwkest import b64e
from jwkest.jwk import RSAKey
from jwkest.jwk import load_jwks

from oic.extension.message import TokenIntrospectionResponse
from oic.extension.signed_http_req import SignedHttpRequest
from oic.oauth2 import compact
from oic.utils.jwt import JWT
from oic.utils.keyio import KeyBundle

__author__ = "roland"


def sign_http_args(method, url, headers, body=""):
    p = urlparse(url)

    kwargs = {"path": p.path, "host": p.netloc, "headers": headers, "method": method}

    if body:
        kwargs["body"] = body

    query_params = compact(parse_qs(p.query))
    kwargs["query_params"] = query_params
    return kwargs


class PoPCallBack(object):
    def __init__(self, key, alg):
        self.key = key
        self.alg = alg

    def __call__(self, method, url, **kwargs):
        try:
            body = kwargs["body"]
        except KeyError:
            body = None
        try:
            headers = kwargs["headers"]
        except KeyError:
            headers = {}

        _kwargs = sign_http_args(method, url, headers, body)
        shr = SignedHttpRequest(self.key)
        kwargs["Authorization"] = "pop {}".format(shr.sign(alg=self.alg, **_kwargs))
        return kwargs


class PoPClient(object):
    def __init__(self, key_size=2048, sign_alg="RS256"):
        self.key_size = key_size
        self.state2key: Dict[str, RSAKey] = {}
        self.token2key: Dict[str, RSAKey] = {}
        self.alg = sign_alg

    def update(self, msg, state, key_size=0):
        """
        Use to 'update' the AccessToken Request.

        :param msg:
        :param state: Used to map access token response to this request
        :param key_size:
        :return:
        """
        if not key_size:
            key_size = self.key_size

        key = RSAKey(key=RSA.generate(key_size))
        self.state2key[state] = key
        msg["key"] = json.dumps(key.serialize())
        return msg

    def handle_access_token_response(self, resp):
        """
        Map access token to a keypair.

        :param resp: AccessTokenResponse instance
        """
        self.token2key[resp["access_token"]] = self.state2key[resp["state"]]


class PoPAS(object):
    def __init__(self, me):
        self.thumbprint2key: Dict[str, RSAKey] = {}
        self.keyjar = None
        self.me = me

    def store_key(self, key):
        kb = KeyBundle()
        kb.do_keys([key])

        # Store key with thumbprint as key
        key_thumbprint = b64e(kb.keys()[0].thumbprint("SHA-256")).decode("utf8")
        self.thumbprint2key[key_thumbprint] = key
        return key_thumbprint

    def create_access_token(self, key_thumbprint):
        # creating the access_token
        jwt_constructor = JWT(self.keyjar, iss=self.me)
        # Audience is myself
        return jwt_constructor.pack(kid="abc", cnf={"kid": key_thumbprint}, aud=self.me)

    def token_introspection(self, token):
        jwt_constructor = JWT(self.keyjar, iss=self.me)
        res = jwt_constructor.unpack(token)

        tir = TokenIntrospectionResponse(active=True)
        tir["key"] = json.dumps(self.thumbprint2key[res["cnf"]["kid"]])

        return tir


class PoPRS(object):
    def __init__(self):
        self.token2key: Dict[str, RSAKey] = {}

    def store_key(self, access_token, tir):
        """
        Store key that was returned in response from token introspection.

        :param access_token: The token that was introspected
        :param tir: TokenIntrospectionResponse instance
        """
        key = load_jwks(json.dumps({"keys": [json.loads(tir["key"])]}))
        self.token2key[access_token] = key

    def eval_signed_http_request(
        self, pop_token, access_token, method, url, headers, body=""
    ):
        kwargs = sign_http_args(method, url, headers, body)

        shr = SignedHttpRequest(self.token2key[access_token][0])
        return shr.verify(
            signature=pop_token,
            strict_query_params_verification=True,
            strict_headers_verification=True,
            **kwargs,
        )
