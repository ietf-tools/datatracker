from typing import Dict

from oic import rndstr
from oic.extension.single import SingleClient
from oic.extension.single import SingleService
from oic.oauth2.message import SINGLE_OPTIONAL_INT
from oic.oauth2.message import SINGLE_OPTIONAL_STRING
from oic.oauth2.message import SINGLE_REQUIRED_STRING
from oic.oauth2.message import AccessTokenResponse
from oic.oauth2.message import Message
from oic.utils.time_util import time_sans_frac


class AuthorizationRequest(Message):
    c_param = {
        "response_type": SINGLE_REQUIRED_STRING,
        "client_id": SINGLE_REQUIRED_STRING,
        "scope": SINGLE_OPTIONAL_STRING,
    }


class AuthorizationResponse(Message):
    c_param = {
        "device_code": SINGLE_REQUIRED_STRING,
        "user_code": SINGLE_REQUIRED_STRING,
        "verification_uri": SINGLE_REQUIRED_STRING,
        "expires_in": SINGLE_OPTIONAL_INT,
        "interval": SINGLE_OPTIONAL_INT,
    }


class TokenRequest(Message):
    c_param = {
        "grant_type": SINGLE_REQUIRED_STRING,
        "device_code": SINGLE_REQUIRED_STRING,
        "client_id": SINGLE_REQUIRED_STRING,
    }


class DeviceFlowServer(SingleService):
    def __init__(self, host):
        SingleService.__init__(self, host)
        self.host = host
        # map between device_code and user_code
        self.client_id2device: Dict[str, str] = {}
        self.device2user: Dict[str, str] = {}
        self.user_auth: Dict[str, bool] = {}
        self.device_code_expire_at: Dict[str, int] = {}
        self.device_code_life_time = 900  # 15 minutes

    def device_endpoint(self, request, authn=None):
        _req = AuthorizationRequest(**request)
        device_code = rndstr(10)
        user_code = rndstr(6)

        self.device2user[device_code] = user_code
        self.user_auth[user_code] = False
        self.client_id2device[_req["client_id"]] = device_code
        self.device_code_expire_at[device_code] = (
            time_sans_frac() + self.device_code_life_time
        )

    def token_endpoint(self, request, authn=None):
        _req = TokenRequest(**request)
        _dc = _req["device_code"]

        if time_sans_frac() > self.device_code_expire_at[_dc]:
            return self.host.error_code(error="expired_token")

        _uc = self.device2user[_dc]

        if self.user_auth[_uc]:  # User is authenticated
            pass
        else:
            return self.host.error_code(error="authorization_pending")

    def device_auth(self, user_code):
        self.user_auth[user_code] = True


class DeviceFlowClient(SingleClient):
    def __init__(self, host):
        SingleClient.__init__(self, host)
        self.requests = {
            "authorization": self.authorization_request,
            "token": self.authorization_request,
        }

    def authorization_request(self, scope=""):
        req = AuthorizationRequest(
            client_id=self.host.client_id, response_type="device_code"
        )
        if scope:
            req["scope"] = scope

        http_response = self.host.http_request(
            self.host.provider_info["device_endpoint"], "POST", req.to_urlencoded()
        )

        response = self.host.parse_request_response(
            AuthorizationResponse, http_response, "json"
        )

        return response

    def token_request(self, device_code=""):
        req = TokenRequest(
            grant_type="urn:ietf:params:oauth:grant-type:device_code",
            device_code=device_code,
            client_id=self.host.client_id,
        )

        http_response = self.host.http_request(
            self.host.provider_info["token_endpoint"], "POST", req.to_urlencoded()
        )

        response = self.host.parse_request_response(
            AccessTokenResponse, http_response, "json"
        )

        return response
