import base64

from oic.utils.authn.client import CLIENT_AUTHN_METHOD
from oic.utils.authn.client import ClientAuthnMethod

__author__ = "rolandh"

SAML2_BEARER_ASSERTION_TYPE = "urn:ietf:params:oauth:client-assertion-type:saml2-bearer"

try:
    from saml2.saml import assertion_from_string
except ImportError:
    pass
else:

    class SAML2AuthnMethod(ClientAuthnMethod):
        """Authenticating clients using the SAML2 assertion profile."""

        def construct(self, cis, assertion=None, **kwargs):
            """
            Create the HTTP request.

            :param cis: The request
            :param assertion: A SAML2 Assertion
            :param kwargs: Extra arguments
            :return: Constructed HTTP arguments, in this case none
            """
            cis["client_assertion"] = base64.urlsafe_b64encode(assertion)
            cis["client_assertion_type"] = SAML2_BEARER_ASSERTION_TYPE

        def verify(self, areq, **kwargs):
            xmlstr = base64.urlsafe_b64decode(areq["client_assertion"])
            try:
                assertion = assertion_from_string(xmlstr)
            except Exception:
                # FIXME: This should catch specific exceptions thrown by `assertion_from_string`
                return False
            return self._verify_saml2_assertion(assertion)

        def _verify_saml2_assertion(self, assertion):
            subject = assertion.subject
            audience = []
            for ar in subject.audience_restiction:
                for aud in ar.audience:
                    audience.append(aud)

    CLIENT_AUTHN_METHOD["saml2_bearer"] = SAML2AuthnMethod
