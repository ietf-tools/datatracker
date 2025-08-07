import time
from typing import List

from oic.oauth2.grant import Grant
from oic.oauth2.grant import Token
from oic.oauth2.message import SINGLE_OPTIONAL_STRING
from oic.oauth2.message import SINGLE_REQUIRED_STRING
from oic.oauth2.message import Message
from oic.oic.message import SINGLE_REQUIRED_INT
from oic.utils.time_util import epoch_in_a_while

__author__ = "roland"


class Content(Message):
    c_param = {
        "typ": SINGLE_REQUIRED_STRING,  # type of token
        "sub": SINGLE_REQUIRED_STRING,  # Which subject that authenticated
        "auz": SINGLE_OPTIONAL_STRING,  # Authorization information
        "aud": SINGLE_OPTIONAL_STRING,  # The intended receiver
        "val": SINGLE_REQUIRED_INT,  # Valid until
        "ref": SINGLE_OPTIONAL_STRING,  # Refresh token
    }
    c_allowed_values = {"type": ["code", "access", "refresh"]}


class StateLess(object):
    def __init__(
        self,
        keys,
        enc_alg,
        enc_method,
        grant_validity=300,
        access_validity=600,
        refresh_validity=0,
    ):
        self.keys = keys
        self.alg = enc_alg
        self.enc = enc_method
        self.validity = {
            "grant": grant_validity,
            "access": access_validity,
            "refresh": refresh_validity,
        }
        self.used_grants: List[Grant] = []
        self.revoked: List[Token] = []

    def __getitem__(self, token):
        """
        Get token.

        :param token: authz grant code or refresh token
        :return: information about the session
        """
        return Content().from_jwe(token, self.keys)

    def get_token(self, cont):
        return cont.to_jwe(self.keys, self.enc, self.alg)

    def create_authz_session(self, sub, areq, **kwargs):
        """
        Create session for keeping the Authorization.

        :param sub: Identifier for the user, this is the real identifier
        :param areq: The AuthorizationRequest instance
        :return: The session identifier, which is the database key
        """
        _cont = Content(
            typ="code",
            sub=sub,
            aud=areq["redirect_uri"],
            val=epoch_in_a_while(self.validity["grant"]),
        )

        return _cont

    def upgrade_to_token(self, cont, issue_refresh=False):
        cont["typ"] = "access"
        cont["val"] = epoch_in_a_while(self.validity["access"])
        if issue_refresh:
            _c = Content(
                sub=cont["sub"],
                aud=cont["aud"],
                typ="refresh",
                val=epoch_in_a_while(self.validity["refresh"]),
            )
            cont["ref"] = _c.to_jwe(self.keys, self.enc, self.alg)

        return cont

    def refresh_token(self, rtoken):
        # assert that it is a refresh token
        _cont = Content().from_jwe(rtoken, self.keys)
        if _cont["typ"] != "refresh":
            raise Exception("Not a refresh token")

    def is_expired(self, token):
        _cont = Content().from_jwe(token, self.keys)
        if _cont["val"] < time.time():
            return True

    def is_valid(self, token):
        _cont = Content().from_jwe(token, self.keys)

        if _cont["val"] >= time.time():
            return False
        if token in self.revoked:
            return False
        else:
            return True

    def is_revoked(self, token):
        if token in self.revoked:
            return True
        else:
            return False

    def revoke_token(self, token):
        # revokes either the refresh token or the access token
        self.revoked.append(token)

    def store_session(self, cont):
        pass
