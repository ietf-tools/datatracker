"""
Message types in draft-ietf-oauth-token-exchange-03.

:copyright: (c) 2016 by Roland Hedberg.
:license: Apache2, see LICENSE for more details.

"""

import json

from oic.oauth2.message import OPTIONAL_LIST_OF_SP_SEP_STRINGS
from oic.oauth2.message import OPTIONAL_LIST_OF_STRINGS
from oic.oauth2.message import REQUIRED_LIST_OF_STRINGS
from oic.oauth2.message import SINGLE_OPTIONAL_INT
from oic.oauth2.message import SINGLE_OPTIONAL_STRING
from oic.oauth2.message import SINGLE_REQUIRED_STRING
from oic.oauth2.message import Message
from oic.oauth2.message import ParamDefinition
from oic.oic.message import SINGLE_REQUIRED_INT
from oic.oic.message import msg_ser

__author__ = "roland"


class TokenExchangeRequest(Message):
    c_param = {
        "grant_type": SINGLE_REQUIRED_STRING,
        "resource": SINGLE_OPTIONAL_STRING,
        "audience": SINGLE_OPTIONAL_STRING,
        "scope": OPTIONAL_LIST_OF_SP_SEP_STRINGS,
        "requested_token_type": SINGLE_OPTIONAL_STRING,
        "subject_token": SINGLE_REQUIRED_STRING,
        "subject_token_type": SINGLE_REQUIRED_STRING,
        "actor_token": SINGLE_OPTIONAL_STRING,
        "actor_token_type": SINGLE_OPTIONAL_STRING,
        "want_composite": SINGLE_OPTIONAL_STRING,
    }

    def verify(self, **kwargs):
        if "actor_token" in self:
            if not "actor_token_type":
                return False


class TokenExchangeResponse(Message):
    c_param = {
        "access_token": SINGLE_REQUIRED_STRING,
        "issued_token_type": SINGLE_REQUIRED_STRING,
        "token_type": SINGLE_REQUIRED_STRING,
        "expires_in": SINGLE_OPTIONAL_INT,
        "refresh_token": SINGLE_OPTIONAL_STRING,
        "scope": OPTIONAL_LIST_OF_SP_SEP_STRINGS,
    }


def sts_deser(val, sformat="json"):
    if sformat == "urlencoded":
        sformat = "json"
    if sformat in ["dict", "json"]:
        if not isinstance(val, str):
            val = json.dumps(val)
            sformat = "json"
    return STS().deserialize(val, sformat)


SINGLE_OPTIONAL_STS = ParamDefinition(Message, False, msg_ser, sts_deser, False)


class STS(Message):
    c_param = {
        "aud": REQUIRED_LIST_OF_STRINGS,  # Array of strings or string
        "iss": SINGLE_REQUIRED_STRING,
        "exp": SINGLE_REQUIRED_INT,
        "nbf": SINGLE_REQUIRED_INT,
        "sub": SINGLE_REQUIRED_STRING,
        "act": SINGLE_OPTIONAL_STS,
        "scp": OPTIONAL_LIST_OF_STRINGS,
    }
