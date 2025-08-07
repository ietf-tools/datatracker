from urllib.parse import parse_qs

from oic.utils.authn.user import UsernamePasswordMako
from oic.utils.authn.user import logger
from oic.utils.http_util import SeeOther
from oic.utils.http_util import Unauthorized

__author__ = "danielevertsson"


class JavascriptFormMako(UsernamePasswordMako):
    """
    Do user authentication.

    This is using the normal username password form in a WSGI environment using Mako as template system.
    """

    def verify(self, request, **kwargs):
        """
        Verify that the given username and password was correct.

        :param request: Either the query part of a URL a urlencoded body of a HTTP message or a parse such.
        :param kwargs: Catch whatever else is sent.
        :return: redirect back to where ever the base applications wants the user after authentication.
        """
        logger.debug("verify(%s)" % request)
        if isinstance(request, str):
            _dict = parse_qs(request)
        elif isinstance(request, dict):
            _dict = request
        else:
            raise ValueError("Wrong type of input")

        logger.debug("dict: %s" % _dict)
        logger.debug("passwd: %s" % self.passwd)
        # verify username and password
        try:
            if _dict["login_parameter"][0] != "logged_in":
                raise KeyError()
        except KeyError:
            return (
                Unauthorized("You are not authorized. Javascript not executed"),
                False,
            )
        else:
            cookie = self.create_cookie("diana", "upm")
            try:
                _qp = _dict["query"][0]
            except KeyError:
                _qp = self.get_multi_auth_cookie(kwargs["cookie"])
            try:
                return_to = self.generate_return_url(kwargs["return_to"], _qp)
            except KeyError:
                return_to = self.generate_return_url(self.return_to, _qp)
            return SeeOther(return_to, headers=[cookie]), True
