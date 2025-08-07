__author__ = "rohe0002"


class PyoidcError(Exception):
    def __init__(self, errmsg, content_type="", *args):
        Exception.__init__(self, errmsg, *args)
        self.content_type = content_type


class MissingAttribute(PyoidcError):
    pass


class UnsupportedMethod(PyoidcError):
    pass


class AccessDenied(PyoidcError):
    pass


class UnknownClient(PyoidcError):
    pass


class MissingParameter(PyoidcError):
    pass


class UnknownAssertionType(PyoidcError):
    pass


class ParameterError(PyoidcError):
    pass


class URIError(PyoidcError):
    pass


class InvalidRequest(PyoidcError):
    pass


class RedirectURIError(PyoidcError):
    pass


class ParseError(PyoidcError):
    pass


class FailedAuthentication(PyoidcError):
    pass


class MissingSession(PyoidcError):
    pass


class NotForMe(PyoidcError):
    pass


class UnSupported(Exception):
    pass


class MessageException(PyoidcError):
    pass


class AuthzError(PyoidcError):
    pass


class IssuerMismatch(PyoidcError):
    pass


class RestrictionError(PyoidcError):
    pass


class InvalidRedirectUri(Exception):
    pass


class MissingPage(Exception):
    pass


class ModificationForbidden(Exception):
    pass


class RegistrationError(PyoidcError):
    pass


class CommunicationError(PyoidcError):
    pass


class RequestError(PyoidcError):
    pass


class AuthnToOld(PyoidcError):
    pass


class ImproperlyConfigured(PyoidcError):
    pass


class SubMismatch(PyoidcError):
    pass
