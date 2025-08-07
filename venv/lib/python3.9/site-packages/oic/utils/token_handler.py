from oic import rndstr
from oic.extension.token import JWTToken

__author__ = "roland"


class NotAllowed(Exception):
    pass


class TokenHandler(object):
    """
    Class for handling tokens.

    Note! the token and refresh token factories both keep their own token databases.
    """

    def __init__(
        self,
        issuer,
        token_policy,
        token_factory=None,
        refresh_token_factory=None,
        keyjar=None,
        sign_alg="RS256",
    ):
        """
        Initialize the class.

        :param token_factory: A callable function that returns a token
        :param refresh_token_factory: A callable function that returns a
            refresh token
        :param token_policy: A dictionary of the form
            {'access_token': {<target_id>: {<grant_type>: <lifetime>}},
             'refresh_token': {<target_id>: {<grant_type>: <lifetime>}}}
        :param keyjar: A oic.utils.keyio.KeyJar instance
        :param sign_alg: Which signature algorithm to use.
        :return: a TokenHandler instance
        """
        self.token_policy = token_policy
        if token_factory is None:
            self.token_factory = JWTToken(
                "T", keyjar=keyjar, iss=issuer, sign_alg=sign_alg
            )
        else:
            self.token_factory = token_factory

        if refresh_token_factory is None:
            self.refresh_token_factory = JWTToken(
                "R",
                keyjar=keyjar,
                iss="https://example.com/as",
                sign_alg=sign_alg,
                token_storage={},
            )
        else:
            self.refresh_token_factory = refresh_token_factory

    def get_access_token(self, target_id, scope, grant_type):
        """
        Return access token for given inputs.

        :param target_id:
        :param scope:
        :param grant_type:
        :return:
        """
        # No default, either there is an explicit policy or there is not
        try:
            lifetime = self.token_policy["access_token"][target_id][grant_type]
        except KeyError:
            raise NotAllowed(
                "Access token for grant_type {} for target_id {} not allowed"
            )

        sid = rndstr(32)
        return self.token_factory(
            sid,
            target_id=target_id,
            scope=scope,
            grant_type=grant_type,
            lifetime=lifetime,
        )

    def refresh_access_token(self, target_id, token, grant_type, **kwargs):
        """
        Return refresh_access_token for given input.

        :param target_id: Who gave me this token
        :param token: The refresh_token
        :param grant_type: Which grant type the token is connected to
        :param kwargs: Extra key word arguments
        :return: New access_token
        """
        # Check that the token is an refresh token
        info = self.refresh_token_factory.get_info(token)

        # Make sure the token should is usable by the client to get a
        # refresh token
        try:
            if target_id != info["azr"]:
                raise NotAllowed("{} can't use this token".format(target_id))
        except KeyError:
            if target_id not in info["aud"]:
                raise NotAllowed("{} can't use this token".format(target_id))

        if self.token_factory.is_valid(info):
            try:
                lifetime = self.token_policy["access_token"][target_id][grant_type]
            except KeyError:
                raise NotAllowed(
                    "Issue access token for grant_type {} for target_id {} not allowed"
                )
            else:
                sid = self.token_factory.db[info["jti"]]
                try:
                    _aud = kwargs["aud"]
                except KeyError:
                    _aud = info["aud"]

                return self.token_factory(
                    sid, target_id=target_id, lifetime=lifetime, aud=_aud
                )

    def get_refresh_token(self, target_id, grant_type, sid):
        try:
            lifetime = self.token_policy["refresh_token"][target_id][grant_type]
        except KeyError:
            raise NotAllowed(
                "Issue access token for grant_type {} for target_id {} not allowed"
            )
        else:
            return self.refresh_token_factory(
                sid, target_id=target_id, lifetime=lifetime
            )

    def invalidate(self, token):
        if self.token_factory.valid(token):
            self.token_factory.invalidate(token)
