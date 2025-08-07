import hashlib
import json
from base64 import urlsafe_b64encode

from jwkest import JWKESTException
from jwkest import jws
from jwkest.jws import JWS


class ValidationError(Exception):
    pass


def get_hash_size(alg):
    return int(alg[2:])


def hash_value(size, data):
    data = data.encode("utf-8")
    if size == 256:
        return hashlib.sha256(data).digest()
    elif size == 384:
        return hashlib.sha384(data).digest()
    elif size == 512:
        return hashlib.sha512(data).digest()

    raise ValueError("The specifed hash size '{}' is unsupported.".format(size))


def serialize_dict(data, serialization_template):
    buffer = []
    keys = []
    for key in data:
        keys.append(key)
        buffer.append(serialization_template.format(key, data[key]))

    return keys, "".join(buffer)


def b64_hash(val, hash_size):
    return urlsafe_b64encode(hash_value(hash_size, val)).decode("utf-8")


def _equals(value, expected):
    if value != expected:
        raise ValidationError("{} != {}".format(value, expected))


def _serialize_params(params, str_format, hash_size):
    _keys, _buffer = serialize_dict(params, str_format)
    _hash = b64_hash(_buffer, hash_size)
    return [_keys, _hash]


def _verify_params(params, req, str_format, hash_size, strict_verification, key):
    key_order, req_hash = req

    if strict_verification and len(key_order) != len(params):
        raise ValidationError("Too many or too few {}".format(key))

    buffer = ""
    try:
        buffer = "".join([str_format.format(k, params[k]) for k in key_order])
    except KeyError:
        raise ValidationError("Too few {}".format(key))

    _equals(req_hash, b64_hash(buffer, hash_size))


def _upper(s):
    return s.upper()


SIMPLE_OPER = {
    "method": ("m", _upper),
    "host": ("u", None),
    "path": ("p", None),
    "time_stamp": ("ts", int),
}

QUERY_PARAM_FORMAT = "{}={}"
REQUEST_HEADER_FORMAT = "{}: {}"

PARAM_ARGS = {
    "query_params": ("q", QUERY_PARAM_FORMAT),
    "headers": ("h", REQUEST_HEADER_FORMAT),
}


class SignedHttpRequest(object):
    def __init__(self, key):
        self.key = key

    def sign(self, alg, **kwargs):
        http_json = {}
        hash_size = get_hash_size(alg)

        for arg, (key, func) in SIMPLE_OPER.items():
            try:
                if func is None:
                    http_json[key] = kwargs[arg]
                else:
                    http_json[key] = func(kwargs[arg])
            except KeyError:
                pass

        for arg, (key, format) in PARAM_ARGS.items():
            try:
                http_json[key] = _serialize_params(kwargs[arg], format, hash_size)
            except KeyError:
                pass

        try:
            http_json["b"] = b64_hash(kwargs["body"], hash_size)
        except KeyError:
            pass

        if not http_json:
            raise ValueError("No data to sign")

        jws = JWS(json.dumps(http_json), alg=alg, typ="pop")
        _jwt = jws.sign_compact(keys=[self.key])
        return _jwt

    def verify(self, signature, **kwargs):
        _jw = jws.factory(signature)
        if not _jw:
            raise ValidationError("Not a signed request")

        try:
            unpacked_req = _jw.verify_compact(signature, keys=[self.key])
        except JWKESTException:
            raise ValidationError("Could not verify signature")

        _header = _jw.jwt.headers
        if "typ" not in _header or _header["typ"] != "pop":
            raise ValidationError("Incorrect JWS header 'typ', must be 'pop'")

        hash_size = get_hash_size(_header["alg"])

        for arg, (key, func) in SIMPLE_OPER.items():
            if arg == "time_stamp":
                continue
            try:
                if func is None:
                    _val = kwargs[arg]
                else:
                    _val = func(kwargs[arg])
                _equals(unpacked_req[key], _val)
            except KeyError:
                pass

        for arg, (key, format) in PARAM_ARGS.items():
            try:
                _attr = "strict_{}_verification".format(arg)
                _strict_verify = kwargs[_attr]
            except KeyError:
                _strict_verify = False

            try:
                _verify_params(
                    kwargs[arg],
                    unpacked_req[key],
                    format,
                    hash_size,
                    _strict_verify,
                    key,
                )
            except KeyError:
                pass

        if "b" not in unpacked_req and "body" not in kwargs:
            pass
        elif "b" in unpacked_req and "body" in kwargs:
            _equals(
                b64_hash(kwargs.get("body", ""), hash_size), unpacked_req.get("b", "")
            )
        else:
            if "b" in unpacked_req:
                raise ValidationError("Body sent but not received!!")
            else:
                raise ValidationError("Body received but not sent!!")

        return unpacked_req
