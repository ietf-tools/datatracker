# Copyright The IETF Trust 2026, All Rights Reserved
"""Tests for exception report filtering"""

from django.test import RequestFactory, TestCase

import debug                            # pyflakes:ignore

from ietf.utils.exception_filter import AuthorizationAwareReporterFilter


class AuthorizationAwareReporterFilterTests(TestCase):
    def test_the_authorization_header_is_redacted(self):
        """Django's own pattern matches X-Api-Key through 'KEY' but nothing in Authorization"""
        request = RequestFactory().get(
            "/", headers={"Authorization": "Bearer a-real-access-token"}
        )
        meta = AuthorizationAwareReporterFilter().get_safe_request_meta(request)
        self.assertEqual(
            meta["HTTP_AUTHORIZATION"],
            AuthorizationAwareReporterFilter.cleansed_substitute,
        )

    def test_the_api_key_header_is_still_redacted(self):
        request = RequestFactory().get("/", headers={"X-Api-Key": "a-real-token"})
        meta = AuthorizationAwareReporterFilter().get_safe_request_meta(request)
        self.assertEqual(
            meta["HTTP_X_API_KEY"],
            AuthorizationAwareReporterFilter.cleansed_substitute,
        )
