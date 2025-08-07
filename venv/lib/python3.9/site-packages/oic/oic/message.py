import inspect
import json
import logging
import sys
import time
import warnings
from typing import Dict
from typing import List
from urllib.parse import urlencode
from urllib.parse import urlparse

from jwkest import jws
from jwkest.jwe import JWEException
from jwkest.jwe import factory as JWE_factory
from jwkest.jwt import JWT

from oic.exception import InvalidRequest
from oic.exception import IssuerMismatch
from oic.exception import MessageException
from oic.exception import NotForMe
from oic.exception import PyoidcError
from oic.oauth2 import message
from oic.oauth2.exception import VerificationError
from oic.oauth2.message import OPTIONAL_LIST_OF_SP_SEP_STRINGS
from oic.oauth2.message import OPTIONAL_LIST_OF_STRINGS
from oic.oauth2.message import REQUIRED_LIST_OF_SP_SEP_STRINGS
from oic.oauth2.message import REQUIRED_LIST_OF_STRINGS
from oic.oauth2.message import SINGLE_OPTIONAL_INT
from oic.oauth2.message import SINGLE_OPTIONAL_JSON
from oic.oauth2.message import SINGLE_OPTIONAL_STRING
from oic.oauth2.message import SINGLE_REQUIRED_STRING
from oic.oauth2.message import Message
from oic.oauth2.message import MessageFactory
from oic.oauth2.message import MessageTuple
from oic.oauth2.message import MissingRequiredAttribute
from oic.oauth2.message import MissingRequiredValue
from oic.oauth2.message import NotAllowedValue
from oic.oauth2.message import ParamDefinition
from oic.oauth2.message import SchemeError
from oic.utils import time_util
from oic.utils.time_util import utc_time_sans_frac

__author__ = "rohe0002"

logger = logging.getLogger(__name__)

NONCE_STORAGE_TIME = 4 * 3600


class AtHashError(VerificationError):
    pass


class CHashError(VerificationError):
    pass


class EXPError(VerificationError):
    pass


class IATError(VerificationError):
    pass


def json_ser(val, sformat=None, lev=0):
    return json.dumps(val)


def json_deser(val, sformat=None, lev=0):
    return json.loads(val)


def json_conv(val, sformat=None, lev=0):
    if isinstance(val, dict):
        for key, _val in val.items():
            if _val is None:
                val[key] = "none"
            elif _val is True:
                val[key] = "true"
            elif _val is False:
                val[key] = "false"

    return val


def json_rest(val, sformat=None, lev=0):
    if isinstance(val, dict):
        for key, _val in val.items():
            if _val == "none":
                val[key] = None
            elif _val == "true":
                val[key] = True
            elif _val == "false":
                val[key] = False

    return val


# value type, required, serializer, deserializer, null value allowed
SINGLE_OPTIONAL_BOOLEAN = ParamDefinition(bool, False, None, None, False)
SINGLE_OPTIONAL_JSON_WN = ParamDefinition(dict, False, json_ser, json_deser, True)
SINGLE_OPTIONAL_JSON_CONV = ParamDefinition(dict, False, json_conv, json_rest, True)
SINGLE_REQUIRED_INT = ParamDefinition(int, True, None, None, False)


def idtoken_deser(val, sformat="urlencoded"):
    # id_token are always serialized as a JWT
    return IdToken().deserialize(val, "jwt")


def address_deser(val, sformat="urlencoded"):
    if sformat in ["dict", "json"]:
        if not isinstance(val, str):
            val = json.dumps(val)
            sformat = "json"
        elif sformat == "dict":
            sformat = "json"
    return AddressClaim().deserialize(val, sformat)


def claims_deser(val, sformat="urlencoded"):
    if sformat in ["dict", "json"]:
        if not isinstance(val, str):
            val = json.dumps(val)
            sformat = "json"
    return Claims().deserialize(val, sformat)


def message_deser(val, sformat="urlencoded"):
    if sformat in ["dict", "json"]:
        if not isinstance(val, str):
            val = json.dumps(val)
            sformat = "json"
    return Message().deserialize(val, sformat)


def msg_ser(inst, sformat, lev=0):
    if sformat in ["urlencoded", "json"]:
        if isinstance(inst, Message):
            res = inst.serialize(sformat, lev)
        else:
            res = inst
    elif sformat == "dict":
        if isinstance(inst, Message):
            res = inst.serialize(sformat, lev)
        elif isinstance(inst, dict):
            res = inst
        elif isinstance(inst, str):  # Iff ID Token
            res = inst
        else:
            raise MessageException("Wrong type: %s" % type(inst))
    else:
        raise PyoidcError("Unknown sformat", inst)

    return res


def msg_ser_json(inst, sformat="json", lev=0):
    # sformat = "json" always except when dict
    if lev:
        sformat = "dict"

    if sformat == "dict":
        if isinstance(inst, Message):
            res = inst.serialize(sformat, lev)
        elif isinstance(inst, dict):
            res = inst
        else:
            raise MessageException("Wrong type: %s" % type(inst))
    else:
        sformat = "json"
        if isinstance(inst, Message):
            res = inst.serialize(sformat, lev)
        else:
            res = inst

    return res


def msg_list_ser(insts, sformat, lev=0):
    return [msg_ser(inst, sformat, lev) for inst in insts]


def claims_ser(val, sformat="urlencoded", lev=0):
    # everything in c_extension
    if isinstance(val, str):
        item = val
    elif isinstance(val, list):
        item = val[0]
    else:
        item = val

    if isinstance(item, Message):
        return item.serialize(method=sformat, lev=lev + 1)

    if sformat == "urlencoded":
        assert isinstance(  # nosec
            item, dict
        )  # We cannot urlencode anything else than Mapping
        res = urlencode(item)
    elif sformat == "json":
        if lev:
            res = item
        else:
            res = json.dumps(item)
    elif sformat == "dict":
        if isinstance(item, dict):
            res = item
        else:
            raise MessageException("Wrong type: %s" % type(item))
    else:
        raise PyoidcError("Unknown sformat: %s" % sformat, val)

    return res


def registration_request_deser(val, sformat="urlencoded"):
    if sformat in ["dict", "json"]:
        if not isinstance(val, str):
            val = json.dumps(val)
            sformat = "json"
    return RegistrationRequest().deserialize(val, sformat)


def claims_request_deser(val, sformat="json"):
    # never 'urlencoded'
    if sformat == "urlencoded":
        sformat = "json"
    if sformat in ["dict", "json"]:
        if not isinstance(val, str):
            val = json.dumps(val)
            sformat = "json"
    return ClaimsRequest().deserialize(val, sformat)


OPTIONAL_ADDRESS = ParamDefinition(Message, False, msg_ser, address_deser, False)
OPTIONAL_LOGICAL = ParamDefinition(bool, False, None, None, False)
OPTIONAL_MULTIPLE_Claims = ParamDefinition(
    Message, False, claims_ser, claims_deser, False
)

SINGLE_OPTIONAL_IDTOKEN = ParamDefinition(str, False, msg_ser, None, False)

SINGLE_OPTIONAL_REGISTRATION_REQUEST = ParamDefinition(
    Message, False, msg_ser, registration_request_deser, False
)
SINGLE_OPTIONAL_CLAIMSREQ = ParamDefinition(
    Message, False, msg_ser_json, claims_request_deser, False
)

OPTIONAL_MESSAGE = ParamDefinition(Message, False, msg_ser, message_deser, False)
REQUIRED_MESSAGE = ParamDefinition(Message, True, msg_ser, message_deser, False)

# ----------------------------------------------------------------------------


SCOPE_CHARSET = []
for char in ["\x21", ("\x23", "\x5b"), ("\x5d", "\x7E")]:
    if isinstance(char, tuple):
        c = char[0]
        while c <= char[1]:
            SCOPE_CHARSET.append(c)
            c = chr(ord(c) + 1)
    else:
        SCOPE_CHARSET.append(set)


def check_char_set(string, allowed):
    for c in string:
        if c not in allowed:
            raise NotAllowedValue("'%c' not in the allowed character set" % c)


TOKEN_VERIFY_ARGS = ["key", "keyjar", "algs", "sender"]


def verify_id_token(instance, check_hash=False, **kwargs):
    # Try to decode the JWT, checks the signature
    args = {}
    for arg in TOKEN_VERIFY_ARGS:
        try:
            args[arg] = kwargs[arg]
        except KeyError:
            pass

    _jws = str(instance["id_token"])

    # It can be encrypted, so try to decrypt first
    _jwe = JWE_factory(_jws)
    if _jwe is not None:
        try:
            _jws = _jwe.decrypt(keys=kwargs["keyjar"].get_decrypt_key())
        except JWEException as err:
            raise VerificationError("Could not decrypt id_token", err)
    _packer = JWT()
    _body = _packer.unpack(_jws).payload()

    if "keyjar" in kwargs:
        try:
            if _body["iss"] not in kwargs["keyjar"]:
                raise ValueError("Unknown issuer")
        except KeyError:
            raise MissingRequiredAttribute("iss")

    if _jwe is not None:
        # Use the original encrypted token to set correct headers
        idt = IdToken().from_jwt(str(instance["id_token"]), **args)
    else:
        idt = IdToken().from_jwt(_jws, **args)
    if not idt.verify(**kwargs):
        raise VerificationError("Could not verify id_token", idt)

    if check_hash:
        _alg = idt.jws_header["alg"]
        if _alg != "none":
            hfunc = "HS" + _alg[-3:]
        else:
            # This is allowed only for `code` and it needs to be checked by a Client
            hfunc = None

        if "access_token" in instance and hfunc is not None:
            if "at_hash" not in idt:
                raise MissingRequiredAttribute("Missing at_hash property", idt)
            if idt["at_hash"] != jws.left_hash(instance["access_token"], hfunc):
                raise AtHashError("Failed to verify access_token hash", idt)

        if "code" in instance and hfunc is not None:
            if "c_hash" not in idt:
                raise MissingRequiredAttribute("Missing c_hash property", idt)
            if idt["c_hash"] != jws.left_hash(instance["code"], hfunc):
                raise CHashError("Failed to verify code hash", idt)

    return idt


# -----------------------------------------------------------------------------


class RefreshAccessTokenRequest(message.RefreshAccessTokenRequest):
    pass


class TokenErrorResponse(message.TokenErrorResponse):
    pass


class AccessTokenResponse(message.AccessTokenResponse):
    c_param = message.AccessTokenResponse.c_param.copy()
    c_param.update({"id_token": SINGLE_OPTIONAL_STRING})

    def verify(self, **kwargs):
        super().verify(**kwargs)
        if "id_token" in self:
            # The ID token JWT needs to be passed in the access token response
            # to be usable as id_token_hint for RP-Initiated Logout. Refer to
            # https://openid.net/specs/openid-connect-rpinitiated-1_0.html#RPLogout
            self["id_token_jwt"] = self["id_token"]
            # replace the JWT with the verified IdToken instance
            self["id_token"] = verify_id_token(self, **kwargs)

        return True


class UserInfoRequest(Message):
    c_param = {"access_token": SINGLE_OPTIONAL_STRING}


class AuthorizationResponse(message.AuthorizationResponse, message.AccessTokenResponse):
    c_param = message.AuthorizationResponse.c_param.copy()
    c_param.update(message.AccessTokenResponse.c_param)
    c_param.update(
        {
            "code": SINGLE_OPTIONAL_STRING,
            "access_token": SINGLE_OPTIONAL_STRING,
            "token_type": SINGLE_OPTIONAL_STRING,
            "id_token": SINGLE_OPTIONAL_IDTOKEN,
        }
    )

    def verify(self, **kwargs):
        super().verify(**kwargs)

        if "aud" in self:
            if "client_id" in kwargs:
                # check that it's for me
                if kwargs["client_id"] not in self["aud"]:
                    return False

        if "id_token" in self:
            self["id_token"] = verify_id_token(self, check_hash=True, **kwargs)

        if "access_token" in self:
            if "token_type" not in self:
                raise MissingRequiredValue("Missing token_type parameter", self)

        return True


class AuthorizationErrorResponse(message.AuthorizationErrorResponse):
    c_allowed_values = message.AuthorizationErrorResponse.c_allowed_values.copy()
    c_allowed_values["error"].extend(
        [
            "interaction_required",
            "login_required",
            "session_selection_required",
            "consent_required",
            "invalid_request_uri",
            "invalid_request_object",
            "registration_not_supported",
            "request_not_supported",
            "request_uri_not_supported",
        ]
    )


class AuthorizationRequest(message.AuthorizationRequest):
    c_param = message.AuthorizationRequest.c_param.copy()
    c_param.update(
        {
            "scope": REQUIRED_LIST_OF_SP_SEP_STRINGS,
            "redirect_uri": SINGLE_REQUIRED_STRING,
            "nonce": SINGLE_OPTIONAL_STRING,
            "display": SINGLE_OPTIONAL_STRING,
            "prompt": OPTIONAL_LIST_OF_STRINGS,
            "max_age": SINGLE_OPTIONAL_INT,
            "ui_locales": OPTIONAL_LIST_OF_SP_SEP_STRINGS,
            "claims_locales": OPTIONAL_LIST_OF_SP_SEP_STRINGS,
            "id_token_hint": SINGLE_OPTIONAL_STRING,
            "login_hint": SINGLE_OPTIONAL_STRING,
            "acr_values": OPTIONAL_LIST_OF_SP_SEP_STRINGS,
            "claims": SINGLE_OPTIONAL_CLAIMSREQ,
            "registration": SINGLE_OPTIONAL_JSON,
            "request": SINGLE_OPTIONAL_STRING,
            "request_uri": SINGLE_OPTIONAL_STRING,
            "response_mode": SINGLE_OPTIONAL_STRING,
        }
    )
    c_allowed_values = message.AuthorizationRequest.c_allowed_values.copy()
    c_allowed_values.update(
        {
            "display": ["page", "popup", "touch", "wap"],
            "prompt": ["none", "login", "consent", "select_account"],
        }
    )

    def verify(self, **kwargs):
        """
        Check that the request is valid.

        Authorization Request parameters that are OPTIONAL in the OAuth 2.0
        specification MAY be included in the OpenID Request Object without also
        passing them as OAuth 2.0 Authorization Request parameters, with one
        exception: The scope parameter MUST always be present in OAuth 2.0
        Authorization Request parameters.
        All parameter values that are present both in the OAuth 2.0
        Authorization Request and in the OpenID Request Object MUST exactly match.
        """
        super().verify(**kwargs)

        args = {}
        for arg in ["key", "keyjar", "opponent_id", "sender"]:
            try:
                args[arg] = kwargs[arg]
            except KeyError:
                pass

        if "opponent_id" not in kwargs:
            args["opponent_id"] = self["client_id"]

        if "request" in self:
            if isinstance(self["request"], str):
                # Try to decode the JWT, checks the signature
                oidr = OpenIDRequest().from_jwt(str(self["request"]), **args)

                # verify that nothing is change in the original message
                for key, val in oidr.items():
                    if key in self and self[key] != val:
                        raise AssertionError()

                # replace the JWT with the parsed and verified instance
                self["request"] = oidr

        if "id_token_hint" in self:
            if isinstance(self["id_token_hint"], str):
                idt = IdToken().from_jwt(str(self["id_token_hint"]), **args)
                self["id_token_hint"] = idt

        if "response_type" not in self:
            raise MissingRequiredAttribute("response_type missing", self)

        _rt = self["response_type"]
        if "token" in _rt or "id_token" in _rt:
            if "nonce" not in self:
                raise MissingRequiredAttribute("Nonce missing", self)

        if "openid" not in self.get("scope", []):
            raise MissingRequiredValue("openid not in scope", self)

        if "offline_access" in self.get("scope", []):
            if "prompt" not in self or "consent" not in self["prompt"]:
                raise MissingRequiredValue("consent in prompt", self)

        if "prompt" in self:
            if "none" in self["prompt"] and len(self["prompt"]) > 1:
                raise InvalidRequest("prompt none combined with other value", self)

        return True


class AccessTokenRequest(message.AccessTokenRequest):
    c_param = message.AccessTokenRequest.c_param.copy()
    c_param.update(
        {
            "client_assertion_type": SINGLE_OPTIONAL_STRING,
            "client_assertion": SINGLE_OPTIONAL_STRING,
        }
    )
    c_default = {"grant_type": "authorization_code"}
    c_allowed_values = {
        "client_assertion_type": [
            "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
        ]
    }


class AddressClaim(Message):
    c_param = {
        "formatted": SINGLE_OPTIONAL_STRING,
        "street_address": SINGLE_OPTIONAL_STRING,
        "locality": SINGLE_OPTIONAL_STRING,
        "region": SINGLE_OPTIONAL_STRING,
        "postal_code": SINGLE_OPTIONAL_STRING,
        "country": SINGLE_OPTIONAL_STRING,
    }


class OpenIDSchema(Message):
    c_param = {
        "sub": SINGLE_REQUIRED_STRING,
        "name": SINGLE_OPTIONAL_STRING,
        "given_name": SINGLE_OPTIONAL_STRING,
        "family_name": SINGLE_OPTIONAL_STRING,
        "middle_name": SINGLE_OPTIONAL_STRING,
        "nickname": SINGLE_OPTIONAL_STRING,
        "preferred_username": SINGLE_OPTIONAL_STRING,
        "profile": SINGLE_OPTIONAL_STRING,
        "picture": SINGLE_OPTIONAL_STRING,
        "website": SINGLE_OPTIONAL_STRING,
        "email": SINGLE_OPTIONAL_STRING,
        "email_verified": SINGLE_OPTIONAL_BOOLEAN,
        "gender": SINGLE_OPTIONAL_STRING,
        "birthdate": SINGLE_OPTIONAL_STRING,
        "zoneinfo": SINGLE_OPTIONAL_STRING,
        "locale": SINGLE_OPTIONAL_STRING,
        "phone_number": SINGLE_OPTIONAL_STRING,
        "phone_number_verified": SINGLE_OPTIONAL_BOOLEAN,
        "address": OPTIONAL_ADDRESS,
        "updated_at": SINGLE_OPTIONAL_INT,
        "_claim_names": OPTIONAL_MESSAGE,
        "_claim_sources": OPTIONAL_MESSAGE,
    }

    def from_dict(self, dictionary, **kwargs):
        result = super().from_dict(dictionary, **kwargs)
        # The spec allows empty fields in the UserInfo/IdToken response, but suggests
        # the OP should omit those. So lets drop them here.
        for key_ in [
            key_ for key_, val in self._dict.items() if val is None or val == ""
        ]:
            del self[key_]
        return result

    def verify(self, **kwargs):
        super().verify(**kwargs)

        if "birthdate" in self:
            # Either YYYY-MM-DD or just YYYY or 0000-MM-DD
            try:
                time.strptime(self["birthdate"], "%Y-%m-%d")
            except ValueError:
                try:
                    time.strptime(self["birthdate"], "%Y")
                except ValueError:
                    try:
                        time.strptime(self["birthdate"], "0000-%m-%d")
                    except ValueError:
                        raise VerificationError("Birthdate format error", self)

        if any(val is None for val in self.values()):
            return False

        return True


class RegistrationRequest(Message):
    c_param = {
        "redirect_uris": REQUIRED_LIST_OF_STRINGS,
        "response_types": OPTIONAL_LIST_OF_STRINGS,
        "grant_types": OPTIONAL_LIST_OF_STRINGS,
        "application_type": SINGLE_OPTIONAL_STRING,
        "contacts": OPTIONAL_LIST_OF_STRINGS,
        "client_name": SINGLE_OPTIONAL_STRING,
        "logo_uri": SINGLE_OPTIONAL_STRING,
        "client_uri": SINGLE_OPTIONAL_STRING,
        "policy_uri": SINGLE_OPTIONAL_STRING,
        "tos_uri": SINGLE_OPTIONAL_STRING,
        "jwks": SINGLE_OPTIONAL_STRING,
        "jwks_uri": SINGLE_OPTIONAL_STRING,
        "sector_identifier_uri": SINGLE_OPTIONAL_STRING,
        "subject_type": SINGLE_OPTIONAL_STRING,
        "id_token_signed_response_alg": SINGLE_OPTIONAL_STRING,
        "id_token_encrypted_response_alg": SINGLE_OPTIONAL_STRING,
        "id_token_encrypted_response_enc": SINGLE_OPTIONAL_STRING,
        "userinfo_signed_response_alg": SINGLE_OPTIONAL_STRING,
        "userinfo_encrypted_response_alg": SINGLE_OPTIONAL_STRING,
        "userinfo_encrypted_response_enc": SINGLE_OPTIONAL_STRING,
        "request_object_signing_alg": SINGLE_OPTIONAL_STRING,
        "request_object_encryption_alg": SINGLE_OPTIONAL_STRING,
        "request_object_encryption_enc": SINGLE_OPTIONAL_STRING,
        "token_endpoint_auth_method": SINGLE_OPTIONAL_STRING,
        "token_endpoint_auth_signing_alg": SINGLE_OPTIONAL_STRING,
        "default_max_age": SINGLE_OPTIONAL_INT,
        "require_auth_time": OPTIONAL_LOGICAL,
        "default_acr_values": OPTIONAL_LIST_OF_STRINGS,
        "initiate_login_uri": SINGLE_OPTIONAL_STRING,
        "request_uris": OPTIONAL_LIST_OF_STRINGS,
        "post_logout_redirect_uris": OPTIONAL_LIST_OF_STRINGS,
        "frontchannel_logout_uri": SINGLE_OPTIONAL_STRING,
        "frontchannel_logout_session_required": OPTIONAL_LOGICAL,
        "backchannel_logout_uri": SINGLE_OPTIONAL_STRING,
        "backchannel_logout_session_required": OPTIONAL_LOGICAL,
    }
    c_default = {"application_type": "web", "response_types": ["code"]}
    c_allowed_values = {
        "application_type": ["native", "web"],
        "subject_type": ["public", "pairwise"],
    }

    def verify(self, **kwargs):
        super().verify(**kwargs)

        if "initiate_login_uri" in self and not self["initiate_login_uri"].startswith(
            "https:"
        ):
            raise AssertionError()

        for param in [
            "request_object_encryption",
            "id_token_encrypted_response",
            "userinfo_encrypted_response",
        ]:
            alg_param = "%s_alg" % param
            enc_param = "%s_enc" % param
            if alg_param in self:
                if enc_param not in self:
                    self[enc_param] = "A128CBC-HS256"

            # both or none
            if enc_param in self and alg_param not in self:
                raise AssertionError()

        if (
            "token_endpoint_auth_signing_alg" in self
            and self["token_endpoint_auth_signing_alg"] == "none"
        ):
            raise AssertionError()

        return True


class RegistrationResponse(Message):
    """Response to client_register registration requests."""

    c_param = {
        "client_id": SINGLE_REQUIRED_STRING,
        "client_secret": SINGLE_OPTIONAL_STRING,
        "registration_access_token": SINGLE_OPTIONAL_STRING,
        "registration_client_uri": SINGLE_OPTIONAL_STRING,
        "client_id_issued_at": SINGLE_OPTIONAL_INT,
        "client_secret_expires_at": SINGLE_OPTIONAL_INT,
    }
    c_param.update(RegistrationRequest.c_param)

    def verify(self, **kwargs):
        """
        Verify that the response is valid.

        Implementations MUST either return both a Client Configuration Endpoint
        and a Registration Access Token or neither of them.
        :param kwargs:
        :return: True if the message is OK otherwise False
        """
        super(RegistrationResponse, self).verify(**kwargs)

        has_reg_uri = "registration_client_uri" in self
        has_reg_at = "registration_access_token" in self
        if has_reg_uri != has_reg_at:
            raise VerificationError(
                (
                    "Only one of registration_client_uri"
                    " and registration_access_token present"
                ),
                self,
            )

        return True


class ClientRegistrationErrorResponse(message.ErrorResponse):
    c_allowed_values = {
        "error": [
            "invalid_redirect_uri",
            "invalid_client_metadata",
            "invalid_configuration_parameter",
        ]
    }


class IdToken(OpenIDSchema):
    c_param = OpenIDSchema.c_param.copy()
    c_param.update(
        {
            "iss": SINGLE_REQUIRED_STRING,
            "sub": SINGLE_REQUIRED_STRING,
            "aud": REQUIRED_LIST_OF_STRINGS,  # Array of strings or string
            "exp": SINGLE_REQUIRED_INT,
            "iat": SINGLE_REQUIRED_INT,
            "auth_time": SINGLE_OPTIONAL_INT,
            "nonce": SINGLE_OPTIONAL_STRING,
            "at_hash": SINGLE_OPTIONAL_STRING,
            "c_hash": SINGLE_OPTIONAL_STRING,
            "acr": SINGLE_OPTIONAL_STRING,
            "amr": OPTIONAL_LIST_OF_STRINGS,
            "azp": SINGLE_OPTIONAL_STRING,
            "sub_jwk": SINGLE_OPTIONAL_STRING,
        }
    )

    def verify(self, **kwargs):
        super(IdToken, self).verify(**kwargs)

        try:
            if kwargs["iss"] != self["iss"]:
                raise IssuerMismatch("{} != {}".format(kwargs["iss"], self["iss"]))
        except KeyError:
            pass

        if "aud" in self:
            if "client_id" in kwargs:
                # check that I'm among the recipients
                if kwargs["client_id"] not in self["aud"]:
                    raise NotForMe(
                        "{} not in aud:{}".format(kwargs["client_id"], self["aud"]),
                        self,
                    )

            # Then azp has to be present and be one of the aud values
            if len(self["aud"]) > 1:
                if "azp" not in self:
                    raise VerificationError("azp missing", self)
                if self["azp"] not in self["aud"]:
                    raise VerificationError("Mismatch between azp and aud claims", self)

        if "azp" in self:
            if "client_id" in kwargs:
                if kwargs["client_id"] != self["azp"]:
                    raise NotForMe(
                        "{} != azp:{}".format(kwargs["client_id"], self["azp"]), self
                    )

        _now = time_util.utc_time_sans_frac()

        try:
            _skew = kwargs["skew"]
        except KeyError:
            _skew = 0

        try:
            _exp = self["exp"]
        except KeyError:
            raise MissingRequiredAttribute("exp")
        else:
            if (_now - _skew) > _exp:
                raise EXPError("Invalid expiration time")

        try:
            _storage_time = kwargs["nonce_storage_time"]
        except KeyError:
            _storage_time = NONCE_STORAGE_TIME

        try:
            _iat = self["iat"]
        except KeyError:
            raise MissingRequiredAttribute("iat")
        else:
            if (_iat + _storage_time) < (_now - _skew):
                raise IATError("Issued too long ago")
            if _now < (_iat - _skew):
                raise IATError("Issued in the future")

        if _exp < _iat:
            raise EXPError("Invalid expiration time")

        return True


class StateFullMessage(Message):
    c_param = {"state": SINGLE_REQUIRED_STRING}


class RefreshSessionRequest(StateFullMessage):
    c_param = StateFullMessage.c_param.copy()
    c_param.update(
        {"id_token": SINGLE_REQUIRED_STRING, "redirect_url": SINGLE_REQUIRED_STRING}
    )

    def verify(self, **kwargs):
        super(RefreshSessionRequest, self).verify(**kwargs)
        if "id_token" in self:
            self["id_token"] = verify_id_token(self, check_hash=True, **kwargs)


class RefreshSessionResponse(StateFullMessage):
    c_param = StateFullMessage.c_param.copy()
    c_param.update({"id_token": SINGLE_REQUIRED_STRING})

    def verify(self, **kwargs):
        super(RefreshSessionResponse, self).verify(**kwargs)
        if "id_token" in self:
            self["id_token"] = verify_id_token(self, check_hash=True, **kwargs)


class CheckSessionRequest(Message):
    c_param = {"id_token": SINGLE_REQUIRED_STRING}

    def verify(self, **kwargs):
        super(CheckSessionRequest, self).verify(**kwargs)
        if "id_token" in self:
            self["id_token"] = verify_id_token(self, check_hash=True, **kwargs)


class CheckIDRequest(Message):
    c_param = {"access_token": SINGLE_REQUIRED_STRING}


class EndSessionRequest(Message):
    c_param = {
        "id_token_hint": SINGLE_OPTIONAL_STRING,
        "post_logout_redirect_uri": SINGLE_OPTIONAL_STRING,
        "state": SINGLE_OPTIONAL_STRING,
    }


class EndSessionResponse(Message):
    c_param = {"state": SINGLE_OPTIONAL_STRING}


class Claims(Message):
    pass


class ClaimsRequest(Message):
    c_param = {
        "userinfo": OPTIONAL_MULTIPLE_Claims,
        "id_token": OPTIONAL_MULTIPLE_Claims,
    }


class OpenIDRequest(AuthorizationRequest):
    pass


class ProviderConfigurationResponse(Message):
    c_param = {
        "issuer": SINGLE_REQUIRED_STRING,
        "authorization_endpoint": SINGLE_REQUIRED_STRING,
        "token_endpoint": SINGLE_OPTIONAL_STRING,
        "userinfo_endpoint": SINGLE_OPTIONAL_STRING,
        "jwks_uri": SINGLE_REQUIRED_STRING,
        "registration_endpoint": SINGLE_OPTIONAL_STRING,
        "scopes_supported": OPTIONAL_LIST_OF_STRINGS,
        "response_types_supported": REQUIRED_LIST_OF_STRINGS,
        "response_modes_supported": OPTIONAL_LIST_OF_STRINGS,
        "grant_types_supported": OPTIONAL_LIST_OF_STRINGS,
        "acr_values_supported": OPTIONAL_LIST_OF_STRINGS,
        "subject_types_supported": REQUIRED_LIST_OF_STRINGS,
        "id_token_signing_alg_values_supported": REQUIRED_LIST_OF_STRINGS,
        "id_token_encryption_alg_values_supported": OPTIONAL_LIST_OF_STRINGS,
        "id_token_encryption_enc_values_supported": OPTIONAL_LIST_OF_STRINGS,
        "userinfo_signing_alg_values_supported": OPTIONAL_LIST_OF_STRINGS,
        "userinfo_encryption_alg_values_supported": OPTIONAL_LIST_OF_STRINGS,
        "userinfo_encryption_enc_values_supported": OPTIONAL_LIST_OF_STRINGS,
        "request_object_signing_alg_values_supported": OPTIONAL_LIST_OF_STRINGS,
        "request_object_encryption_alg_values_supported": OPTIONAL_LIST_OF_STRINGS,
        "request_object_encryption_enc_values_supported": OPTIONAL_LIST_OF_STRINGS,
        "token_endpoint_auth_methods_supported": OPTIONAL_LIST_OF_STRINGS,
        "token_endpoint_auth_signing_alg_values_supported": OPTIONAL_LIST_OF_STRINGS,
        "display_values_supported": OPTIONAL_LIST_OF_STRINGS,
        "claim_types_supported": OPTIONAL_LIST_OF_STRINGS,
        "claims_supported": OPTIONAL_LIST_OF_STRINGS,
        "service_documentation": SINGLE_OPTIONAL_STRING,
        "claims_locales_supported": OPTIONAL_LIST_OF_STRINGS,
        "ui_locales_supported": OPTIONAL_LIST_OF_STRINGS,
        "claims_parameter_supported": SINGLE_OPTIONAL_BOOLEAN,
        "request_parameter_supported": SINGLE_OPTIONAL_BOOLEAN,
        "request_uri_parameter_supported": SINGLE_OPTIONAL_BOOLEAN,
        "require_request_uri_registration": SINGLE_OPTIONAL_BOOLEAN,
        "op_policy_uri": SINGLE_OPTIONAL_STRING,
        "op_tos_uri": SINGLE_OPTIONAL_STRING,
        "check_session_iframe": SINGLE_OPTIONAL_STRING,
        "end_session_endpoint": SINGLE_OPTIONAL_STRING,
        "frontchannel_logout_supported": SINGLE_OPTIONAL_BOOLEAN,
        "frontchannel_logout_session_supported": SINGLE_OPTIONAL_BOOLEAN,
        "backchannel_logout_supported": SINGLE_OPTIONAL_BOOLEAN,
        "backchannel_logout_session_supported": SINGLE_OPTIONAL_BOOLEAN,
    }
    c_default = {
        "version": "3.0",
        "token_endpoint_auth_methods_supported": ["client_secret_basic"],
        "claims_parameter_supported": False,
        "request_parameter_supported": False,
        "request_uri_parameter_supported": True,
        "require_request_uri_registration": False,
        "grant_types_supported": ["authorization_code", "implicit"],
        "frontchannel_logout_supported": False,
        "frontchannel_logout_session_supported": False,
        "backchannel_logout_supported": False,
        "backchannel_logout_session_supported": False,
    }

    def verify(self, **kwargs):
        super().verify(**kwargs)

        if "scopes_supported" in self:
            if "openid" not in self["scopes_supported"]:
                raise AssertionError()
            for scope in self["scopes_supported"]:
                check_char_set(scope, SCOPE_CHARSET)

        parts = urlparse(self["issuer"])
        if parts.scheme != "https":
            raise SchemeError("Not HTTPS")

        if parts.query or parts.fragment:
            raise AssertionError()

        if (
            any("code" in rt for rt in self["response_types_supported"])
            and "token_endpoint" not in self
        ):
            raise MissingRequiredAttribute("token_endpoint")

        return True


class AuthnToken(Message):
    c_param = {
        "iss": SINGLE_REQUIRED_STRING,
        "sub": SINGLE_REQUIRED_STRING,
        "aud": REQUIRED_LIST_OF_STRINGS,  # Array of strings or string
        "jti": SINGLE_REQUIRED_STRING,
        "exp": SINGLE_REQUIRED_INT,
        "iat": SINGLE_OPTIONAL_INT,
    }


# According to RFC 7519 all claims are optional
class JasonWebToken(Message):
    c_param = {
        "iss": SINGLE_OPTIONAL_STRING,
        "sub": SINGLE_OPTIONAL_STRING,
        "aud": OPTIONAL_LIST_OF_STRINGS,  # Array of strings or string
        "exp": SINGLE_OPTIONAL_INT,
        "nbf": SINGLE_OPTIONAL_INT,
        "iat": SINGLE_OPTIONAL_INT,
        "jti": SINGLE_OPTIONAL_STRING,
    }


def jwt_deser(val, sformat="json"):
    if sformat == "urlencoded":
        sformat = "json"
    if sformat in ["dict", "json"]:
        if not isinstance(val, str):
            val = json.dumps(val)
            sformat = "json"
    return JasonWebToken().deserialize(val, sformat)


SINGLE_OPTIONAL_JWT = ParamDefinition(Message, False, msg_ser, jwt_deser, False)


class UserInfoErrorResponse(message.ErrorResponse):
    c_allowed_values = {
        "error": [
            "invalid_schema",
            "invalid_request",
            "invalid_token",
            "insufficient_scope",
        ]
    }


class DiscoveryRequest(Message):
    c_param = {"principal": SINGLE_REQUIRED_STRING, "service": SINGLE_REQUIRED_STRING}


class DiscoveryResponse(Message):
    c_param = {"locations": REQUIRED_LIST_OF_STRINGS}


class ResourceRequest(Message):
    c_param = {"access_token": SINGLE_OPTIONAL_STRING}


SCOPE2CLAIMS: Dict[str, List[str]] = {
    "openid": ["sub"],
    "profile": [
        "name",
        "given_name",
        "family_name",
        "middle_name",
        "nickname",
        "profile",
        "picture",
        "website",
        "gender",
        "birthdate",
        "zoneinfo",
        "locale",
        "updated_at",
        "preferred_username",
    ],
    "email": ["email", "email_verified"],
    "address": ["address"],
    "phone": ["phone_number", "phone_number_verified"],
    "offline_access": [],
}

# LOGOUT related messages

SINGLE_OPTIONAL_JSON = ParamDefinition(dict, False, json_ser, json_deser, False)
SINGLE_REQUIRED_JSON = ParamDefinition(dict, True, json_ser, json_deser, False)

BACK_CHANNEL_LOGOUT_EVENT = "http://schemas.openid.net/event/backchannel-logout"


class LogoutToken(Message):
    """Defined in https://openid.net/specs/openid-connect-backchannel-1_0.html#LogoutToken ."""

    c_param = {
        "iss": SINGLE_REQUIRED_STRING,
        "sub": SINGLE_OPTIONAL_STRING,
        "aud": REQUIRED_LIST_OF_STRINGS,  # Array of strings or string
        "iat": SINGLE_REQUIRED_INT,
        "jti": SINGLE_REQUIRED_STRING,
        "events": SINGLE_REQUIRED_JSON,
        "sid": SINGLE_OPTIONAL_STRING,
    }

    def verify(self, **kwargs):
        super().verify(**kwargs)

        if "nonce" in self:
            raise MessageException(
                '"nonce" is prohibited from appearing in a LogoutToken.'
            )

        # Check the 'events' JSON
        _keys = list(self["events"].keys())
        if len(_keys) != 1:
            raise ValueError('Must only be one member in "events"')
        if _keys[0] != BACK_CHANNEL_LOGOUT_EVENT:
            raise ValueError('Wrong member in "events"')
        if self["events"][_keys[0]] != {}:
            raise ValueError('Wrong member value in "events"')

        # There must be either a 'sub' or a 'sid', and may contain both
        if not ("sub" in self or "sid" in self):
            raise ValueError('There MUST be either a "sub" or a "sid"')

        try:
            if kwargs["aud"] not in self["aud"]:
                raise NotForMe("Not among intended audience")
        except KeyError:
            pass

        try:
            if kwargs["iss"] != self["iss"]:
                raise NotForMe("Wrong issuer")
        except KeyError:
            pass

        _now = utc_time_sans_frac()

        _skew = kwargs.get("skew", 0)
        _iat = self.get("iat", 0)

        if _iat and _iat > (_now + _skew):
            raise ValueError("Invalid issued_at time")

        return True


ID_TOKEN_VERIFY_ARGS = [
    "keyjar",
    "verify",
    "encalg",
    "encenc",
    "sigalg",
    "issuer",
    "allow_missing_kid",
    "no_kid_issuer",
    "trusting",
    "skew",
    "nonce_storage_time",
    "client_id",
]


class BackChannelLogoutRequest(Message):
    """Defines the message used in https://openid.net/specs/openid-connect-backchannel-1_0.html ."""

    c_param = {"logout_token": SINGLE_REQUIRED_STRING}

    def verify(self, **kwargs):
        super().verify(**kwargs)

        args = {arg: kwargs[arg] for arg in TOKEN_VERIFY_ARGS if arg in kwargs}

        logout_token = LogoutToken().from_jwt(str(self["logout_token"]), **args)
        logout_token.verify(**kwargs)

        self["logout_token"] = logout_token
        logger.info("Verified Logout Token: {}".format(logout_token.to_dict()))

        return True


class FrontChannelLogoutRequest(Message):
    """Defines the message used in https://openid.net/specs/openid-connect-frontchannel-1_0.html ."""

    c_param = {"iss": SINGLE_OPTIONAL_STRING, "sid": SINGLE_OPTIONAL_STRING}


MSG = {
    "RefreshAccessTokenRequest": RefreshAccessTokenRequest,
    "TokenErrorResponse": TokenErrorResponse,
    "AccessTokenResponse": AccessTokenResponse,
    "UserInfoRequest": UserInfoRequest,
    "AuthorizationResponse": AuthorizationResponse,
    "AuthorizationErrorResponse": AuthorizationErrorResponse,
    "AuthorizationRequest": AuthorizationRequest,
    "AccessTokenRequest": AccessTokenRequest,
    "AddressClaim": AddressClaim,
    "OpenIDSchema": OpenIDSchema,
    "RegistrationRequest": RegistrationRequest,
    "RegistrationResponse": RegistrationResponse,
    "ClientRegistrationErrorResponse": ClientRegistrationErrorResponse,
    "IdToken": IdToken,
    "RefreshSessionRequest": RefreshSessionRequest,
    "RefreshSessionResponse": RefreshSessionResponse,
    "CheckSessionRequest": CheckSessionRequest,
    "CheckIDRequest": CheckIDRequest,
    "EndSessionRequest": EndSessionRequest,
    "EndSessionResponse": EndSessionResponse,
    "Claims": Claims,
    "OpenIDRequest": OpenIDRequest,
    "ProviderConfigurationResponse": ProviderConfigurationResponse,
    "AuthnToken": AuthnToken,
    "UserInfoErrorResponse": UserInfoErrorResponse,
    "DiscoveryRequest": DiscoveryRequest,
    "DiscoveryResponse": DiscoveryResponse,
    "ResourceRequest": ResourceRequest,
    # LOGOUT messages
    "LogoutToken": LogoutToken,
    "BackChannelLogoutRequest": BackChannelLogoutRequest,
    "FrontChannelLogoutRequest": FrontChannelLogoutRequest,
}


def factory(msgtype):
    warnings.warn(
        "`factory` is deprecated. Use `OIDCMessageFactory` instead.", DeprecationWarning
    )
    for _, obj in inspect.getmembers(sys.modules[__name__]):
        if inspect.isclass(obj) and issubclass(obj, Message):
            try:
                if obj.__name__ == msgtype:
                    return obj
            except AttributeError:
                pass

    # Fall back to basic OAuth2 messages
    return message.factory(msgtype)


class OIDCMessageFactory(MessageFactory):
    """Factory that knows OIDC message types."""

    authorization_endpoint = MessageTuple(AuthorizationRequest, AuthorizationResponse)
    token_endpoint = MessageTuple(AccessTokenRequest, AccessTokenResponse)
    refresh_endpoint = MessageTuple(RefreshAccessTokenRequest, AccessTokenResponse)
    resource_endpoint = MessageTuple(ResourceRequest, Message)
    configuration_endpoint = MessageTuple(Message, ProviderConfigurationResponse)

    userinfo_endpoint = MessageTuple(UserInfoRequest, Message)
    registration_endpoint = MessageTuple(RegistrationRequest, RegistrationResponse)
    endsession_endpoint = MessageTuple(EndSessionRequest, EndSessionResponse)
    checkid_endpoint = MessageTuple(CheckIDRequest, IdToken)
    checksession_endpoint = MessageTuple(CheckSessionRequest, IdToken)
    refreshsession_endpoint = MessageTuple(
        RefreshSessionRequest, RefreshSessionResponse
    )
    discovery_endpoint = MessageTuple(DiscoveryRequest, DiscoveryResponse)
