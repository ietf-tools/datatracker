# Copyright The IETF Trust 2025, All Rights Reserved

from django.test import TestCase, RequestFactory
from django.test.utils import override_settings

from ietf.api.ietf_utils import is_valid_token, requires_api_token


class IetfUtilsTests(TestCase):
    @override_settings(APP_API_TOKENS={"ietf.api.foobar": ["valid-token"]})
    def test_is_valid_token(self):
        self.assertFalse(is_valid_token("ietf.fake.endpoint", "valid-token"))
        self.assertFalse(is_valid_token("ietf.api.foobar", "invalid-token"))
        self.assertTrue(is_valid_token("ietf.api.foobar", "valid-token"))

    @override_settings(
        APP_API_TOKENS={
            "ietf.api.foo": ["valid-token"],
            "ietf.api.bar": ["another-token"],
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

        # request with an valid token
        request = RequestFactory().get(
            "/some/url", headers={"X_API_KEY": "invalid-token"}
        )
        result = protected_function(request)
        self.assertEqual(result.status_code, 403)

        # request with a valid token for another API endpoint
        request = RequestFactory().get(
            "/some/url", headers={"X_API_KEY": "another-token"}
        )
        result = protected_function(request)
        self.assertEqual(result.status_code, 403)
