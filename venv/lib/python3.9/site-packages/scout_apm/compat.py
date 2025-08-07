# coding=utf-8

import datetime as dt
import gzip
import inspect
import queue
from contextlib import ContextDecorator
from functools import wraps
from html import escape
from urllib.parse import parse_qsl, urlencode, urljoin

import certifi
import urllib3


def iteritems(dictionary):
    return dictionary.items()


# datetime_to_timestamp converts a naive UTC datetime to a unix timestamp
def datetime_to_timestamp(datetime_obj):
    return datetime_obj.replace(tzinfo=dt.timezone.utc).timestamp()


def text(value, encoding="utf-8", errors="strict"):
    """
    Convert a value to str on Python 3 and unicode on Python 2.
    """
    if isinstance(value, str):
        return value
    elif isinstance(value, bytes):
        return str(value, encoding, errors)
    else:
        return str(value)


def get_pos_args(func):
    return inspect.getfullargspec(func).args


def unwrap_decorators(func):
    unwrapped = func
    while True:
        # N.B. only some decorators set __wrapped__ on Python 2.7
        try:
            unwrapped = unwrapped.__wrapped__
        except AttributeError:
            break
    return unwrapped


def kwargs_only(func):
    """
    Source: https://pypi.org/project/kwargs-only/
    Make a function only accept keyword arguments.
    This can be dropped in Python 3 in lieu of:
        def foo(*, bar=default):
    Source: https://pypi.org/project/kwargs-only/
    """
    if hasattr(inspect, "signature"):  # pragma: no cover
        # Python 3
        signature = inspect.signature(func)
        arg_names = list(signature.parameters.keys())
    else:  # pragma: no cover
        # Python 2
        signature = inspect.getargspec(func)
        arg_names = signature.args

    if len(arg_names) > 0 and arg_names[0] in ("self", "cls"):
        allowable_args = 1
    else:
        allowable_args = 0

    @wraps(func)
    def wrapper(*args, **kwargs):
        if len(args) > allowable_args:
            raise TypeError(
                "{} should only be called with keyword args".format(func.__name__)
            )
        return func(*args, **kwargs)

    return wrapper


def urllib3_cert_pool_manager(**kwargs):
    return urllib3.PoolManager(cert_reqs="CERT_REQUIRED", ca_certs=certifi.where())


def gzip_compress(data):
    return gzip.compress(data)


__all__ = [
    "ContextDecorator",
    "datetime_to_timestamp",
    "escape",
    "gzip_compress",
    "kwargs_only",
    "parse_qsl",
    "queue",
    "text",
    "urlencode",
    "urljoin",
]
