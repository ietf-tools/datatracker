from functools import cmp_to_key
from typing import Any
from typing import Dict

from oic.utils.http_util import extract_from_request

__author__ = "rolandh"

UNSPECIFIED = "urn:oasis:names:tc:SAML:2.0:ac:classes:unspecified"
INTERNETPROTOCOLPASSWORD = (
    "urn:oasis:names:tc:SAML:2.0:ac:classes:InternetProtocolPassword"
)
MOBILETWOFACTORCONTRACT = (
    "urn:oasis:names:tc:SAML:2.0:ac:classes:MobileTwoFactorContract"
)
PASSWORDPROTECTEDTRANSPORT = (
    "urn:oasis:names:tc:SAML:2.0:ac:classes:PasswordProtectedTransport"
)
PASSWORD = "urn:oasis:names:tc:SAML:2.0:ac:classes:Password"  # nosec
TLSCLIENT = "urn:oasis:names:tc:SAML:2.0:ac:classes:TLSClient"
TIMESYNCTOKEN = "urn:oasis:names:tc:SAML:2.0:ac:classes:TimeSyncToken"

CMP_TYPE = ["exact", "minimum", "maximum", "better"]


class AuthnBroker(object):
    def __init__(self):
        self.db: Dict[str, Any] = {"info": {}, "key": {}}
        self.next = 0

    @staticmethod
    def exact(a, b):
        return a == b

    @staticmethod
    def minimum(a, b):
        return b >= a

    @staticmethod
    def maximum(a, b):
        return b <= a

    @staticmethod
    def better(a, b):
        return b > a

    def add(self, acr, method, level=0, authn_authority=""):
        """
        Add a new authentication method.

        Assumes not more than one authentication method per type.

        :param acr: Add to what the authentication endpoint offers for this acr
        :param method: A identifier of the authentication method.
        :param level: security level, positive integers, 0 is lowest
        :return:
        """
        _info = {
            "ref": acr,
            "method": method,
            "level": level,
            "authn_auth": authn_authority,
        }

        self.next += 1
        _ref = str(self.next)
        self.db["info"][_ref] = _info
        try:
            self.db["key"][acr].append(_ref)
        except KeyError:
            self.db["key"][acr] = [_ref]

    def remove(self, acr, method=None, level=0, authn_authority=""):
        try:
            _refs = self.db["key"][acr]
        except KeyError:
            return
        else:
            _remain = []
            for _ref in _refs:
                item = self.db["info"][_ref]
                if method and method != item["method"]:
                    _remain.append(_ref)
                if level and level != item["level"]:
                    _remain.append(_ref)
                if authn_authority and authn_authority != item["authn_authority"]:
                    _remain.append(_ref)
            if _remain:
                self.db[acr] = _remain

    @staticmethod
    def _cmp(item0, item1):
        v0 = item0[0]
        v1 = item1[0]
        if v0 > v1:
            return 1
        elif v0 == v1:
            return 0
        else:
            return -1

    def _pick_by_class_ref(self, acr, comparision_type="exact"):
        func = getattr(self, comparision_type)
        try:
            _refs = self.db["key"][acr]
        except KeyError:
            return []
        else:
            _info = self.db["info"]
            _item = _info[_refs[0]]
            _level = _item["level"]
            if comparision_type != "better":
                if _item["method"]:
                    res = [(_level, _item["method"], _item["ref"])]
                else:
                    res = []
            else:
                res = []

            for ref in _refs[1:]:
                item = _info[ref]
                res.append((item["level"], item["method"], item["ref"]))
                if func(_level, item["level"]):
                    _level = item["level"]
            res_other = []
            if comparision_type != "exact":
                for ref, _dic in _info.items():
                    if ref in _refs:
                        continue
                    elif func(_level, _dic["level"]):
                        if _dic["method"]:
                            _val = (_dic["level"], _dic["method"], _dic["ref"])
                            if _val not in res:
                                res_other.append(_val)
            res.extend(res_other)
            # sort on level
            res.sort(key=cmp_to_key(self._cmp), reverse=True)

            return [(b, c) for a, b, c in res]

    def get_method(self, name):
        for key, item in self.db["info"].items():
            if item["method"].__class__.__name__ == name:
                return item["method"]
        raise KeyError("No method by that name")

    def pick(self, acr=None, comparision_type="minimum"):
        """
        Given the authentication context find zero or more places where the user could be sent next.

        Ordered according to security level.

        :param acr: The authentication class reference requested
        :param comparision_type: If the caller wants exact, at a minimum, ... this level
        :return: An URL
        """
        if not comparision_type:
            comparision_type = "minimum"

        if acr is None:
            # Anything else doesn't make sense
            return self._pick_by_class_ref(UNSPECIFIED, "minimum")
        else:
            return self._pick_by_class_ref(acr, comparision_type)

    @staticmethod
    def match(requested, provided):
        if requested == provided:
            return True
        else:
            return False

    def __getitem__(self, item):
        i = 0
        for key, info in self.db["info"].items():
            if i == item:
                return info["method"], info["ref"]
            i += 1

        raise IndexError()

    def getAcrValuesString(self):
        acr_values = None
        for item in self.db["info"].values():
            if acr_values is None:
                acr_values = item["ref"]
            else:
                acr_values += " " + item["ref"]
        return acr_values

    def __iter__(self):
        for item in self.db["info"].values():
            yield item["method"]
        return

    def __len__(self):
        return len(self.db["info"].keys())


def make_auth_verify(callback, next_module_instance=None):
    """
    Closure encapsulating the next module (if any exist) in a multi auth chain.

    :param callback: function to execute for the callback URL at the OP, see UserAuthnMethod.verify and its subclasses
    (e.g. SAMLAuthnMethod) for signature
    :param next_module_instance: an object instance of the module next in the chain after the module whose verify method
    is the callback -- do not use this parameter!! If you want a multi auth chain see the convenience function
    setup_multi_auth (in multi_auth.py)
    :return: function encapsulating the specified callback which properly handles a multi auth chain.
    """

    def auth_verify(environ, start_response, logger=None):
        kwargs = extract_from_request(environ)

        response, auth_is_complete = callback(**kwargs)

        if auth_is_complete and next_module_instance:
            response = next_module_instance(**kwargs)

        return response(environ, start_response)

    return auth_verify
