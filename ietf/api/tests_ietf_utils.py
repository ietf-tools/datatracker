# Copyright The IETF Trust 2025-2026, All Rights Reserved

from unittest import mock

from django.core.cache.backends.base import BaseCache
from django.test import RequestFactory
from django.test.utils import override_settings

from ietf.api.ietf_utils import (
    cached_hashed_token_store,
    is_valid_token,
    requires_api_token,
)
from ietf.api.models import AppApiToken
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


class CachedHashedTokenStoreTests(TestCase):
    def setUp(self):
        super().setUp()
        # Mock the cache so we control it. Use autospec to ensure we don't mask
        # calling errors that would not work with an actual Cache class.
        self.cache = mock.create_autospec(BaseCache, instance=True)
        cache_patcher = mock.patch(
            "ietf.api.ietf_utils.caches", {"default": self.cache}
        )
        cache_patcher.start()
        self.addCleanup(cache_patcher.stop)

        model_patcher = mock.patch("ietf.api.ietf_utils.AppApiToken")
        mocked_model = model_patcher.start()
        self.addCleanup(model_patcher.stop)
        self.built_store = {"ietf.api.foobar": ["a-hashed-token"]}
        self.builder = mocked_model.objects.as_hashed_token_dict
        self.builder.return_value = self.built_store

        self.cached_store = {"ietf.api.cached": ["a-different-hashed-token"]}

    def test_cold_cache_builds_and_stores(self):
        self.cache.get.return_value = None
        self.assertEqual(
            cached_hashed_token_store(), self.built_store, "the store was not returned"
        )
        self.assertEqual(self.builder.call_count, 1, "the store was not built")
        self.assertEqual(
            self.cache.set.call_args.args[0],
            self.cache.get.call_args.args[0],
            "the store was cached under a different key than it is read from",
        )
        self.assertEqual(
            self.cache.set.call_args.args[1],
            self.built_store,
            "the store was not cached",
        )

    def test_warm_cache_returns_cached_value(self):
        self.cache.get.return_value = self.cached_store
        self.assertEqual(
            cached_hashed_token_store(),
            self.cached_store,
            "the cached store was not returned",
        )
        # building the store is the only database access this method makes
        self.assertEqual(self.builder.call_count, 0, "a warm cache rebuilt the store")
        self.assertEqual(self.cache.set.call_count, 0, "a warm cache was written again")

    def test_force_update_rebuilds(self):
        self.cache.get.return_value = self.cached_store
        self.assertEqual(
            cached_hashed_token_store(force_update=True),
            self.built_store,
            "the cached store was returned instead of a rebuilt one",
        )
        self.assertEqual(self.cache.get.call_count, 0, "the cache was consulted anyway")
        self.assertEqual(self.builder.call_count, 1, "the store was not rebuilt")
        self.assertEqual(
            self.cache.set.call_args.args[1],
            self.built_store,
            "the rebuilt store was not cached",
        )


class IsValidTokenTests(TestCase):
    def setUp(self):
        super().setUp()
        self.raw_token = "a-valid-token"
        # only ietf.api.foobar has a model-backed token
        self.store = {"ietf.api.foobar": [AppApiToken.hash(self.raw_token)]}
        store_patcher = mock.patch(
            "ietf.api.ietf_utils.cached_hashed_token_store", return_value=self.store
        )
        self.mocked_store = store_patcher.start()
        self.addCleanup(store_patcher.stop)

    def test_is_valid_token(self):
        self.assertTrue(
            is_valid_token("ietf.api.foobar", self.raw_token),
            "valid token was rejected",
        )
        self.assertFalse(
            is_valid_token("ietf.api.foobar", "an-invalid-token"),
            "invalid token was accepted",
        )
        self.assertFalse(
            is_valid_token("ietf.api.other", self.raw_token),
            "token was accepted for an endpoint it does not cover",
        )

        self.mocked_store.reset_mock()
        self.assertFalse(is_valid_token("ietf.api.foobar", None), "null token accepted")
        self.assertFalse(is_valid_token("ietf.api.foobar", ""), "empty token accepted")
        self.assertEqual(
            self.mocked_store.call_count, 0, "an empty token reached the token store"
        )

    @override_settings(APP_API_TOKENS={"ietf.api.disabled": ["a-settings-token"]})
    def test_disabled_endpoint_does_not_block_settings_token(self):
        """Settings-based access does not depend on the state of a KnownApiEndpoint

        A disabled endpoint is absent from the token store, which denies its
        model-backed tokens but intentionally leaves settings-based tokens alone.
        """
        self.assertTrue(
            is_valid_token("ietf.api.disabled", "a-settings-token"),
            "settings-based token was refused for an endpoint missing from the store",
        )

    @override_settings(APP_API_TOKENS={"ietf.api.settings": ["a-settings-token"]})
    def test_makes_no_database_queries(self):
        # the results are asserted so that the query count cannot be satisfied by
        # calls that short-circuit before doing the work
        with self.assertNumQueries(0):
            self.assertTrue(is_valid_token("ietf.api.foobar", self.raw_token))
            self.assertFalse(is_valid_token("ietf.api.foobar", "an-invalid-token"))
            self.assertTrue(is_valid_token("ietf.api.settings", "a-settings-token"))
