import re
from collections.abc import Mapping
from textwrap import dedent

SENSITIVE_THINGS = {
    "password",
    "passwd",
    "client_secret",
    "code",
    "authorization",
    "access_token",
    "refresh_token",
}

REPLACEMENT = "<REDACTED>"

SANITIZE_PATTERN = r"""
    (?<!_) # Negative-lookbehind for underscore.
    # Necessary to keep 'authorization_code' from matching 'code'
    ( # Start of capturing group--we'll keep this bit.
         (?: # non-capturing group
             {} # Template-in things we want to sanitize
         ) #
        ['\"]? # Might have a quote after them?
        \s* # Maybe some whitespace
        [=:,] # Probably a : , or = in tuple, dict or qs format
        \s* # Maybe more whitespace
        [([]? # Could be inside a list/tuple, parse_qs?
        ([bu][\"'])? # Python 2
        [\"']? # Might be a quote here.
    ) # End of capturing group
    (?:[%=/+\w]+) # This is the bit we replace with '<REDACTED>'
"""

SANITIZE_PATTERN = dedent(SANITIZE_PATTERN.format("|".join(SENSITIVE_THINGS)))
SANITIZE_REGEX = re.compile(SANITIZE_PATTERN, re.VERBOSE | re.IGNORECASE | re.UNICODE)


def redacted(key, value):
    if key in SENSITIVE_THINGS:
        return (key, REPLACEMENT)
    return (key, value)


def sanitize(potentially_sensitive):
    if isinstance(potentially_sensitive, Mapping):
        # Makes new dict so we don't modify the original
        # Also case-insensitive--possibly important for HTTP headers.
        return dict(redacted(k.lower(), v) for k, v in potentially_sensitive.items())
    else:
        if not isinstance(potentially_sensitive, str):
            potentially_sensitive = str(potentially_sensitive)
        return SANITIZE_REGEX.sub(r"\1{}".format(REPLACEMENT), potentially_sensitive)
