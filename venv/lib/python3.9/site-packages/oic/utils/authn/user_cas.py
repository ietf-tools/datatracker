import base64
import json
import logging
import uuid
from typing import Optional
from urllib.parse import parse_qs
from urllib.parse import urlencode

import requests
from defusedxml import ElementTree as ET

from oic.utils.authn.user import UserAuthnMethod
from oic.utils.http_util import SeeOther
from oic.utils.http_util import Unauthorized

logger = logging.getLogger(__name__)


# This class handles user authentication with CAS.
class CasAuthnMethod(UserAuthnMethod):
    # Standard login url for a CAS server.
    CONST_CASLOGIN = "/login?"
    # Standard URL for validation of a ticket for a CAS server.
    CONST_CAS_VERIFY_TICKET = "/serviceValidate"
    # Standard name for the parameter containing a CAS ticket.
    CONST_TICKET = "ticket"
    # Standard name for the parameter containing the service url (callback url).
    CONST_SERVICE = "service"
    # A successful verification of a ticket against a CAS service will contain
    # this XML element.
    CONST_AUTHSUCCESS = "authenticationSuccess"
    # If a success full verification of a CAS ticket has been perform, the uid
    # will be containd in a XML element
    # with this name.
    CONST_USER = "user"
    # Used for preventing replay attacks.
    CONST_NONCE = "nonce"
    # Parameter name for queries to be sent back on the URL, after successful
    # authentication.
    CONST_QUERY = "query"
    # The name for the CAS cookie, containing query parameters and nonce.
    CONST_CAS_COOKIE = "cascookie"

    def __init__(
        self, srv, cas_server, service_url, return_to, extra_validation=None, timeout=5
    ):
        """
        Construct the class.

        :param srv: Usually none, but otherwise the oic server.
        :param cas_server: Base URL to the cas server.
        :param service_url: BASE url to the service that will use CAS. In
        this case the oic server's verify URL.
        :param return_to: The URL to return to after a successful
        authentication.
        :param timeout: Timeout for requests library.
        """
        UserAuthnMethod.__init__(self, srv)
        self.cas_server = cas_server
        self.service_url = service_url
        self.return_to = return_to
        self.extra_validation = extra_validation
        self.timeout = timeout

    def create_redirect(self, query):
        """
        Perform the redirect to the CAS server.

        :rtype : Response
        :param query: All query parameters to be added to the return_to URL
        after successful authentication.
        :return: A redirect response to the CAS server.
        """
        try:
            req = parse_qs(query)
            acr: Optional[str] = req["acr_values"][0]
        except KeyError:
            acr = None

        nonce = uuid.uuid4().urn.encode()
        service_url = urlencode({self.CONST_SERVICE: self.get_service_url(nonce, acr)})
        cas_url = self.cas_server + self.CONST_CASLOGIN + service_url
        cookie = self.create_cookie(
            '{"'
            + self.CONST_NONCE
            + '": "'
            + base64.b64encode(nonce).decode()
            + '", "'
            + self.CONST_QUERY
            + '": "'
            + base64.b64encode(query).decode()
            + '"}',
            self.CONST_CAS_COOKIE,
            self.CONST_CAS_COOKIE,
        )
        return SeeOther(cas_url, headers=[cookie])

    def handle_callback(self, ticket, service_url):
        """
        Handle the callback from the CAS server.

        :rtype : String
        :param ticket: Onetime CAS ticket to be validated.
        :param service_url: The URL the CAS server redirected to.
        :return: Uid if the login was successful otherwise None.
        """
        data = {self.CONST_TICKET: ticket, self.CONST_SERVICE: service_url}
        resp = requests.get(
            self.cas_server + self.CONST_CAS_VERIFY_TICKET,
            params=data,
            timeout=self.timeout,
        )
        root = ET.fromstring(resp.content)
        for l1 in root:
            if self.CONST_AUTHSUCCESS in l1.tag:
                for l2 in l1:
                    if self.CONST_USER in l2.tag:
                        if self.extra_validation is not None:
                            if self.extra_validation(l2.text):
                                return l2.text
                            else:
                                return None
                        return l2.text
        return None

    def __call__(self, query, *args, **kwargs):
        return self.create_redirect(query)

    def get_service_url(self, nonce, acr):
        """
        Create the service url for the CAS server.

        :rtype : String
        :param nonce: The nonce to be added to the service url.
        :return: A service url with a nonce.
        """
        if acr is None:
            acr = ""
        return (
            self.service_url
            + "?"
            + self.CONST_NONCE
            + "="
            + nonce
            + "&acr_values="
            + acr
        )

    def verify(self, request, cookie, **kwargs):
        """
        Verify if the authentication was successful.

        :rtype : Response
        :param request: Contains the request parameters.
        :param cookie: Cookies sent with the request.
        :param kwargs: Any other parameters.
        :return: If the authentication was successful: a redirect to the
        return_to url. Otherwise a unauthorized response.
        :raise: ValueError
        """
        logger.debug("verify(%s)" % request)
        if isinstance(request, str):
            _dict = parse_qs(request)
        elif isinstance(request, dict):
            _dict = request
        else:
            raise ValueError("Wrong type of input")
        try:
            cas_cookie, _ts, _typ = self.getCookieValue(cookie, self.CONST_CAS_COOKIE)
            data = json.loads(cas_cookie)
            nonce = base64.b64decode(data[self.CONST_NONCE])
            if nonce != _dict[self.CONST_NONCE][0]:
                logger.warning("Someone tried to login without a correct nonce!")
                return Unauthorized("You are not authorized!")
            acr = None
            try:
                acr = _dict["acr_values"][0]
            except KeyError:
                pass
            uid = self.handle_callback(
                _dict[self.CONST_TICKET], self.get_service_url(nonce, acr)
            )
            if uid is None or uid == "":
                logger.info("Someone tried to login, but was denied by CAS!")
                return Unauthorized("You are not authorized!")
            cookie = self.create_cookie(uid, "casm")
            return_to = self.generate_return_url(self.return_to, uid)
            if "?" in return_to:
                return_to += "&"
            else:
                return_to += "?"
            return_to += base64.b64decode(data[self.CONST_QUERY])
            return SeeOther(return_to, headers=[cookie])
        except Exception:
            # FIXME: This should catch specific exception thrown from methods in the block
            logger.critical(
                "Metod verify in user_cas.py had a fatal exception.", exc_info=True
            )
            return Unauthorized("You are not authorized!")
