import hashlib
import logging
import warnings

from jwkest import b64e

from oic import oauth2
from oic import unreserved
from oic.exception import AuthzError
from oic.exception import PyoidcError
from oic.extension.message import ClientRegistrationError
from oic.extension.message import ExtensionMessageFactory
from oic.oauth2.exception import Unsupported
from oic.oauth2.message import ErrorResponse
from oic.utils.http_util import SUCCESSFUL
from oic.utils.sanitize import sanitize
from oic.utils.settings import OauthClientSettings

logger = logging.getLogger(__name__)

__author__ = "roland"

# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------

RESPONSE2ERROR = {
    "ClientInfoResponse": [ClientRegistrationError],
    "ClientUpdateRequest": [ClientRegistrationError],
}

CC_METHOD = {"S256": hashlib.sha256, "S384": hashlib.sha384, "S512": hashlib.sha512}


class Client(oauth2.Client):
    def __init__(
        self,
        client_id=None,
        client_authn_method=None,
        keyjar=None,
        verify_ssl=None,
        config=None,
        message_factory=ExtensionMessageFactory,
        settings=None,
    ):
        self.settings = settings or OauthClientSettings()
        if verify_ssl is not None:
            warnings.warn(
                "`verify_ssl` is deprecated, please use `settings` instead if you need to set a non-default value.",
                DeprecationWarning,
                stacklevel=2,
            )
            self.settings.verify_ssl = verify_ssl
        super().__init__(
            client_id=client_id,
            client_authn_method=client_authn_method,
            keyjar=keyjar,
            config=config,
            message_factory=message_factory,
            settings=self.settings,
        )
        self.allow = {}
        self.request2endpoint.update(
            {
                "RegistrationRequest": "registration_endpoint",
                "ClientUpdateRequest": "clientinfo_endpoint",
                "TokenIntrospectionRequest": "introspection_endpoint",
                "TokenRevocationRequest": "revocation_endpoint",
            }
        )
        self.registration_response = None

    def construct_RegistrationRequest(
        self, request=None, request_args=None, extra_args=None, **kwargs
    ):
        if request is None:
            request = self.message_factory.get_request_type("registration_endpoint")
        if request_args is None:
            request_args = {}

        return self.construct_request(request, request_args, extra_args)

    def construct_ClientUpdateRequest(
        self, request=None, request_args=None, extra_args=None, **kwargs
    ):
        if request is None:
            request = self.message_factory.get_request_type("update_endpoint")
        if request_args is None:
            request_args = {}

        return self.construct_request(request, request_args, extra_args)

    def _token_interaction_setup(self, request_args=None, **kwargs):
        if request_args is None or "token" not in request_args:
            token = self.get_token(**kwargs)
            try:
                _token_type_hint = kwargs["token_type_hint"]
            except KeyError:
                _token_type_hint = "access_token"  # nosec

            request_args = {
                "token_type_hint": _token_type_hint,
                "token": getattr(token, _token_type_hint),
            }

        if "client_id" not in request_args:
            request_args["client_id"] = self.client_id
        elif not request_args["client_id"]:
            request_args["client_id"] = self.client_id

        return request_args

    def construct_TokenIntrospectionRequest(
        self, request=None, request_args=None, extra_args=None, **kwargs
    ):
        if request is None:
            request = self.message_factory.get_request_type("introspection_endpoint")
        request_args = self._token_interaction_setup(request_args, **kwargs)
        return self.construct_request(request, request_args, extra_args)

    def construct_TokenRevocationRequest(
        self, request=None, request_args=None, extra_args=None, **kwargs
    ):
        if request is None:
            request = self.message_factory.get_request_type("revocation_endpoint")
        request_args = self._token_interaction_setup(request_args, **kwargs)

        return self.construct_request(request, request_args, extra_args)

    def do_op(
        self,
        request,
        body_type="",
        method="GET",
        request_args=None,
        extra_args=None,
        http_args=None,
        response_cls=None,
        **kwargs,
    ):
        url, body, ht_args, _ = self.request_info(
            request, method, request_args, extra_args, **kwargs
        )

        if http_args is None:
            http_args = ht_args
        else:
            http_args.update(ht_args)

        resp = self.request_and_return(
            url, response_cls, method, body, body_type, http_args=http_args
        )

        return resp

    def do_client_registration(
        self,
        body_type="",
        method="GET",
        request_args=None,
        extra_args=None,
        http_args=None,
        **kwargs,
    ):
        request = self.message_factory.get_request_type("registration_endpoint")
        response_cls = self.message_factory.get_response_type("registration_endpoint")
        return self.do_op(
            request=request,
            body_type=body_type,
            method=method,
            request_args=request_args,
            extra_args=extra_args,
            http_args=http_args,
            response_cls=response_cls,
            **kwargs,
        )

    def do_client_read_request(
        self,
        body_type="",
        method="GET",
        request_args=None,
        extra_args=None,
        http_args=None,
        **kwargs,
    ):
        request = self.message_factory.get_request_type("update_endpoint")
        response_cls = self.message_factory.get_response_type("update_endpoint")
        return self.do_op(
            request=request,
            body_type=body_type,
            method=method,
            request_args=request_args,
            extra_args=extra_args,
            http_args=http_args,
            response_cls=response_cls,
            **kwargs,
        )

    def do_client_update_request(
        self,
        body_type="",
        method="PUT",
        request_args=None,
        extra_args=None,
        http_args=None,
        **kwargs,
    ):
        request = self.message_factory.get_request_type("update_endpoint")
        response_cls = self.message_factory.get_response_type("update_endpoint")
        return self.do_op(
            request=request,
            body_type=body_type,
            method=method,
            request_args=request_args,
            extra_args=extra_args,
            http_args=http_args,
            response_cls=response_cls,
            **kwargs,
        )

    def do_client_delete_request(
        self,
        body_type="",
        method="DELETE",
        request_args=None,
        extra_args=None,
        http_args=None,
        **kwargs,
    ):
        request = self.message_factory.get_request_type("delete_endpoint")
        response_cls = self.message_factory.get_response_type("delete_endpoint")
        return self.do_op(
            request=request,
            body_type=body_type,
            method=method,
            request_args=request_args,
            extra_args=extra_args,
            http_args=http_args,
            response_cls=response_cls,
            **kwargs,
        )

    def do_token_introspection(
        self,
        body_type="json",
        method="POST",
        request_args=None,
        extra_args=None,
        http_args=None,
        **kwargs,
    ):
        request = self.message_factory.get_request_type("introspection_endpoint")
        response_cls = self.message_factory.get_response_type("introspection_endpoint")
        return self.do_op(
            request=request,
            body_type=body_type,
            method=method,
            request_args=request_args,
            extra_args=extra_args,
            http_args=http_args,
            response_cls=response_cls,
            **kwargs,
        )

    def do_token_revocation(
        self,
        body_type=None,
        method="POST",
        request_args=None,
        extra_args=None,
        http_args=None,
        **kwargs,
    ):
        request = self.message_factory.get_request_type("revocation_endpoint")
        # There is no expected response, only the status code is important,
        # so do not use do_op().

        url, body, ht_args, _ = self.request_info(
            request, method, request_args, extra_args, **kwargs
        )

        if http_args is None:
            http_args = ht_args
        else:
            http_args.update(ht_args)

        resp = self.http_request(url, method, data=body, **http_args)

        if resp.status_code == 200:
            return 200
        if resp.status_code == 503:
            # Revoke failed, should retry later
            raise PyoidcError("Retry revocation later.")

        if 400 <= resp.status_code < 500:
            # check for error response
            try:
                err = ErrorResponse().deserialize(resp.text)
                try:
                    err.verify()
                except PyoidcError:
                    pass
                else:
                    return err
            except Exception:
                logger.exception(
                    "Failed to decode error response (%d) %s",
                    resp.status_code,
                    sanitize(resp.text),
                )

        return resp

    def add_code_challenge(self):
        try:
            cv_len = self.config["code_challenge"]["length"]
        except KeyError:
            cv_len = 64  # Use default

        code_verifier = unreserved(cv_len)
        _cv = code_verifier.encode("ascii")

        try:
            _method = self.config["code_challenge"]["method"]
        except KeyError:
            _method = "S256"

        try:
            _h = CC_METHOD[_method](_cv).digest()
            code_challenge = b64e(_h).decode("ascii")
        except KeyError:
            raise Unsupported("PKCE Transformation method:{}".format(_method))

        # TODO store code_verifier

        return (
            {"code_challenge": code_challenge, "code_challenge_method": _method},
            code_verifier,
        )

    def do_authorization_request(
        self,
        state="",
        body_type="",
        method="GET",
        request_args=None,
        extra_args=None,
        http_args=None,
        **kwargs,
    ):
        if "code_challenge" in self.config and self.config["code_challenge"]:
            _args, code_verifier = self.add_code_challenge()
            request_args.update(_args)

        oauth2.Client.do_authorization_request(
            self,
            state=state,
            body_type=body_type,
            method=method,
            request_args=request_args,
            extra_args=extra_args,
            http_args=http_args,
            **kwargs,
        )

    def store_registration_info(self, reginfo):
        self.registration_response = reginfo
        self.client_secret = reginfo["client_secret"]
        self.client_id = reginfo["client_id"]
        self.redirect_uris = reginfo["redirect_uris"]

    def handle_registration_info(self, response):
        if response.status_code in SUCCESSFUL:
            resp = self.message_factory.get_response_type(
                "registration_endpoint"
            )().deserialize(response.text, "json")
            self.store_response(resp, response.text)
            self.store_registration_info(resp)
        else:
            resp = ErrorResponse().deserialize(response.text, "json")
            try:
                resp.verify()
                self.store_response(resp, response.text)
            except Exception:
                raise PyoidcError("Registration failed: {}".format(response.text))

        return resp

    def register(self, url, **kwargs):
        """
        Register the client at an OP.

        :param url: The OPs registration endpoint
        :param kwargs: parameters to the registration request
        :return:
        """
        req = self.construct_RegistrationRequest(request_args=kwargs)

        headers = {"content-type": "application/json"}

        rsp = self.http_request(url, "POST", data=req.to_json(), headers=headers)

        return self.handle_registration_info(rsp)

    def parse_authz_response(self, query):
        aresp = self.parse_response(
            self.message_factory.get_response_type("authorization_endpoint"),
            info=query,
            sformat="urlencoded",
            keyjar=self.keyjar,
        )
        if isinstance(aresp, ErrorResponse):
            logger.info("ErrorResponse: %s" % sanitize(aresp))
            raise AuthzError(
                aresp.error  # type: ignore # Messages have no classical attrs
            )

        logger.info("Aresp: %s" % sanitize(aresp))

        return aresp
