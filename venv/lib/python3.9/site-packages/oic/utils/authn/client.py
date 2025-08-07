import base64
import logging
from urllib.parse import quote_plus

from jwkest import Invalid
from jwkest import MissingKey
from jwkest import as_bytes
from jwkest.jws import alg2keytype

from oic import rndstr
from oic.exception import FailedAuthentication
from oic.exception import NotForMe
from oic.exception import UnknownAssertionType
from oic.oauth2 import AccessTokenRequest
from oic.oauth2.message import SINGLE_OPTIONAL_STRING
from oic.oauth2.message import VREQUIRED
from oic.oic import DEF_SIGN_ALG
from oic.oic import JWT_BEARER
from oic.oic.message import AuthnToken
from oic.utils.keyio import check_key_availability
from oic.utils.sanitize import sanitize
from oic.utils.time_util import utc_time_sans_frac

logger = logging.getLogger(__name__)

__author__ = "rolandh"


class AuthnFailure(Exception):
    pass


class NoMatchingKey(Exception):
    pass


class UnknownAuthnMethod(Exception):
    pass


# ========================================================================
def assertion_jwt(cli, keys, audience, algorithm, lifetime=600):
    _now = utc_time_sans_frac()

    at = AuthnToken(
        iss=cli.client_id,
        sub=cli.client_id,
        aud=audience,
        jti=rndstr(32),
        exp=_now + lifetime,
        iat=_now,
    )
    logger.debug("AuthnToken: {}".format(at.to_dict()))
    return at.to_jwt(key=keys, algorithm=algorithm)


class ClientAuthnMethod(object):
    def __init__(self, cli=None):
        """
        Initialize class.

        :param cli: Client instance
        """
        self.cli = cli

    def construct(self, **kwargs):
        """
        Add authentication information to a request.

        :return:
        """
        raise NotImplementedError

    def verify(self, **kwargs):
        """
        Verify authentication information in a request.

        :param kwargs:
        :return:
        """
        raise NotImplementedError


class ClientSecretBasic(ClientAuthnMethod):
    """
    Use HTTP Basic authentication.

    Clients that have received a client_secret value from the Authorization
    Server, authenticate with the Authorization Server in accordance with
    Section 3.2.1 of OAuth 2.0 [RFC6749] using HTTP Basic authentication scheme.
    """

    def construct(self, cis, request_args=None, http_args=None, **kwargs):
        """
        Create the request.

        :param cis: Request class instance
        :param request_args: Request arguments
        :param http_args: HTTP arguments
        :return: dictionary of HTTP arguments
        """
        if http_args is None:
            http_args = {}

        try:
            passwd = kwargs["password"]
        except KeyError:
            try:
                passwd = http_args["password"]
            except KeyError:
                try:
                    passwd = cis["client_secret"]
                except KeyError:
                    passwd = self.cli.client_secret

        try:
            user = kwargs["user"]
        except KeyError:
            user = self.cli.client_id

        if "headers" not in http_args:
            http_args["headers"] = {}

        credentials = "{}:{}".format(quote_plus(user), quote_plus(passwd))
        authz = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")
        http_args["headers"]["Authorization"] = "Basic {}".format(authz)

        try:
            del cis["client_secret"]
        except KeyError:
            pass

        if (
            ("client_id" not in cis.c_param.keys())
            or cis.c_param["client_id"][VREQUIRED]
        ) is False:
            try:
                del cis["client_id"]
            except KeyError:
                pass

        return http_args

    def verify(self, areq, client_id, **kwargs):
        if self.cli.cdb[client_id]["client_secret"] == areq["client_secret"]:
            return client_id
        else:
            raise AuthnFailure()


class ClientSecretPost(ClientSecretBasic):
    """
    Authenticate using client_secret in POST body.

    Clients that have received a client_secret value from the Authorization
    Server, authenticate with the Authorization Server in accordance with
    Section 3.2.1 of OAuth 2.0 [RFC6749] by including the Client Credentials in the request body.
    """

    def construct(self, cis, request_args=None, http_args=None, **kwargs):
        if "client_secret" not in cis:
            try:
                cis["client_secret"] = http_args["client_secret"]
                del http_args["client_secret"]
            except (KeyError, TypeError):
                if self.cli.client_secret:
                    cis["client_secret"] = self.cli.client_secret
                else:
                    raise AuthnFailure("Missing client secret")

        cis["client_id"] = self.cli.client_id

        return http_args


class BearerHeader(ClientAuthnMethod):
    def construct(self, cis=None, request_args=None, http_args=None, **kwargs):
        """
        More complicated logic then I would have liked it to be.

        :param cli: Client instance
        :param cis: Request class instance
        :param request_args: request arguments
        :param http_args: HTTP header arguments
        :param kwargs:
        :return:
        """
        if cis is not None:
            if "access_token" in cis:
                _acc_token = cis["access_token"]
                del cis["access_token"]
                # Required under certain circumstances :-) not under other
                cis.c_param["access_token"] = SINGLE_OPTIONAL_STRING
            else:
                try:
                    _acc_token = request_args["access_token"]
                    del request_args["access_token"]
                except (KeyError, TypeError):
                    try:
                        _acc_token = kwargs["access_token"]
                    except KeyError:
                        _acc_token = self.cli.get_token(**kwargs).access_token
        else:
            try:
                _acc_token = kwargs["access_token"]
            except KeyError:
                _acc_token = request_args["access_token"]

        # Do I need to base64 encode the access token ? Probably !
        _bearer = "Bearer %s" % _acc_token
        if http_args is None:
            http_args = {"headers": {}}
            http_args["headers"]["Authorization"] = _bearer
        else:
            try:
                http_args["headers"]["Authorization"] = _bearer
            except KeyError:
                http_args["headers"] = {"Authorization": _bearer}

        return http_args

    def verify(self, environ, **kwargs):
        try:
            cred = environ["HTTP_AUTHORIZATION"]
        except KeyError:
            raise AuthnFailure("missing authorization info")

        if not cred.startswith("Bearer "):
            raise AuthnFailure("Wrong type of authorization token")

        _, token = cred.split(" ")
        return token


class BearerBody(ClientAuthnMethod):
    def construct(self, cis, request_args=None, http_args=None, **kwargs):
        if request_args is None:
            request_args = {}

        if "access_token" in cis:
            pass
        else:
            try:
                cis["access_token"] = request_args["access_token"]
            except KeyError:
                try:
                    kwargs["state"]
                except KeyError:
                    if not self.cli.state:
                        raise AuthnFailure("Missing state specification")
                    kwargs["state"] = self.cli.state

                cis["access_token"] = self.cli.get_token(**kwargs).access_token

        return http_args


class JWSAuthnMethod(ClientAuthnMethod):
    def choose_algorithm(self, entity, **kwargs):
        try:
            algorithm = kwargs["algorithm"]
        except KeyError:
            algorithm = DEF_SIGN_ALG[entity]
        if not algorithm:
            raise AuthnFailure("Missing algorithm specification")
        return algorithm

    def get_signing_key(self, algorithm):
        return self.cli.keyjar.get_signing_key(alg2keytype(algorithm), alg=algorithm)

    def get_key_by_kid(self, kid, algorithm):
        _key = self.cli.keyjar.get_key_by_kid(kid)
        if _key:
            ktype = alg2keytype(algorithm)
            if _key.kty == ktype:
                return _key
            else:
                raise NoMatchingKey("Wrong key type")
        else:
            raise NoMatchingKey("No key with kid:%s" % kid)

    def construct(self, cis, request_args=None, http_args=None, **kwargs):
        """
        Construct a client assertion and signs it with a key.

        The request is modified as a side effect.
        :param cis: The request
        :param request_args: request arguments
        :param http_args: HTTP arguments
        :param kwargs: Extra arguments
        :return: Constructed HTTP arguments, in this case none
        """
        # audience is the OP endpoint
        # OR OP identifier
        algorithm = None
        if kwargs["authn_endpoint"] in ["token", "refresh"]:
            try:
                algorithm = self.cli.registration_info[
                    "token_endpoint_auth_signing_alg"
                ]
            except (KeyError, AttributeError):
                pass
            audience = self.cli.provider_info["token_endpoint"]
        else:
            audience = self.cli.provider_info["issuer"]

        if not algorithm:
            algorithm = self.choose_algorithm(**kwargs)

        ktype = alg2keytype(algorithm)
        try:
            if "kid" in kwargs:
                signing_key = [self.get_key_by_kid(kwargs["kid"], algorithm)]
            elif ktype in self.cli.kid["sig"]:
                try:
                    signing_key = [
                        self.get_key_by_kid(self.cli.kid["sig"][ktype], algorithm)
                    ]
                except KeyError:
                    signing_key = self.get_signing_key(algorithm)
            else:
                signing_key = self.get_signing_key(algorithm)
        except NoMatchingKey as err:
            logger.error("%s" % sanitize(err))
            raise

        if "client_assertion" in kwargs:
            cis["client_assertion"] = kwargs["client_assertion"]
            if "client_assertion_type" in kwargs:
                cis["client_assertion_type"] = kwargs["client_assertion_type"]
            else:
                cis["client_assertion_type"] = JWT_BEARER
        elif "client_assertion" in cis:
            if "client_assertion_type" not in cis:
                cis["client_assertion_type"] = JWT_BEARER
        else:
            try:
                _args = {"lifetime": kwargs["lifetime"]}
            except KeyError:
                _args = {}

            cis["client_assertion"] = assertion_jwt(
                self.cli, signing_key, audience, algorithm, **_args
            )

            cis["client_assertion_type"] = JWT_BEARER

        try:
            del cis["client_secret"]
        except KeyError:
            pass

        if not cis.c_param["client_id"][VREQUIRED]:
            try:
                del cis["client_id"]
            except KeyError:
                pass

        return {}

    def verify(self, areq, **kwargs):
        try:
            try:
                argv = {"sender": areq["client_id"]}
            except KeyError:
                argv = {}
            bjwt = AuthnToken().from_jwt(
                areq["client_assertion"], keyjar=self.cli.keyjar, **argv
            )
        except (Invalid, MissingKey) as err:
            logger.info("%s" % sanitize(err))
            raise AuthnFailure("Could not verify client_assertion.")

        logger.debug("authntoken: %s" % sanitize(bjwt.to_dict()))
        areq["parsed_client_assertion"] = bjwt

        try:
            cid = kwargs["client_id"]
        except KeyError:
            cid = bjwt["iss"]

            # There might not be a client_id in the request
        if cid not in self.cli.cdb:
            raise AuthnFailure("Unknown client id")

        # aud can be a string or a list
        _aud = bjwt["aud"]
        logger.debug("audience: %s, baseurl: %s" % (_aud, self.cli.baseurl))

        # figure out authn method
        if alg2keytype(bjwt.jws_header["alg"]) == "oct":  # Symmetric key
            authn_method = "client_secret_jwt"
        else:
            authn_method = "private_key_jwt"

        if isinstance(_aud, str):
            if not str(_aud).startswith(self.cli.baseurl):
                raise NotForMe("Not for me!")
        else:
            for target in _aud:
                if target.startswith(self.cli.baseurl):
                    return cid, authn_method
            raise NotForMe("Not for me!")

        return cid, authn_method


class ClientSecretJWT(JWSAuthnMethod):
    """
    Authentication using JWT.

    Clients that have received a client_secret value from the Authorization Server create a JWT using
    an HMAC SHA algorithm, such as HMAC SHA-256.
    The HMAC (Hash-based Message Authentication Code) is calculated using the
    bytes of the UTF-8 representation of the client_secret as the shared key.
    """

    def choose_algorithm(self, entity="client_secret_jwt", **kwargs):
        return JWSAuthnMethod.choose_algorithm(self, entity, **kwargs)

    def get_signing_key(self, algorithm):
        return self.cli.keyjar.get_signing_key(alg2keytype(algorithm), alg=algorithm)


class PrivateKeyJWT(JWSAuthnMethod):
    """Clients that have registered a public key sign a JWT using that key."""

    def choose_algorithm(self, entity="private_key_jwt", **kwargs):
        return JWSAuthnMethod.choose_algorithm(self, entity, **kwargs)

    def get_signing_key(self, algorithm):
        return self.cli.keyjar.get_signing_key(
            alg2keytype(algorithm), "", alg=algorithm
        )


CLIENT_AUTHN_METHOD = {
    "client_secret_basic": ClientSecretBasic,
    "client_secret_post": ClientSecretPost,
    "bearer_header": BearerHeader,
    "bearer_body": BearerBody,
    "client_secret_jwt": ClientSecretJWT,
    "private_key_jwt": PrivateKeyJWT,
}

TYPE_METHOD = [(JWT_BEARER, JWSAuthnMethod)]


def valid_client_info(cinfo):
    eta = cinfo.get("client_secret_expires_at", 0)
    if eta != 0 and eta < utc_time_sans_frac():
        return False
    return True


def get_client_id(cdb, req, authn):
    """
    Verify the client and return the client id.

    :param req: The request
    :param authn: Authentication information from the HTTP header
    :return:
    """
    logger.debug("REQ: %s" % sanitize(req.to_dict()))
    _secret = None
    if not authn:
        try:
            _id = str(req["client_id"])
        except KeyError:
            raise FailedAuthentication("Missing client_id")
    elif authn.startswith("Basic "):
        logger.debug("Basic auth")
        (_id, _secret) = (
            base64.b64decode(authn[6:].encode("utf-8")).decode("utf-8").split(":")
        )
        # Either as string or encoded
        if _id not in cdb:
            _bid = as_bytes(_id)
            _id = _bid
    elif authn[:6].lower() == "bearer":
        logger.debug("Bearer auth")
        _token = authn[7:]
        try:
            _id = cdb[_token]
        except KeyError:
            logger.debug("Unknown access token")
            raise FailedAuthentication("Unknown access token")
    else:
        raise FailedAuthentication("AuthZ type I don't know")
    # We have the client_id by now, so let's verify it
    _cinfo = cdb.get(_id)
    if _cinfo is None:
        raise FailedAuthentication("Unknown client")
    if not valid_client_info(_cinfo):
        logger.debug("Invalid Client info")
        raise FailedAuthentication("Invalid Client")
    if _secret is not None:
        if _secret != _cinfo["client_secret"]:
            logger.debug("Incorrect secret")
            raise FailedAuthentication("Incorrect secret")
    # All should be good, so return it
    return _id


def verify_client(inst, areq, authn, type_method=TYPE_METHOD):
    """
    Guess authentication method and get client from that.

    :param inst: Entity instance
    :param areq: The request
    :param authn: client authentication information
    :return: tuple containing client id and client authentication method
    """
    if authn:  # HTTP Basic auth (client_secret_basic)
        cid = get_client_id(inst.cdb, areq, authn)
        auth_method = "client_secret_basic"
    elif "client_secret" in areq:  # client_secret_post
        client_id = get_client_id(inst.cdb, areq, authn)
        logger.debug("Verified Client ID: %s" % client_id)
        cid = ClientSecretBasic(inst).verify(areq, client_id)
        auth_method = "client_secret_post"
    elif "client_assertion" in areq:  # client_secret_jwt or private_key_jwt
        check_key_availability(inst, areq["client_assertion"])

        for typ, method in type_method:
            if areq["client_assertion_type"] == typ:
                cid, auth_method = method(inst).verify(areq)
                break
        else:
            logger.error(
                "UnknownAssertionType: {}".format(areq["client_assertion_type"])
            )
            raise UnknownAssertionType(areq["client_assertion_type"], areq)
    else:
        logger.error("Missing client authentication.")
        raise FailedAuthentication("Missing client authentication.")

    if isinstance(areq, AccessTokenRequest):
        try:
            _method = inst.cdb[cid]["token_endpoint_auth_method"]
        except KeyError:
            _method = "client_secret_basic"

        if _method != auth_method:
            logger.error(
                "Wrong authentication method used: {} != {}".format(
                    auth_method, _method
                )
            )
            raise FailedAuthentication("Wrong authentication method used")

    # store which authn method was used where
    try:
        inst.cdb[cid]["auth_method"][areq.__class__.__name__] = auth_method
    except KeyError:
        try:
            inst.cdb[cid]["auth_method"] = {areq.__class__.__name__: auth_method}
        except KeyError:
            pass

    return cid
