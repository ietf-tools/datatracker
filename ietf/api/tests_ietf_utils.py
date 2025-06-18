# Copyright The IETF Trust 2025, All Rights Reserved

from django.test import RequestFactory
from django.test.utils import override_settings

from ietf.api.ietf_utils import is_valid_token, requires_api_token
from ietf.utils.test_utils import TestCase


class IetfUtilsTests(TestCase):
    @override_settings(
        APP_API_TOKENS={
            "ietf.api.foobar": ["valid-token"],
            "ietf.api.misconfigured": "valid-token",  # misconfigured
        }
    )
    def test_is_valid_token(self):
        self.assertFalse(is_valid_token("ietf.fake.endpoint", "valid-token"))
        self.assertFalse(is_valid_token("ietf.api.foobar", "invalid-token"))
        self.assertFalse(is_valid_token("ietf.api.foobar", None))
        self.assertTrue(is_valid_token("ietf.api.foobar", "valid-token"))

        # misconfiguration
        self.assertFalse(is_valid_token("ietf.api.misconfigured", "v"))
        self.assertFalse(is_valid_token("ietf.api.misconfigured", None))
        self.assertTrue(is_valid_token("ietf.api.misconfigured", "valid-token"))

    @override_settings(
        APP_API_TOKENS={
            "ietf.api.foo": ["valid-token"],
            "ietf.api.bar": ["another-token"],
            "ietf.api.misconfigured": "valid-token",  # misconfigured
        }
    )
    def test_requires_api_token(self):
        @requires_api_token("ietf.api.foo")
        def protected_function(request):
            return f"Access granted: {request.method}"

        # request with a valid token
        request = RequestFactory().get(
            "/some/url", headers={"X_API_KEY": "valid-token"}
        )
        result = protected_function(request)
        self.assertEqual(result, "Access granted: GET")

        # request with an invalid token
        request = RequestFactory().get(
            "/some/url", headers={"X_API_KEY": "invalid-token"}
        )
        result = protected_function(request)
        self.assertEqual(result.status_code, 403)

        # request without a token
        request = RequestFactory().get("/some/url", headers={"X_API_KEY": ""})
        result = protected_function(request)
        self.assertEqual(result.status_code, 403)

        # request without a X_API_KEY token
        request = RequestFactory().get("/some/url")
        result = protected_function(request)
        self.assertEqual(result.status_code, 403)

        # request with a valid token for another API endpoint
        request = RequestFactory().get(
            "/some/url", headers={"X_API_KEY": "another-token"}
        )
        result = protected_function(request)
        self.assertEqual(result.status_code, 403)

        # requests for a misconfigured endpoint
        @requires_api_token("ietf.api.misconfigured")
        def another_protected_function(request):
            return f"Access granted: {request.method}"

        # request with valid token
        request = RequestFactory().get(
            "/some/url", headers={"X_API_KEY": "valid-token"}
        )
        result = another_protected_function(request)
        self.assertEqual(result, "Access granted: GET")

        # request with invalid token with the correct initial character
        request = RequestFactory().get("/some/url", headers={"X_API_KEY": "v"})
        result = another_protected_function(request)
        self.assertEqual(result.status_code, 403)
