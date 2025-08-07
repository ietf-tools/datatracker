from oic.exception import PyoidcError

__author__ = "roland"


class HttpError(PyoidcError):
    pass


class MissingRequiredAttribute(PyoidcError):
    pass


class VerificationError(PyoidcError):
    pass


class ResponseError(PyoidcError):
    pass


class TimeFormatError(PyoidcError):
    pass


class CapabilitiesMisMatch(PyoidcError):
    pass


class MissingEndpoint(PyoidcError):
    pass


class TokenError(PyoidcError):
    pass


class GrantError(PyoidcError):
    pass


class ParseError(PyoidcError):
    pass


class OtherError(PyoidcError):
    pass


class NoClientInfoReceivedError(PyoidcError):
    pass


class InvalidRequest(PyoidcError):
    pass


class NonFatalException(PyoidcError):
    """
    Return the response but accompany it by an error message.

    :param resp: A response that the function/method would return on non-error
    :param msg: A message describing what error has occurred.
    """

    def __init__(self, resp, msg):
        self.resp = resp
        self.msg = msg


class Unsupported(PyoidcError):
    pass


class UnsupportedResponseType(Unsupported):
    pass
