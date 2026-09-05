# Copyright The IETF Trust 2025-2026, All Rights Reserved

from django.test import RequestFactory
from django.test.utils import override_settings

from ietf.api.ietf_utils import is_valid_token, requires_api_token
from ietf.api.models import MIN_TOKEN_LENGTH, AppApiToken, KnownApiEndpoint
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


class ModelBackedTokenTests(TestCase):
    def setUp(self):
        super().setUp()
        self.raw_token = "a-valid-token-" + "a" * MIN_TOKEN_LENGTH
        self.token = AppApiToken(client="test client")
        self.token.set_token(self.raw_token)
        self.token.save()
        self.endpoint = KnownApiEndpoint.objects.create(name="ietf.api.foobar")
        # the token is deliberately not linked to other_endpoint
        self.other_endpoint = KnownApiEndpoint.objects.create(name="ietf.api.other")
        self.token.endpoints.add(self.endpoint)

    def test_is_valid_token(self):
        self.assertTrue(
            is_valid_token("ietf.api.foobar", self.raw_token), "valid token was rejected"
        )
        self.assertFalse(
            is_valid_token("ietf.api.foobar", "an-invalid-token"),
            "invalid token was accepted",
        )
        self.assertFalse(
            is_valid_token("ietf.api.other", self.raw_token),
            "token was accepted for an endpoint it is not linked to",
        )

        self.token.enabled = False
        self.token.save()
        self.assertFalse(
            is_valid_token("ietf.api.foobar", self.raw_token),
            "disabled token was accepted",
        )

        self.token.enabled = True
        self.token.save()
        self.endpoint.enabled = False
        self.endpoint.save()
        self.assertFalse(
            is_valid_token("ietf.api.foobar", self.raw_token),
            "disabled endpoint accepted a valid token",
        )

    @override_settings(APP_API_TOKENS={"ietf.api.foobar": ["a-settings-token"]})
    def test_disabled_endpoint_denies_settings_token(self):
        """A disabled endpoint denies access, it does not fall through to settings"""
        self.endpoint.enabled = False
        self.endpoint.save()
        self.assertFalse(
            is_valid_token("ietf.api.foobar", "a-settings-token"),
            "disabled endpoint honored a settings-based token",
        )

    @override_settings(
        APP_API_TOKENS={
            "ietf.api.other": ["a-settings-token"],
            "ietf.api.unknown": ["a-settings-token"],
        }
    )
    def test_falls_through_to_settings(self):
        # an endpoint with a model costs two queries, one for the endpoint and one
        # for the prefetch of its matching tokens
        with self.assertNumQueries(2):
            self.assertTrue(
                is_valid_token("ietf.api.other", "a-settings-token"),
                "enabled endpoint with no matching token ignored settings",
            )
        # nothing to prefetch against when the endpoint has no model
        with self.assertNumQueries(1):
            self.assertTrue(
                is_valid_token("ietf.api.unknown", "a-settings-token"),
                "endpoint with no model ignored settings",
            )
        with self.assertNumQueries(2):
            self.assertFalse(
                is_valid_token("ietf.api.other", "an-invalid-token"),
                "invalid token was accepted",
            )
