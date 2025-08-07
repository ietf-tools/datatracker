import base64
import json
import time
from typing import Dict
from urllib.parse import parse_qs
from urllib.parse import parse_qsl

from jwkest import jws
from jwkest.jwk import keyrep
from jwkest.jws import JWS

from oic.extension.signed_http_req import SignedHttpRequest
from oic.extension.signed_http_req import ValidationError
from oic.oauth2 import error_response
from oic.oic.message import AccessTokenRequest
from oic.oic.message import AccessTokenResponse
from oic.oic.provider import Provider
from oic.utils.http_util import Response
from oic.utils.http_util import get_post

__author__ = "regu0004"


class NonPoPTokenError(Exception):
    pass


class PoPProvider(Provider):
    def __init__(self, *args, **kwargs):
        super(PoPProvider, self).__init__(*args, **kwargs)

        # mapping from signed pop token to access token in db
        self.access_tokens: Dict[JWS, str] = {}

    def token_endpoint(self, dtype="urlencoded", **kwargs):
        atr = AccessTokenRequest().deserialize(kwargs["request"], dtype)
        resp = super(PoPProvider, self).token_endpoint(**kwargs)

        if "token_type" not in atr or atr["token_type"] != "pop":
            return resp

        client_public_key = base64.urlsafe_b64decode(atr["key"].encode("utf-8")).decode(
            "utf-8"
        )
        pop_key = json.loads(client_public_key)
        atr = AccessTokenResponse().deserialize(resp.message, method="json")
        data = self.sdb.read(atr["access_token"])

        jwt = {
            "iss": self.baseurl,
            "aud": self.baseurl,
            "exp": data["token_expires_at"],
            "nbf": int(time.time()),
            "cnf": {"jwk": pop_key},
        }
        _jws = JWS(jwt, alg="RS256").sign_compact(self.keyjar.get_signing_key(owner=""))
        self.access_tokens[_jws] = data["access_token"]

        atr["access_token"] = _jws
        atr["token_type"] = "pop"  # nosec
        return Response(atr.to_json(), content="application/json")

    def userinfo_endpoint(self, request, **kwargs):
        access_token = self._parse_access_token(request)
        shr = SignedHttpRequest(self._get_client_public_key(access_token))
        http_signature = self._parse_signature(request)
        try:
            shr.verify(
                http_signature,
                method=request["method"],
                host=request["host"],
                path=request["path"],
                query_params=request["query"],
                headers=request["headers"],
                body=request["body"],
                strict_query_param_verification=True,
                strict_headers_verification=False,
            )
        except ValidationError:
            return error_response(
                "access_denied", descr="Could not verify proof of " "possession"
            )

        return self._do_user_info(self.access_tokens[access_token], **kwargs)

    def _get_client_public_key(self, access_token):
        _jws = jws.factory(access_token)
        if _jws:
            data = _jws.verify_compact(
                access_token, self.keyjar.get_verify_key(owner="")
            )
            try:
                return keyrep(data["cnf"]["jwk"])
            except KeyError:
                raise NonPoPTokenError(
                    "Could not extract public key as JWK from access token"
                )

        raise NonPoPTokenError("Unsigned access token, maybe not PoP?")

    def parse_request(self, environ):
        def rebuild_header_name(environ_key):
            """Construct the HTTP header name from a WSGI environ variable."""
            header_name = environ_key[5:]  # strip 'HTTP_'
            name_parts = header_name.split("_")
            header_name = "-".join(part.capitalize() for part in name_parts)
            return header_name

        request = {}
        request["host"] = environ.get("HTTP_HOST", None)
        request["path"] = environ.get("PATH_INFO", None)
        request["query"] = dict(parse_qsl(environ.get("QUERY_STRING", None)))
        request["method"] = environ.get("REQUEST_METHOD", None)

        request["headers"] = {}
        for key in environ:
            if key.startswith("HTTP_"):
                header_name = rebuild_header_name(key)
                request["headers"][header_name] = environ[key]

        if "CONTENT_TYPE" in environ:
            request["headers"]["Content-Type"] = environ["CONTENT_TYPE"]
        if "CONTENT_LENGTH" in environ:
            request["headers"]["Content-Length"] = environ["CONTENT_LENGTH"]

        if environ["CONTENT_LENGTH"]:
            request["body"] = get_post(environ)

        return request

    def _parse_access_token(self, request, **kwargs):
        if "access_token" in request["query"]:
            return request["query"]["access_token"]
        elif "access_token" in request["body"]:
            return parse_qs(request["body"])["access_token"][0]
        elif (
            "Authorization" in request["headers"]
            and request["headers"]["Authorization"]
        ):
            auth_header = request["headers"]["Authorization"]
            if auth_header.startswith("pop "):
                return auth_header[len("pop ") :]

        return None

    def _parse_signature(self, request):
        if "Http-Signature" in request["headers"]:
            return request["headers"]["Http-Signature"]
        elif "body" in request:
            return parse_qs(request["body"])["http_signature"][0]

        return None
