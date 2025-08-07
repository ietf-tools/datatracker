import copy
import json
import logging
import warnings
from collections import namedtuple
from collections.abc import MutableMapping
from json import JSONDecodeError
from typing import Any
from typing import Dict
from typing import List
from typing import Mapping
from typing import Optional
from typing import Tuple
from typing import Union
from urllib.parse import parse_qs
from urllib.parse import urlencode

from jwkest import as_unicode
from jwkest import b64d
from jwkest import jwe
from jwkest import jws
from jwkest.jwe import JWE
from jwkest.jwk import keyitems2keyreps
from jwkest.jws import JWS
from jwkest.jws import NoSuitableSigningKeys
from jwkest.jws import alg2keytype
from jwkest.jwt import JWT

from oic.exception import MessageException
from oic.exception import PyoidcError
from oic.oauth2.exception import VerificationError
from oic.utils.keyio import key_summary
from oic.utils.keyio import update_keyjar
from oic.utils.sanitize import sanitize

logger = logging.getLogger(__name__)

ParamDefinition = namedtuple(
    "ParamDefinition",
    ["type", "required", "serializer", "deserializer", "null_allowed"],
)


class FormatError(PyoidcError):
    pass


class MissingRequiredAttribute(MessageException):
    def __init__(self, attr, message=""):
        Exception.__init__(self, attr)
        self.message = message

    def __str__(self):
        return "Missing required attribute '%s'" % self.args[0]


class MissingRequiredValue(MessageException):
    pass


class MissingSigningKey(PyoidcError):
    pass


class TooManyValues(MessageException):
    pass


class DecodeError(MessageException):
    pass


class GrantExpired(PyoidcError):
    pass


class OldAccessToken(PyoidcError):
    pass


class SchemeError(MessageException):
    pass


class ParameterError(MessageException):
    pass


class NotAllowedValue(MessageException):
    pass


class WrongSigningAlgorithm(MessageException):
    pass


class WrongEncryptionAlgorithm(MessageException):
    pass


ERRTXT = "On '%s': %s"


def gather_keys(comb, collection, jso, target):
    try:
        _id = jso[target]
    except KeyError:
        return comb

    try:
        _col = collection[_id]
    except KeyError:
        if _id.endswith("/"):
            _id = _id[:-1]
            try:
                _col = collection[_id]
            except KeyError:
                return comb
        else:
            return comb

    try:
        for typ, keys in _col.items():
            try:
                comb[typ].update(keys)
            except KeyError:
                comb[typ] = keys
    except KeyError:
        pass

    return comb


def swap_dict(dic):
    return dict([(val, key) for key, val in dic.items()])


def jwt_header(txt):
    return json.loads(b64d(str(txt.split(".")[0])))


class Message(MutableMapping):
    c_param: Mapping[str, ParamDefinition] = {}
    c_default: Dict[str, Any] = {}
    c_allowed_values = {}  # type: ignore

    def __init__(self, **kwargs):
        self._dict = self.c_default.copy()
        self.lax = False
        self.jwt = None
        self.jws_header = None
        self.jwe_header = None
        self.from_dict(kwargs)
        self.verify_ssl = True

    def __iter__(self):
        return iter(self._dict)

    def type(self):
        return self.__class__.__name__

    def parameters(self):
        return self.c_param.keys()

    def set_defaults(self):
        for key, val in self.c_default.items():
            self._dict[key] = val

    @staticmethod
    def _extract_cparam(key, _spec):
        """
        Extract ParamDefinition for a given key.

        The key can be direct attribute or lang typed attribute.
        If ParamDefinition is not found, tries to return "*" attribute, if it exists, otherwise returns None.
        """
        for _key in (key, key.split("#")[0], "*"):
            if _key in _spec:
                return _spec[_key]
        return None

    def to_urlencoded(self, lev=0):
        """
        Create a string using the application/x-www-form-urlencoded format.

        :return: A string of the application/x-www-form-urlencoded format
        """
        _spec = self.c_param
        if not self.lax:
            for attribute, cparam in _spec.items():
                if cparam.required and attribute not in self._dict:
                    raise MissingRequiredAttribute("%s" % attribute, "%s" % self)

        params: List[Tuple[str, Optional[Union[str, bytes, Message]]]] = []

        for key, val in self._dict.items():
            cparam = self._extract_cparam(key, _spec)
            if cparam is not None:
                _ser = cparam.serializer
                null_allowed = cparam.null_allowed
            else:
                _ser = None
                null_allowed = False

            if val is None and null_allowed is False:
                continue
            elif isinstance(val, str):
                # Should I allow parameters with "" as value ???
                params.append((key, val.encode("utf-8")))
            elif isinstance(val, list):
                if _ser:
                    params.append((key, str(_ser(val, sformat="urlencoded", lev=lev))))
                else:
                    for item in val:
                        params.append((key, str(item).encode("utf-8")))
            elif isinstance(val, Message):
                try:
                    _val = json.dumps(_ser(val, sformat="dict", lev=lev + 1))
                    params.append((key, _val))
                except TypeError:
                    params.append((key, val))
            elif val is None:
                params.append((key, val))
            else:
                try:
                    params.append((key, _ser(val, lev=lev)))
                except Exception:
                    params.append((key, str(val)))

        try:
            return urlencode(params)
        except UnicodeEncodeError:
            _val2: List[Tuple[str, Optional[Union[str, bytes, Message]]]] = []
            for k, v in params:
                if isinstance(v, str):
                    _val2.append((k, v.encode("utf-8")))
                else:
                    _val2.append((k, v))
            return urlencode(_val2)

    def serialize(self, method="urlencoded", lev=0, **kwargs):
        return getattr(self, "to_%s" % method)(lev=lev, **kwargs)

    def deserialize(self, info, method="urlencoded", **kwargs):
        try:
            func = getattr(self, "from_%s" % method)
        except AttributeError:
            raise FormatError("Unknown serialization method (%s)" % method)
        else:
            return func(info, **kwargs)

    def from_urlencoded(self, urlencoded, **kwargs):
        """
        Create a class instance from a string of the application/x-www-form-urlencoded format.

        :param urlencoded: The string
        :return: An instance of the cls class
        """
        # parse_qs returns a dictionary with keys and values. The values are
        # always lists even if there is only one value in the list.
        # keys only appears once.

        if isinstance(urlencoded, str):
            pass
        elif isinstance(urlencoded, list):
            urlencoded = urlencoded[0]

        _spec = self.c_param

        for key, val in parse_qs(urlencoded).items():
            cparam = self._extract_cparam(key, _spec)
            if cparam is None:
                if len(val) == 1:
                    val = val[0]  # type: ignore

                self._dict[key] = val
                continue

            if isinstance(cparam.type, list):
                if cparam.deserializer is not None:
                    self._dict[key] = cparam.deserializer(val[0], "urlencoded")
                else:
                    self._dict[key] = val
            else:  # must be single value
                if len(val) == 1:
                    if cparam.deserializer is not None:
                        self._dict[key] = cparam.deserializer(val[0], "urlencoded")
                    elif isinstance(val[0], cparam.type):
                        self._dict[key] = val[0]
                    else:
                        try:
                            self._dict[key] = cparam.type(val[0])
                        except KeyError:
                            raise ParameterError(key)
                else:
                    raise TooManyValues("{}".format(key))

        return self

    def to_dict(self, lev=0):
        """
        Return a dictionary representation of the class.

        :return: A dict
        """
        _spec = self.c_param

        _res = {}
        lev += 1
        for key, val in self._dict.items():
            cparam = self._extract_cparam(key, _spec)
            if cparam is not None:
                _ser = cparam.serializer
            else:
                _ser = None
            if _ser:
                val = _ser(val, "dict", lev)

            if isinstance(val, Message):
                _res[key] = val.to_dict(lev + 1)
            elif isinstance(val, list) and isinstance(
                next(iter(val or []), None), Message
            ):
                _res[key] = [v.to_dict(lev) for v in val]
            else:
                _res[key] = val

        return _res

    def from_dict(self, dictionary, **kwargs):
        """
        Direct translation so the value for one key might be a list or a single value.

        :param dictionary: The info
        :return: A class instance or raise an exception on error
        """
        _spec = self.c_param

        for key, val in dictionary.items():
            if val in ("", [""]):
                continue
            cparam = self._extract_cparam(key, _spec)
            if cparam is not None:
                self._add_value(
                    key, cparam.type, key, val, cparam.deserializer, cparam.null_allowed
                )
            else:
                self._dict[key] = val
        return self

    def _add_value(self, skey, vtyp, key, val, _deser, null_allowed):
        if isinstance(val, list):
            if (len(val) == 0 or val[0] is None) and null_allowed is False:
                return

        if isinstance(vtyp, list):
            self._add_value_list(skey, vtyp[0], key, val, _deser, null_allowed)
        else:
            if val is None:
                self._dict[skey] = None
            elif isinstance(val, bool):
                if vtyp is bool:
                    self._dict[skey] = val
                else:
                    raise ParameterError(
                        '"{}", wrong type of value for "{}"'.format(val, skey)
                    )
            elif isinstance(val, vtyp):  # Not necessary to do anything
                self._dict[skey] = val
            else:
                if _deser:
                    try:
                        val = _deser(val, sformat="dict")
                    except Exception as exc:
                        raise DecodeError(ERRTXT % (key, exc))
                elif vtyp is int:
                    try:
                        self._dict[skey] = int(val)
                    except (ValueError, TypeError):
                        raise ParameterError(
                            '"{}", wrong type of value for "{}"'.format(val, skey)
                        )
                    else:
                        return
                elif vtyp is bool:
                    raise ParameterError(
                        '"{}", wrong type of value for "{}"'.format(val, skey)
                    )

                if isinstance(val, str):
                    self._dict[skey] = val
                elif isinstance(val, list):
                    if len(val) == 1:
                        self._dict[skey] = val[0]
                    elif not len(val):
                        pass
                    else:
                        raise TooManyValues(key)
                else:
                    self._dict[skey] = val

    def _add_value_list(self, skey, vtype, key, val, _deser, null_allowed):
        """
        Add value with internal type (``vtype``) of ``list`` to the message object.

        :param skey: String representation of key
        :param vtype: Type of object in list
        :param key: Key for the object
        :param val: Value of the object
        :param _deser: Deserialization method
        :param null_allowed: If null value is allowed
        """
        if isinstance(val, vtype):
            if issubclass(vtype, Message):
                self._dict[skey] = [val]
            elif _deser is not None:
                try:
                    self._dict[skey] = _deser(val, sformat="urlencoded")
                except Exception as exc:
                    raise DecodeError(ERRTXT % (key, exc))
            else:
                setattr(self, skey, [val])
            return
        if isinstance(val, list):
            if _deser is not None:
                try:
                    val = _deser(val, sformat="dict")
                except Exception as exc:
                    raise DecodeError(ERRTXT % (key, exc))

            if issubclass(vtype, Message):
                try:
                    _val = []
                    for v in val:
                        _val.append(vtype(**dict([(str(x), y) for x, y in v.items()])))
                    val = _val
                except Exception as exc:
                    raise DecodeError(ERRTXT % (key, exc))
            else:
                for v in val:
                    if not isinstance(v, vtype):
                        raise DecodeError(
                            ERRTXT % (key, "type != %s (%s)" % (vtype, type(v)))
                        )
            self._dict[skey] = val
            return
        if isinstance(val, dict):
            try:
                val = _deser(val, sformat="dict")
            except Exception as exc:
                raise DecodeError(ERRTXT % (key, exc))
            else:
                self._dict[skey] = val
                return

        raise DecodeError(ERRTXT % (key, "type != %s" % vtype))

    def to_json(self, lev=0, indent=None):
        if lev:
            return self.to_dict(lev + 1)
        else:
            return json.dumps(self.to_dict(1), indent=indent)

    def from_json(self, txt: str, **kwargs) -> "Message":
        """Create the Message from json encoded string."""
        try:
            unpacked = json.loads(txt)
        except JSONDecodeError:
            raise DecodeError("Cannot unpack, not a valid JSON.")
        if not isinstance(unpacked, dict):
            raise DecodeError("Cannot unpack, not a valid message.")
        return self.from_dict(unpacked)

    def to_jwt(self, key=None, algorithm="", lev=0):
        """
        Create a signed JWT representation of the class instance.

        :param key: The signing key
        :param algorithm: The signature algorithm to use
        :return: A signed JWT
        """
        _jws = JWS(self.to_json(lev), alg=algorithm)
        return _jws.sign_compact(key)

    def _add_key(self, keyjar, issuer, key, key_type="", kid="", no_kid_issuer=None):
        if issuer not in keyjar:
            logger.error('Issuer "{}" not in keyjar'.format(issuer))
            return

        logger.debug(
            "Key set summary for {}: {}".format(issuer, key_summary(keyjar, issuer))
        )

        if kid:
            _key = keyjar.get_key_by_kid(kid, issuer)
            if _key and _key not in key:
                key.append(_key)
                return
        else:
            try:
                kl = keyjar.get_verify_key(owner=issuer, key_type=key_type)
            except KeyError:
                pass
            else:
                if len(kl) == 1:
                    if kl[0] not in key:
                        key.append(kl[0])
                elif no_kid_issuer:
                    try:
                        allowed_kids = no_kid_issuer[issuer]
                    except KeyError:
                        return
                    else:
                        if allowed_kids:
                            key.extend([k for k in kl if k.kid in allowed_kids])
                        else:
                            key.extend(kl)

    def get_verify_keys(self, keyjar, key, jso, header, jwt, **kwargs):
        """
        Get keys from a keyjar that can be used to verify a signed JWT.

        :param keyjar: A KeyJar instance
        :param key: List of keys to start with
        :param jso: The payload of the JWT, expected to be a dictionary.
        :param header: The header of the JWT
        :param jwt: A jwkest.jwt.JWT instance
        :param kwargs: Other key word arguments
        :return: list of usable keys
        """
        try:
            _kid = header["kid"]
        except KeyError:
            _kid = ""

        try:
            _iss = jso["iss"]
        except KeyError:
            pass
        else:
            # First extend the keyjar if allowed
            if "jku" in header:
                if not keyjar.find(header["jku"], _iss):
                    # This is really questionable
                    try:
                        if kwargs["trusting"]:
                            keyjar.add(jso["iss"], header["jku"])
                    except KeyError:
                        pass

            # If there is a kid and a key is found with that kid at the issuer
            # then I'm done
            if _kid:
                jwt["kid"] = _kid
                try:
                    _key = keyjar.get_key_by_kid(_kid, _iss)
                    if _key:
                        key.append(_key)
                        return key
                except KeyError:
                    pass

        try:
            nki = kwargs["no_kid_issuer"]
        except KeyError:
            nki = {}

        try:
            _key_type = alg2keytype(header["alg"])
        except KeyError:
            _key_type = ""

        try:
            self._add_key(keyjar, kwargs["opponent_id"], key, _key_type, _kid, nki)
        except KeyError:
            pass

        for ent in ["iss", "aud", "client_id"]:
            if ent not in jso:
                continue
            if ent == "aud":
                # list or basestring
                if isinstance(jso["aud"], str):
                    _aud = [jso["aud"]]
                else:
                    _aud = jso["aud"]
                for _e in _aud:
                    self._add_key(keyjar, _e, key, _key_type, _kid, nki)
            else:
                self._add_key(keyjar, jso[ent], key, _key_type, _kid, nki)
        return key

    def from_jwt(self, txt, key=None, verify=True, keyjar=None, **kwargs):
        """
        Given a signed and/or encrypted JWT, verify its correctness and then create a class instance from the content.

        :param txt: The JWT
        :param key: keys that might be used to decrypt and/or verify the
            signature of the JWT
        :param verify: Whether the signature should be verified or not
        :param keyjar: A KeyJar that might contain the necessary key.
        :param kwargs: Extra key word arguments
        :return: A class instance
        """
        _jw = jwe.factory(txt)
        if _jw:
            logger.debug("JWE headers: {}".format(_jw.jwt.headers))

            if "algs" in kwargs and "encalg" in kwargs["algs"]:
                if kwargs["algs"]["encalg"] != _jw["alg"]:
                    raise WrongEncryptionAlgorithm(
                        "%s != %s" % (_jw["alg"], kwargs["algs"]["encalg"])
                    )
                if kwargs["algs"]["encenc"] != _jw["enc"]:
                    raise WrongEncryptionAlgorithm(
                        "%s != %s" % (_jw["enc"], kwargs["algs"]["encenc"])
                    )
            if keyjar:
                dkeys = keyjar.get_decrypt_key(owner="")
                if "sender" in kwargs:
                    dkeys.extend(keyjar.get_verify_key(owner=kwargs["sender"]))
            elif key:
                dkeys = key
            else:
                dkeys = []

            logger.debug("Decrypt class: {}".format(_jw.__class__))
            _res = _jw.decrypt(txt, dkeys)
            logger.debug("decrypted message:{}".format(_res))
            if isinstance(_res, tuple):
                txt = as_unicode(_res[0])
            elif isinstance(_res, list) and len(_res) == 2:
                txt = as_unicode(_res[0])
            else:
                txt = as_unicode(_res)
            self.jwe_header = _jw.jwt.headers

        _jw = jws.factory(txt)
        if _jw:
            if "algs" in kwargs and "sign" in kwargs["algs"]:
                _alg = _jw.jwt.headers["alg"]
                if kwargs["algs"]["sign"] != _alg:
                    raise WrongSigningAlgorithm(
                        "%s != %s" % (_alg, kwargs["algs"]["sign"])
                    )
            try:
                _jwt = JWT().unpack(txt)
                jso = _jwt.payload()
                _header = _jwt.headers

                if key is None and keyjar is not None:
                    key = keyjar.get_verify_key(owner="")
                elif key is None:
                    key = []

                if keyjar is not None and "sender" in kwargs:
                    key.extend(keyjar.get_verify_key(owner=kwargs["sender"]))

                logger.debug("Raw JSON: {}".format(sanitize(jso)))
                logger.debug("JWS header: {}".format(sanitize(_header)))
                if _header["alg"] == "none":
                    pass
                elif verify:
                    if keyjar:
                        key = self.get_verify_keys(
                            keyjar, key, jso, _header, _jw, **kwargs
                        )

                    if "alg" in _header and _header["alg"] != "none":
                        if not key:
                            raise MissingSigningKey("alg=%s" % _header["alg"])

                    logger.debug("Found signing key.")
                    try:
                        _jw.verify_compact(txt, key)
                    except NoSuitableSigningKeys:
                        if keyjar:
                            update_keyjar(keyjar)
                            key = self.get_verify_keys(
                                keyjar, key, jso, _header, _jw, **kwargs
                            )
                            _jw.verify_compact(txt, key)
            except Exception:
                raise
            else:
                self.jws_header = _jwt.headers
        else:
            jso = json.loads(txt)

        self.jwt = txt
        return self.from_dict(jso)

    def __str__(self):
        return "{}".format(self.to_dict())

    def _type_check(self, typ, _allowed, val, na=False):
        if typ is str:
            if val not in _allowed:
                raise NotAllowedValue(val)
        elif typ is int:
            if val not in _allowed:
                raise NotAllowedValue(val)
        elif isinstance(typ, list):
            if isinstance(val, list):
                for item in val:
                    if item not in _allowed:
                        raise NotAllowedValue(val)
        elif val is None and na is False:
            raise NotAllowedValue(val)

    def verify(self, **kwargs):
        """Make sure all the required values are there and that the values are of the correct type."""
        _spec = self.c_param
        try:
            _allowed = self.c_allowed_values
        except KeyError:
            _allowed = {}

        for attribute, cparam in _spec.items():
            if attribute == "*":
                continue

            val = self._dict.get(attribute)
            if val is None:
                if cparam.required:
                    raise MissingRequiredAttribute("%s" % attribute)
                continue
            if cparam.type != bool and not val:
                if cparam.required:
                    raise MissingRequiredAttribute("%s" % attribute)
                continue

            if attribute not in _allowed:
                continue

            if isinstance(cparam.type, tuple):
                for _typ in cparam.type:
                    try:
                        self._type_check(_typ, _allowed[attribute], val)
                        break
                    except ValueError:
                        pass
                    else:
                        raise NotAllowedValue(val)
            else:
                self._type_check(
                    cparam.type, _allowed[attribute], val, cparam.null_allowed
                )

        return True

    def keys(self):
        """
        Return a list of attribute/keys/parameters of this class that has values.

        :return: A list of attribute names
        """
        return self._dict.keys()

    def __getitem__(self, item):
        return self._dict[item]

    def get(self, item, default=None):
        try:
            return self[item]
        except KeyError:
            return default

    def items(self):
        return self._dict.items()

    def values(self):
        return self._dict.values()

    def __contains__(self, item):
        return item in self._dict

    def request(self, location, fragment_enc=False):
        _l = as_unicode(location)
        _qp = as_unicode(self.to_urlencoded())
        if fragment_enc:
            return "%s#%s" % (_l, _qp)
        else:
            if "?" in location:
                return "%s&%s" % (_l, _qp)
            else:
                return "%s?%s" % (_l, _qp)

    def __setitem__(self, key, value):
        try:
            cparam = self.c_param[key]
            self._add_value(
                str(key),
                cparam.type,
                key,
                value,
                cparam.deserializer,
                cparam.null_allowed,
            )
        except KeyError:
            self._dict[key] = value

    def __eq__(self, other):
        if not isinstance(other, Message):
            return False
        if self.type() != other.type():
            return False

        if self._dict != other._dict:
            return False

        return True

    def __delitem__(self, key):
        del self._dict[key]

    def __len__(self):
        return len(self._dict)

    def extra(self):
        return dict(
            [(key, val) for key, val in self._dict.items() if key not in self.c_param]
        )

    def only_extras(self):
        extras = [key for key in self._dict.keys() if key in self.c_param]
        if not extras:
            return True
        else:
            return False

    def update(self, item):
        if isinstance(item, dict):
            self._dict.update(item)
        elif isinstance(item, Message):
            for key, val in item.items():
                self._dict[key] = val
        else:
            raise ValueError("Can't update message using: '%s'" % (item,))

    def to_jwe(self, keys, enc, alg, lev=0):
        """
        Place the information in this instance in a JSON object.

        Make that JSON object the body of a JWT. Then encrypt that JWT using the specified algorithms
        and the given keys. Return the encrypted JWT.

        :param keys: Dictionary, keys are key type and key is the value or
        simple list.
        :param enc: Content Encryption Algorithm
        :param alg: Key Management Algorithm
        :param lev: Used for JSON construction
        :return: An encrypted JWT. If encryption failed an exception will be raised.
        """
        if isinstance(keys, dict):
            keys = keyitems2keyreps(keys)

        _jwe = JWE(self.to_json(lev), alg=alg, enc=enc)
        return _jwe.encrypt(keys)

    def from_jwe(self, msg, keys):
        """
        Decrypt an encrypted JWT and load the JSON object that was the body of the JWT into this object.

        :param msg: An encrypted JWT
        :param keys: Dictionary, keys are key type and key is the value or simple list.
        :return: The decrypted message. If decryption failed an exception will be raised.
        """
        if isinstance(keys, dict):
            keys = keyitems2keyreps(keys)

        jwe = JWE()
        _res = jwe.decrypt(msg, keys)
        return self.from_json(_res.decode())

    def copy(self):
        return copy.deepcopy(self)

    def weed(self):
        """Get rid of key value pairs that are not standard."""
        _ext = [k for k in self._dict.keys() if k not in self.c_param]
        for k in _ext:
            del self._dict[k]

    def rm_blanks(self):
        """Get rid of parameters that has no value."""
        _blanks = [k for k in self._dict.keys() if not self._dict[k]]
        for key in _blanks:
            del self._dict[key]


# =============================================================================


def by_schema(cls, **kwa):
    return dict([(key, val) for key, val in kwa.items() if key in cls.c_param])


def add_non_standard(msg1, msg2):
    for key, val in msg2.extra().items():
        if key not in msg1.c_param:
            msg1[key] = val


# =============================================================================


def list_serializer(vals, sformat="urlencoded", lev=0):
    if isinstance(vals, str) or not isinstance(vals, list):
        raise ValueError("Expected list: %s" % vals)
    if sformat == "urlencoded":
        return " ".join(vals)
    else:
        return vals


def list_deserializer(val, sformat="urlencoded"):
    if sformat == "urlencoded":
        if isinstance(val, str):
            return val.split(" ")
        elif isinstance(val, list) and len(val) == 1:
            return val[0].split(" ")
    else:
        return val


def sp_sep_list_serializer(vals, sformat="urlencoded", lev=0):
    if isinstance(vals, str):
        return vals
    else:
        return " ".join(vals)


def sp_sep_list_deserializer(val, sformat="urlencoded"):
    if isinstance(val, str):
        return val.split(" ")
    elif isinstance(val, list) and len(val) == 1:
        return val[0].split(" ")
    else:
        return val


def json_serializer(obj, sformat="urlencoded", lev=0):
    return json.dumps(obj)


def json_deserializer(txt, sformat="urlencoded"):
    return json.loads(txt)


VTYPE = 0
VREQUIRED = 1
VSER = 2
VDESER = 3
VNULLALLOWED = 4

SINGLE_REQUIRED_STRING = ParamDefinition(str, True, None, None, False)
SINGLE_OPTIONAL_STRING = ParamDefinition(str, False, None, None, False)
SINGLE_OPTIONAL_INT = ParamDefinition(int, False, None, None, False)
OPTIONAL_LIST_OF_STRINGS = ParamDefinition(
    [str], False, list_serializer, list_deserializer, False
)
REQUIRED_LIST_OF_STRINGS = ParamDefinition(
    [str], True, list_serializer, list_deserializer, False
)
OPTIONAL_LIST_OF_SP_SEP_STRINGS = ParamDefinition(
    [str], False, sp_sep_list_serializer, sp_sep_list_deserializer, False
)
REQUIRED_LIST_OF_SP_SEP_STRINGS = ParamDefinition(
    [str], True, sp_sep_list_serializer, sp_sep_list_deserializer, False
)
SINGLE_OPTIONAL_JSON = ParamDefinition(
    str, False, json_serializer, json_deserializer, False
)

REQUIRED = [
    SINGLE_REQUIRED_STRING,
    REQUIRED_LIST_OF_STRINGS,
    REQUIRED_LIST_OF_SP_SEP_STRINGS,
]


#
# =============================================================================
#


class ErrorResponse(Message):
    c_param = {
        "error": SINGLE_REQUIRED_STRING,
        "error_description": SINGLE_OPTIONAL_STRING,
        "error_uri": SINGLE_OPTIONAL_STRING,
    }


class AuthorizationErrorResponse(ErrorResponse):
    c_param = ErrorResponse.c_param.copy()
    c_param.update({"state": SINGLE_OPTIONAL_STRING})
    c_allowed_values = ErrorResponse.c_allowed_values.copy()
    c_allowed_values.update(
        {
            "error": [
                "invalid_request",
                "unauthorized_client",
                "access_denied",
                "unsupported_response_type",
                "invalid_scope",
                "server_error",
                "temporarily_unavailable",
            ]
        }
    )


class TokenErrorResponse(ErrorResponse):
    c_allowed_values = {
        "error": [
            "invalid_request",
            "invalid_client",
            "invalid_grant",
            "unauthorized_client",
            "unsupported_grant_type",
            "invalid_scope",
        ]
    }


class AccessTokenRequest(Message):
    c_param = {
        "grant_type": SINGLE_REQUIRED_STRING,
        "code": SINGLE_REQUIRED_STRING,
        "redirect_uri": SINGLE_REQUIRED_STRING,
        "client_id": SINGLE_OPTIONAL_STRING,
        "client_secret": SINGLE_OPTIONAL_STRING,
        "state": SINGLE_OPTIONAL_STRING,
    }
    c_default = {"grant_type": "authorization_code"}


class AuthorizationRequest(Message):
    c_param = {
        "response_type": REQUIRED_LIST_OF_SP_SEP_STRINGS,
        "client_id": SINGLE_REQUIRED_STRING,
        "scope": OPTIONAL_LIST_OF_SP_SEP_STRINGS,
        "redirect_uri": SINGLE_OPTIONAL_STRING,
        "state": SINGLE_OPTIONAL_STRING,
    }


class AuthorizationResponse(Message):
    c_param = {
        "code": SINGLE_REQUIRED_STRING,
        "state": SINGLE_OPTIONAL_STRING,
        "iss": SINGLE_OPTIONAL_STRING,
        "client_id": SINGLE_OPTIONAL_STRING,
    }

    def verify(self, **kwargs):
        super(AuthorizationResponse, self).verify(**kwargs)

        if "client_id" in self:
            try:
                if self["client_id"] != kwargs["client_id"]:
                    raise VerificationError("client_id mismatch")
            except KeyError:
                logger.info("No client_id to verify against")
                pass
        if "iss" in self:
            try:
                # Issuer URL for the authorization server issuing the response.
                if self["iss"] != kwargs["iss"]:
                    raise VerificationError("Issuer mismatch")
            except KeyError:
                logger.info("No issuer set in the Client config")
                pass

        return True


class AccessTokenResponse(Message):
    c_param = {
        "access_token": SINGLE_REQUIRED_STRING,
        "token_type": SINGLE_REQUIRED_STRING,
        "expires_in": SINGLE_OPTIONAL_INT,
        "refresh_token": SINGLE_OPTIONAL_STRING,
        "scope": OPTIONAL_LIST_OF_SP_SEP_STRINGS,
        "state": SINGLE_OPTIONAL_STRING,
    }


class NoneResponse(Message):
    c_param = {"state": SINGLE_OPTIONAL_STRING}


class ROPCAccessTokenRequest(Message):
    c_param = {
        "grant_type": SINGLE_REQUIRED_STRING,
        "username": SINGLE_OPTIONAL_STRING,
        "password": SINGLE_OPTIONAL_STRING,
        "scope": OPTIONAL_LIST_OF_SP_SEP_STRINGS,
    }


class CCAccessTokenRequest(Message):
    c_param = {
        "grant_type": SINGLE_REQUIRED_STRING,
        "scope": OPTIONAL_LIST_OF_SP_SEP_STRINGS,
    }
    c_default = {"grant_type": "client_credentials"}
    c_allowed_values = {"grant_type": ["client_credentials"]}


class ExtensionTokenRequest(Message):
    """Extension Grant defined by RFC6749 4.5."""

    c_param = {"grant_type": SINGLE_REQUIRED_STRING}


class RefreshAccessTokenRequest(Message):
    c_param = {
        "grant_type": SINGLE_REQUIRED_STRING,
        "refresh_token": SINGLE_REQUIRED_STRING,
        "scope": OPTIONAL_LIST_OF_SP_SEP_STRINGS,
        "client_id": SINGLE_OPTIONAL_STRING,
        "client_secret": SINGLE_OPTIONAL_STRING,
    }
    c_default = {"grant_type": "refresh_token"}
    c_allowed_values = {"grant_type": ["refresh_token"]}


class ResourceRequest(Message):
    c_param = {"access_token": SINGLE_OPTIONAL_STRING}


class ASConfigurationResponse(Message):
    c_param = {
        "issuer": SINGLE_REQUIRED_STRING,
        "authorization_endpoint": SINGLE_OPTIONAL_STRING,
        "token_endpoint": SINGLE_OPTIONAL_STRING,
        "jwks_uri": SINGLE_OPTIONAL_STRING,
        "registration_endpoint": SINGLE_OPTIONAL_STRING,
        "scopes_supported": OPTIONAL_LIST_OF_STRINGS,
        "response_types_supported": REQUIRED_LIST_OF_STRINGS,
        "response_modes_supported": OPTIONAL_LIST_OF_STRINGS,
        "grant_types_supported": REQUIRED_LIST_OF_STRINGS,
        "token_endpoint_auth_methods_supported": OPTIONAL_LIST_OF_STRINGS,
        "token_endpoint_auth_signing_alg_values_supported": OPTIONAL_LIST_OF_STRINGS,
        "service_documentation": SINGLE_OPTIONAL_STRING,
        "ui_locales_supported": OPTIONAL_LIST_OF_STRINGS,
        "op_policy_uri": SINGLE_OPTIONAL_STRING,
        "op_tos_uri": SINGLE_OPTIONAL_STRING,
        "revocation_endpoint": SINGLE_OPTIONAL_STRING,
        "revocation_endpoint_auth_methods_supported": OPTIONAL_LIST_OF_STRINGS,
        "revocation_endpoint_auth_signing_alg_values_supported": OPTIONAL_LIST_OF_STRINGS,
        "introspection_endpoint": SINGLE_OPTIONAL_STRING,
        "introspection_endpoint_auth_methods_supported": OPTIONAL_LIST_OF_STRINGS,
        "introspection_endpoint_auth_signing_alg_values_supported": OPTIONAL_LIST_OF_STRINGS,
        "code_challenge_methods_supported": OPTIONAL_LIST_OF_STRINGS,
    }
    c_default = {"version": "3.0"}


MSG = {
    "Message": Message,
    "ErrorResponse": ErrorResponse,
    "AuthorizationErrorResponse": AuthorizationErrorResponse,
    "TokenErrorResponse": TokenErrorResponse,
    "AccessTokenRequest": AccessTokenRequest,
    "AuthorizationRequest": AuthorizationRequest,
    "AuthorizationResponse": AuthorizationResponse,
    "AccessTokenResponse": AccessTokenResponse,
    "NoneResponse": NoneResponse,
    "ROPCAccessTokenRequest": ROPCAccessTokenRequest,
    "CCAccessTokenRequest": CCAccessTokenRequest,
    "RefreshAccessTokenRequest": RefreshAccessTokenRequest,
    "ResourceRequest": ResourceRequest,
    "ASConfigurationResponse": ASConfigurationResponse,
}


def factory(msgtype):
    warnings.warn(
        "`factory` is deprecated. Use `OauthMessageFactory` instead.",
        DeprecationWarning,
    )
    try:
        return MSG[msgtype]
    except KeyError:
        raise FormatError("Unknown message type: %s" % msgtype)


MessageTuple = namedtuple("MessageTuple", ["request_cls", "response_cls"])


class MessageFactory:
    """Factory for holding message types."""

    @classmethod
    def get_request_type(cls, endpoint: str):
        """Return class representing the request_cls for given endpoint."""
        try:
            return getattr(cls, endpoint).request_cls
        except AttributeError:
            raise MessageException("Unknown endpoint.")

    @classmethod
    def get_response_type(cls, endpoint: str):
        """Return class representing the response_cls for given endpoint."""
        try:
            return getattr(cls, endpoint).response_cls
        except AttributeError:
            raise MessageException("Unknown endpoint.")


class OauthMessageFactory(MessageFactory):
    """Factory that knows Oauth2.0 message types."""

    authorization_endpoint = MessageTuple(AuthorizationRequest, AuthorizationResponse)
    token_endpoint = MessageTuple(AccessTokenRequest, AccessTokenResponse)
    refresh_endpoint = MessageTuple(RefreshAccessTokenRequest, AccessTokenResponse)
    # Message as a placeholder ...
    resource_endpoint = MessageTuple(ResourceRequest, Message)
    configuration_endpoint = MessageTuple(Message, ASConfigurationResponse)
