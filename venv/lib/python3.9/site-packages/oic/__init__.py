import hashlib
import string

# Since SystemRandom is not available on all systems
try:
    # Python 3.6+, designed for this usecase
    from secrets import choice
except ImportError:
    import random

    try:
        # Python 2.4+ if available on the platform
        _sysrand = random.SystemRandom()
        choice = _sysrand.choice
    except AttributeError:
        # Fallback, really bad
        import warnings

        choice = random.choice
        warnings.warn(
            "No good random number generator available on this platform. "
            "Security tokens will be weak and guessable.",
            RuntimeWarning,
        )

__author__ = "Roland Hedberg"
__version__ = "1.7.0"


OIDCONF_PATTERN = "%s/.well-known/openid-configuration"
CC_METHOD = {"S256": hashlib.sha256, "S384": hashlib.sha384, "S512": hashlib.sha512}


def rndstr(size=16):
    """
    Return a string of random ascii characters or digits.

    :param size: The length of the string
    :return: string
    """
    _basech = string.ascii_letters + string.digits
    return "".join([choice(_basech) for _ in range(size)])


BASECH = string.ascii_letters + string.digits + "-._~"


def unreserved(size=64):
    """
    Return a string of random ascii characters, digits and unreserved characters for use as RFC 7636 code verifiers.

    :param size: The length of the string
    :return: string
    """
    return "".join([choice(BASECH) for _ in range(size)])
